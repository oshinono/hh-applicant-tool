from __future__ import annotations

import html
import random
import re
import string
from difflib import SequenceMatcher
from html.parser import HTMLParser
from typing import Any


def split_words(s: str) -> list[str]:
    return (
        s.lower()
        .translate(
            str.maketrans(string.punctuation, " " * len(string.punctuation))
        )
        .split()
    )


def choose_similar(input_text: str, options: list[str]) -> str | None:
    """Возвращает элемент из options, максимально похожий на input_text."""
    if not options:
        return None

    def normalize(s: str) -> str:
        return " ".join(s.casefold().split())

    query = normalize(input_text)

    def score(option: str) -> float:
        return SequenceMatcher(None, query, normalize(option)).ratio()

    return max(options, key=score)


def shorten(s: str, limit: int = 75, ellipsis: str = "…") -> str:
    return s[:limit] + bool(s[limit:]) * ellipsis


def rand_text(s: str) -> str:
    while (
        temp := re.sub(
            r"{([^{}]+)}",
            lambda m: random.choice(
                m.group(1).split("|"),
            ),
            s,
        )
    ) != s:
        s = temp
    return s


def render_template(
    template: str,
    placeholders: dict[str, str],
    name: str = "шаблоне",
    *,
    randomize_text: bool = False,
    escape_html: bool = False,
) -> str:
    """Подставляет плейсхолдеры `%(имя)s`, а неизвестный плейсхолдер
    превращает из невнятного `KeyError: 'имя'` в понятную ошибку."""
    if randomize_text:
        template = rand_text(template)
    if escape_html:
        placeholders = {k: html.escape(v) for k, v in placeholders.items()}
    try:
        return template % placeholders
    except KeyError as ex:
        raise ValueError(
            f"Неизвестный плейсхолдер %({ex.args[0]})s в {name}. "
            f"Доступные: {', '.join(sorted(placeholders))}"
        ) from ex


def bool2str(v: Any) -> str:
    """
    Возвращает переданное значение в виде строки: true/false

        >>> bool2str(1)
        'true'
        >>> bool2str(True)
        'true'
        >>> bool2str({})
        'false'
        >>> bool2str(' ')
        'true'
    """
    return str(bool(v)).lower()


def br2nl(s: str) -> str:
    return re.sub(r"<br\s*/?>", "\n", s, flags=re.I)


class _VacancyTextParser(HTMLParser):
    blocks = {"br", "p", "div", "li", "tr", "td", "th", *(f"h{i}" for i in range(1, 7))}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden = True
        elif tag in self.blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = False
        elif tag in self.blocks:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def vacancy_description_text(content: str) -> str:
    parser = _VacancyTextParser()
    parser.feed(content)
    parser.close()
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def strip_tags(content: str) -> str:
    content = br2nl(content)
    # убираем содержимое script/style целиком
    content = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1\s*>", "", content, flags=re.I | re.S
    )
    content = re.sub(r"<[^>]+>", "", content)
    content = html.unescape(content)
    # content = re.sub(r"\s+", " ", content)
    return content.strip()
