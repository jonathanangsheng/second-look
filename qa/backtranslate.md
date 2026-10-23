# Back-translation QA

23 cards checked, 7 strings flagged. Review each and fill in its Note (one line).

### demo/fail-sceptic/02-debate.json ar verdict
- English: North East London controls possession at 72% but box entries lag at 6.4
- Translated: North East London يسيطر على الكرة بنسبة 72% لكن دخول منطقة الجزاء متأخر بنسبة 6.4
- Back-translated: North East London controls the ball at 72% but box entries are late at 6.4
Note: Accepted (Claude review): same meaning; only wording, synonyms or minute format differ.

### demo/fail-sceptic/05-debate.json es hype
- English: North East London dominate possession with 71% but struggle on 11.5
- Translated: North East London dominan la posesión con un 71% pero tienen problemas con el 11,5
- Back-translated: North East London dominate possession with 71% but have problems with 11.5
Note: Accepted (Claude review): same meaning; only wording, synonyms or minute format differ.

### demo/fail-sceptic/05-debate.json ar hype
- English: North East London dominate possession with 71% but struggle on 11.5
- Translated: North East London يسيطرون على الكرة بنسبة 71% لكنهم يواجهون صعوبة في الدخول إلى منطقة الجزاء بنسبة 11.5
- Back-translated: North East London dominate possession with 71% but they face difficulty entering the box at 11.5
Note: Accepted (Claude review): same meaning; only wording, synonyms or minute format differ.

### demo/normal/15-called_it.json es analyst
- English: Call made at 60', goal at 78', deadline 85'.
- Translated: Pronóstico en el 60', gol en el 78', plazo 85'.
- Back-translated: Forecast at 60', goal at 78', term 85'.
Note: Accepted (Claude review): same meaning; only wording, synonyms or minute format differ.

### demo/normal/15-called_it.json ar analyst
- English: Call made at 60', goal at 78', deadline 85'.
- Translated: التوقع في 60، الهدف في 78، والمهلة 85.
- Back-translated: Prediction at 60, goal at 78, and the timeout at 85.
Note: Accepted (Claude review): same meaning; only wording, synonyms or minute format differ.

### demo/normal/15-debate.json es fan_yob
- English: They have had the better chances recently, but we still lead. A goal is coming for North East London.
- Translated: Ellos han tenido mejores ocasiones recientemente, pero aún seguimos ganando. Se acerca un gol para North East London.
- Back-translated: They have had better chances recently, but we are still winning. A goal is coming for North East London.
Note: Accepted (Claude review): same meaning; only wording, synonyms or minute format differ.

### random1/normal/05-debate.json es fan_eat
- English: They have the better chances and look set to score soon A goal is coming for Man Blue.
- Translated: Ellos tienen las mejores oportunidades y parece que marcarán pronto. Un gol está por venir para Man Blue.
- Back-translated: They have the best chances and it seems they will score soon. A goal is coming for Man Blue.
Note: Accepted (Claude review): same meaning; only wording, synonyms or minute format differ.
