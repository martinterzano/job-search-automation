"""
fix_projects_batch.py
Removes professional projects from cv_*.json files and sets correct Personal Projects entry.
Regenerates .docx for each fixed file.
Usage: python fix_projects_batch.py
"""

import json
import glob
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[4]
SCRIPT = Path(__file__).parent / "generate_cv_docx.py"

PROFESSIONAL_KW = [
    "pltv", "lapse", "delve", "balun", "balún", "credigo", "turnover",
    "esade", "capstone", "policyholders", "asegurador", "churn prediction",
    "credit scoring", "customer segmentation", "valor de vida", "lifetime value",
    "cancelaci", "predictive lifetime", "early lapse", "employee turnover",
    "predicción de rotaci", "rotación de empleados", "pro bono",
    "segmentación", "churn (bal",
]

# Folder name substrings that indicate an AI/ML engineering role
HIGH_RELEVANCE_SUBSTRINGS = [
    "aily_labs", "albatrossai", "alira_health", "crossing_hurdles",
    "frekuent", "hk_smart_tech", "joveo", "oliver_bernard",
    "product_madness", "zoolatech",
]

JSA_EN_DETAILED = {
    "name": "Job Search Automation Pipeline",
    "year": "2025–2026",
    "context": "Personal Project",
    "bullets": [
        "Designed and built a multi-agent orchestration system using Claude Code and the Anthropic Python SDK: an Orchestrator coordinates specialized agents (Analyzer, CV Adapter, Cover Letter Writer, Critic/QA), each with defined tool schemas, inputs, and outputs.",
        "Implemented semantic fit scoring (Must/Should/Nice weighted algorithm), JSON-based document templating with dynamic field injection, and HITL approval gates before each pipeline stage.",
        "Integrated Google Drive API for application tracking and a Chart.js analytics dashboard; batch mode processes full job posting queue end-to-end with error recovery.",
    ],
}

JSA_EN_COMPACT = {
    "name": "Job Search Automation Pipeline",
    "year": "2025–2026",
    "context": "Personal Project",
    "description": "Built a multi-agent automation system using Claude Code and the Anthropic Python SDK to process job applications end-to-end: parsing postings, scoring fit (Must/Should/Nice), adapting CV, and generating cover letters, with HITL review gates and Google Sheets tracking.",
}

JSA_ES_DETAILED = {
    "name": "Pipeline de Automatización de Búsqueda de Empleo",
    "year": "2025–2026",
    "context": "Proyecto Personal",
    "bullets": [
        "Diseñé y construí un sistema de orquestación multi-agente con Claude Code y el SDK de Python de Anthropic; un Orquestador coordina agentes especializados, cada uno con schemas de herramientas, inputs y outputs definidos.",
        "Implementé scoring semántico de fit (algoritmo ponderado Must/Should/Nice), generación dinámica de documentos desde templates JSON y puertas de aprobación HITL antes de cada etapa.",
        "Integré la API de Google Drive para tracking de postulaciones y un dashboard analítico con Chart.js; modo batch procesa la cola completa de ofertas de forma autónoma.",
    ],
}

JSA_ES_COMPACT = {
    "name": "Pipeline de Automatización de Búsqueda de Empleo",
    "year": "2025–2026",
    "context": "Proyecto Personal",
    "description": "Construí un sistema multi-agente con Claude Code y el SDK de Anthropic para automatizar el proceso completo de postulaciones: parseo de ofertas, scoring de fit (Must/Should/Nice), adaptación de CV y generación de cover letters, con revisión HITL y tracking en Google Sheets.",
}


def is_professional(project: dict) -> bool:
    text = " ".join([
        project.get("name", ""),
        project.get("description", ""),
        project.get("context", ""),
        " ".join(project.get("bullets", [])),
    ]).lower()
    return any(kw in text for kw in PROFESSIONAL_KW)


def is_jsa(project: dict) -> bool:
    name = project.get("name", "").lower()
    return "job search" in name or "automatizaci" in name or "búsqueda" in name


def get_relevance(folder: str) -> str:
    folder_lower = folder.lower()
    if any(kw in folder_lower for kw in HIGH_RELEVANCE_SUBSTRINGS):
        return "high"
    return "standard"


def main():
    pattern_ready   = str(ROOT / "outputs" / "ready"   / "*" / "cv_*.json")
    pattern_applied = str(ROOT / "outputs" / "applied"  / "*" / "cv_*.json")
    all_files = sorted(glob.glob(pattern_ready) + glob.glob(pattern_applied))

    processed, skipped, errors = [], [], []

    for f in all_files:
        f_path = Path(f)
        folder = f_path.parent.name

        with open(f_path, encoding="utf-8") as fp:
            data = json.load(fp)

        projects = data.get("projects", [])
        has_problem = any(is_professional(p) for p in projects)

        if not has_problem:
            skipped.append(folder)
            continue

        language  = data.get("language", "en")
        relevance = get_relevance(folder)

        if language == "es":
            jsa = JSA_ES_DETAILED if relevance == "high" else JSA_ES_COMPACT
        else:
            jsa = JSA_EN_DETAILED if relevance == "high" else JSA_EN_COMPACT

        data["projects"] = [jsa]

        with open(f_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

        output_dir = str(f_path.parent)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(f_path), output_dir],
            capture_output=True, text=True,
        )

        tag = f"[{relevance}/{language}] {folder}"
        if result.returncode != 0:
            errors.append(f"{tag}: {result.stderr.strip()[:200]}")
        else:
            processed.append(tag)

    print(f"\n=== Corregidos: {len(processed)} ===")
    for p in processed:
        print(f"  OK  {p}")

    print(f"\n=== Sin cambios: {len(skipped)} ===")
    for s in skipped:
        print(f"  --  {s}")

    if errors:
        print(f"\n=== Errores: {len(errors)} ===")
        for e in errors:
            print(f"  ERR {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
