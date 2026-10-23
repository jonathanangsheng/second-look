# Back-translation QA

14 cards checked, 3 strings flagged. Review each and fill in its Note (one line).

### demo/normal/11-debate.json es hype
- English: North East London dominating with 1.3 xG since 30' minutes
- Translated: North East London domina con 1,3 xG en los últimos 30' minutos
- Back-translated: North East London dominates with 1.3 xG in the last 30 minutes
Note: Accepted (Claude review): "since 30'" read back as "in the last 30 minutes"; same window, same claim.

### demo/normal/11-debate.json es analyst
- English: Rolling xG since 30': 1.3 against 0.1, past the 1.0 gap.
- Translated: xG desde el 30': 1,3 contra 0,1, por encima de 1,0.
- Back-translated: xG since 30': 1.3 against 0.1, above 1.0.
Note: Accepted (Claude review): template Spanish says "above 1,0" without the word gap; the threshold is still clear.

### random1/normal/05-debate.json es analyst
- English: Rolling xG since 0': 1.2 against 0.1, past the 1.0 gap.
- Translated: xG desde el 0': 1,2 contra 0,1, por encima de 1,0.
- Back-translated: xG since 0': 1.2 against 0.1, above 1.0.
Note: Accepted (Claude review): same template Spanish as above; the gap word is implied by the threshold.
