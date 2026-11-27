from __future__ import annotations

import re
import unicodedata

_EXTRA_FOLDS = str.maketrans({"đ": "d", "Đ": "D", "ð": "d", "ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "ß": "ss", "æ": "ae", "Æ": "AE"})
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def fold(value: str | None) -> str:
    text = unicodedata.normalize("NFD", (value or "").translate(_EXTRA_FOLDS))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower().strip()


def slugify(value: str | None) -> str:
    return _NON_SLUG.sub("-", fold(value)).strip("-")


def clean(value: object, max_length: int = 200) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = _CONTROL.sub("", text).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return re.sub(r"\s{2,}", " ", text).strip()[:max_length]


def volume_slug(value: str | None) -> str:
    """Folder names in the documents volume drop every non-ASCII letter (Ćićevac -> i-evac, Vršac -> vr-ac)."""
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def plan_key(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def kebab(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
