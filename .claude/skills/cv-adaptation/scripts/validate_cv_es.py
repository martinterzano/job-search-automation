"""
Tool: validate_cv_es.py
Responsabilidad: Valida y auto-corrige el JSON de un CV adaptado en español (language=es).
Detecta y corrige:
  - Tildes y ñ faltantes (produccion→producción, anos→años, etc.)
  - Verbos en tercera persona del pretérito → primera persona
  - Títulos de cargo en inglés → traducción canónica al español
  - Em dashes en bullets/summary → coma
Input:  <output_dir>/cv_{company}_{role}.json  (debe tener language="es")
Output: JSON corregido en el mismo path + reporte de cambios en stdout
Exit:   0 si todo OK (con o sin auto-fixes), 1 si hay issues no reparables
"""

import json
import io
import re
import sys
from pathlib import Path

# Windows consoles default to cp1252; force UTF-8 so arrows/accents print correctly
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ── TILDE / Ñ FIXES ──────────────────────────────────────────────────────────
# List of (wrong_word_no_accent, correct_form). All lowercase — replacer handles
# leading-capital case. Regex uses \b word boundaries to avoid false positives
# inside longer words (e.g. "produccion" won't accidentally corrupt "produccionista").
# Order: multi-word / longer patterns first to prevent partial matches.

TILDE_WORD_FIXES: list[tuple[str, str]] = [
    # ── Palabras con ñ ────────────────────────────────────────────────────────
    # Note: "anos" in a CV always means "años" (years), never "anos" (anatomy).
    # "campanas" in a CV always means "campañas" (campaigns), never "campanas" (bells).
    ("espana",              "España"),
    ("campanas",            "campañas"),
    ("anos",                "años"),
    ("diseno",              "diseño"),
    ("companias",           "compañías"),
    ("compania",            "compañía"),

    # ── Verbos pretérito 1ª persona que pierden el acento ────────────────────
    # En bullets de CV, el verbo de acción es siempre 1ª persona pretérito.
    # "implemente" sin tilde ≈ "implementé"; riesgo de falso positivo (subjuntivo)
    # es mínimo en este contexto.
    ("construi",            "construí"),
    ("contribui",           "contribuí"),
    ("dirigi",              "dirigí"),
    ("enriqueci",           "enriquecí"),
    ("desarrolle",          "desarrollé"),
    ("implemente",          "implementé"),
    ("limpie",              "limpié"),
    ("integre",             "integré"),
    ("lidere",              "lideré"),
    ("entregue",            "entregué"),
    ("coordine",            "coordiné"),
    ("estandarice",         "estandaricé"),
    ("disene",              "diseñé"),     # también restituye ñ
    ("disenoie",            "diseñé"),     # variante corrupción tipográfica
    ("diseno",              "diseño"),     # sustantivo: sin ñ → diseño

    # ── Esdrújulas (acento en la antepenúltima sílaba — siempre llevan tilde) ─
    ("cientifico",          "científico"),
    ("agenticos",           "agénticos"),
    ("agentico",            "agéntico"),
    ("semantico",           "semántico"),
    ("analiticos",          "analíticos"),
    ("analitico",           "analítico"),
    ("hibrida",             "híbrida"),
    ("hibrido",             "híbrido"),
    ("tecnicas",            "técnicas"),
    ("tecnica",             "técnica"),
    ("tecnicos",            "técnicos"),
    ("tecnico",             "técnico"),
    ("dinamica",            "dinámica"),
    ("dinamico",            "dinámico"),
    ("logistica",           "logística"),
    ("logistico",           "logístico"),
    ("matematica",          "matemática"),
    ("matematico",          "matemático"),
    ("estadistica",         "estadística"),
    ("estadistico",         "estadístico"),
    ("metricas",            "métricas"),
    ("metrica",             "métrica"),
    ("metodo",              "método"),
    ("automaticos",         "automáticos"),
    ("automatica",          "automática"),
    ("automatico",          "automático"),
    ("electronico",         "electrónico"),
    ("electronica",         "electrónica"),
    ("organico",            "orgánico"),
    ("organica",            "orgánica"),
    ("publico",             "público"),
    ("publica",             "pública"),

    # ── Palabras llanas terminadas en consonante ≠ n/s (llevan tilde) ─────────
    ("lider",               "líder"),
    ("microcreditos",       "microcréditos"),
    ("creditos",            "créditos"),
    ("prestamos",           "préstamos"),

    # ── Palabras llanas terminadas en vocal/-n/-s cuando el acento NO ─────────
    #    recae en la penúltima (llevan tilde por ser agudas o diacríticas)
    ("consultoria",         "consultoría"),
    ("economia",            "economía"),
    ("autonoma",            "autónoma"),
    ("autonomo",            "autónomo"),
    ("ingles",              "inglés"),
    ("frances",             "francés"),
    ("produccion",          "producción"),
    ("segmentacion",        "segmentación"),
    ("extraccion",          "extracción"),
    ("calibracion",         "calibración"),
    ("validacion",          "validación"),
    ("clasificacion",       "clasificación"),
    ("regresion",           "regresión"),
    ("prediccion",          "predicción"),
    ("propension",          "propensión"),
    ("recuperacion",        "recuperación"),
    ("generacion",          "generación"),
    ("aprobacion",          "aprobación"),
    ("orchestracion",       "orquestación"),   # also wrong spelling
    ("orquestacion",        "orquestación"),
    ("rotacion",            "rotación"),
    ("reduccion",           "reducción"),
    ("solucion",            "solución"),
    ("soluciones",          "soluciones"),      # guard: prevent solucion→solución inside "soluciones"
    ("formacion",           "formación"),
    ("extension",           "extensión"),
    ("precision",           "precisión"),
    ("comprension",         "comprensión"),
    ("adaptacion",          "adaptación"),
    ("implementacion",      "implementación"),
    ("optimizacion",        "optimización"),
    ("automatizacion",      "automatización"),
    ("visualizacion",       "visualización"),
    ("seleccion",           "selección"),
    ("correlacion",         "correlación"),
    ("construccion",        "construcción"),
    ("documentacion",       "documentación"),
    ("comunicacion",        "comunicación"),
    ("colaboracion",        "colaboración"),
    ("descripcion",         "descripción"),
    ("actualizacion",       "actualización"),
    ("configuracion",       "configuración"),
    ("evaluacion",          "evaluación"),
    ("aplicacion",          "aplicación"),
    ("integracion",         "integración"),
    ("especificacion",      "especificación"),
    ("presentacion",        "presentación"),

    # ── Tilde diacrítica ─────────────────────────────────────────────────────
    # "mas" as a standalone word in a CV always means "más" (more), not "mas" (but).
    ("mas",                 "más"),
]

# Guard entries: words that look like a "wrong" form but are actually correct
# (e.g. "soluciones" should NOT become "soluciónes"). Process guards BEFORE fixes
# by putting them first. We handle this via the ORDERED list above — "soluciones"
# appears right after "solucion" so if the text already has the correct plural,
# the \b-bounded "solucion\b" pattern won't match inside "soluciones".
# (Word boundary: "solucion\b" does NOT match inside "soluciones" because 'e' is
# a word character, so there is no word boundary between 'n' and 'e'.)


def _make_tilde_replacer(correct: str):
    """Returns a replacement function that preserves leading capitalization."""
    def replacer(m: re.Match) -> str:
        matched = m.group(0)
        if matched[0].isupper():
            # Capitalize first char of the correct form
            return correct[0].upper() + correct[1:]
        return correct
    return replacer


# Compile tilde patterns with word boundaries, case-insensitive
_TILDE_PATTERNS = [
    (re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE), _make_tilde_replacer(correct))
    for wrong, correct in TILDE_WORD_FIXES
]

# Threshold: if a single text field has ≥ this many tilde fixes applied,
# report it as a SYSTEMIC GENERATION FAILURE rather than isolated mistakes.
_SYSTEMIC_TILDE_THRESHOLD = 4


# ── Tabla de conjugaciones: 3ª persona pretérito → 1ª persona pretérito ──────
# Aplicado con word-boundary para evitar falsos positivos dentro de palabras.
VERB_FIXES: dict[str, str] = {
    # -ar verbs
    "gestionó":     "gestioné",
    "diseñó":       "diseñé",
    "implementó":   "implementé",
    "lideró":       "lideré",
    "desarrolló":   "desarrollé",
    "realizó":      "realicé",
    "optimizó":     "optimicé",
    "automatizó":   "automaticé",
    "trabajó":      "trabajé",
    "colaboró":     "colaboré",
    "migró":        "migré",
    "desplegó":     "desplegué",
    "entrenó":      "entrené",
    "calibró":      "calibré",
    "validó":       "validé",
    "limpió":       "limpié",
    "procesó":      "procesé",
    "integró":      "integré",
    "coordinó":     "coordiné",
    "simplificó":   "simplifiqué",
    "segmentó":     "segmenté",
    "rediseñó":     "rediseñé",
    "estandarizó":  "estandaricé",
    "enriqueció":   "enriquecí",
    "priorizó":     "prioricé",
    "documentó":    "documenté",
    "monitoreó":    "monitoreé",
    "monitorizó":   "monitericé",
    "presentó":     "presenté",
    "identificó":   "identifiqué",
    "mejoró":       "mejoré",
    "redujo":       "reduje",
    "produjo":      "produje",
    "tradujo":      "traduje",
    # -er/-ir verbs
    "construyó":    "construí",
    "dirigió":      "dirigí",
    "definió":      "definí",
    "abrió":        "abrí",
    "permitió":     "permití",
    "aseguró":      "aseguré",
    "generó":       "generé",
    # present tense (3rd person) — sometimes Claude writes these instead of preterite
    "gestiona":     "gestiono",
    "diseña":       "diseño",
    "trabaja":      "trabajo",
    "desarrolla":   "desarrollo",
    "lidera":       "lidero",
    "construye":    "construyo",
}

def _make_verb_replacer(correct: str):
    """Returns a re.sub replacement function that preserves leading capitalization."""
    def replacer(m: re.Match) -> str:
        matched = m.group(0)
        if matched[0].isupper():
            return correct[0].upper() + correct[1:]
        return correct
    return replacer


# Compilar regex con word boundaries, case-insensitive
_VERB_PATTERNS = [
    (re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE), _make_verb_replacer(correct))
    for wrong, correct in VERB_FIXES.items()
]


# ── Tabla de títulos: inglés → español canónico ───────────────────────────────
# Matching exacto (case-insensitive, stripped)
TITLE_TRANSLATIONS: dict[str, str] = {
    "data scientist":                          "Científico de Datos",
    "senior data scientist":                   "Científico de Datos Senior",
    "co-founder and data scientist":           "Cofundador y Científico de Datos",
    "co-founder":                              "Co-Fundador",
    "cofounder":                               "Co-Fundador",
    "capital markets manager":                 "Gerente de Mercado de Capitales",
    "data & corporate finance consultant":     "Consultor de Datos y Finanzas Corporativas",
    "data and corporate finance consultant":   "Consultor de Datos y Finanzas Corporativas",
    "product analyst":                         "Analista de Producto",
    "financial analyst":                       "Analista Financiero",
    "analytics engineer":                      "Analista de Ingeniería de Datos",
    "data engineer":                           "Ingeniero de Datos",
    "machine learning engineer":               "Ingeniero de Machine Learning",
    "data analyst":                            "Analista de Datos",
    "data consultant":                         "Consultor de Datos",
    "business analyst":                        "Analista de Negocio",
}


# ── EM DASH regex ─────────────────────────────────────────────────────────────
_EM_DASH_RE = re.compile(r'\s*—\s*')
# Space-hyphen-space as clause separator (not in compound words)
_CLAUSE_DASH_RE = re.compile(r' - ')

# ── DETECTOR DE INGLÉS ────────────────────────────────────────────────────────
# Verbos de acción comunes en CVs técnicos que indican que el texto está en inglés
_ENGLISH_COMMON_VERBS = re.compile(
    r'\b(built|developed|designed|implemented|created|managed|led|deployed|'
    r'trained|optimized|validated|automated|migrated|coordinated|'
    r'integrated|delivered|established|reduced|improved|increased|'
    r'collaborated|maintained|supported|analyzed|defined|engineered|'
    r'architected|scaled|configured|monitored|documented|standardized|'
    r'launched|refactored|migrated|troubleshot|resolved|executed|'
    r'spearheaded|initiated|oversaw|streamlined|facilitated)\b',
    re.IGNORECASE
)

# Términos técnicos permitidos en inglés (no deben disparar la alerta)
# Estos pueden aparecer mezclados con texto en español
_TECHNICAL_TERMS_ALLOWED = {
    "python", "sql", "bigquery", "vertex", "airflow", "composer", "lightgbm",
    "gcp", "cloud", "dataflow", "docker", "kubernetes", "api", "etl", "pipeline",
    "model", "dataset", "feature", "score", "batch", "streaming", "ml", "ai",
    "pandas", "numpy", "scikit-learn", "tensorflow", "xgboost", "github",
    "gitlab", "jupyter", "notebook", "yaml", "json", "csv", "parquet",
}


def _fix_tildes(text: str, label: str, changes: list[str], systemic_warnings: list[str]) -> str:
    """
    Apply tilde/ñ fixes to a text string using word-boundary-safe regex.
    If ≥ _SYSTEMIC_TILDE_THRESHOLD fixes are needed in a single field, also
    emits a SYSTEMIC_FAILURE warning so the skill pipeline knows generation
    had a global accent-stripping issue.
    """
    original = text
    fixes_in_this_field = 0

    for pattern, replacer_fn in _TILDE_PATTERNS:
        if pattern.search(text):
            new_text = pattern.sub(replacer_fn, text)
            if new_text != text:
                fixes_in_this_field += 1
                text = new_text

    if text != original:
        changes.append(f"  [tildes/{label}] '{original[:90]}'\n             → '{text[:90]}'")
        if fixes_in_this_field >= _SYSTEMIC_TILDE_THRESHOLD:
            systemic_warnings.append(
                f"  ⚠ SYSTEMIC: [{label}] {fixes_in_this_field} tildes/ñ faltantes en un solo campo. "
                f"El JSON fue generado sin diacríticos — revisar la instrucción del skill."
            )

    return text


def _fix_text(text: str, label: str, changes: list[str],
              systemic_warnings: list[str] | None = None) -> str:
    """Apply tilde fixes, verb fixes and em-dash removal to a single text string."""
    if systemic_warnings is None:
        systemic_warnings = []
    original = text

    # 1. Fix tildes/ñ first (before verb fixes, which expect correctly-accented words)
    text = _fix_tildes(text, label, changes, systemic_warnings)

    # 2. Em dash → comma+space
    text = _EM_DASH_RE.sub(', ', text)
    # Space-hyphen-space → comma+space  (only as clause separator)
    text = _CLAUSE_DASH_RE.sub(', ', text)

    # 3. Verb fixes (word-boundary aware, case-insensitive, preserves leading cap)
    for pattern, replacer_fn in _VERB_PATTERNS:
        if pattern.search(text):
            text = pattern.sub(replacer_fn, text)

    if text != original and not any(label in c for c in changes):
        changes.append(f"  [{label}] '{original[:80]}' → '{text[:80]}'")

    return text

def _check_for_english(text: str, label: str, warnings: list[str]) -> None:
    """
    Detecta si el texto contiene verbos comunes en inglés que indican
    que el contenido fue generado en inglés en lugar de español.

    No genera alerta para términos técnicos permitidos.
    """
    matches = _ENGLISH_COMMON_VERBS.findall(text)
    if not matches:
        return

    suspicious_verbs = [v for v in matches if v.lower() not in _TECHNICAL_TERMS_ALLOWED]

    if suspicious_verbs:
        verbs_str = ", ".join(set(suspicious_verbs))
        warnings.append(
            f"  ⚠ [{label}] INGLÉS DETECTADO: '{text[:100]}...'\n"
            f"      Verbos en inglés encontrados: {verbs_str}\n"
            f"      → El JSON debe generarse en español desde el origen. "
            f"Este validador NO traduce contenido completo."
        )


def _fix_title(title: str, label: str, changes: list[str]) -> str:
    """Translate English job title to canonical Spanish if found in table."""
    key = title.strip().lower()
    if key in TITLE_TRANSLATIONS:
        translated = TITLE_TRANSLATIONS[key]
        if translated != title:
            changes.append(f"  [{label}] title '{title}' → '{translated}'")
        return translated
    return title


def _warn_if_english_title(title: str, label: str, warnings: list[str]) -> None:
    """Warn if title looks like untranslated English (common English words in job titles)."""
    english_keywords = {
        "scientist", "engineer", "analyst", "manager", "consultant",
        "founder", "director", "specialist", "developer", "architect",
        "lead", "head", "officer", "associate", "intern",
    }
    words = set(title.lower().split())
    found = words & english_keywords
    if found:
        warnings.append(
            f"  [{label}] Possible English title not in translation table: '{title}' "
            f"(keyword: {', '.join(found)})"
        )


def validate_and_fix(cv: dict) -> tuple[dict, list[str], list[str]]:
    """
    Returns (fixed_cv, changes, unfixable_warnings).
    changes: list of strings describing auto-applied fixes.
    unfixable_warnings: list of strings describing issues requiring manual fix.
    """
    changes: list[str] = []
    warnings: list[str] = []
    systemic: list[str] = []

    # Fix summary
    if cv.get("summary"):
        cv["summary"] = _fix_text(cv["summary"], "summary", changes, systemic)

    # Fix experience entries
    for idx, exp in enumerate(cv.get("experience", [])):
        company = exp.get("company", f"exp[{idx}]")
        label_base = f"experience/{company}"

        # Fix title
        if exp.get("title"):
            exp["title"] = _fix_title(exp["title"], f"{label_base}/title", changes)
            _warn_if_english_title(exp["title"], f"{label_base}/title", warnings)

        # Fix description
        if exp.get("description"):
            exp["description"] = _fix_text(exp["description"], f"{label_base}/description", changes, systemic)

        # Fix bullets
        for b_idx, bullet in enumerate(exp.get("bullets", [])):
            fixed = _fix_text(bullet, f"{label_base}/bullet[{b_idx}]", changes, systemic)
            exp["bullets"][b_idx] = fixed

        # Fix adapted_bullets if present
        for b_idx, bullet in enumerate(exp.get("adapted_bullets", [])):
            fixed = _fix_text(bullet, f"{label_base}/adapted_bullet[{b_idx}]", changes, systemic)
            exp["adapted_bullets"][b_idx] = fixed

    # Fix projects
    for idx, proj in enumerate(cv.get("projects", [])):
        name = proj.get("name", f"proj[{idx}]")
        label_p = f"projects/{name}"

        if proj.get("description"):
            proj["description"] = _fix_text(proj["description"], f"{label_p}/description", changes, systemic)

        if proj.get("name"):
            proj["name"] = _fix_tildes(proj["name"], f"{label_p}/name", changes, systemic)

        for b_idx, bullet in enumerate(proj.get("bullets", [])):
            fixed = _fix_text(bullet, f"{label_p}/bullet[{b_idx}]", changes, systemic)
            proj["bullets"][b_idx] = fixed

    # Fix education notes
    for idx, edu in enumerate(cv.get("education", [])):
        label_e = f"education[{idx}]"
        if edu.get("notes"):
            edu["notes"] = _fix_text(edu["notes"], f"{label_e}/notes", changes, systemic)
        if edu.get("location"):
            edu["location"] = _fix_tildes(edu["location"], f"{label_e}/location", changes, systemic)
        if edu.get("degree"):
            edu["degree"] = _fix_tildes(edu["degree"], f"{label_e}/degree", changes, systemic)

    # Emit any systemic tilde warnings
    if systemic:
        warnings.extend(systemic)

    return cv, changes, warnings


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main(json_path: str) -> int:
    path = Path(json_path)
    if not path.exists():
        print(f"[validate_cv_es] ERROR: Archivo no encontrado: {path}")
        return 1

    cv = load_json(path)

    language = cv.get("language", "en")
    if language != "es":
        print(f"[validate_cv_es] INFO: language='{language}' — no es español, nada que validar.")
        return 0

    cv_fixed, changes, warnings = validate_and_fix(cv)

    if changes:
        print(f"[validate_cv_es] {len(changes)} corrección(es) aplicada(s):")
        for line in changes:
            print(line)
        save_json(path, cv_fixed)
        print(f"[validate_cv_es] JSON guardado: {path}")
    else:
        print("[validate_cv_es] Sin problemas detectados. JSON sin cambios.")

    if warnings:
        print(f"\n[validate_cv_es] ⚠ {len(warnings)} advertencia(s):")
        for line in warnings:
            print(line)

        # Systemic tilde failure is auto-fixed but we still flag it so the skill
        # pipeline can review the output before proceeding.
        systemic_count = sum(1 for w in warnings if "SYSTEMIC" in w)
        if systemic_count:
            print(
                f"\n[validate_cv_es] ⚠ SYSTEMIC TILDE FAILURE detectado en {systemic_count} campo(s)."
                "\n  Las correcciones fueron aplicadas automáticamente."
                "\n  Causa probable: el modelo generó el JSON sin diacríticos."
                "\n  Acción: revisar el output generado y ajustar el prompt del skill si el problema persiste."
            )

        manual_warnings = [w for w in warnings if "SYSTEMIC" not in w and "INGLÉS" not in w]
        if manual_warnings:
            return 1  # Only fail for truly unresolvable warnings

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validate_cv_es.py <cv_adapted.json>")
        print("Ejemplo: python validate_cv_es.py outputs/ready/hiberus_Data_Scientist/cv_hiberus_Data_Scientist.json")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
