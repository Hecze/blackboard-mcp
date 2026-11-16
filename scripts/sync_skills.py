"""Copy the canonical skills in skills/ to the folders agent harnesses look in.

skills/<name>/SKILL.md is the source of truth (plain Markdown + YAML frontmatter, readable by any agent).
Some harnesses auto-discover skills only in their own folder, so we mirror them there:
  .claude/skills/  (Claude Code)
Add more targets below if another harness needs its own folder. Run after editing a skill:
  python scripts/sync_skills.py          # copy
  python scripts/sync_skills.py --check  # exit 1 if a mirror is out of date (used by the tests)
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "skills"
TARGETS = [ROOT / ".claude" / "skills"]


def main(check: bool) -> int:
    stale = []
    for skill in sorted(p for p in SOURCE.iterdir() if (p / "SKILL.md").is_file()):
        for target in TARGETS:
            for src in skill.rglob("*"):
                if src.is_dir():
                    continue
                dst = target / skill.name / src.relative_to(skill)
                if dst.exists() and dst.read_bytes() == src.read_bytes():
                    continue
                stale.append(str(dst.relative_to(ROOT)))
                if not check:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
    if check and stale:
        print("Out of date (run python scripts/sync_skills.py):", *stale, sep="\n  ")
        return 1
    print(("Up to date" if check else f"Synced {len(stale)} file(s)"))
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
