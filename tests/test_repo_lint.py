"""No tracked file may contain a term from the gitignored .denylist.local."""

import subprocess
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DENYLIST = ROOT / ".denylist.local"


def _terms() -> list[str]:
    if not DENYLIST.exists():
        return []
    lines = DENYLIST.read_text(encoding="utf-8").splitlines()
    return [t.strip().lower() for t in lines if t.strip() and not t.startswith("#")]


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [ROOT / p for p in out.decode("utf-8").split("\0") if p]


def test_denylist_terms_absent_from_repo():
    terms = _terms()
    if not terms:
        warnings.warn(".denylist.local missing or empty: banned-term check skipped", stacklevel=2)
        return
    hits = []
    for path in _tracked_files():
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if b"\0" in raw[:8000]:
            continue  # binary
        text = raw.decode("utf-8", errors="ignore").lower()
        rel = path.relative_to(ROOT).as_posix()
        hits += [f"{rel}: {t!r}" for t in terms if t in text or t in rel.lower()]
    assert not hits, "banned terms found:\n" + "\n".join(hits)
