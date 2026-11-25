from __future__ import annotations

import json
import re
from datetime import date, datetime
from functools import lru_cache
from typing import Any

import constants

_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
}
_MONTHS_SHORT = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"],
    "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
}


@lru_cache(maxsize=None)
def messages(locale: str) -> dict[str, Any]:
    path = constants.LOCALES_DIR / f"{locale}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_locale(value: str | None) -> str:
    value = (value or "").strip().lower()
    return value if value in constants.LOCALES else constants.DEFAULT_LOCALE


class Translator:
    def __init__(self, locale: str = constants.DEFAULT_LOCALE):
        self.locale = normalize_locale(locale)
        self.messages = messages(self.locale)
        self._fallback = messages(constants.DEFAULT_LOCALE)

    def _lookup(self, key: str, tree: dict[str, Any] | None = None) -> Any:
        node: Any = tree if tree is not None else self.messages
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

    def raw(self, key: str) -> Any:
        value = self._lookup(key)
        return value if value is not None else self._lookup(key, self._fallback)

    def _fill(self, text: str, values: dict[str, Any]) -> str:
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in values:
                return match.group(0)
            value = values[name]
            if isinstance(value, bool):
                return str(value)
            if isinstance(value, (int, float)):
                return self.number(value)
            return str(value)

        return _PLACEHOLDER.sub(replace, text)

    def t(self, message_key: str, /, **values: Any) -> str:
        text = self.raw(message_key)
        return self._fill(text, values) if isinstance(text, str) else message_key

    def t_or(self, message_key: str, fallback: str, /, **values: Any) -> str:
        text = self.raw(message_key)
        return self._fill(text, values) if isinstance(text, str) else fallback

    def plural_form(self, count: float) -> str:
        if self.locale == "fr":
            return "one" if 0 <= count < 2 else "other"
        return "one" if count == 1 else "other"

    def tp(self, message_key: str, count: float, /, **values: Any) -> str:
        form = self.plural_form(count)
        return self.t(f"{message_key}.{form}", count=count, **values)

    def items(self, key: str) -> list[Any]:
        node = self.raw(key)
        return list(node.values()) if isinstance(node, dict) else []

    def entries(self, key: str) -> list[tuple[str, Any]]:
        node = self.raw(key)
        return list(node.items()) if isinstance(node, dict) else []

    def _group(self, digits: str) -> str:
        sep = " " if self.locale == "fr" else ","
        out = []
        while len(digits) > 3:
            out.insert(0, digits[-3:])
            digits = digits[:-3]
        out.insert(0, digits)
        return sep.join(out)

    def number(self, value: float | int | None, digits: int | None = None, grouping: bool = True) -> str:
        if value is None:
            return "–"
        if digits is None:
            if isinstance(value, int) or float(value).is_integer():
                digits = 0
            else:
                digits = min(3, len(f"{value}".split(".")[1].rstrip("0")))
        text = f"{abs(value):.{digits}f}"
        whole, _, frac = text.partition(".")
        whole = self._group(whole) if grouping else whole
        decimal = "," if self.locale == "fr" else "."
        sign = "-" if value < 0 and float(text) != 0 else ""
        return f"{sign}{whole}{decimal + frac if frac else ''}"

    def score(self, value: float | None, digits: int = 1) -> str:
        if value is None:
            return "–"
        return self.number(round(value + 0.0, digits), digits, grouping=False)

    def count(self, value: float | None) -> str:
        return "–" if value is None else self.number(round(value), 0)

    def area(self, value: float | None) -> str:
        return "–" if value is None else f"{self.number(round(value), 0)} km²"

    def percent(self, ratio: float) -> str:
        return f"{self.number(round(ratio * 100), 0)}{' %' if self.locale == 'fr' else '%'}"

    def compact(self, value: float | None) -> str:
        if value is None:
            return "–"
        for size, en, fr in ((1e9, "B", "Md"), (1e6, "M", "M"), (1e3, "K", "k")):
            if abs(value) >= size:
                scaled = round(value / size, 1)
                suffix = fr if self.locale == "fr" else en
                return f"{self.number(scaled, 0 if float(scaled).is_integer() else 1)}{' ' if self.locale == 'fr' else ''}{suffix}"
        return self.number(round(value), 0)

    def delta(self, value: float, digits: int = 0) -> str:
        rounded = round(value, digits)
        if rounded == 0:
            return self.score(0, digits)
        return f"{'+' if rounded > 0 else '−'}{self.score(abs(rounded), digits)}"

    def date(self, value: str | date | datetime | None, short: bool = False) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        months = (_MONTHS_SHORT if short else _MONTHS)[self.locale]
        return f"{value.day} {months[value.month - 1]} {value.year}"


@lru_cache(maxsize=None)
def translator(locale: str) -> Translator:
    return Translator(locale)
