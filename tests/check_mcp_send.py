"""Run with .venv/bin/python tests/check_mcp_send.py; no network."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hh_applicant_tool.operations.apply_vacancies import Operation

op = Operation()
api = Mock(delay=0)
api.get.side_effect = [{"name": "Open"}, {"name": "Closed", "archived": True}]
api.post.return_value = {}
op.tool = SimpleNamespace(api_client=api)
op.review_letters = {"123": None, "456": None}
op.approved_ids = set(op.review_letters)
op.excluded_employer_id = []
op.max_responses = None
op.excluded_pat = None
op.force_cover_letter = op.dry_run = op.ai_filter = op.send_email = False
resume = {"id": "resume", "title": "PM", "alternate_url": "resume-url"}
with (
    patch.object(op, "_get_vacancies", side_effect=AssertionError("search repeated")),
    patch.object(op, "_build_resume_placeholders", return_value={}),
    patch("hh_applicant_tool.operations.apply_vacancies.logger") as log,
):
    assert not op._apply_resume(resume, {}, set())
    log.info.assert_any_call("Пропуск %s: %s", "https://hh.ru/vacancy/456", "в архиве")
assert [c.args[0] for c in api.get.call_args_list] == ["/vacancies/123", "/vacancies/456"]
api.post.assert_called_once()
assert api.post.call_args.args[1]["vacancy_id"] == "123"
