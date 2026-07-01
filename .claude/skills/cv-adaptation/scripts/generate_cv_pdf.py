"""
Tool: generate_cv_pdf.py
Responsabilidad: Convierte el .docx del CV adaptado a PDF usando Microsoft Word via PowerShell.
El PDF resultante tiene exactamente el mismo formato que el .docx.

Input:  cv_{company}_{role}.json  (localiza el .docx correspondiente)
Output: CV_{company}_{CandidateLastName}.pdf  (in the same output_dir)

Uso: python generate_cv_pdf.py <cv_adapted.json> [output_dir]
"""

import json
import re
import subprocess
import sys
from pathlib import Path


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def generate_cv_pdf(json_path: str, output_dir: str = "outputs") -> Path:
    cv_adapted = load_json(json_path)
    company = cv_adapted.get("company", "Unknown")
    role    = cv_adapted.get("role", "Unknown")

    company_clean = re.sub(r"[^\w]", "_", company)
    role_clean    = re.sub(r"[^\w]", "_", role)[:30]

    # Read candidate last name from profile.json for PDF filename
    candidate_last = "Candidate"
    profile_path = Path(__file__).parents[4] / "profile.json"
    if profile_path.exists():
        try:
            with open(profile_path, encoding="utf-8") as pf:
                profile = json.load(pf)
            full_name = profile.get("name", "")
            if full_name:
                candidate_last = full_name.split()[-1]
        except Exception:
            pass

    docx_path = Path(output_dir) / f"cv_{company_clean}_{role_clean}.docx"
    pdf_path  = Path(output_dir) / f"CV_{company_clean}_{candidate_last}.pdf"

    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX no encontrado: {docx_path}")

    docx_abs = str(docx_path.resolve())
    pdf_abs  = str(pdf_path.resolve())

    ps_script = f"""
$word = New-Object -ComObject Word.Application
$word.Visible = $true
$word.DisplayAlerts = 0
Start-Sleep -Milliseconds 500
$doc = $word.Documents.Open('{docx_abs}', [ref]$false, [ref]$false)
Start-Sleep -Milliseconds 500
$doc.SaveAs([ref]'{pdf_abs}', [ref]17)
$doc.Close([ref]$false)
$word.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
"""

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(
            f"PowerShell PDF export falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    print(f"[generate_cv_pdf] PDF generado: {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python generate_cv_pdf.py <cv_adapted.json> [output_dir]")
        print("Ejemplo: python generate_cv_pdf.py outputs/Booksy/cv_Booksy_Senior_Data_Scientist.json outputs/Booksy/")
        sys.exit(1)

    json_path  = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "outputs"

    result_path = generate_cv_pdf(json_path, output_dir)
    print(f"[generate_cv_pdf] Completado: {result_path}")
