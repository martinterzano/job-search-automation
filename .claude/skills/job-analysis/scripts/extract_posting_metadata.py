"""
Tool: extract_posting_metadata.py
CLI wrapper sobre extract_posting_metadata() de parse_job_posting.py.

La lógica de extracción vive en parse_job_posting.py — este script
solo provee una interfaz de línea de comandos standalone.

Uso:
    python extract_posting_metadata.py jobs_inbox/Empresa_Rol.txt
"""

import json
import sys
from pathlib import Path

# Importar desde parse_job_posting (misma carpeta)
sys.path.insert(0, str(Path(__file__).parent))
from parse_job_posting import extract_posting_metadata


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python extract_posting_metadata.py <ruta_al_archivo.txt>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    if not Path(path).exists():
        print(f"ERROR: archivo no encontrado: {path}", file=sys.stderr)
        sys.exit(1)

    raw    = Path(path).read_text(encoding="utf-8", errors="replace")
    result = extract_posting_metadata(raw, source_path=path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
