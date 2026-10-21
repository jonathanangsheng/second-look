# Second Look synthetic match data

Fictional teams inspired by public playing-style analysis. Not affiliated with or endorsed by the Premier League or any club. Every event is generated; no real match data is used.

## Generate

```bash
uv run second-look-sim --seed-name demo --out demo.jsonl      # a committed preset
uv run second-look-sim --home nel --away yob --seed 42        # any two profiles, to stdout
uv run second-look-sim --write-seeds                          # regenerate data/seeds/*
```

Same profiles + same seed = byte-identical output.

| Seed | Teams | Notes |
|---|---|---|
| `demo` | `nel` v `yob` | Scripted goals (`yob` ~22', 51'; `nel` 78') and per-window profile overrides: long-range volume before half time, box chances from 54'. Only scripted shots score. |
| `random1` | `mnb` v `eat` | Unscripted, seed 26. Goals are drawn from each shot's xG; the scoreline detector makes a call here that misses. |
| `even` | `mer` v `mnb` | Unscripted, seed 11, two evenly matched profiles. |

## Events (`data/seeds/<seed>/events.jsonl`)

One JSON object per line, validated by `second_look.contracts.Event`. `null` fields are omitted.

| Field | Type | Notes |
|---|---|---|
| `id` | int | 0-based, in time order |
| `t` | float | seconds since kick-off (second half starts at 2700) |
| `minute`, `period` | int | match minute; 1 or 2 |
| `type` | string | `pass`, `carry`, `shot`, `pressure`, `tackle`, `possession_start`, `possession_end`, `goal`, `period` |
| `team`, `player` | string | team id; player id `p_<team>_<1-11>` (squad order: GK, RB, CB, CB, LB, DM, CM, CM, RW, ST, LW) |
| `sequence_id` | int | groups one possession |
| `x`, `y` | float | metres, see coordinates |
| `end_x`, `end_y` | float | pass and carry destinations (always present for those types) |
| `outcome` | string | `complete`/`incomplete` (pass, carry), `saved`/`off_target`/`blocked`/`goal` (shot), `won` (tackle) |
| `xg` | float | shots only, 0.01–0.95 |

**Coordinates.** Pitch 105 × 68 m. Every event is in its own team's frame: attacking left to right, goal at x = 105, y = 34. A box entry is a pass or carry ending at x ≥ 88.5 with 13.84 ≤ y ≤ 54.16.

**xG.** `logistic(0.4 − 0.17 × distance_m + 1.2 × goal_angle_rad)`, clamped to 0.01–0.95, where `goal_angle_rad` is the angle the 7.32 m goal mouth subtends from the shot. A central shot from 11 m is about 0.33, from 18 m about 0.10, from 27 m about 0.02.

**Possession.** A sequence runs from `possession_start` to `possession_end` for one team; possession share is the sum of sequence durations.

## Profiles (`profiles/teams.toml`)

20 fictional regional teams. Values are hand-set qualitative approximations of playing styles; squads are generated fictional names.

| Field | Meaning |
|---|---|
| `name`, `short`, `colors` | display name, 3-letter code, [primary, secondary] hex |
| `possession_bias` | relative weight of starting a sequence |
| `pass_completion` | chance a short pass completes (long passes: −0.25) |
| `long_ball_pct` | share of passes that are long (22–38 m) |
| `shot_rate` | chance a sequence entering the final third ends in a shot |
| `shot_distance_mean_m`, `shot_distance_sd_m` | shot distance distribution |
| `pressures_per_5min` | pressing intensity against the opponent's sequences |
