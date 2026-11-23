"""Run with .venv/bin/python tests/check_mcp_captcha.py; no network."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hh_applicant_tool.operations.apply_vacancies import SEARCH_PARAM_NAMES, Operation

args = SimpleNamespace(
    **{name: None for name in SEARCH_PARAM_NAMES},
    mcp_ai_filter=Path("logs/decisions.json"),
    resume_id="resume",
    ai_filter=False,
    send_email=False,
    dry_run=False,
    export_review=None,
    approved_ids=None,
    excluded_filter=None,
    force_cover_letter=False,
    max_responses=None,
    skip_tests=True,
    total_pages=1,
    start_page=1,
)
tool = SimpleNamespace(
    general_config={},
    verbosity=1,
    use_ai=True,
    ai_chat_for=Mock(side_effect=AssertionError("model API call")),
)
op = Operation()
with (
    patch("hh_applicant_tool.operations._mcp_vacancy_filter.run_mcp_filter", return_value={"123": None}),
    patch.object(Operation, "_apply_vacancies", return_value=None),
):
    op.run(tool, args)

assert tool.use_ai is True
assert op.cover_letter_ai is op.test_ai is op.vacancy_filter_ai is None
assert not tool.ai_chat_for.called
assert op.approved_ids == {"123"}
print("OK")
