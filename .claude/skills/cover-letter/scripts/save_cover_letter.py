"""
Tool: save_cover_letter.py
Responsabilidad: Guardar el texto de una cover letter (generado por Claude en sesión)
como archivo .docx con formato estándar, saludo y firma.

Input:  JSON con {text, company, role, language, output_dir}
Output: Archivo .docx guardado en output_dir/{company}/{filename}

Uso:
    python save_cover_letter.py <draft.json>

donde draft.json tiene la estructura:
{
    "text": "cuerpo de la cover letter (sin saludo ni firma)",
    "company": "Nombre de la empresa",
    "role": "Nombre del rol",
    "language": "en" | "es",
    "output_dir": "outputs/ready/company_role"
}
"""

import json
import re
import sys
from pathlib import Path


LANGUAGE_NAMES = {
    "en": "inglés",
    "es": "español",
}

GREETINGS = {
    "en": "Dear {company} Hiring Team,",
    "es": "Estimado equipo de {company},",
}

SIGNATURES = {
    "en": "Wishing you a great day,",
    "es": "Que tengas un excelente día,",
}


def save_cover_letter(text: str, company: str, role: str, output_dir: str, language: str = "en") -> Path:
    """
    Guarda la cover letter como archivo .docx (Calibri 11pt, márgenes estándar).

    El saludo formal se agrega SIEMPRE (independientemente del tipo de empresa).
    The signature ("Wishing you a great day, / [Candidate Name]") is always added.

    Args:
        text: Cuerpo de la cover letter (sin saludo ni firma — solo el body).
        company: Nombre de la empresa (para el saludo y el nombre del archivo).
        role: Nombre del rol (para el nombre del archivo).
        output_dir: Directorio raíz de outputs.
        language: "en" o "es" (determina saludo y firma).

    Returns:
        Path del archivo .docx guardado.
    """
    from docx import Document
    from docx.shared import Inches, Pt

    company_clean = re.sub(r"[^\w]", "_", company).lower()
    role_clean = re.sub(r"[^\w]", "_", role).lower()[:30]

    company_dir = Path(output_dir)
    company_dir.mkdir(parents=True, exist_ok=True)

    filename = f"cover_letter_{company_clean}_{role_clean}.docx"
    filepath = company_dir / filename

    doc = Document()

    # Remove default blank paragraph
    for p in doc.paragraphs:
        p._element.getparent().remove(p._element)

    # Set Normal style
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(6)

    # Set page margins (1.25 inch sides, 1 inch top/bottom)
    sec = doc.sections[0]
    sec.top_margin = Inches(1.0)
    sec.bottom_margin = Inches(1.0)
    sec.left_margin = Inches(1.25)
    sec.right_margin = Inches(1.25)

    def _add_para(text_content, space_after=Pt(6)):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = space_after
        r = p.add_run(text_content)
        r.font.name = "Calibri"
        r.font.size = Pt(11)
        return p

    # Greeting — siempre obligatorio
    company_display = company.replace('_', ' ')
    greeting_template = GREETINGS.get(language, GREETINGS["en"])
    _add_para(greeting_template.format(company=company_display), space_after=Pt(12))

    # Body paragraphs
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        for i, line in enumerate(lines):
            if i > 0:
                p.add_run().add_break()
            r = p.add_run(line.strip())
            r.font.name = "Calibri"
            r.font.size = Pt(11)

    # Signature — siempre obligatoria
    # Read candidate name from profile.json at project root
    candidate_name = "Your Name"
    profile_path = Path(__file__).parents[4] / "profile.json"
    if profile_path.exists():
        try:
            with open(profile_path, encoding="utf-8") as pf:
                profile = json.load(pf)
            candidate_name = profile.get("name", candidate_name)
        except Exception:
            pass

    signature_line = SIGNATURES.get(language, SIGNATURES["en"])
    _add_para("", space_after=Pt(6))  # blank line before signature
    _add_para(signature_line, space_after=Pt(0))
    _add_para(candidate_name, space_after=Pt(0))

    doc.save(str(filepath))
    print(f"[save_cover_letter] Guardado en: {filepath}")
    return filepath


def validate_text(text: str) -> None:
    """Valida que el texto cumpla los criterios mínimos."""
    word_count = len(text.split())
    if word_count < 200:
        print(f"[save_cover_letter] ADVERTENCIA: Cover letter muy corta ({word_count} palabras). Mínimo esperado: 250.")
    elif word_count > 400:
        print(f"[save_cover_letter] ADVERTENCIA: Cover letter muy larga ({word_count} palabras). Máximo esperado: 350.")
    else:
        print(f"[save_cover_letter] Word count OK: {word_count} palabras.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python save_cover_letter.py <draft.json>")
        print()
        print("El archivo draft.json debe contener:")
        print('  {"text": "...", "company": "...", "role": "...", "language": "en", "output_dir": "..."}')
        sys.exit(1)

    draft_path = Path(sys.argv[1])
    if not draft_path.exists():
        print(f"Error: No se encontró el archivo {draft_path}")
        sys.exit(1)

    with open(draft_path, encoding="utf-8") as f:
        draft = json.load(f)

    required_fields = ["text", "company", "role", "output_dir"]
    missing = [f for f in required_fields if f not in draft]
    if missing:
        print(f"Error: Faltan campos en el JSON: {missing}")
        sys.exit(1)

    validate_text(draft["text"])

    output_path = save_cover_letter(
        text=draft["text"],
        company=draft["company"],
        role=draft["role"],
        output_dir=draft["output_dir"],
        language=draft.get("language", "en"),
    )

    result = {
        "cover_letter_path": str(output_path),
        "word_count": len(draft["text"].split()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
