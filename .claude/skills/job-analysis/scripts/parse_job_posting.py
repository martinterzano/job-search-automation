"""
Tool: parse_job_posting.py
Responsabilidad: Parsear texto crudo de una oferta laboral y estructurarlo en JSON.
Incluye extracción de metadatos de competencia (días publicado, aplicantes, batch date).

Input: ruta al archivo .txt de la oferta
Output: dict estructurado con campos normalizados + metadatos de competencia
"""

import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path


# ── Metadata de competencia ──────────────────────────────────────────────────

def extract_posting_metadata(raw_text: str, source_path: str = None) -> dict:
    """
    Extrae metadatos de competencia de un texto raw de LinkedIn.

    Captura:
      - días publicado (desde "hace X días/horas/semanas/meses")
      - conteo y label de aplicantes ("N personas / N solicitudes / Más de N ...")
      - batch_date (mtime del archivo fuente)

    Retorna dict con campos:
      days_posted, days_posted_raw, applicants_count, applicants_label, batch_date
    """
    # ── Días publicado ─────────────────────────────────────────────────────────
    # Cubre: "hace 6 días", "hace 3 horas", "hace 1 hora", "hace 45 minutos",
    #        "hace 4 semanas", "hace 2 meses", "Publicado de nuevo hace X semanas"
    time_match = re.search(
        r'(?:Publicado de nuevo\s+)?hace\s+(\d+)\s+'
        r'(días|día|horas|hora|minutos|minuto|semanas|semana|meses|mes)',
        raw_text, re.IGNORECASE
    )
    days_posted = None
    days_posted_raw = None
    if time_match:
        n    = int(time_match.group(1))
        unit = time_match.group(2).lower()
        if 'hora' in unit or 'minuto' in unit:
            days_posted = 0
        elif 'día' in unit:
            days_posted = n
        elif 'semana' in unit:
            days_posted = n * 7
        elif 'mes' in unit:
            days_posted = n * 30
        days_posted_raw = f"hace {n} {time_match.group(2)}"

    # ── Aplicantes ──────────────────────────────────────────────────────────────
    # Cubre:
    #   "Más de 100 personas han hecho clic en «Solicitar»"
    #   "60 personas han hecho clic en"
    #   "1 persona ha hecho clic en"
    #   "200 solicitudes"
    #   "1 solicitud"
    #   "Más de 200 solicitudes"
    app_match = re.search(
        r'(Más de\s+)?(\d+)\s+(?:personas?\s+ha[sn]?\s+hecho\s+clic\s+en|solicitudes?)',
        raw_text, re.IGNORECASE
    )
    applicants_count = None
    applicants_label = None
    if app_match:
        n = int(app_match.group(2))
        applicants_count = n
        applicants_label = f"Más de {n}" if app_match.group(1) else str(n)

    # ── Batch date (mtime del archivo fuente) ──────────────────────────────────
    batch_date = None
    if source_path:
        try:
            mtime = os.path.getmtime(source_path)
            batch_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
        except OSError:
            pass

    return {
        "days_posted":      days_posted,
        "days_posted_raw":  days_posted_raw,
        "applicants_count": applicants_count,
        "applicants_label": applicants_label,
        "batch_date":       batch_date,
    }


# ── Parseo principal ─────────────────────────────────────────────────────────

def parse_job_posting(raw_text: str, output_dir: str = "jobs_parsed",
                      source_file: str = None) -> dict:
    """
    Parsea el texto de una oferta laboral y extrae campos estructurados.
    Si se provee source_file, también extrae metadatos de competencia del texto raw.

    Args:
        raw_text:    Texto completo de la oferta laboral
        output_dir:  Directorio donde guardar el JSON resultante
        source_file: Path al archivo .txt original (para mtime y extracción pre-clean)

    Returns:
        dict con la oferta estructurada + metadatos de competencia
    """
    meta = extract_posting_metadata(raw_text, source_path=source_file)

    parsed = {
        "date_processed":   str(date.today()),
        "company":          _extract_company(raw_text),
        "role":             _extract_role(raw_text),
        "location":         _extract_location(raw_text),
        "modality":         _extract_modality(raw_text),
        "seniority":        _extract_seniority(raw_text),
        "description":      _extract_description(raw_text),
        "requirements_raw": _extract_requirements(raw_text),
        "raw_text":         raw_text.strip(),
        "language":         _detect_language(raw_text),
        # Metadatos de competencia extraídos del raw text
        "batch_date":       meta["batch_date"],
        "days_posted":      meta["days_posted"],
        "days_posted_raw":  meta["days_posted_raw"],
        "applicants_count": meta["applicants_count"],
        "applicants_label": meta["applicants_label"],
    }

    _save_output(parsed, output_dir)
    return parsed


def _extract_company(text: str) -> str:
    patterns = [
        r"(?:empresa|company|at|en)\s*[:\-]?\s*([A-Z][^\n]{2,50})",
        r"^([A-Z][A-Za-z\s&.,]+)\s*(?:busca|seeks|is hiring)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return "UNKNOWN"


def _extract_role(text: str) -> str:
    patterns = [
        r"(?:posici[oó]n|rol|role|position|puesto|cargo)\s*[:\-]?\s*([^\n]{5,80})",
        r"(?:buscamos|we are looking for|hiring)\s+(?:un|una|a|an)?\s*([^\n]{5,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    for line in text.split("\n"):
        line = line.strip()
        if len(line) > 5:
            return line
    return "UNKNOWN"


def _extract_location(text: str) -> str:
    patterns = [
        r"(?:ubicaci[oó]n|location|lugar|city|ciudad)\s*[:\-]?\s*([^\n]{3,60})",
        r"(?:New York|San Francisco|London|Berlin|Madrid|Barcelona|Remote|Remoto|H[íi]brido|Hybrid)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip() if match.lastindex is None else match.group(1).strip()
    return "No especificada"


def _extract_modality(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["remoto", "remote", "100% remoto", "fully remote"]):
        return "remote"
    if any(w in text_lower for w in ["híbrido", "hybrid"]):
        return "hybrid"
    if any(w in text_lower for w in ["presencial", "on-site", "onsite", "in office"]):
        return "on-site"
    return "no especificada"


def _extract_seniority(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["senior", "sr.", "sr "]):
        return "senior"
    if any(w in text_lower for w in ["semi senior", "semi-senior", "ssr"]):
        return "semi-senior"
    if any(w in text_lower for w in ["junior", "jr.", "jr "]):
        return "junior"
    if any(w in text_lower for w in ["lead", "staff", "principal"]):
        return "lead"
    return "no especificado"


def _extract_description(text: str) -> str:
    return text.strip()[:2000]


def _extract_requirements(text: str) -> list[str]:
    requirements = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if re.match(r"^[-•*✓✔→]\s+.{10,}", line):
            requirements.append(line.lstrip("-•*✓✔→ ").strip())
    return requirements


def _detect_language(text: str) -> str:
    spanish_markers = ["busca", "experiencia", "requisitos", "empresa", "equipo"]
    english_markers = ["looking for", "experience", "requirements", "company", "team"]
    text_lower = text.lower()
    es = sum(1 for w in spanish_markers if w in text_lower)
    en = sum(1 for w in english_markers if w in text_lower)
    return "es" if es >= en else "en"


def _save_output(data: dict, output_dir: str) -> None:
    company  = re.sub(r"[^\w]", "_", data.get("company", "unknown")).lower()
    role     = re.sub(r"[^\w]", "_", data.get("role", "unknown")).lower()[:30]
    date_str = data.get("date_processed", str(date.today()))

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{company}_{role}_{date_str}.json"
    filepath = Path(output_dir) / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)

    print(f"[parse_job_posting] Guardado en: {filepath}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python parse_job_posting.py <ruta_al_archivo_oferta.txt>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: archivo no encontrado: {input_path}")
        sys.exit(1)

    raw = input_path.read_text(encoding="utf-8", errors="replace")
    result = parse_job_posting(raw, source_file=str(input_path))
    print(json.dumps(result, ensure_ascii=True, indent=2))
