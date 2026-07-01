"""
Tool: inject_posting_metadata.py
Parchea un analysis.json existente con metadatos de competencia extraídos
del archivo .txt raw de LinkedIn.

Uso (backfill de ofertas ya procesadas):
    python inject_posting_metadata.py outputs/applied/Empresa_Rol/analysis.json jobs_inbox/Done/Empresa.txt

La lógica de extracción vive en parse_job_posting.py.
Este script se usa exclusivamente para el backfill — en el flujo normal
los metadatos ya entran en parse_job_posting.py y fluyen a analysis.json.
"""

import json
import sys
from pathlib import Path

# Importar la lógica centralizada desde parse_job_posting
sys.path.insert(0, str(Path(__file__).parents[4] / ".claude" / "skills" / "job-analysis" / "scripts"))
from parse_job_posting import extract_posting_metadata


def inject(analysis_path: str, txt_path: str) -> None:
    analysis_file = Path(analysis_path)
    txt_file      = Path(txt_path)

    if not analysis_file.exists():
        print(f"[inject_posting_metadata] ERROR: no existe {analysis_path}", flush=True)
        sys.exit(1)

    raw_text = ""
    if txt_file.exists():
        raw_text = txt_file.read_text(encoding="utf-8", errors="replace")
    else:
        print(f"[inject_posting_metadata] WARN: .txt no encontrado ({txt_path}), campos quedarán null", flush=True)

    meta = extract_posting_metadata(raw_text, source_path=str(txt_file) if txt_file.exists() else None)

    with open(analysis_file, encoding="utf-8") as f:
        analysis = json.load(f)

    analysis["batch_date"]       = meta["batch_date"]
    analysis["days_posted"]      = meta["days_posted"]
    analysis["days_posted_raw"]  = meta["days_posted_raw"]
    analysis["applicants_count"] = meta["applicants_count"]
    analysis["applicants_label"] = meta["applicants_label"]

    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    print(
        f"[inject_posting_metadata] {analysis_file.parent.name} — "
        f"batch={meta['batch_date']} | "
        f"days_posted={meta['days_posted_raw'] or 'n/a'} | "
        f"applicants={meta['applicants_label'] or 'n/a'}",
        flush=True
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python inject_posting_metadata.py <analysis.json> <raw.txt>")
        sys.exit(1)

    inject(sys.argv[1], sys.argv[2])
