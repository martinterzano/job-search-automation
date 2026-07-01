"""
Tool: extract_skills.py
Responsabilidad: Extraer y clasificar skills de una oferta parseada.
Clasificación: Must (requerido) / Should (deseable) / Nice (diferenciador)
Input: dict de oferta parseada o path a JSON
Output: dict con skills clasificados + role_type + recommended_thresholds
"""

import json
import re
import sys
from pathlib import Path


# Taxonomía de skills para Data Science / ML / AI Engineering
SKILLS_TAXONOMY = {
    "languages": ["python", "r", "sql", "scala", "julia", "java", "c++", "go"],
    "ml_frameworks": [
        "scikit-learn", "sklearn", "tensorflow", "keras", "pytorch", "xgboost",
        "lightgbm", "catboost", "hugging face", "huggingface", "transformers",
        "spacy", "nltk",
    ],
    "llm_ai": [
        "llm", "llms", "large language model", "large language models",
        "gpt", "openai", "chatgpt",
        "anthropic", "anthropic api", "claude api",
        "gemini", "gemini api",
        "llm api", "llm apis",
        "prompt engineering",
        "rag", "retrieval augmented generation", "retrieval-augmented generation",
        "vector database", "vector db", "vector store",
        "embeddings",
        "langchain", "llamaindex", "llama index",
        "agentic", "ai agents", "autonomous agents", "agentic workflows", "agentic systems",
        "fine-tuning", "fine tuning",
        "llmops",
        "generative ai", "gen ai",
    ],
    "api_dev": [
        "fastapi", "flask", "rest api", "restful api", "api development", "api design",
    ],
    "data_tools": [
        "pandas", "numpy", "polars", "dask", "spark", "pyspark", "airflow",
        "dbt", "great expectations", "mlflow", "wandb", "prefect", "luigi",
    ],
    "databases": [
        "postgresql", "postgres", "mysql", "mongodb", "redis", "bigquery",
        "snowflake", "redshift", "databricks", "elasticsearch", "cassandra",
    ],
    "cloud": [
        "aws", "gcp", "azure", "s3", "ec2", "lambda", "sagemaker",
        "vertex ai", "azure ml", "cloud run", "cloud composer", "kubernetes", "docker",
    ],
    "visualization": [
        "tableau", "power bi", "looker", "metabase", "matplotlib", "seaborn",
        "plotly", "streamlit", "dash",
    ],
    "practices": [
        "machine learning", "deep learning", "nlp", "computer vision", "mlops",
        "data engineering", "feature engineering", "a/b testing", "statistics",
        "hypothesis testing", "time series", "forecasting", "eda", "etl", "elt",
    ],
    "soft_skills": [
        "comunicación", "communication", "liderazgo", "leadership", "trabajo en equipo",
        "teamwork", "autonomía", "autonomy", "resolución de problemas", "problem solving",
    ],
}

# Umbrales diferenciados por tipo de rol (apply/conditional/skip)
ROLE_TYPE_THRESHOLDS = {
    "ai_engineer":    {"apply": 60, "conditional": 45},   # LLM skills pueden eludir extracción
    "ml_engineer":    {"apply": 63, "conditional": 48},
    "analytics":      {"apply": 70, "conditional": 55},   # higher bar: pure BI roles require specific dashboard focus
    "data_scientist": {"apply": 65, "conditional": 50},
    "default":        {"apply": 65, "conditional": 50},
}

ROLE_TYPE_KEYWORDS = {
    "ai_engineer": [
        "ai engineer", "ai/ml engineer", "llm engineer", "generative ai engineer",
        "ml platform engineer", "ai infrastructure", "ml infrastructure",
        "applied scientist", "applied ai",
    ],
    "ml_engineer": [
        "ml engineer", "machine learning engineer", "mlops engineer",
        "data engineer", "analytics engineer",
    ],
    "analytics": [
        "data analyst", "bi analyst", "business intelligence analyst",
        "reporting analyst", "analytics manager",
    ],
}

# Indicadores de obligatoriedad
MUST_INDICATORS = [
    "requerido", "required", "obligatorio", "mandatory", "imprescindible",
    "indispensable", "must have", "must-have", "excluyente", "es necesario",
    "es un requisito", "you must", "you will need",
]

SHOULD_INDICATORS = [
    "deseable", "deseable pero no excluyente", "preferible", "preferred",
    "nice to have", "nice-to-have", "plus", "se valorará", "valoramos",
    "idealmente", "ideally", "would be a plus", "beneficial",
    "stand out", "what will make you stand out",
]


def detect_role_type(role: str) -> str:
    """Detecta el tipo de rol basándose en el título para aplicar umbrales diferenciados."""
    role_lower = role.lower()
    for role_type, keywords in ROLE_TYPE_KEYWORDS.items():
        if any(kw in role_lower for kw in keywords):
            return role_type
    return "data_scientist"


def extract_skills(parsed_job: dict) -> dict:
    """
    Extrae y clasifica los skills de una oferta parseada.

    Args:
        parsed_job: dict con la oferta estructurada

    Returns:
        dict con skills clasificados en must/should/nice + role_type + recommended_thresholds
    """
    text = parsed_job.get("raw_text", "") + " " + parsed_job.get("description", "")
    text_lower = text.lower()

    role = parsed_job.get("role", "UNKNOWN")
    role_type = detect_role_type(role)
    recommended_thresholds = ROLE_TYPE_THRESHOLDS.get(role_type, ROLE_TYPE_THRESHOLDS["default"])

    all_found_skills = _find_all_skills(text_lower)
    classified = _classify_skills(text_lower, all_found_skills)

    result = {
        "company": parsed_job.get("company", "UNKNOWN"),
        "role": role,
        "role_type": role_type,
        "recommended_thresholds": recommended_thresholds,
        "skills": classified,
        "skills_flat": {
            "must": classified["must"],
            "should": classified["should"],
            "nice": classified["nice"],
            "all": list(set(classified["must"] + classified["should"] + classified["nice"])),
        },
        "total_skills_found": len(set(classified["must"] + classified["should"] + classified["nice"])),
    }

    return result


def _find_all_skills(text_lower: str) -> list[str]:
    """Detecta todos los skills mencionados en el texto."""
    found = []
    for category, skills in SKILLS_TAXONOMY.items():
        for skill in skills:
            if re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
                found.append(skill)
    return list(set(found))


def _classify_skills(text_lower: str, all_skills: list[str]) -> dict:
    """
    Clasifica los skills encontrados en Must/Should/Nice
    basándose en el contexto donde aparecen.
    """
    must = []
    should = []
    nice = []

    lines = text_lower.split("\n")

    for skill in all_skills:
        classification = _classify_single_skill(skill, lines, text_lower)
        if classification == "must":
            must.append(skill)
        elif classification == "should":
            should.append(skill)
        else:
            nice.append(skill)

    return {"must": sorted(must), "should": sorted(should), "nice": sorted(nice)}


def _classify_single_skill(skill: str, lines: list[str], full_text: str) -> str:
    """Determina si un skill es Must, Should o Nice según su contexto."""
    skill_pattern = r"\b" + re.escape(skill) + r"\b"

    for line in lines:
        if re.search(skill_pattern, line):
            # Verificar si la línea tiene indicadores de obligatoriedad
            for indicator in MUST_INDICATORS:
                if indicator in line:
                    return "must"
            for indicator in SHOULD_INDICATORS:
                if indicator in line:
                    return "should"

    # Heurística: si aparece en la primera mitad del texto → probably must
    # NOTA: revisar manualmente el output — puede clasificar como must skills
    # mencionadas en la descripción de empresa (primer párrafo) que no son requisitos.
    first_half = full_text[: len(full_text) // 2]
    if re.search(skill_pattern, first_half):
        return "must"

    return "nice"


def load_from_file(json_path: str) -> dict:
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {json_path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python extract_skills.py <ruta_al_parsed_job.json>")
        sys.exit(1)

    parsed = load_from_file(sys.argv[1])
    result = extract_skills(parsed)
    print(json.dumps(result, ensure_ascii=True, indent=2))
