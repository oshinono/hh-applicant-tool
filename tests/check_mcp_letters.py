"""Run with .venv/bin/python tests/check_mcp_letters.py; no network."""
from unittest.mock import patch

from hh_applicant_tool.errors import OperationError
from hh_applicant_tool.operations._mcp_vacancy_filter import _review_decisions, _vacancy_for_review
from hh_applicant_tool.operations.apply_vacancies import Operation

description = ("Полное описание. " * 1000).strip()
assert _vacancy_for_review("123", {
    "description": description, "contacts": {}, "address": {},
    "employer": {"id": "7", "name": "Компания", "logo_urls": {}},
    "area": None, "response_letter_required": False,
}) == {
    "id": "123", "description": description, "response_letter_required": False,
    "employer": {"id": "7", "name": "Компания"}, "area": {},
}

rows = {"123": {}, "456": {}}
apply = {"decision": "apply", "reason": "Опыт работы с Jira"}
skip = {"decision": "skip", "reason": "Тестовое задание"}
assert _review_decisions({"123": apply, "456": skip}, rows) == {"123": None}
assert _review_decisions({"123": skip, "456": skip}, rows) == {}
for invalid in (
    ["123", "456"],
    {"123": apply},
    {"123": apply, "999": skip},
    {"123": apply, "456": {**skip, "reason": " "}},
    {"123": apply, "456": {**skip, "reason": "a\nb"}},
    {"123": apply, "456": {**skip, "reason": "a" * 161}},
    {"123": apply, "456": {**skip, "letter": "Ответ"}},
    {"123": {**apply, "letter": "a" * 1001}, "456": skip},
):
    try:
        _review_decisions(invalid, rows)
    except OperationError:
        pass
    else:
        raise AssertionError(f"Accepted invalid decisions: {invalid!r}")

op = Operation()
op.review_letters = _review_decisions({"123": {**apply, "letter": "1. Ответ."}, "456": apply}, rows)
op.force_cover_letter = False
op.cover_letter_ai = None
op.cover_letter = "Шаблон"
with patch("hh_applicant_tool.operations.apply_vacancies.render_template", return_value="Шаблон") as render:
    assert op._build_cover_letter({"id": "123", "response_letter_required": True}, {}) == "1. Ответ."
    assert op._build_cover_letter({"id": "123", "response_letter_required": False}, {}) == "1. Ответ."
    assert op._build_cover_letter({"id": "456", "response_letter_required": False}, {}) == ""
    render.assert_not_called()
    assert op._build_cover_letter({"id": "456", "response_letter_required": True}, {}) == "Шаблон"
    render.assert_called_once()
