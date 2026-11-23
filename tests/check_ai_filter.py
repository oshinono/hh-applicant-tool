""".venv/bin/python tests/check_ai_filter.py — без сети."""
import json
from unittest import TestCase
from unittest.mock import Mock

from hh_applicant_tool.operations.apply_vacancies import DEFAULT_AI_FILTER_PROMPT, DEFAULT_TEST_CHOICE_PROMPT, Operation, _ApplyError
from hh_applicant_tool.tool import HHApplicantTool
from hh_applicant_tool.utils.string import render_template

op = Operation()
op.tool = HHApplicantTool()
op.tool.api_client = Mock()
op.tool.config = {"general": {"candidate_context": "Готов к релокации"}}
op.test_ai = Mock()
op.vacancy_filter_ai = Mock()
op.ai_filter_prompt = DEFAULT_AI_FILTER_PROMPT
jobs = [{"position": f"Роль {i}", "description": "a" * 1100 + " конец"} for i in range(5)]
op.tool.api_client.get.return_value = {
    "experience": jobs,
    "area": {"name": "Москва"},
    "business_trip_readiness": {"name": "Готов к командировкам"},
    "language": [{"name": "Английский", "level": {"id": "b2", "name": "B2 — Средне-продвинутый"}}],
}
fields = op._build_resume_placeholders({"id": "resume"}, {})
test_prompt = render_template(DEFAULT_TEST_CHOICE_PROMPT, {**fields, "question": "Переезд?", "reply_options": "1: Да"})
assert "Роль 4" in test_prompt and "Готов к релокации" in test_prompt and "1: Да" in test_prompt
op.tool.api_client.get.return_value = {"description": "<ul><li>A &amp; B</li><li>C</li></ul><script>hidden()</script><p>" + "b" * 2050 + "</p>"}
for decision in ("apply", "skip"):
    op.vacancy_filter_ai.complete.return_value = json.dumps({"decision": decision, "reason": "По опыту"})
    assert op._is_vacancy_suitable({"id": "1"}, {**fields, "vacancy_name": "PM"}) == (decision == "apply")
prompt = op.vacancy_filter_ai.complete.call_args.args[0]
assert "Языки: Английский — B2 — Средне-продвинутый" in prompt
assert "Город по резюме: Москва\nКомандировки: Готов к командировкам" in prompt
assert "Роль 4" in prompt and prompt.count(" конец") == 5
assert "A & B\nC\n" + "b" * 1992 in prompt and "b" * 1993 not in prompt and "hidden()" not in prompt
op.ai_filter = True
op.excluded_pat = op.approved_ids = None
vacancy = {"id": "1", "alternate_url": "url"}
for op.dry_run in (True, False):
    op.vacancy_filter_ai.complete.return_value = "да"
    with TestCase().assertRaises(_ApplyError):
        op._is_vacancy_rejected(vacancy, {**fields, "vacancy_name": "PM"})
    op.api_client.put.assert_not_called()
    op.vacancy_filter_ai.complete.return_value = json.dumps({"decision": "skip", "reason": "По опыту"})
    assert op._is_vacancy_rejected(vacancy, {**fields, "vacancy_name": "PM"})
    assert op.api_client.put.call_count == int(not op.dry_run)
op.api_client.put.assert_called_once_with("/vacancies/blacklisted/1")
for invalid in ('да', '{}', '{"decision":"apply","reason":""}', '{"decision":"skip","reason":"x\\ny"}'):
    try:
        op._parse_filter_response(invalid)
    except ValueError:
        continue
    raise AssertionError(invalid)
