"""Hand off HH vacancies to the chat agent; never call a model API."""
from __future__ import annotations

import json
import logging
import os
import re
from time import monotonic, sleep
from typing import TYPE_CHECKING

from ..errors import OperationError
from ..utils.string import strip_tags

if TYPE_CHECKING:
    from pathlib import Path

    from .apply_vacancies import Operation

logger = logging.getLogger(__name__.split(".")[0])


def _resume_for_model(resume: dict) -> dict:
    fields = (
        "title", "area", "total_experience", "skill_set", "language",
        "education", "professional_roles", "salary", "work_format", "employment",
    )
    result = {key: resume[key] for key in fields if key in resume}
    result["experience"] = [
        {key: item[key] for key in ("company", "position", "start", "end", "description") if key in item}
        for item in resume.get("experience") or []
    ]
    return result


def _vacancy_for_review(vacancy_id: str, detail: dict) -> dict:
    # ponytail: keep only fields the reviewer needs; extend the allowlist for new criteria.
    row = {
        key: detail[key]
        for key in (
            "name", "alternate_url", "salary", "salary_range", "experience",
            "work_format", "schedule", "employment", "employment_form", "work_hours",
            "key_skills", "has_test", "response_letter_required",
        )
        if key in detail
    }
    for key in ("employer", "area"):
        item = detail.get(key) or {}
        row[key] = {field: item[field] for field in ("id", "name") if field in item}
    return {**row, "id": vacancy_id, "description": strip_tags(detail.get("description") or "")}


def _review_decisions(data: object, rows: dict) -> dict[str, str | None]:
    if not isinstance(data, dict) or data.keys() != rows.keys():
        raise OperationError("Нужно решение для каждого ID текущей MCP-выгрузки и ни одного лишнего")
    approved = {}
    for id_, entry in data.items():
        if not isinstance(entry, dict) or entry.keys() - {"decision", "reason", "letter"}:
            raise OperationError(f"Неверный формат решения MCP для вакансии {id_}")
        decision, reason, letter = entry.get("decision"), entry.get("reason"), entry.get("letter")
        if decision not in ("apply", "skip") or not (
            isinstance(reason, str) and 0 < len(reason) <= 160 and reason.strip()
            and reason.splitlines() == [reason]
        ):
            raise OperationError(f"Вакансия {id_}: нужны apply/skip и причина в одну строку до 160 символов")
        if letter is not None and not (
            decision == "apply" and isinstance(letter, str) and 0 < len(letter) <= 1000 and letter.strip()
        ):
            raise OperationError(f"Вакансия {id_}: текст письма до 1000 символов допустим только для apply")
        if decision == "apply":
            approved[id_] = letter
    return approved

def run_mcp_filter(op: Operation, output: Path) -> dict[str, str | None]:
    output = output.absolute()
    review = output.with_name(output.name + ".review.json")
    if output.exists() or output.is_symlink() or review.exists() or review.is_symlink():
        raise OperationError("Для --mcp-ai-filter укажите новый путь к JSON")
    if not any(r["id"] == op.resume_id and r["status"]["id"] == "published" for r in op.tool.get_resumes()):
        raise OperationError("--resume-id должен указывать на ваше опубликованное резюме HH")

    rows = {}
    for item in op._get_vacancies(op.resume_id):
        vacancy_id = str(item["id"])
        if vacancy_id in rows:
            continue
        if not re.fullmatch(r"[0-9]{1,20}", vacancy_id):
            raise OperationError("HH вернул некорректный ID вакансии")
        reason = op._vacancy_skip_reason(item)
        if not reason:
            detail = dict(op.api_client.get(f"/vacancies/{vacancy_id}"))
            reason = op._vacancy_skip_reason(detail)
            if not reason and op._is_excluded(item, description=detail.get("description") or ""):
                reason = "фильтр исключений"
        if reason:
            logger.info("[1/2] Вакансия %s пропущена: %s", vacancy_id, reason)
            continue
        rows[vacancy_id] = _vacancy_for_review(vacancy_id, detail)

    if not rows:
        return {}

    try:
        fd = os.open(review, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(list(rows.values()), file, ensure_ascii=False)
    except OSError as ex:
        raise OperationError(f"Не удалось сохранить выгрузку: {review}") from ex
    message = f"[1/2] Жду оценку агента через MCP: {review}. Решения: {output}"
    logger.info("%s", message)
    if not op.tool.verbosity:
        print(message, flush=True)

    # ponytail: one local JSON handoff; use a service only if remote agents need access.
    deadline = monotonic() + 600
    while monotonic() < deadline:
        try:
            with output.open(encoding="utf-8") as file:
                decisions = json.load(file)
        except FileNotFoundError:
            sleep(1)
            continue
        except (OSError, ValueError) as ex:
            raise OperationError("Не удалось прочитать решения MCP") from ex
        return _review_decisions(decisions, rows)
    raise OperationError("Агент не вернул решения за 10 минут. Отклики не отправлены")
