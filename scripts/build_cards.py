"""Build overlay cards for a seed into cards/<seed>/normal/.

Usage: uv run python scripts/build_cards.py --seed demo [--force]
Existing cards are kept unless --force (which rebuilds the seed from scratch).
"""

from __future__ import annotations

import argparse
import sys

from second_look.pipeline import CARDS_DIR, template_cards, write_cards
from second_look.sim import SEEDS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", choices=sorted(SEEDS), action="append", help="repeatable; default: every seed")
    ap.add_argument("--force", action="store_true", help="delete the seed's cached cards first")
    args = ap.parse_args()
    for seed in args.seed or sorted(SEEDS):
        cards = template_cards(seed)
        written = write_cards(cards, seed, force=args.force)
        print(f"{seed}: {len(cards)} cards, {written} written to {CARDS_DIR / seed / 'normal'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
