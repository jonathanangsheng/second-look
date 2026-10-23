"""Deterministic EN/ES/AR card text. Used as-is for template cards and as the agents' fallback.

Every number comes from a {placeholder} filled from evidence, formatted per language.
"""

from __future__ import annotations

from second_look.contracts import Lang

LANGS: tuple[Lang, ...] = ("en", "es", "ar")
MINUTE_FIELDS = {"minute", "made_at_minute", "by_minute", "window_from_minute"}
TEAM_FIELDS = {"team", "leader"}

T = dict[Lang, str]
TEMPLATES: dict[str, dict[str, T]] = {
    "volume_quality": {
        "hype": {
            "en": "{team}: {shots} shots already. They are all over them.",
            "es": "{team}: ya {shots} disparos. Los tienen encerrados.",
            "ar": "{team}: {shots} تسديدات حتى الآن. يحاصرون منافسهم.",
        },
        "sceptic": {
            "en": "{shots} shots at {xg_per_shot} xG each, from {avg_shot_distance_m} metres on average.",
            "es": "{shots} disparos de {xg_per_shot} xG cada uno, desde {avg_shot_distance_m} metros de media.",
            "ar": "{shots} تسديدات بمعدل {xg_per_shot} لكل منها، من {avg_shot_distance_m} مترًا في المتوسط.",
        },
        "verdict": {
            "en": "Volume, not danger. These shots rarely score.",
            "es": "Volumen, no peligro. Estos disparos casi nunca acaban en gol.",
            "ar": "كمية بلا خطورة. هذه التسديدات نادرًا ما تهز الشباك.",
        },
        "analyst": {
            "en": "{shots} shots at {xg_per_shot} xG per shot, under the {threshold} threshold.",
            "es": "{shots} disparos a {xg_per_shot} xG por disparo, bajo el umbral de {threshold}.",
            "ar": "{shots} تسديدات بمعدل {xg_per_shot} للتسديدة، أقل من حد {threshold}.",
        },
        "casual": {
            "en": "Lots of shots, almost no real chances.",
            "es": "Muchos disparos, casi ninguna ocasión real.",
            "ar": "تسديدات كثيرة، وفرص حقيقية شبه معدومة.",
        },
    },
    "scoreline_xg": {
        "hype": {
            "en": "{leader} lead and look comfortable. This one is done.",
            "es": "{leader} va por delante y parece tranquilo. Esto está hecho.",
            "ar": "{leader} متقدم ويبدو مرتاحًا. المباراة محسومة.",
        },
        "sceptic": {
            "en": "Since {window_from_minute}, {team} have {trailer_xg_window} xG to {leader_xg_window}. The score is lying.",
            "es": "Desde el {window_from_minute}, {team} suma {trailer_xg_window} xG contra {leader_xg_window}. El marcador miente.",
            "ar": "منذ الدقيقة {window_from_minute}، لدى {team} ‏{trailer_xg_window} مقابل {leader_xg_window}. النتيجة تكذب.",
        },
        # Also the prediction's claim_text (English).
        "verdict": {
            "en": "A goal is coming for {team}.",
            "es": "Se viene un gol de {team}.",
            "ar": "هدف قادم لفريق {team}.",
        },
        "analyst": {
            "en": "Rolling xG since {window_from_minute}: {trailer_xg_window} against {leader_xg_window}, past the {threshold} gap.",
            "es": "xG desde el {window_from_minute}: {trailer_xg_window} contra {leader_xg_window}, por encima de {threshold}.",
            "ar": "الأهداف المتوقعة منذ الدقيقة {window_from_minute}: {trailer_xg_window} مقابل {leader_xg_window}، فوق فارق {threshold}.",
        },
        "casual": {
            "en": "The score says one thing. The chances say {team} will score.",
            "es": "El marcador dice una cosa. Las ocasiones dicen que {team} marcará.",
            "ar": "النتيجة تقول شيئًا، والفرص تقول إن {team} سيسجل.",
        },
    },
    "called_it": {
        "verdict": {
            "en": "Called it at {made_at_minute}. {team} score at {minute}.",
            "es": "Lo vimos en el {made_at_minute}. {team} marca en el {minute}.",
            "ar": "توقعناه في الدقيقة {made_at_minute}. {team} يسجل في الدقيقة {minute}.",
        },
        "analyst": {
            "en": "Call made at {made_at_minute}, goal at {minute}, deadline {by_minute}.",
            "es": "Pronóstico en el {made_at_minute}, gol en el {minute}, plazo {by_minute}.",
            "ar": "التوقع في {made_at_minute}، الهدف في {minute}، والمهلة {by_minute}.",
        },
        "casual": {
            "en": "The sceptic saw it coming.",
            "es": "El escéptico lo vio venir.",
            "ar": "المتشكك رآه قادمًا.",
        },
    },
    "missed_call": {
        "verdict": {
            "en": "Missed: no goal for {team} by {by_minute}.",
            "es": "Fallado: ningún gol de {team} antes del {by_minute}.",
            "ar": "توقع خاطئ: لا هدف لـ {team} بحلول الدقيقة {by_minute}.",
        },
        "analyst": {
            "en": "Call made at {made_at_minute}, deadline {by_minute}, no goal.",
            "es": "Pronóstico en el {made_at_minute}, plazo {by_minute}, sin gol.",
            "ar": "التوقع في {made_at_minute}، والمهلة {by_minute}، دون هدف.",
        },
        "casual": {
            "en": "The sceptic got this one wrong.",
            "es": "Esta vez el escéptico se equivocó.",
            "ar": "أخطأ المتشكك هذه المرة.",
        },
    },
}


def display(evidence: dict, team_names: dict[str, str]) -> dict[str, T]:
    """One formatted string per evidence field and language."""
    out: dict[str, T] = {}
    for key, value in evidence.items():
        if key in TEAM_FIELDS:
            out[key] = dict.fromkeys(LANGS, team_names.get(value, value))
        elif key in MINUTE_FIELDS:
            out[key] = {"en": f"{value}'", "es": f"{value}'", "ar": f"{value}"}
        elif isinstance(value, float):
            text = f"{value:.3g}"  # 0.075 stays 0.075, so it never reads as equal to a 0.08 threshold
            text = text if "." in text else text + ".0"
            out[key] = {"en": text, "es": text.replace(".", ","), "ar": text}
        elif isinstance(value, int):
            out[key] = dict.fromkeys(LANGS, str(value))
    return out


def claim(team_name: str) -> T:
    """The prediction a scoreline_xg Verdict makes, in every language (team names read the same in all three)."""
    return {lang: text.format(team=team_name) for lang, text in TEMPLATES["scoreline_xg"]["verdict"].items()}


def render(key: str, evidence: dict, team_names: dict[str, str]) -> tuple[dict[str, T], dict[str, T], dict[str, T]]:
    """(lines by speaker, variants by persona, evidence_display) for a detector or outcome kind."""
    shown = display(evidence, team_names)
    parts = {
        part: {lang: text.format(**{k: v[lang] for k, v in shown.items()}) for lang, text in texts.items()}
        for part, texts in TEMPLATES[key].items()
    }
    lines = {s: parts[s] for s in ("hype", "sceptic", "verdict") if s in parts}
    variants = {p: parts[p] for p in ("analyst", "casual")}
    return lines, variants, shown
