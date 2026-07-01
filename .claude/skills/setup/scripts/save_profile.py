"""
Tool: save_profile.py
Responsibility: Save a profile JSON (collected by Claude in session) as profile.json at the project root.

Input:  JSON file path OR JSON piped via stdin
Output: profile.json written to project root

Usage:
    python .claude/skills/setup/scripts/save_profile.py <profile_draft.json>
    cat profile_data.json | python .claude/skills/setup/scripts/save_profile.py -
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[4]
OUTPUT_PATH = PROJECT_ROOT / "profile.json"

REQUIRED_FIELDS = ["name", "email", "experience", "skills", "projects", "education"]


def validate_profile(profile: dict) -> list[str]:
    """Return list of missing required fields."""
    missing = []
    for field in REQUIRED_FIELDS:
        if field not in profile or not profile[field]:
            missing.append(field)
    return missing


def main():
    if len(sys.argv) < 2:
        print("Usage: python save_profile.py <profile_draft.json>")
        print("       python save_profile.py -   (read from stdin)")
        sys.exit(1)

    source = sys.argv[1]

    try:
        if source == "-":
            raw = sys.stdin.read()
        else:
            path = Path(source)
            if not path.exists():
                print(f"Error: File not found: {path}")
                sys.exit(1)
            with open(path, encoding="utf-8") as f:
                raw = f.read()

        profile = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)

    missing = validate_profile(profile)
    if missing:
        print(f"Warning: Profile is missing fields: {', '.join(missing)}")
        print("Saving anyway — run /setup validate to check completeness.")

    # Backup existing profile if it exists
    if OUTPUT_PATH.exists():
        backup_path = PROJECT_ROOT / "profile.backup.json"
        OUTPUT_PATH.rename(backup_path)
        print(f"[save_profile] Existing profile backed up to: {backup_path}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    print(f"[save_profile] profile.json saved to: {OUTPUT_PATH}")
    print(f"  Name: {profile.get('name', 'N/A')}")
    print(f"  Experience entries: {len(profile.get('experience', []))}")
    print(f"  Skills: {len(profile.get('skills', []))}")
    print(f"  Projects: {len(profile.get('projects', []))}")


if __name__ == "__main__":
    main()
