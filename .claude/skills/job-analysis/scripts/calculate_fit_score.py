"""
Tool: calculate_fit_score.py
Responsabilidad: Calcular el fit score mecánico entre el perfil del candidato y los skills de la oferta.
Input: skills extraídos de la oferta + perfil del candidato (profile.json)
Output: score mecánico 0-100, gaps identificados, recomendación provisional.
        Claude ajusta el score ±20 pts en Paso 4 del SKILL.md para producir el fit_score final.
"""

import json
import sys
from pathlib import Path


# Pesos para el cálculo del score
WEIGHTS = {
    "must": 0.65,    # 65% del score depende de los skills Must
    "should": 0.25,  # 25% de los skills Should
    "nice": 0.10,    # 10% de los skills Nice
}

# Umbrales diferenciados por tipo de rol
# Deben mantenerse sincronizados con ROLE_TYPE_THRESHOLDS en extract_skills.py
ROLE_TYPE_THRESHOLDS = {
    "ai_engineer":    {"apply": 60, "conditional": 45},
    "ml_engineer":    {"apply": 63, "conditional": 48},
    "analytics":      {"apply": 70, "conditional": 55},
    "data_scientist": {"apply": 65, "conditional": 50},
    "default":        {"apply": 65, "conditional": 50},
}

# Equivalencias semánticas conservadoras para matching
# Grupos de términos tratados como idénticos en la comparación.
# Solo alias inequívocos o relaciones técnicas directas (ej. Cloud Composer IS managed Airflow).
SKILL_EQUIVALENCES = [
    frozenset({"gcp", "google cloud", "google cloud platform"}),
    frozenset({"sklearn", "scikit-learn"}),
    frozenset({"postgres", "postgresql"}),
    frozenset({"hugging face", "huggingface"}),
    frozenset({"airflow", "apache airflow", "cloud composer"}),  # Cloud Composer es Airflow gestionado en GCP
    frozenset({"vertex ai", "google vertex"}),
    frozenset({"llm", "llms", "large language model", "llm api", "llm apis"}),  # "llm" en JD cubre experiencia con "llm apis"
    frozenset({"rag", "retrieval augmented generation", "retrieval-augmented generation"}),
    frozenset({"embeddings", "vector embeddings"}),
    frozenset({"random forest", "random forests"}),
    frozenset({"anthropic", "anthropic api"}),  # "anthropic" en JD = experiencia con Anthropic API
    frozenset({"agentic", "agentic systems", "agentic workflows", "autonomous agents", "ai agents"}),
    frozenset({"generative ai", "gen ai", "genai"}),
]


def calculate_fit_score(skills_data: dict, profile: dict) -> dict:
    """
    Calcula el fit score entre la oferta y el perfil del candidato.

    Args:
        skills_data: output de extract_skills.py (incluye role_type y recommended_thresholds)
        profile: dict con skills del candidato (profile.json)

    Returns:
        dict con score mecánico, gaps, fortalezas y recomendación provisional
    """
    candidate_skills = _normalize_skills(profile.get("skills", []))

    job_must = skills_data["skills"]["must"]
    job_should = skills_data["skills"]["should"]
    job_nice = skills_data["skills"]["nice"]

    must_match, must_gaps = _compute_match(job_must, candidate_skills)
    should_match, should_gaps = _compute_match(job_should, candidate_skills)
    nice_match, nice_gaps = _compute_match(job_nice, candidate_skills)

    score = _compute_score(
        must_match, len(job_must),
        should_match, len(job_should),
        nice_match, len(job_nice),
    )

    role_type = skills_data.get("role_type", "default")
    recommendation = _get_recommendation(score, role_type)
    strengths = _get_strengths(job_must + job_should, candidate_skills)

    result = {
        "company": skills_data.get("company", "UNKNOWN"),
        "role": skills_data.get("role", "UNKNOWN"),
        "role_type": role_type,
        "fit_score": round(score, 1),  # Score mecánico — Claude lo ajusta ±20 en Paso 4
        "recommendation": recommendation,
        "breakdown": {
            "must": {
                "total": len(job_must),
                "matched": must_match,
                "coverage_pct": _pct(must_match, len(job_must)),
            },
            "should": {
                "total": len(job_should),
                "matched": should_match,
                "coverage_pct": _pct(should_match, len(job_should)),
            },
            "nice": {
                "total": len(job_nice),
                "matched": nice_match,
                "coverage_pct": _pct(nice_match, len(job_nice)),
            },
        },
        "gaps": {
            "must": must_gaps,
            "should": should_gaps,
            "nice": nice_gaps,
        },
        "strengths": strengths,
        "summary": _build_summary(score, must_gaps, should_gaps, recommendation),
    }

    return result


def _normalize_skills(skills: list) -> set:
    """Normaliza los skills a minúsculas para comparación."""
    return {s.lower().strip() for s in skills}


def _skills_match(job_skill: str, candidate_skills: set) -> bool:
    """
    Retorna True si el job_skill matchea algún skill del candidato.
    Considera equivalencias semánticas conservadoras definidas en SKILL_EQUIVALENCES.
    """
    if job_skill in candidate_skills:
        return True
    for equiv_set in SKILL_EQUIVALENCES:
        if job_skill in equiv_set and equiv_set & candidate_skills:
            return True
    return False


def _compute_match(job_skills: list, candidate_skills: set) -> tuple[int, list]:
    """Retorna cuántos skills matchean (incluyendo aliases) y cuáles faltan."""
    matched = 0
    gaps = []
    for skill in job_skills:
        if _skills_match(skill.lower(), candidate_skills):
            matched += 1
        else:
            gaps.append(skill)
    return matched, gaps


def _compute_score(
    must_match: int, must_total: int,
    should_match: int, should_total: int,
    nice_match: int, nice_total: int,
) -> float:
    """Calcula el score ponderado entre 0 y 100.
    Solo pondera las categorías que tienen skills definidos (total > 0).
    Los pesos se redistribuyen proporcionalmente entre las categorías activas.
    """
    components = []
    active_weight = 0.0

    if must_total > 0:
        components.append((must_match / must_total * 100, WEIGHTS["must"]))
        active_weight += WEIGHTS["must"]
    if should_total > 0:
        components.append((should_match / should_total * 100, WEIGHTS["should"]))
        active_weight += WEIGHTS["should"]
    if nice_total > 0:
        components.append((nice_match / nice_total * 100, WEIGHTS["nice"]))
        active_weight += WEIGHTS["nice"]

    if active_weight == 0:
        return 0.0

    return sum(score * (weight / active_weight) for score, weight in components)


def _get_recommendation(score: float, role_type: str = "default") -> str:
    """Determina la recomendación usando umbrales diferenciados por tipo de rol."""
    thresholds = ROLE_TYPE_THRESHOLDS.get(role_type, ROLE_TYPE_THRESHOLDS["default"])
    if score >= thresholds["apply"]:
        return "apply"
    if score >= thresholds["conditional"]:
        return "conditional"
    return "skip"


def _get_strengths(key_skills: list, candidate_skills: set) -> list:
    """Skills clave de la oferta que el candidato posee (incluyendo aliases)."""
    return [s for s in key_skills if _skills_match(s.lower(), candidate_skills)]


def _pct(matched: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(matched / total * 100, 1)


def _build_summary(score: float, must_gaps: list, should_gaps: list, recommendation: str) -> str:
    lines = [f"Fit Score: {round(score, 1)}/100 → {recommendation.upper()}"]
    if must_gaps:
        lines.append(f"Gaps críticos (Must): {', '.join(must_gaps)}")
    if should_gaps:
        lines.append(f"Gaps deseables (Should): {', '.join(should_gaps)}")
    if not must_gaps:
        lines.append("Cubre todos los requisitos Must.")
    return " | ".join(lines)


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python calculate_fit_score.py <skills.json> <profile.json>")
        sys.exit(1)

    skills_data = load_json(sys.argv[1])
    profile = load_json(sys.argv[2])
    result = calculate_fit_score(skills_data, profile)
    print(json.dumps(result, ensure_ascii=True, indent=2))
