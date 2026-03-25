"""Extra coverage: PM loop, harness LLM branches, LLM retries, state_manager KeyError."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orchestrator.state_manager import StateManager, empty_session
from xr_ai_co.config import AppConfig, LLMConfig
from xr_ai_co.harness_executor import HarnessExecutor
from xr_ai_co.llm import LLMProvider, LLMProviderError, LLMResponse, Usage
from xr_ai_co.pm_clarification import run_pm_clarification_loop


def test_pm_clarification_skip_empty_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    out = run_pm_clarification_loop("my mission", AppConfig(), None)
    assert out == "my mission"


def test_pm_clarification_ceo_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt="": "must be fast")
    out = run_pm_clarification_loop("mission", AppConfig(), None)
    assert "CEO clarification" in out


def test_pm_clarification_llm_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    class F(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(
                text='```json\n{"questions": ["Use pytest?"]}\n```',
                usage=Usage(2, 2),
            )

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    llm = F(cfg.llm)
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    out = run_pm_clarification_loop("build api", cfg, llm)
    assert "Clarification Q&A" in out
    assert "Use pytest?" in out


def test_pm_clarification_llm_bad_then_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    class F(LLMProvider):
        def chat(self, **kwargs):
            raise LLMProviderError("down")

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    out = run_pm_clarification_loop("m", cfg, F(cfg.llm))
    assert out == "m"


def test_pm_extract_eof_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    class F(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(
                text='```json\n{"questions": ["Q?"]}\n```',
                usage=Usage(1, 1),
            )

    cfg = AppConfig(llm=LLMConfig(api_key="k"))

    def boom(_p: str = "") -> str:
        raise EOFError()

    monkeypatch.setattr("builtins.input", boom)
    out = run_pm_clarification_loop("m", cfg, F(cfg.llm))
    assert "Q?" in out
    assert "(no answer)" in out


def test_harness_coder_llm_fails_uses_template(tmp_path: Path) -> None:
    class Bad(LLMProvider):
        def chat(self, **kwargs):
            raise LLMProviderError("nope")

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    session = empty_session()
    ex = HarnessExecutor(tmp_path, "generic", config=cfg, llm=Bad(cfg.llm), session=session)
    r = ex.execute({"id": "T1", "type": "code"})
    assert r.success


def test_harness_architect_llm_success(tmp_path: Path) -> None:
    class Ok(LLMProvider):
        def chat(self, **kwargs):
            return LLMResponse(
                text="```markdown:docs/interface.md\n# API\n```",
                usage=Usage(3, 4),
            )

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    session = empty_session()
    ex = HarnessExecutor(tmp_path, "generic", config=cfg, llm=Ok(cfg.llm), session=session)
    r = ex.execute({"id": "D0", "type": "design"})
    assert r.success
    assert (tmp_path / "docs" / "interface.md").is_file()


def test_harness_architect_llm_fails_stub(tmp_path: Path) -> None:
    class Bad(LLMProvider):
        def chat(self, **kwargs):
            raise LLMProviderError("x")

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    session = empty_session()
    ex = HarnessExecutor(tmp_path, "generic", config=cfg, llm=Bad(cfg.llm), session=session)
    r = ex.execute({"id": "D0", "type": "design"})
    assert r.success


def test_harness_tester_llm_error(tmp_path: Path) -> None:
    class Bad(LLMProvider):
        def chat(self, **kwargs):
            raise LLMProviderError("api")

    cfg = AppConfig(llm=LLMConfig(api_key="k"))
    session = empty_session()
    ex = HarnessExecutor(tmp_path, "generic", config=cfg, llm=Bad(cfg.llm), session=session)
    r = ex.execute(
        {"id": "T2", "type": "test", "verification": {"paths": ["tests/missing.py"]}},
    )
    assert not r.success


def test_llm_chat_transient_retry_then_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class Transient503(Exception):
        status_code = 503

    fake_block = MagicMock()
    fake_block.text = "done"
    ok_resp = MagicMock()
    ok_resp.content = [fake_block]
    ok_resp.usage.input_tokens = 1
    ok_resp.usage.output_tokens = 1
    ok_resp.stop_reason = "end_turn"

    client = MagicMock()
    client.messages.create.side_effect = [Transient503("down"), ok_resp]

    prov = LLMProvider(LLMConfig(api_key="k", max_retries_transient_api=3))
    monkeypatch.setattr(prov, "_ensure_client", lambda: client)
    monkeypatch.setattr("xr_ai_co.llm.time.sleep", lambda s: None)
    r = prov.chat(system="s", messages=[{"role": "user", "content": "u"}])
    assert r.text == "done"
    assert client.messages.create.call_count == 2


def test_llm_anthropic_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import xr_ai_co.llm as lm

    monkeypatch.setattr(lm, "anthropic", None)
    p = LLMProvider(LLMConfig(api_key="k"))
    with pytest.raises(LLMProviderError, match="anthropic package"):
        p._ensure_client()


def test_state_update_unknown_task() -> None:
    s = empty_session()
    with pytest.raises(KeyError):
        StateManager.update_task_status(s, "nope", "done")
