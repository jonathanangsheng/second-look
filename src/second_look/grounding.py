"""Hallucination guard for agent text: numbers may only enter through evidence placeholders.

A model line is accepted only if it contains no digits of its own (Arabic-Indic digits
included) and every {placeholder} names an evidence field. Placeholders are then filled
with the language's formatted value. Spelled-out numbers are not rejected (too many idioms:
"no one", "one-way"); they are returned as flags for a human to review.
"""

from __future__ import annotations

import re
import string

from second_look.contracts import Lang

ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# fmt: off
NUMBER_WORDS: dict[str, set[str]] = {
    "en": {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
           "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"},
    "es": {"cero", "uno", "una", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once",
           "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte"},
    "ar": {"صفر", "واحد", "اثنان", "اثنين", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة", "عشرة",
           "عشرون", "عشرين"},
}
# fmt: on


class GroundingError(ValueError):
    pass


def ground(raw: str, shown: dict[str, dict[str, str]], lang: Lang) -> str:
    """Fill placeholders from `shown` (evidence_display) or raise GroundingError."""
    if re.search(r"\d", re.sub(r"\{[^{}]*\}", "", raw).translate(ARABIC_INDIC)):  # placeholder names may hold digits
        raise GroundingError(f"digit outside a placeholder: {raw!r}")
    for key, value in shown.items():  # a name typed out would get translated or drift; only its placeholder is safe
        name = value[lang]
        if not re.search(r"\d", name) and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", raw, re.I):
            raise GroundingError(f"write {{{key}}} instead of {name!r}")
    fields = placeholders(raw)
    unknown = fields - shown.keys()
    if unknown:
        raise GroundingError(f"unknown placeholder(s) {sorted(unknown)}")
    return raw.format(**{k: shown[k][lang] for k in fields})


def placeholders(raw: str) -> set[str]:
    """The {placeholder} names in `raw`."""
    try:
        return {name for _, name, _, _ in string.Formatter().parse(raw) if name}
    except ValueError as exc:  # unbalanced braces
        raise GroundingError(str(exc)) from exc


def number_words(text: str, lang: Lang) -> list[str]:
    """Spelled-out numbers in `text`, for the review log (not a rejection)."""
    return [w for w in re.findall(r"\w+", text.lower()) if w in NUMBER_WORDS[lang]]
