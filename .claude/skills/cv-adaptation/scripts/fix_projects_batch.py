"""
fix_projects_batch.py
Utility: scan all cv_*.json files in outputs/ and remove professional work projects
that were incorrectly placed in the Personal Projects section. Replaces them with
the correct personal project entry from profile.json.

Usage: python fix_projects_batch.py [--dry-run]

HOW TO CUSTOMIZE:
  1. Update PROFESSIONAL_KW with keywords from your professional project names/descriptions.
     These are used to detect projects that belong in the Experience section, not Projects.
  2. Run with --dry-run first to see what would change.
  3. The script reads your personal projects from profile.json automatically.
"""

import json
import glob
import sys
from pathlib import Path

ROOT   = Path(__file__).parents[4]
SCRIPT = Path(__file__).parent / "generate_cv_docx.py"


def load_profile() -> dict:
    profile_path = ROOT / "profile.json"
    if not profile_path.exists():
        raise FileNotFoundError("profile.json not found — run /setup profile first")
    with open(profile_path, encoding="utf-8") as f:
        return json.load(f)


def get_personal_projects(profile: dict) -> list[dict]:
    """Return projects marked as personal (context != work/professional)."""
    personal = []
    for p in profile.get("projects", []):
        ctx = p.get("context", "").lower()
        if "personal" in ctx or "side" in ctx or "open source" in ctx:
            personal.append(p)
    return personal


def build_professional_keywords(profile: dict) -> list[str]:
    """
    Auto-build keyword list from professional projects in profile.json.
    Extend EXTRA_KW manually with any additional terms you want to catch.
    """
    EXTRA_KW: list[str] = []  # add your own keywords here if needed

    keywords = list(EXTRA_KW)
    for p in profile.get("projects", []):
        ctx = p.get("context", "").lower()
        if "personal" not in ctx and "side" not in ctx:
            name = p.get("name", "").lower()
            if name:
                keywords.append(name[:20])
    employer = profile.get("experience", [{}])[0].get("company", "").lower()
    if employer:
        keywords.append(employer[:20])
    return list(set(kw for kw in keywords if len(kw) > 3))


def is_professional(project: dict, keywords: list[str]) -> bool:
    text = " ".join([
        project.get("name", ""),
        project.get("description", ""),
        project.get("context", ""),
        " ".join(project.get("bullets", [])),
    ]).lower()
    return any(kw in text for kw in keywords)


def main():
    dry_run = "--dry-run" in sys.argv

    profile    = load_profile()
    keywords   = build_professional_keywords(profile)
    personal   = get_personal_projects(profile)

    if not personal:
        print("No personal projects found in profile.json. Nothing to do.")
        sys.exit(0)

    pattern_ready   = str(ROOT / "outputs" / "ready"   / "*" / "cv_*.json")
    pattern_applied = str(ROOT / "outputs" / "applied"  / "*" / "cv_*.json")
    all_files = sorted(glob.glob(pattern_ready) + glob.glob(pattern_applied))

    processed, skipped, errors = [], [], []

    for f in all_files:
        f_path = Path(f)
        with open(f_path, encoding="utf-8") as fp:
            data = json.load(fp)

        projects = data.get("projects", [])
        has_problem = any(is_professional(p, keywords) for p in projects)

        if not has_problem:
            skipped.append(f_path.parent.name)
            continue

        if dry_run:
            print(f"[DRY RUN] Would fix: {f_path.parent.name}")
            processed.append(f_path.parent.name)
            continue

        data["projects"] = personal

        with open(f_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

        import subprocess
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(f_path), str(f_path.parent)],
            capture_output=True, text=True,
        )

        tag = f_path.parent.name
        if result.returncode != 0:
            errors.append(f"{tag}: {result.stderr.strip()[:200]}")
        else:
            processed.append(tag)

    suffix = " (dry run)" if dry_run else ""
    print(f"\n=== Fixed{suffix}: {len(processed)} ===")
    for p in processed:
        print(f"  OK  {p}")

    print(f"\n=== No changes: {len(skipped)} ===")

    if errors:
        print(f"\n=== Errors: {len(errors)} ===")
        for e in errors:
            print(f"  ERR {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
