"""
Tool: validate_setup.py
Responsibility: Check that all required setup files exist and have real content (no placeholder values).

Output: Checklist printed to stdout.
Exit code 0 = all files complete. Exit code 1 = missing or incomplete files.

Usage:
    python .claude/skills/setup/scripts/validate_setup.py
"""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[4]

PLACEHOLDER_STRINGS = [
    "YOUR_FULL_NAME",
    "YOUR_EMAIL",
    "YOUR_PHONE",
    "YOUR_LINKEDIN",
    "YOUR_CITY",
    "YOUR_COUNTRY",
    "YOUR_NATIONALITY",
    "YOUR_SUMMARY",
    "COMPANY_NAME_HERE",
    "ROLE_TITLE_HERE",
    "YOUR_DEGREE",
    "YOUR_INSTITUTION",
    "Fill in your",
    "Replace with",
    "Add your",
    "[CANDIDATE_NAME]",
    "## How to generate this file",
]

TEMPLATE_MARKER = "How to generate this file"


def check_profile():
    path = PROJECT_ROOT / "profile.json"
    if not path.exists():
        return "MISSING", "profile.json not found — run /setup profile"

    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        profile = json.loads(content)
    except Exception as e:
        return "ERROR", f"profile.json is invalid JSON: {e}"

    # Check for placeholder values
    for placeholder in PLACEHOLDER_STRINGS:
        if placeholder in content:
            return "PLACEHOLDER", f"profile.json still has placeholder: '{placeholder}'"

    # Check essential fields
    if not profile.get("name"):
        return "INCOMPLETE", "profile.json missing 'name' field"
    if not profile.get("email"):
        return "INCOMPLETE", "profile.json missing 'email' field"
    if not profile.get("experience"):
        return "INCOMPLETE", "profile.json missing 'experience' array"
    if not profile.get("skills"):
        return "INCOMPLETE", "profile.json missing 'skills' array"

    return "COMPLETE", f"profile.json — {profile.get('name')}, {len(profile.get('experience', []))} positions, {len(profile.get('skills', []))} skills"


def check_kb_file(filename, display_name):
    path = PROJECT_ROOT / "assets" / "knowledge_base" / filename
    if not path.exists():
        return "MISSING", f"{display_name} not found — run /setup {filename.replace('.md', '').replace('_', ' ').split()[0]}"

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return "ERROR", f"{display_name} could not be read: {e}"

    if TEMPLATE_MARKER in content:
        return "TEMPLATE", f"{display_name} still has template instructions — run /setup to fill it in"

    for placeholder in PLACEHOLDER_STRINGS:
        if placeholder in content:
            return "PLACEHOLDER", f"{display_name} still has placeholder: '{placeholder}'"

    if len(content.strip()) < 200:
        return "INCOMPLETE", f"{display_name} seems too short ({len(content.strip())} chars) — may be incomplete"

    word_count = len(content.split())
    return "COMPLETE", f"{display_name} — {word_count} words"


def check_cv_template():
    en_path = PROJECT_ROOT / "assets" / "cv" / "cv_base_en.docx"
    es_path = PROJECT_ROOT / "assets" / "cv" / "cv_base_es.docx"

    if not en_path.exists():
        return "MISSING", "cv_base_en.docx not found in assets/cv/ — add your base English CV"
    return "COMPLETE", f"cv_base_en.docx found{' (cv_base_es.docx also present)' if es_path.exists() else ' (cv_base_es.docx not found — only needed for Spanish CVs)'}"


def check_env():
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return "MISSING", ".env not found — copy .env.example to .env and fill in ANTHROPIC_API_KEY"

    content = env_path.read_text(encoding="utf-8")
    if "sk-ant-..." in content or "ANTHROPIC_API_KEY=" not in content:
        return "INCOMPLETE", ".env found but ANTHROPIC_API_KEY not set"

    return "COMPLETE", ".env found with API key"


def main():
    checks = [
        ("profile.json", check_profile()),
        ("writing_voice.md", check_kb_file("writing_voice.md", "writing_voice.md")),
        ("self_framing.md", check_kb_file("self_framing.md", "self_framing.md")),
        ("project_depth.md", check_kb_file("project_depth.md", "project_depth.md")),
        ("cv_base_en.docx", check_cv_template()),
        (".env", check_env()),
    ]

    status_icons = {
        "COMPLETE": "✓",
        "MISSING": "✗",
        "PLACEHOLDER": "⚠",
        "TEMPLATE": "⚠",
        "INCOMPLETE": "⚠",
        "ERROR": "✗",
    }

    print("\nSetup validation")
    print("=" * 60)

    all_complete = True
    for name, (status, message) in checks:
        icon = status_icons.get(status, "?")
        print(f"  {icon} [{status:12s}] {message}")
        if status != "COMPLETE":
            all_complete = False

    print("=" * 60)

    if all_complete:
        print("\n✓ All files complete. You're ready to use the pipeline!")
        print("  Try: /apply [job_url] or drop .txt files in jobs_inbox/ and run /apply-all")
        sys.exit(0)
    else:
        print("\n⚠ Some files are missing or incomplete.")
        print("  Run /setup all to complete the setup interactively.")
        sys.exit(1)


if __name__ == "__main__":
    main()
