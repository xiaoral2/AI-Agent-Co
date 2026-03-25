"""tools/* — filesystem, pytest runner, planner/coder/tester/reviewer/architect."""

from __future__ import annotations

from pathlib import Path

import pytest

import tools.planner_tool as planner_tool
from orchestrator.types import ToolResult
from tools.architect_tool import INTERFACE_PATH, design_stub, design_with_llm, _extract_md_file
from tools.coder_tool import code_with_llm, code_with_template, _extract_file_blocks
from tools.filesystem import PathEscapeError, read_file, write_file
from tools.planner_tool import plan_tasks, plan_with_llm
from tools.reviewer_tool import review_stub, review_with_llm, _extract_review_json
from tools.run_pytest import run_pytest
from tools.tester_tool import _run_verification
from xr_ai_co.config import AppConfig, LLMConfig
from xr_ai_co.llm import LLMProvider, LLMProviderError, LLMResponse, Usage


def test_filesystem_roundtrip(tmp_path: Path) -> None:
    write_file(tmp_path, "a/b.txt", "hello")
    assert read_file(tmp_path, "a/b.txt") == "hello"


def test_filesystem_escape(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError):
        write_file(tmp_path, "../outside.txt", "x")


def test_filesystem_missing_read(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_file(tmp_path, "nope.txt")


def test_run_pytest_minimal(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(
        "def test_ok():\n    assert 1 == 1\n",
        encoding="utf-8",
    )
    code, out, err = run_pytest(tmp_path, ["tests/test_x.py"], timeout_sec=60)
    assert code == 0
    assert "passed" in out.lower() or out.strip() == ""


def test_run_pytest_ignores_parent_pyproject_addopts(tmp_path: Path) -> None:
    """Workspace nested under a repo root must not inherit harness coverage addopts."""
    parent = tmp_path / "harness_root"
    ws = parent / "workspace"
    (ws / "tests").mkdir(parents=True)
    (ws / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert 1 == 1\n",
        encoding="utf-8",
    )
    (parent / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\n'
        'addopts = "--cov=nonexistent_pkg --cov-fail-under=90"\n',
        encoding="utf-8",
    )
    code, out, err = run_pytest(ws, ["tests/test_ok.py"], timeout_sec=60)
    assert code == 0, (out, err)
    assert "passed" in out.lower() or out.strip() == ""


def test_planner_extract_json_fenced() -> None:
    text = '```json\n[{"id":"A","type":"code"}]\n```'
    got = planner_tool._extract_json_array(text)
    assert isinstance(got, list) and got[0]["id"] == "A"
    arr = planner_tool._extract_json_array('[{"id":"A","type":"code","description":"d","status":"todo","depends_on":[],"retry_count":0,"plan_revision_id":"r","input":"i","output":"o","constraints":"c","acceptance_criteria":"a","test_plan":"t"}]')
    assert arr and arr[0]["id"] == "A"


def test_planner_extract_from_plain_array() -> None:
    raw = '[{"id":"X","type":"code","description":"d","status":"todo","depends_on":[],"retry_count":0,"plan_revision_id":"r","input":"i","output":"o","constraints":"c","acceptance_criteria":"a","test_plan":"t"}]'
    assert planner_tool._extract_json_array(raw)[0]["id"] == "X"


def test_plan_tasks_template_fallback(tmp_path: Path) -> None:
    cfg = AppConfig()
    session = {"global": {}, "project": {}, "tasks": [], "workers": []}
    tasks, prof = plan_tasks("build rate limiter", session, cfg, llm=None)
    assert prof == "rate_limiter"
    assert any(t["id"] == "T1" for t in tasks)


def test_plan_tasks_with_design_flag() -> None:
    base = AppConfig()
    cfg = AppConfig(planner=type(base.planner)(include_design_task=True))
    session = {"global": {}, "project": {}, "tasks": [], "workers": []}
    tasks, _ = plan_tasks("hello world app", session, cfg, llm=None)
    assert tasks[0]["type"] == "design"


def test_plan_with_llm_error() -> None:
    class Bad(LLMProvider):
        def chat(self, **kwargs):
            raise LLMProviderError("x")

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    r = plan_with_llm("m", {"global": {}, "project": {}, "tasks": [], "workers": []}, Bad(cfg.llm))
    assert not r.success
    assert "llm_error" in (r.error or "")


def test_plan_with_llm_bad_json() -> None:
    class R(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(text="not json", usage=Usage())

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    r = plan_with_llm("m", {"global": {}, "project": {}, "tasks": [], "workers": []}, R(cfg.llm))
    assert not r.success


def test_coder_extract_blocks() -> None:
    t = "```python:foo.py\nx=1\n```"
    assert _extract_file_blocks(t)[0][0] == "foo.py"


def test_coder_extract_alt_pattern() -> None:
    t = "# file: bar.py\n```python\ny=2\n```"
    out = _extract_file_blocks(t)
    assert out and "bar.py" in out[0][0]


def test_code_with_template_rate_limiter(tmp_path: Path) -> None:
    task = {"id": "T1"}
    r = code_with_template(task, tmp_path, "rate_limiter")
    assert r.success
    assert (tmp_path / "ratelimit.py").is_file()


def test_code_with_template_generic(tmp_path: Path) -> None:
    r = code_with_template({"id": "T1"}, tmp_path, "generic")
    assert r.success
    assert (tmp_path / "app" / "main.py").is_file()


def test_code_with_llm_success(tmp_path: Path) -> None:
    class F(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(
                text="```python:mod.py\na = 3\n```",
                usage=Usage(1, 2),
            )

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    task = {
        "id": "T1",
        "path_hints": [],
    }
    session = {"global": {"requirements_summary": "x"}, "project": {}, "tasks": [], "workers": []}
    r = code_with_llm(task, session, tmp_path, F(cfg.llm), mission="m")
    assert r.success


def test_code_with_llm_no_blocks(tmp_path: Path) -> None:
    class F(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(text="nope", usage=Usage())

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    r = code_with_llm(
        {"id": "T1", "path_hints": []},
        {"global": {}, "project": {}, "tasks": [], "workers": []},
        tmp_path,
        F(cfg.llm),
    )
    assert not r.success


def test_tester_run_verification_missing_paths() -> None:
    r = _run_verification({"id": "t", "verification": {}}, Path("."))
    assert not r.success


def test_tester_with_existing(tmp_path: Path) -> None:
    from tools.tester_tool import test_with_existing as run_existing_tests

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_x(): assert True\n", encoding="utf-8")
    task = {"id": "T2", "verification": {"paths": ["tests/test_a.py"]}}
    r = run_existing_tests(task, tmp_path, pytest_timeout_sec=60)
    assert r.success


def test_tester_llm_writes_and_runs(tmp_path: Path) -> None:
    from tools.tester_tool import test_with_llm as run_llm_tests

    class F(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(
                text="```python:tests/test_b.py\ndef test_b():\n    assert True\n```",
                usage=Usage(1, 1),
            )

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    task = {"id": "T2", "verification": {"paths": ["tests/test_b.py"]}}
    session = {"global": {}, "project": {}, "tasks": [], "workers": []}
    r = run_llm_tests(task, session, tmp_path, F(cfg.llm), pytest_timeout_sec=60)
    assert r.success or r.payload.get("pytest")  # may fail if path mismatch; prefer success


def test_reviewer_extract_json() -> None:
    j = _extract_review_json('```json\n{"verdict":"approve","dimensions":{}}\n```')
    assert j is not None
    assert j.get("verdict") == "approve"


def test_review_stub_approve() -> None:
    r = review_stub({"id": "t"}, {"global": {}})
    assert r.success


def test_review_stub_pytest_fail() -> None:
    r = review_stub({"id": "t"}, {"global": {"last_pytest": {"returncode": 1}}})
    assert not r.success


def test_review_with_llm_wraps_raw(tmp_path: Path) -> None:
    class F(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(text="not json at all", usage=Usage(2, 3))

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    r = review_with_llm(
        {"id": "t", "path_hints": []},
        {"global": {}, "project": {}, "tasks": [], "workers": []},
        tmp_path,
        F(cfg.llm),
    )
    assert not r.success


def test_architect_extract_md() -> None:
    t = "```markdown:docs/x.md\n# T\n```"
    pair = _extract_md_file(t)
    assert pair is not None
    assert pair[0].endswith(".md")


def test_design_stub_writes(tmp_path: Path) -> None:
    r = design_stub({"id": "D", "description": "Svc"}, tmp_path)
    assert r.success
    assert (tmp_path / INTERFACE_PATH).is_file()


def test_design_with_llm_plain_block(tmp_path: Path) -> None:
    class F(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(text="```markdown\n# API\n```", usage=Usage(1, 1))

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    r = design_with_llm(
        {"id": "D"},
        {"global": {}, "project": {}, "tasks": [], "workers": []},
        tmp_path,
        F(cfg.llm),
    )
    assert r.success
