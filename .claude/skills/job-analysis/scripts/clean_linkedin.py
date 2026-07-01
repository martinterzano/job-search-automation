"""
Tool: clean_linkedin.py
Responsabilidad: Limpiar el boilerplate de los archivos exportados de LinkedIn
y reestructurarlos con los campos "Empresa:" y "Posición:" que parse_job_posting.py
puede extraer correctamente.

Input:  archivo .txt exportado de LinkedIn (jobs_inbox/)
Output: archivo .txt limpio en .tmp/ listo para parse_job_posting.py

Uso:
    python clean_linkedin.py <input_file> <output_file>
    python clean_linkedin.py "jobs_inbox/Logotipo de Empresa.txt" ".tmp/Empresa_clean.txt"
"""

import re
import sys
from pathlib import Path

# ── Líneas boilerplate a eliminar ────────────────────────────────────────────
SKIP_PATTERNS = [
    r"^Logotipo de ",
    r"^Compartir$",
    r"^Mostrar más opciones$",
    r"^Solicitud sencilla$",
    r"^Guardar$",
    r"^Guardar «",
    r"^Se ha guardado «",
    r"^Guardado$",
    r"^Mostrar todo$",
    r"^Enviar mensaje$",
    r"^Mira una comparación",
    r"^Accede a información exclusiva",
    r"^Volver a probar Premium",
    r"^Personas con las que puedes hablar",
    r"^Antiguos alumnos de",
    r"^Conoce al equipo de contratación",
    r"^Anunciante del empleo$",
    r"^\d+er$",
    r"^\d+º$",
    r"^Promocionado por técnico",
    r"^Evaluando solicitudes de forma activa",
    r"^Coincide con tus preferencias",
    r"^\d+ de \d+ coincidencias de aptitudes",
    r"^· hace \d+",
    r"^· Publicado de nuevo",
    r"^Seguir$",
    r"^Acerca del empleo$",          # header de sección — el contenido sí se conserva
    r"^Foto de perfil de ",
    r"cuenta con verificación",
]


def is_boilerplate(line: str) -> bool:
    stripped = line.strip()
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, stripped, re.IGNORECASE):
            return True
    return False


def strip_emojis(text: str) -> str:
    """Elimina emojis para evitar errores de encoding en Windows."""
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def extract_company(lines: list[str]) -> str:
    """Extrae el nombre de la empresa desde la primera línea 'Logotipo de X'."""
    for line in lines[:3]:
        stripped = line.strip()
        if stripped.startswith("Logotipo de "):
            return stripped.replace("Logotipo de ", "").strip()
    # Fallback: segunda línea no vacía
    non_empty = [l.strip() for l in lines[:5] if l.strip()]
    return non_empty[1] if len(non_empty) > 1 else non_empty[0] if non_empty else "Unknown"


def extract_title(lines: list[str], company: str) -> str:
    """
    Extrae el título del puesto. En el export de LinkedIn el título
    aparece justo después del bloque inicial:
      Logotipo de X / X / Compartir / Mostrar más opciones / → TÍTULO
    """
    skip_until_options = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "Mostrar más opciones":
            skip_until_options = True
            continue
        if skip_until_options and stripped and stripped != company:
            return stripped
    # Fallback: primera línea que no sea boilerplate ni la empresa
    for line in lines:
        stripped = line.strip()
        if stripped and stripped != company and not is_boilerplate(line):
            return stripped
    return "Data Scientist"


def extract_job_content(lines: list[str]) -> str:
    """
    Extrae el contenido real del aviso: todo lo que está después de
    'Acerca del empleo'. Si no existe ese marcador, filtra el boilerplate
    línea a línea.
    """
    acerca_idx = None
    for i, line in enumerate(lines):
        if "Acerca del empleo" in line.strip():
            acerca_idx = i
            break

    if acerca_idx is not None:
        content_lines = lines[acerca_idx + 1:]
    else:
        content_lines = [l for l in lines if not is_boilerplate(l)]

    # Limpiar líneas vacías consecutivas al inicio/fin
    return "\n".join(content_lines).strip()


def clean_linkedin(input_path: Path, output_path: Path) -> tuple[str, str]:
    """
    Limpia el archivo y escribe el resultado en output_path.
    Retorna (company, title) extraídos.
    """
    raw = input_path.read_text(encoding="utf-8")
    raw = strip_emojis(raw)
    lines = raw.split("\n")

    company = extract_company(lines)
    title = extract_title(lines, company)
    content = extract_job_content(lines)

    # Estructura compatible con los patrones de parse_job_posting.py
    output = (
        f"Empresa: {company}\n"
        f"Posición: {title}\n"
        f"\n"
        f"{content}"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    return company, title


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python clean_linkedin.py <input_file> <output_file>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"ERROR: No se encontró {input_path}")
        sys.exit(1)

    company, title = clean_linkedin(input_path, output_path)
    print(f"[clean_linkedin] {company} / {title}")
    print(f"[clean_linkedin] Guardado en: {output_path}")
