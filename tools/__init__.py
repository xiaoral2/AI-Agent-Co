"""Concrete Tools scoped to workspace/ (§6.1, §6.2, §5.2–§5.4)."""

from .filesystem import read_file, write_file
from .run_pytest import run_pytest

__all__ = ["read_file", "write_file", "run_pytest"]

# LLM-backed tools are imported on demand via:
#   tools.planner_tool   — plan_tasks, plan_with_llm
#   tools.architect_tool — design_with_llm, design_stub
#   tools.coder_tool     — code_with_llm, code_with_template
#   tools.tester_tool    — test_with_llm, test_with_existing
#   tools.reviewer_tool  — review_with_llm, review_stub
