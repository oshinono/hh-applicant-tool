"""Run with .venv/bin/python tests/check_employer_exclusions.py; no network."""
from unittest.mock import patch

from hh_applicant_tool.operations.apply_vacancies import Operation
from hh_applicant_tool.tool import HHApplicantTool

with (
    patch.object(HHApplicantTool, "general_config", {"excluded_employer_ids": ["123", "456"]}),
    patch.object(HHApplicantTool, "ai_enabled", False),
    patch.object(Operation, "_apply_vacancies"),
):
    tool = HHApplicantTool()
    op = Operation()
    op.run(tool, tool._parser.parse_args(["apply-vacancies", "--excluded-employer-id", "456", "789"]))
    assert op._get_search_params(0)["excluded_employer_id"] == ["123", "456", "789"]
    assert op._vacancy_skip_reason({"employer": {"id": 123}}) is not None
    assert op._vacancy_skip_reason({"employer": {"id": "321"}}) is None
