"""Deterministic EN/ES/AR card text. Used as-is for template cards and as the agents' fallback.

Every number comes from a {placeholder} filled from evidence, formatted per language.
"""

from __future__ import annotations

from second_look.contracts import Lang

LANGS: tuple[Lang, ...] = ("en", "es", "ar")
MINUTE_FIELDS = {"minute", "made_at_minute", "by_minute", "window_from_minute"}
PERCENT_FIELDS = {"possession_pct"}
TEAM_FIELDS = {"team", "trailer", "leader", "opponent"}

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
        # Fan lines: a supporter of the team the stat is about (side), then of the other team.
        "fan_side": {
            "en": "We keep shooting, but we need better chances than these.",
            "es": "Seguimos disparando, pero necesitamos ocasiones mejores que estas.",
            "ar": "نواصل التسديد، لكننا نحتاج فرصًا أفضل من هذه.",
        },
        "fan_other": {
            "en": "They are shooting from anywhere. Nothing to worry about yet.",
            "es": "Disparan desde cualquier sitio. De momento, nada de qué preocuparse.",
            "ar": "يسددون من أي مكان. لا داعي للقلق حتى الآن.",
        },
    },
    "scoreline_xg": {
        "hype": {
            "en": "{leader} lead and look comfortable. This one is done.",
            "es": "{leader} va por delante y parece tranquilo. Esto está hecho.",
            "ar": "{leader} متقدم ويبدو مرتاحًا. المباراة محسومة.",
        },
        "sceptic": {
            "en": "Since {window_from_minute}, {trailer} have {trailer_xg_window} xG to {leader_xg_window}. The score is lying.",
            "es": "Desde el {window_from_minute}, {trailer} suma {trailer_xg_window} xG contra {leader_xg_window}. El marcador miente.",
            "ar": "منذ الدقيقة {window_from_minute}، لدى {trailer} ‏{trailer_xg_window} مقابل {leader_xg_window}. النتيجة تكذب.",
        },
        # Also the prediction itself: CLAIM below, used for the card's claim and the ledger's claim_text.
        "verdict": {
            "en": "A goal is coming for {trailer}.",
            "es": "Se viene un gol de {trailer}.",
            "ar": "هدف قادم لفريق {trailer}.",
        },
        "analyst": {
            "en": "Rolling xG since {window_from_minute}: {trailer_xg_window} against {leader_xg_window}, past the {threshold} gap.",
            "es": "xG desde el {window_from_minute}: {trailer_xg_window} contra {leader_xg_window}, por encima de {threshold}.",
            "ar": "الأهداف المتوقعة منذ الدقيقة {window_from_minute}: {trailer_xg_window} مقابل {leader_xg_window}، فوق فارق {threshold}.",
        },
        "casual": {
            "en": "The score says one thing. The chances say {trailer} will score.",
            "es": "El marcador dice una cosa. Las ocasiones dicen que {trailer} marcará.",
            "ar": "النتيجة تقول شيئًا، والفرص تقول إن {trailer} سيسجل.",
        },
        "fan_side": {
            "en": "Behind on the scoreboard, ahead on chances. Keep believing.",
            "es": "Por detrás en el marcador, por delante en ocasiones. A seguir creyendo.",
            "ar": "متأخرون في النتيجة، متقدمون في الفرص. واصلوا الإيمان.",
        },
        "fan_other": {
            "en": "We are ahead, but they are making the better chances.",
            "es": "Vamos por delante, pero ellos generan las mejores ocasiones.",
            "ar": "نحن متقدمون، لكنهم يصنعون الفرص الأفضل.",
        },
    },
    "possession_penetration": {
        "hype": {
            "en": "{team} own the ball: {possession_pct} possession. Total control.",
            "es": "{team} es dueño del balón: {possession_pct} de posesión. Control total.",
            "ar": "{team} يسيطر على الكرة: استحواذ {possession_pct}. سيطرة تامة.",
        },
        "sceptic": {
            "en": "Box entry rate: {box_entry_rate} against {opponent_box_entry_rate} for {opponent}.",
            "es": "Entradas al área: {box_entry_rate} frente a {opponent_box_entry_rate} de {opponent}.",
            "ar": "معدل الدخول إلى المنطقة: {box_entry_rate} مقابل {opponent_box_entry_rate} لـ {opponent}.",
        },
        "verdict": {
            "en": "The ball, not the box. Possession is not pressure.",
            "es": "El balón, no el área. Tener la pelota no es apretar.",
            "ar": "الكرة لا المنطقة. الاستحواذ ليس خطورة.",
        },
        "analyst": {
            "en": "{possession_pct} possession; box entry rate {box_entry_rate} vs {opponent_box_entry_rate}, a ratio of {ratio}, under {max_ratio}.",
            "es": "{possession_pct} de posesión; entradas al área {box_entry_rate} frente a {opponent_box_entry_rate}, una proporción de {ratio}, bajo {max_ratio}.",
            "ar": "استحواذ {possession_pct}؛ معدل الدخول إلى المنطقة {box_entry_rate} مقابل {opponent_box_entry_rate}، بنسبة {ratio}، أقل من {max_ratio}.",
        },
        "casual": {
            "en": "Lots of the ball, hardly any trips into the box.",
            "es": "Mucho balón, casi ninguna llegada al área.",
            "ar": "استحواذ كبير، وبالكاد وصول إلى المنطقة.",
        },
        "fan_side": {
            "en": "We have all the ball. Now we need to get into the box.",
            "es": "Tenemos todo el balón. Ahora hay que pisar el área.",
            "ar": "الكرة كلها معنا. الآن علينا دخول المنطقة.",
        },
        "fan_other": {
            "en": "Let them pass it around. They are not getting near our box.",
            "es": "Que se la pasen. No se acercan a nuestra área.",
            "ar": "دعهم يتناقلون الكرة. لا يقتربون من منطقتنا.",
        },
    },
    "effort_game_state": {
        "hype": {
            "en": "{team} are behind but still fighting for every ball.",
            "es": "{team} va por detrás pero sigue peleando cada balón.",
            "ar": "{team} متأخر لكنه ما زال يقاتل على كل كرة.",
        },
        "sceptic": {
            "en": "Their pressing rate fell from {press_rate_while_level} to {press_rate_while_behind} since going behind.",
            "es": "Su ritmo de presión bajó de {press_rate_while_level} a {press_rate_while_behind} desde que van perdiendo.",
            "ar": "تراجع معدل ضغطهم من {press_rate_while_level} إلى {press_rate_while_behind} منذ تأخرهم.",
        },
        "verdict": {
            "en": "Behind on the scoreboard, and the effort has faded with it.",
            "es": "Por detrás en el marcador, y el esfuerzo se ha apagado con él.",
            "ar": "متأخرون في النتيجة، والجهد تراجع معها.",
        },
        "analyst": {
            "en": "Pressing rate {press_rate_while_behind} while behind against {press_rate_while_level} before: a ratio of {ratio}, under {max_ratio}.",
            "es": "Ritmo de presión {press_rate_while_behind} perdiendo frente a {press_rate_while_level} antes: una proporción de {ratio}, bajo {max_ratio}.",
            "ar": "معدل الضغط {press_rate_while_behind} أثناء التأخر مقابل {press_rate_while_level} قبله: بنسبة {ratio}، أقل من {max_ratio}.",
        },
        "casual": {
            "en": "Since going behind, they have stopped chasing the ball.",
            "es": "Desde que van perdiendo, han dejado de perseguir el balón.",
            "ar": "منذ أن تأخروا، توقفوا عن مطاردة الكرة.",
        },
        "fan_side": {
            "en": "We are behind and we have stopped pressing. Wake up.",
            "es": "Vamos perdiendo y hemos dejado de presionar. Despertemos.",
            "ar": "نحن متأخرون وتوقفنا عن الضغط. استيقظوا.",
        },
        "fan_other": {
            "en": "They have gone quiet since falling behind. Keep it that way.",
            "es": "Se han apagado desde que van perdiendo. Que siga así.",
            "ar": "هدأوا منذ تأخرهم. فلنحافظ على ذلك.",
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
        elif key in PERCENT_FIELDS:
            out[key] = dict.fromkeys(LANGS, f"{value}%")
        elif key in MINUTE_FIELDS:
            out[key] = {"en": f"{value}'", "es": f"{value}'", "ar": f"{value}"}
        elif isinstance(value, float):
            text = f"{value:.3g}"  # 0.075 stays 0.075, so it never reads as equal to a 0.08 threshold
            text = text if "." in text else text + ".0"
            out[key] = {"en": text, "es": text.replace(".", ","), "ar": text}
        elif isinstance(value, int):
            out[key] = dict.fromkeys(LANGS, str(value))
    return out


CLAIM = TEMPLATES["scoreline_xg"]["verdict"]  # the prediction a scoreline_xg call makes, with a {trailer} placeholder


def claim(team_name: str) -> T:
    """The prediction filled in, in every language (team names read the same in all three)."""
    return {lang: text.format(trailer=team_name) for lang, text in CLAIM.items()}


FAN_SIDES = ("fan_side", "fan_other")


def render(
    key: str, evidence: dict, team_names: dict[str, str]
) -> tuple[dict[str, T], dict[str, T], dict[str, T], dict[str, T]]:
    """(lines by speaker, variants by persona, evidence_display, fan lines by side) for a detector or outcome kind."""
    shown = display(evidence, team_names)
    parts = {
        part: {lang: text.format(**{k: v[lang] for k, v in shown.items()}) for lang, text in texts.items()}
        for part, texts in TEMPLATES[key].items()
    }
    lines = {s: parts[s] for s in ("hype", "sceptic", "verdict") if s in parts}
    variants = {p: parts[p] for p in ("analyst", "casual")}
    fans = {side: parts[side] for side in FAN_SIDES if side in parts}
    return lines, variants, shown, fans
