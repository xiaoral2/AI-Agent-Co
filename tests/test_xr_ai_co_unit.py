"""xr_ai_co/* unit tests (config, context, harness, planner, llm, knowledge, workspace git, …)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orchestrator.state_manager import empty_session
from orchestrator.types import ToolResult
from xr_ai_co.config import AppConfig, LLMConfig, load_config
from xr_ai_co.context import assemble_messages, read_workspace_files, system_prompt
from xr_ai_co.harness_executor import HarnessExecutor
from xr_ai_co.knowledge_store import KB_FILENAME, load_kb_into_session, persist_kb_from_session
from xr_ai_co.llm import LLMProvider, LLMProviderError, LLMResponse, Usage, _is_transient, _status_code
from xr_ai_co.plan_validate import detect_dag_cycles, load_schema, validate_plan_tasks
from xr_ai_co.planner import build_tasks, detect_profile, requirements_summary
from xr_ai_co.session_builder import (
    build_session,
    ceo_approve,
    ceo_continue,
    ceo_pause,
    merge_replan_tasks,
    next_revision_id,
)
from xr_ai_co.session_validate import validate_session_shape
from xr_ai_co.task_token_estimates import annotate_task_token_estimates
import xr_ai_co.builtin_templates as bt
import xr_ai_co.pm_clarification as pm


def test_load_schema() -> None:
    s = load_schema()
    assert "$schema" in s or "properties" in s


def test_validate_plan_tasks_ok() -> None:
    tasks, _ = build_tasks("rate limiter")
    validate_plan_tasks(tasks)


def test_validate_plan_tasks_schema_fail() -> None:
    with pytest.raises(ValueError, match="task"):
        validate_plan_tasks([{"id": "x"}])


def test_detect_dag_acyclic() -> None:
    tasks, _ = build_tasks("hello")
    assert detect_dag_cycles(tasks) is None


def test_session_validate_branches() -> None:
    assert validate_session_shape({"tasks": []}) != []
    issues = validate_session_shape({"project": "bad", "tasks": [], "workers": []})
    assert any("project must be an object" in i for i in issues)
    s = {"project": {"status": "x"}, "tasks": "nope", "workers": []}
    issues = validate_session_shape(s)
    assert any("tasks must be an array" in i for i in issues)


def test_config_yaml_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    y = tmp_path / "c.yaml"
    y.write_text(
        "llm:\n  model: test-model\nbudget:\n  max_retries_total: 7\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    cfg = load_config(y)
    assert cfg.llm.model == "test-model"
    assert cfg.budget.max_retries_total == 7
    assert cfg.llm.api_key == "sk-test"


def test_config_missing_file() -> None:
    cfg = load_config("/nonexistent/path/xyz.yaml")
    assert isinstance(cfg, AppConfig)


def test_deep_merge_dict() -> None:
    from xr_ai_co.config import _deep_merge

    base = {"a": {"b": 1}, "x": 1}
    _deep_merge(base, {"a": {"c": 2}, "x": 2})
    assert base["a"]["b"] == 1 and base["a"]["c"] == 2
    assert base["x"] == 2


def test_context_system_prompt_fallback() -> None:
    assert "Coder" in system_prompt("unknown_role_xyz")


def test_assemble_planner_blocks() -> None:
    session = {
        "global": {"requirements_summary": "do thing"},
        "project": {"status": "executing"},
        "tasks": [{"id": "T1", "status": "todo", "type": "code"}],
        "workers": [],
    }
    task = {"id": "T1", "type": "code", "description": "d"}
    sys_p, msgs = assemble_messages(role="planner", task=task, session=session, mission="m")
    assert "Planner" in sys_p
    assert "T1" in msgs[0]["content"]


def test_assemble_coder_with_workspace(tmp_path: Path) -> None:
    (tmp_path / "f.py").write_text("# x", encoding="utf-8")
    session = {"global": {}, "project": {"status": "executing"}, "tasks": [], "workers": []}
    task = {"id": "T1", "type": "code", "description": "d", "path_hints": []}
    _, msgs = assemble_messages(
        role="coder", task=task, session=session, mission="m", workspace=tmp_path,
    )
    assert "f.py" in msgs[0]["content"] or "workspace" in msgs[0]["content"].lower()


def test_read_workspace_files_cap(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x" * 100, encoding="utf-8")
    s = read_workspace_files(tmp_path, ["a.txt"], cap=20)
    assert "truncated" in s


def test_planner_detect_profile() -> None:
    assert detect_profile("build a rate limiter") == "rate_limiter"
    assert detect_profile("hello") == "generic"


def test_next_revision_id() -> None:
    assert next_revision_id("rev-001") == "rev-002"
    assert next_revision_id("custom") == "custom-next"


def test_requirements_summary() -> None:
    assert "Mission" in requirements_summary("hi", "generic")


def test_session_builder_flow() -> None:
    tasks, prof = build_tasks("x")
    s = build_session("mission text", tasks, prof, auto_approve=True)
    assert s["project"]["status"] == "executing"
    ceo_pause(s)
    assert s["project"]["status"] == "paused"
    ceo_continue(s)
    assert s["project"]["status"] == "executing"


def test_session_builder_ceo_approve_manual() -> None:
    tasks, prof = build_tasks("x")
    s = build_session("m", tasks, prof, auto_approve=False)
    ceo_approve(s)
    assert s["project"]["approved_plan_revision_id"]


def test_session_builder_ceo_approve_empty_raises() -> None:
    s = empty_session()
    s["tasks"] = []
    with pytest.raises(ValueError):
        ceo_approve(s)


def test_merge_replan_tasks() -> None:
    s = empty_session()
    s["tasks"] = [{"id": "old"}]
    nt, _ = build_tasks("new mission")
    rev = merge_replan_tasks(s, nt)
    assert rev.startswith("rev-")
    assert s["project"]["status"] == "planning"


def test_ceo_continue_reset_ids() -> None:
    s = empty_session()
    s["tasks"] = [{"id": "A", "status": "failed", "retry_count": 3, "owner": "w"}]
    ceo_continue(s, reset_task_ids=["A"])
    assert s["tasks"][0]["status"] == "todo"
    assert s["tasks"][0]["retry_count"] == 0


def test_annotate_token_estimates() -> None:
    tasks = [{"type": "code", "description": "x" * 500}]
    annotate_task_token_estimates(tasks)
    assert tasks[0].get("estimated_prompt_tokens", 0) > 0


def test_builtin_templates_non_empty() -> None:
    assert len(bt.RATE_LIMIT_MODULE) > 10


def test_knowledge_roundtrip(tmp_path: Path) -> None:
    s = empty_session()
    s.setdefault("global", {})["knowledge_base"] = [{"a": 1}]
    persist_kb_from_session(s, tmp_path)
    s2 = empty_session()
    load_kb_into_session(s2, tmp_path)
    assert s2["global"]["knowledge_base"]


def test_knowledge_load_bad_json(tmp_path: Path) -> None:
    (tmp_path / KB_FILENAME).write_text("{", encoding="utf-8")
    s = empty_session()
    load_kb_into_session(s, tmp_path)


def test_knowledge_persist_merge(tmp_path: Path) -> None:
    (tmp_path / KB_FILENAME).write_text(json.dumps([{"old": True}]), encoding="utf-8")
    s = empty_session()
    s.setdefault("global", {})["knowledge_base"] = [{"new": True}]
    persist_kb_from_session(s, tmp_path)
    data = json.loads((tmp_path / KB_FILENAME).read_text(encoding="utf-8"))
    assert len(data) >= 1


def test_pm_extract_questions() -> None:
    text = '```json\n{"questions": ["Q1?", "Q2?"]}\n```'
    qs = pm._extract_questions_json(text)
    assert qs == ["Q1?", "Q2?"]


def test_usage_total() -> None:
    u = Usage(3, 4)
    assert u.total_tokens == 7


def test_llm_provider_no_key() -> None:
    p = LLMProvider(LLMConfig(api_key=""))
    with pytest.raises(LLMProviderError):
        p._ensure_client()


def test_llm_chat_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_block = MagicMock()
    fake_block.text = "ok"
    fake_resp = MagicMock()
    fake_resp.content = [fake_block]
    fake_resp.usage.input_tokens = 5
    fake_resp.usage.output_tokens = 6
    fake_resp.stop_reason = "end_turn"
    client = MagicMock()
    client.messages.create.return_value = fake_resp

    prov = LLMProvider(LLMConfig(api_key="k"))
    monkeypatch.setattr(prov, "_ensure_client", lambda: client)
    r = prov.chat(system="s", messages=[{"role": "user", "content": "u"}])
    assert r.text == "ok"
    assert prov.cumulative_usage.total_tokens == 11


def test_is_transient_timeout() -> None:
    assert _is_transient(TimeoutError())


def test_status_code_from_exc() -> None:
    e = MagicMock()
    e.status_code = 429
    assert _status_code(e) == 429


def test_harness_execute_code_template(tmp_path: Path) -> None:
    cfg = AppConfig()
    session = empty_session()
    ex = HarnessExecutor(tmp_path, "generic", config=cfg, llm=None, session=session)
    task = {
        "id": "T1",
        "type": "code",
        "plan_revision_id": "r",
        "retry_count": 0,
    }
    r = ex.execute(task)
    assert r.success


def test_harness_execute_test(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "tests" / "test_z.py").write_text("def test_z(): assert True\n", encoding="utf-8")
    cfg = AppConfig()
    session = empty_session()
    ex = HarnessExecutor(tmp_path, "generic", config=cfg, session=session)
    task = {
        "id": "T2",
        "type": "test",
        "verification": {"paths": ["tests/test_z.py"]},
    }
    r = ex.execute(task)
    assert r.success


def test_harness_design(tmp_path: Path) -> None:
    ex = HarnessExecutor(tmp_path, "generic", config=None, llm=None, session=empty_session())
    r = ex.execute({"id": "D", "type": "design"})
    assert r.success


def test_harness_unsupported_type(tmp_path: Path) -> None:
    ex = HarnessExecutor(tmp_path, "generic", session=empty_session())
    r = ex.execute({"id": "x", "type": "weird"})
    assert not r.success


def test_harness_budget_block(tmp_path: Path) -> None:
    cfg = AppConfig()
    cfg.budget.max_tokens_per_session = 1
    session = empty_session()
    session["budget_counters"] = {"tokens_used_session": 5}
    ex = HarnessExecutor(tmp_path, "generic", config=cfg, llm=LLMProvider(LLMConfig(api_key="k")), session=session)
    assert not ex._budget_ok({})


def test_harness_record_usage() -> None:
    session = empty_session()
    cfg = AppConfig()
    cfg.budget.max_cost_per_project = 100.0
    cfg.budget.usd_per_1k_total_tokens = 1.0
    ex = HarnessExecutor(Path("."), "generic", config=cfg, session=session)
    ex.record_tool_usage(ToolResult(success=True, payload={"usage": {"prompt_tokens": 1000, "completion_tokens": 0}}))
    assert session["budget_counters"]["tokens_used_session"] >= 1000


def test_harness_review_stub() -> None:
    ex = HarnessExecutor(Path("."), "generic", session=empty_session())
    r = ex.review({"id": "t"})
    assert r.success


@pytest.mark.skipif(not shutil.which("git"), reason="no git on PATH")
def test_workspace_git_init_snapshot(tmp_path: Path) -> None:
    from xr_ai_co import workspace_git as wg

    (tmp_path / "f.txt").write_text("v1", encoding="utf-8")
    assert wg.git_init(tmp_path) is True
    assert wg.git_init(tmp_path) is False
    (tmp_path / "f.txt").write_text("v2", encoding="utf-8")
    sha = wg.snapshot(tmp_path, "msg", task_id="T1")
    assert sha
    head = wg.current_sha(tmp_path)
    assert head == sha
    logs = wg.log_short(tmp_path, n=3)
    assert logs


def test_plan_with_llm_happy_path_json_from_stub() -> None:
    import json as json_lib

    from tools.planner_tool import plan_with_llm

    tasks, _ = build_tasks("rate limiter for api")
    payload = "```json\n" + json_lib.dumps(tasks, ensure_ascii=False) + "\n```"

    class F(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(text=payload, usage=Usage(10, 20))

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    session = {"global": {}, "project": {}, "tasks": [], "workers": []}
    r = plan_with_llm("m", session, F(cfg.llm))
    assert r.success
    assert "tasks" in r.payload
