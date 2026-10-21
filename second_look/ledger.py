"""Open predictions, resolved by goals or by their deadline."""

from __future__ import annotations

from dataclasses import dataclass, field

from second_look.contracts import FULL_TIME_MINUTE, PREDICTION_HORIZON_MIN, Prediction


@dataclass
class Ledger:
    open: dict[str, Prediction] = field(default_factory=dict)  # team -> its one open prediction

    def has_open(self, team: str) -> bool:
        return team in self.open

    def make(self, team: str, minute: int, claim_text: str) -> Prediction:
        """Open a goal prediction for `team`. One open prediction per team."""
        if self.has_open(team):
            raise ValueError(f"{team} already has an open prediction")
        prediction = Prediction(
            id=f"pr_{team}_{minute}", team=team, made_at_minute=minute,
            by_minute=min(minute + PREDICTION_HORIZON_MIN, FULL_TIME_MINUTE), claim_text=claim_text,
        )
        self.open[team] = prediction
        return prediction

    def goal(self, team: str, minute: int) -> Prediction | None:
        """A goal by `team` fulfils its open prediction if the deadline hasn't passed."""
        p = self.open.get(team)
        if p is None or minute > p.by_minute:
            return None
        del self.open[team]
        return p.model_copy(update={"status": "fulfilled"})

    def expire(self, minute: int, full_time: bool = False) -> list[Prediction]:
        """Close predictions whose deadline is before `minute`, or all of them at full time."""
        gone = [p for p in self.open.values() if full_time or p.by_minute < minute]
        for p in gone:
            del self.open[p.team]
        return [p.model_copy(update={"status": "expired"}) for p in gone]
