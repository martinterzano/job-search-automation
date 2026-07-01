"""
generate_dashboard.py — Genera un dashboard HTML desde el Google Sheets tracker.

Uso:
    python generate_dashboard.py

Output:
    outputs/dashboard.html

Lee las sheets "Active" y "Skip" del Google Sheet definido en .env
y genera un dashboard HTML standalone con Chart.js y diseño moderno.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ── Dependencias ──────────────────────────────────────────────────────────────
try:
    import gspread
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except ImportError as e:
    print(
        f"ERROR: Dependencia faltante — {e}\n"
        "Instalar con: pip install gspread google-auth-oauthlib"
    )
    sys.exit(1)

# ── Rutas ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT     = Path(__file__).parents[4]
CREDENTIALS_PATH = PROJECT_ROOT / "assets" / "google" / "credentials.json"
TOKEN_PATH       = PROJECT_ROOT / "assets" / "google" / "token.json"
ENV_PATH         = PROJECT_ROOT / ".env"
OUTPUT_PATH      = PROJECT_ROOT / "outputs" / "dashboard.html"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

HEADERS = [
    "Company", "Role", "Date", "Fit Score", "Recommendation",
    "Language", "Company Summary", "Role Summary", "Modality",
    "Must Skills", "Should Skills", "Nice Skills", "Exp. Requirements",
    "Strengths", "Gaps", "Interpretation",
    "Salary Posted", "Salary Target",
    "Applied?", "Application", "Status", "Comments",
    "Days Posted", "Applicants",
]


# ── Auth ──────────────────────────────────────────────────────────────────────

def _get_credentials() -> Credentials:
    if not CREDENTIALS_PATH.exists():
        print(
            f"ERROR: No se encontró {CREDENTIALS_PATH}\n"
            "Seguir instrucciones en assets/google/SETUP.md"
        )
        sys.exit(1)

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def _load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


# ── Lectura de datos ──────────────────────────────────────────────────────────

def _rows_to_dicts(rows: list, header: list | None = None) -> list:
    """Mapea filas a dicts usando el header real del sheet (o HEADERS como fallback)."""
    cols = header if header else HEADERS
    result = []
    for row in rows:
        padded = row + [""] * max(0, len(cols) - len(row))
        result.append(dict(zip(cols, padded)))
    return result


def fetch_data():
    env            = _load_env()
    spreadsheet_id = env.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()

    if not spreadsheet_id:
        print(
            "ERROR: GOOGLE_SHEETS_SPREADSHEET_ID no está en .env\n"
            "Correr primero: python update_tracker.py <analysis.json>"
        )
        sys.exit(1)

    creds = _get_credentials()
    gc    = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(spreadsheet_id)

    def _get_sheet_rows(sheet_name):
        try:
            ws     = spreadsheet.worksheet(sheet_name)
            values = ws.get_all_values()
            if len(values) <= 1:
                return []
            return _rows_to_dicts(values[1:], header=values[0])
        except gspread.WorksheetNotFound:
            return []

    active = _get_sheet_rows("Active")
    skip   = _get_sheet_rows("Skip")
    return active, skip


# ── Helpers de datos ──────────────────────────────────────────────────────────

def _safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _normalize_date(date_str):
    """Normaliza cualquier formato de fecha a ISO 'YYYY-MM-DD'. Retorna '' si no parseable."""
    s = (date_str or "").strip()
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10] if "-" in s else s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _parse_skills(skills_str):
    if not skills_str:
        return []
    return [s.strip() for s in skills_str.split(",") if s.strip()]


# ── Semantic classification rules ─────────────────────────────────────────────

EXP_THEME_RULES = [
    ("ML en producción (5+ años)",       r"(?:5|6|7|8)\+?\s*a[ñn]os?|5\+\s*year|4-6\s*a[ñn]|produccion.*(?:5|6|7|8)|(?:5|6|7|8).*producc"),
    ("ML en producción (2-4 años)",      r"[12]-[34]\s*a[ñn]os?|2\+\s*a[ñn]os?.*(?:ml|ds|data)|3\+\s*a[ñn]os?.*(?:ml|ds|data)|1-4\s*a[ñn]"),
    ("LLM / GenAI en producción",        r"llm|rag\b|langchain|llamaindex|gen\s*ai|generativa|openai|anthropic|agente.*ia|fine.tun|embedding"),
    ("A/B Testing / Experimentación",    r"a/b\s*test|ab\s*test|experiment|causal\s*inferen"),
    ("Deep Learning (PyTorch/TF)",       r"pytorch|tensorflow|\btf\b|jax\b|transformers\b|hugging.face"),
    ("Big Data: Spark / Databricks",     r"spark|databricks|pyspark"),
    ("Master's o PhD requerido",         r"master|phd|doctorado|msc\b|advanced\s*degree|titulacion.*superior"),
    ("7+ años de experiencia",           r"7\+|8\+|7-8\s*a[ñn]|8\s*a[ñn]os"),
    ("Dominio: Finance / Risk",          r"financiero|finance|payment|fraud|credit\s*scor|insurance.*dom|servicios\s*financ"),
    ("Dominio: Healthcare / Pharma",     r"salud|health|pharma|life\s*sciences|sanitario|clinico"),
    ("Dominio: Sports / Gaming / AdTech",r"sport|gaming|adtech|advertis|futbol|wearable"),
    ("NLP / Computer Vision",            r"\bnlp\b|computer\s*vision|\bcv\b.*model|text\s*processing|information\s*retrieval"),
    ("Time Series / Forecasting",        r"time\s*series|forecasting|forecast|demand\s*model|elasticity"),
    ("Cloud: Azure específico",          r"azure|microsoft.*cloud"),
    ("Consulting background",            r"consulting|consultoria|consultor"),
]

def _classify_exp_themes(text):
    """Classify Exp. Requirements text into semantic experience categories."""
    if not text:
        return []
    t = text.lower()
    return [label for label, pattern in EXP_THEME_RULES if re.search(pattern, t)]


INTERP_THEME_RULES = [
    ("Match técnico fuerte",             r"match.*fuerte|fuerte.*match|stack.*cubre|cubre.*core|tecnico.*encaja|encaja.*direc"),
    ("Gap: LLM / GenAI enterprise",      r"gap.*llm|llm.*gap|genai.*profesional|personal.*no.*enterprise|hands-on.*llm.*gap"),
    ("Gap: Deep Learning (PyTorch/TF)",  r"gap.*pytorch|pytorch.*gap|tensorflow.*gap|deep\s*learning.*gap"),
    ("Gap: A/B Testing",                 r"gap.*a/b|a/b.*gap|experimentacion.*gap|testing.*gap|a/b.*core\s*gap"),
    ("Fortaleza: GCP / producción ML",   r"produccion.*gcp|gcp.*encaja|cloud\s*composer.*encaja|gcp.*match|lapse.*encaja|pltv.*encaja|gcp.*prod"),
    ("Barrera: dominio específico",      r"barrera.*dominio|dominio.*claro|sector.*barrera|domain.*gap.*hard|especializacion.*sector"),
    ("Barrera: 7+ años hard",            r"barrera.*dura.*exp|7.*a[ñn]os.*requerido|barrera.*exp|7-8.*hard|8\+.*requerido|hard\s*blocker.*a[ñn]"),
    ("Gap: Spark / Big Data",            r"spark.*gap|gap.*spark|scala.*gap|pyspark.*gap|spark.*barrier"),
    ("Perfil: LLM puro / AI Engineer",   r"rol.*llm|llm.*puro|no.*ds.*rol|llm\s*engineering.*core|ai\s*engineer.*llm"),
    ("Barrera: credenciales académicas", r"phd.*requerido|master.*requerido|credencial.*acad|grado.*requerido.*barrera|advanced\s*degree.*barrier"),
    ("Gap semántico / compensable",      r"gap.*semantico|semantico.*gap|compensado|no.*gap.*duro|equivalente.*gap|minor\s*gap"),
    ("Barrera: idioma",                  r"barrera.*idioma|hard.*blocker.*idioma|catalan|russian|ruso\b"),
    ("Gap: MLOps / infraestructura",     r"mlops.*gap|gap.*mlops|kubernetes.*gap|stratio"),
    ("Match: consulting / analytics",    r"consulting.*match|match.*consulting|analytics.*background.*match"),
]

def _classify_interp_themes(text):
    """Classify interpretation text into recurring semantic patterns."""
    if not text:
        return []
    t = text.lower()
    return [label for label, pattern in INTERP_THEME_RULES if re.search(pattern, t)]


def _classify_role(role_str):
    """Returns (role_type, seniority). Priority order handles overlap (e.g. 'Data Engineer' before 'engineer')."""
    s = (role_str or "").lower().replace("_", " ")

    if any(x in s for x in ["senior", "sr.", " sr ", "lead", "staff", "principal",
                              "head of", "director", "manager"]):
        seniority = "Senior"
    elif any(x in s for x in ["junior", "jr.", "jr ", "entry level", "associate", "intern"]):
        seniority = "Junior"
    else:
        seniority = "Mid"

    if any(x in s for x in ["consultant", "consulting", "consultor"]):
        role_type = "DS/Analytics Consultant"
    elif any(x in s for x in ["data scientist", "data science"]):
        role_type = "Data Scientist"
    elif any(x in s for x in ["research scientist", "research engineer", "scientist"]):
        role_type = "Research"
    elif "data engineer" in s:
        role_type = "Data Engineer"
    elif any(x in s for x in ["engineer", "ingeniero", "developer"]):
        role_type = "AI/ML Engineer"
    elif any(x in s for x in ["data analyst", "business analyst", "product analyst", "specialist"]):
        role_type = "Data Analyst"
    elif any(x in s for x in ["quantitative", "quant analyst", "quant researcher"]):
        role_type = "Quantitative"
    else:
        role_type = "Other"

    return role_type, seniority


def _score_range(score_int):
    if score_int is None:
        return None
    if score_int < 30:  return "0-29"
    if score_int < 50:  return "30-49"
    if score_int < 70:  return "50-69"
    if score_int < 90:  return "70-89"
    return "90-100"


def _normalize_modality(s):
    """Normalizes modality variants to one of: On site, Remote, Hybrid, Unknown."""
    s = (s or "").lower().strip()
    if any(x in s for x in ["onsite", "on-site", "presencial", "in-office", "office"]):
        return "On site"
    elif any(x in s for x in ["remote", "remoto", "fully remote", "100% remote", "wfh"]):
        return "Remote"
    elif any(x in s for x in ["hybrid", "híbrido", "hibrido", "flex"]):
        return "Hybrid"
    elif s:
        # Fallback: try to classify by partial match
        if "remote" in s:
            return "Remote"
        if "hybrid" in s or "hibrido" in s:
            return "Hybrid"
        return "On site"
    return "Unknown"


def _row_to_js(row, sheet):
    score_int        = _safe_int(row.get("Fit Score", ""))
    role_type, seniority = _classify_role(row.get("Role", ""))
    return {
        "company":        row.get("Company", ""),
        "role":           row.get("Role", ""),
        "date":           _normalize_date(row.get("Date", "")),
        "score":          row.get("Fit Score", ""),
        "scoreInt":       score_int,
        "scoreRange":     _score_range(score_int),
        "recommendation": (row.get("Recommendation", "") or "").lower(),
        "modality":       _normalize_modality(row.get("Modality", "")),
        "strengths":      row.get("Strengths", ""),
        "gaps":           row.get("Gaps", ""),
        "interpretation": row.get("Interpretation", ""),
        "apliqueQ":       row.get("Apliqué?", ""),
        "aplicacion":     row.get("Aplicación", ""),
        "mustSkills":     _parse_skills(row.get("Must Skills", "")),
        "shouldSkills":   _parse_skills(row.get("Should Skills", "")),
        "niceSkills":     _parse_skills(row.get("Nice Skills", "")),
        "expThemes":      _classify_exp_themes(row.get("Exp. Requirements", "")),
        "interpThemes":   _classify_interp_themes(row.get("Interpretation", "")),
        "roleType":       role_type,
        "seniority":      seniority,
        "roleFull":       f"{seniority} {role_type}",
        "sheet":          sheet,
        "batchDate":      _normalize_date(row.get("Date", "")),
        "daysPosted":     _safe_int(row.get("Days Posted", "")),
        "applicants":     row.get("Applicants", "") or "",
    }


# ── Métricas ──────────────────────────────────────────────────────────────────

def compute_metrics(active, skip):
    all_rows = active + skip

    apply_rows = [r for r in active if r["Recommendation"].lower() == "apply"]
    cond_rows  = [r for r in active if r["Recommendation"].lower() == "conditional"]

    scores    = [s for s in (_safe_int(r["Fit Score"]) for r in active) if s is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Score ranges
    ranges = {"0-29": 0, "30-49": 0, "50-69": 0, "70-89": 0, "90-100": 0}
    for r in all_rows:
        sr = _score_range(_safe_int(r["Fit Score"]))
        if sr:
            ranges[sr] += 1

    # Timeline — ISO week aggregation
    from datetime import timedelta
    timeline = {}
    for row in all_rows:
        date_str = row.get("Date", "")
        if date_str:
            try:
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d" if "-" in date_str else "%d/%m/%Y")
                iso_year, iso_week, _ = dt.isocalendar()
                monday = dt - timedelta(days=dt.weekday())
                key = f"W{iso_week:02d} {monday.strftime('%d %b %Y')}"
                timeline[key] = timeline.get(key, 0) + 1
            except ValueError:
                pass

    def _week_key(s):
        try:
            parts = s.split(" ", 1)
            return datetime.strptime(parts[1], "%d %b %Y")
        except:
            return datetime.min

    sorted_tl = dict(sorted(timeline.items(), key=lambda x: _week_key(x[0])))

    # Role type distribution (all rows, label = "Seniority Type")
    role_type_dist = {}
    for row in all_rows:
        rt, sn = _classify_role(row.get("Role", ""))
        key = f"{sn} {rt}"
        role_type_dist[key] = role_type_dist.get(key, 0) + 1
    role_type_dist = dict(sorted(role_type_dist.items(), key=lambda x: -x[1])[:12])

    # Modality distribution (using normalized values)
    modality_dist = {}
    for row in all_rows:
        mod = _normalize_modality(row.get("Modality", ""))
        modality_dist[mod] = modality_dist.get(mod, 0) + 1

    # Must skills overall top 15
    skills_ctr = {}
    for row in all_rows:
        for sk in _parse_skills(row.get("Must Skills", "")):
            skills_ctr[sk] = skills_ctr.get(sk, 0) + 1
    top_skills = dict(sorted(skills_ctr.items(), key=lambda x: -x[1])[:15])

    # Must skills by base role type (no seniority), top 10 each
    skills_by_role = {}
    for row in all_rows:
        rt, _ = _classify_role(row.get("Role", ""))
        if rt not in skills_by_role:
            skills_by_role[rt] = {}
        for sk in _parse_skills(row.get("Must Skills", "")):
            skills_by_role[rt][sk] = skills_by_role[rt].get(sk, 0) + 1
    for rt in skills_by_role:
        skills_by_role[rt] = dict(sorted(skills_by_role[rt].items(), key=lambda x: -x[1])[:10])

    # Should skills overall top 15
    should_ctr = {}
    for row in all_rows:
        for sk in _parse_skills(row.get("Should Skills", "")):
            should_ctr[sk] = should_ctr.get(sk, 0) + 1
    top_should = dict(sorted(should_ctr.items(), key=lambda x: -x[1])[:15])

    # Nice skills overall top 15
    nice_ctr = {}
    for row in all_rows:
        for sk in _parse_skills(row.get("Nice Skills", "")):
            nice_ctr[sk] = nice_ctr.get(sk, 0) + 1
    top_nice = dict(sorted(nice_ctr.items(), key=lambda x: -x[1])[:15])

    # Should / Nice by role (top 10 each)
    should_by_role = {}
    nice_by_role   = {}
    for row in all_rows:
        rt, _ = _classify_role(row.get("Role", ""))
        should_by_role.setdefault(rt, {})
        nice_by_role.setdefault(rt, {})
        for sk in _parse_skills(row.get("Should Skills", "")):
            should_by_role[rt][sk] = should_by_role[rt].get(sk, 0) + 1
        for sk in _parse_skills(row.get("Nice Skills", "")):
            nice_by_role[rt][sk] = nice_by_role[rt].get(sk, 0) + 1
    for rt in should_by_role:
        should_by_role[rt] = dict(sorted(should_by_role[rt].items(), key=lambda x: -x[1])[:10])
    for rt in nice_by_role:
        nice_by_role[rt]   = dict(sorted(nice_by_role[rt].items(),   key=lambda x: -x[1])[:10])

    # Exp themes and interp themes are computed per-row in _row_to_js() — no pre-computation needed here.

    # ── Posting Intelligence ──────────────────────────────────────────────────
    from datetime import timedelta as _td

    dp_buckets  = {"0–1": 0, "2–3": 0, "4–5": 0, "6–7": 0, "7+": 0}
    app_buckets = {"0–24": 0, "25–49": 0, "50–74": 0, "75–99": 0, ">100": 0}
    dp_vals_all = []
    app_vals_all = []

    for row in all_rows:
        dp_raw = row.get("Days Posted", "")
        dp = _safe_int(dp_raw)
        if dp is not None:
            dp_vals_all.append(dp)
            if dp <= 1:   dp_buckets["0–1"]  += 1
            elif dp <= 3: dp_buckets["2–3"]  += 1
            elif dp <= 5: dp_buckets["4–5"]  += 1
            elif dp <= 7: dp_buckets["6–7"]  += 1
            else:         dp_buckets["7+"]        += 1

        app_raw      = row.get("Applicants", "") or ""
        app_stripped = app_raw.strip()
        app_num_str  = re.sub(r'[^\d]', '', app_raw)
        if app_num_str:
            app_vals_all.append(int(app_num_str))
        if app_stripped:
            if not re.fullmatch(r'\d+', app_stripped):
                app_buckets[">100"] += 1
            else:
                n = int(app_stripped)
                if n <= 24:   app_buckets["0–24"]  += 1
                elif n <= 49: app_buckets["25–49"] += 1
                elif n <= 74: app_buckets["50–74"] += 1
                elif n <= 99: app_buckets["75–99"] += 1
                else:         app_buckets[">100"]       += 1

    posting_metrics = {
        "dp_buckets":       dp_buckets,
        "app_buckets":      app_buckets,
        "avg_days_posted":  round(sum(dp_vals_all) / len(dp_vals_all), 1) if dp_vals_all else None,
        "avg_applicants":   round(sum(app_vals_all) / len(app_vals_all), 1) if app_vals_all else None,
        "has_data":         len(dp_vals_all) > 0,
    }

    total = len(all_rows)
    return {
        "total":           total,
        "active_count":    len(active),
        "skip_count":      len(skip),
        "apply_count":     len(apply_rows),
        "cond_count":      len(cond_rows),
        "avg_score":       avg_score,
        "apply_rate":      round(len(apply_rows) / total * 100, 1) if total else 0,
        "active_rate":     round(len(active)     / total * 100, 1) if total else 0,
        "score_ranges":    ranges,
        "timeline_labels": list(sorted_tl.keys()),
        "timeline_values": list(sorted_tl.values()),
        "role_type_dist":  role_type_dist,
        "modality_dist":   modality_dist,
        "top_skills":      top_skills,
        "top_should":      top_should,
        "top_nice":        top_nice,
        "skills_by_role":  skills_by_role,
        "should_by_role":  should_by_role,
        "nice_by_role":    nice_by_role,
        "posting":         posting_metrics,
    }


# ── HTML generation ───────────────────────────────────────────────────────────

def generate_html(active, skip, metrics):
    now       = datetime.now().strftime("%d %b %Y, %H:%M")
    env       = _load_env()
    sheet_id  = env.get("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit" if sheet_id else "#"

    all_js_rows = (
        [_row_to_js(r, "active") for r in active] +
        [_row_to_js(r, "skip")   for r in skip]
    )

    # Only this section is an f-string — embeds Python data as JS constants.
    # The HTML template below is a plain string, so { } don't need escaping.
    js_data = (
        "const DATA           = " + json.dumps(all_js_rows,            ensure_ascii=False) + ";\n"
        "const METRICS        = " + json.dumps(metrics,                ensure_ascii=False) + ";\n"
        "const SKILLS_BY_ROLE = " + json.dumps(metrics["skills_by_role"], ensure_ascii=False) + ";\n"
        "const SHOULD_BY_ROLE = " + json.dumps(metrics["should_by_role"], ensure_ascii=False) + ";\n"
        "const NICE_BY_ROLE   = " + json.dumps(metrics["nice_by_role"],   ensure_ascii=False) + ";\n"
        "const SHEET_URL      = " + json.dumps(sheet_url) + ";\n"
        "const UPDATED        = " + json.dumps(now) + ";\n"
        "const POSTING        = " + json.dumps(metrics["posting"], ensure_ascii=False) + ";\n"
    )

    return _HTML_TEMPLATE.replace("/*__JSDATA__*/", js_data)


# ── HTML Template (plain string — no f-string brace escaping needed) ──────────

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Job Search Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg-base:    #0F172A;
      --bg-card:    #1E293B;
      --bg-card2:   #162032;
      --border:     #334155;
      --accent:     #1F4E79;
      --accent-lg:  #2563EB;
      --text-main:  #F1F5F9;
      --text-muted: #94A3B8;
      --green:      #4ADE80;
      --yellow:     #FACC15;
      --red:        #F87171;
      --green-bg:   rgba(74,222,128,.15);
      --yellow-bg:  rgba(250,204,21,.15);
      --red-bg:     rgba(248,113,113,.15);
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Inter', sans-serif; background: var(--bg-base); color: var(--text-main); min-height: 100vh; }
    .shell { max-width: 1500px; margin: 0 auto; padding: 2rem 1.5rem; }

    /* Header */
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 2.5rem; flex-wrap: wrap; gap: 1rem; }
    .page-header h1 { font-size: 1.75rem; font-weight: 700; background: linear-gradient(135deg, #60A5FA, #818CF8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
    .header-meta { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
    .header-badge { background: rgba(31,78,121,.6); border: 1px solid #2563EB44; border-radius: 9999px; padding: .35rem .9rem; font-size: .78rem; font-weight: 500; color: #93C5FD; }
    .updated-label { font-size: .78rem; color: var(--text-muted); }
    .sheet-link { display: inline-flex; align-items: center; gap: .4rem; font-size: .78rem; color: #60A5FA; text-decoration: none; padding: .35rem .8rem; border: 1px solid #60A5FA44; border-radius: 6px; transition: background .2s; }
    .sheet-link:hover { background: rgba(96,165,250,.1); }

    /* KPI Cards */
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2.5rem; }
    .kpi-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; position: relative; overflow: hidden; transition: transform .2s, border-color .2s; }
    .kpi-card:hover { transform: translateY(-2px); border-color: #475569; }
    .kpi-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; border-radius: 16px 16px 0 0; }
    .kpi-card.accent-blue::before   { background: linear-gradient(90deg, #2563EB, #818CF8); }
    .kpi-card.accent-green::before  { background: linear-gradient(90deg, #4ADE80, #22D3EE); }
    .kpi-card.accent-yellow::before { background: linear-gradient(90deg, #FACC15, #FB923C); }
    .kpi-card.accent-purple::before { background: linear-gradient(90deg, #A78BFA, #EC4899); }
    .kpi-label { font-size: .75rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); margin-bottom: .6rem; }
    .kpi-value { font-size: 2.4rem; font-weight: 700; line-height: 1; margin-bottom: .4rem; }
    .kpi-sub   { font-size: .78rem; color: var(--text-muted); }

    /* Charts grid */
    .charts-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.25rem; margin-bottom: 1.25rem; }
    .charts-grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 1.25rem; margin-bottom: 1.25rem; }
    .charts-grid-full { display: grid; grid-template-columns: 1fr; gap: 1.25rem; margin-bottom: 1.25rem; }
    @media (max-width: 1100px) { .charts-grid, .charts-grid-2 { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 700px)  { .charts-grid, .charts-grid-2 { grid-template-columns: 1fr; } }
    .chart-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; cursor: default; }
    .chart-card.clickable { cursor: pointer; }
    .chart-card.clickable:hover { border-color: #475569; }
    .chart-card.filter-active { border-color: #2563EB; box-shadow: 0 0 0 1px #2563EB33; }
    .chart-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem; flex-wrap: wrap; gap: .5rem; }
    .chart-title { font-size: .85rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; }
    .chart-hint  { font-size: .72rem; color: #475569; font-style: italic; }
    .chart-wrap  { position: relative; height: 220px; }
    .chart-wrap-tall { position: relative; height: 300px; }
    .chart-wrap-skills { position: relative; height: 500px; }

    /* Selects */
    .skill-select { background: var(--bg-card2); border: 1px solid var(--border); color: var(--text-main); border-radius: 8px; padding: .35rem .7rem; font-size: .82rem; font-family: inherit; cursor: pointer; }
    .skill-select:focus { outline: none; border-color: #2563EB; }
    .skill-select option { background: #1E293B; }
    .select-group { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }

    /* Skill type checkboxes */
    .skills-type-checks { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; }
    .skill-check-label { display: flex; align-items: center; gap: .3rem; font-size: .82rem; color: var(--text-muted); cursor: pointer; user-select: none; }
    .skill-check-label input[type="checkbox"] { accent-color: #60A5FA; cursor: pointer; width: 13px; height: 13px; }
    .skill-check-label:hover { color: var(--text-main); }

    /* Section heading */
    .section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: .75rem; }
    .section-head h2 { font-size: 1.05rem; font-weight: 600; }
    .count-badge { background: rgba(37,99,235,.2); border: 1px solid #2563EB55; color: #93C5FD; border-radius: 9999px; padding: .2rem .7rem; font-size: .75rem; font-weight: 600; }

    /* Filters row */
    .filters-row { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; margin-bottom: .75rem; }
    .search-box { background: var(--bg-card2); border: 1px solid var(--border); border-radius: 8px; padding: .45rem .85rem; color: var(--text-main); font-size: .85rem; font-family: inherit; width: 200px; transition: border-color .2s; }
    .search-box:focus { outline: none; border-color: #2563EB; }
    .search-box::placeholder { color: var(--text-muted); }
    .filter-select { background: var(--bg-card2); border: 1px solid var(--border); color: var(--text-main); border-radius: 8px; padding: .42rem .7rem; font-size: .83rem; font-family: inherit; cursor: pointer; }
    .filter-select:focus { outline: none; border-color: #2563EB; }
    .filter-select option { background: #1E293B; }

    /* Active filter pills */
    .pills-row { display: flex; gap: .45rem; flex-wrap: wrap; margin-bottom: .75rem; min-height: 0; }
    .pill { display: inline-flex; align-items: center; gap: .35rem; background: rgba(37,99,235,.2); border: 1px solid #2563EB55; color: #93C5FD; border-radius: 9999px; padding: .2rem .65rem; font-size: .75rem; font-weight: 500; }
    .pill-x { cursor: pointer; opacity: .7; font-size: .85rem; line-height: 1; }
    .pill-x:hover { opacity: 1; }
    .clear-all-btn { background: none; border: 1px solid #475569; color: var(--text-muted); border-radius: 9999px; padding: .2rem .65rem; font-size: .72rem; font-family: inherit; cursor: pointer; transition: border-color .2s, color .2s; }
    .clear-all-btn:hover { border-color: var(--text-muted); color: var(--text-main); }

    /* Table */
    .table-wrap { background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; overflow: hidden; margin-bottom: 2rem; }
    .table-scroll { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: .82rem; }
    thead tr { background: rgba(31,78,121,.55); border-bottom: 1px solid var(--border); }
    th { padding: .7rem .9rem; text-align: left; font-size: .71rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); white-space: nowrap; }
    tbody tr { border-bottom: 1px solid #1E293B; transition: background .15s; }
    tbody tr:last-child { border-bottom: none; }
    tbody tr:hover { background: rgba(255,255,255,.03); }
    tbody tr.data-row { cursor: pointer; }
    tbody tr.data-row.row-expanded { background: rgba(37,99,235,.07); border-bottom-color: transparent; }
    tbody tr.data-row.row-expanded:hover { background: rgba(37,99,235,.1); }
    .detail-row td { padding: 0 !important; border-bottom: 1px solid #1E293B; }
    .detail-cell { padding: .9rem 1.1rem !important; background: rgba(15,23,42,.55); border-top: 1px solid rgba(37,99,235,.25); }
    .detail-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.25rem; }
    @media (max-width: 900px) { .detail-grid { grid-template-columns: 1fr; } }
    .detail-label { font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; color: var(--text-muted); margin-bottom: .35rem; }
    .detail-text { font-size: .82rem; color: var(--text-main); line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
    td { padding: .65rem .9rem; vertical-align: top; color: var(--text-main); }
    .col-company  { font-weight: 600; white-space: nowrap; max-width: 120px; overflow: hidden; text-overflow: ellipsis; }
    .col-role     { color: #CBD5E1; max-width: 120px; overflow: hidden; text-overflow: ellipsis; }
    .col-date     { color: var(--text-muted); white-space: nowrap; font-size: .77rem; }
    .col-score    { white-space: nowrap; }
    .col-modality { color: var(--text-muted); font-size: .77rem; white-space: nowrap; }
    .col-aplique  { white-space: nowrap; width: 55px; }
    .col-app      { width: 100px; max-width: 100px; color: #CBD5E1; font-size: .77rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .col-long     { max-width: 260px; color: #CBD5E1; font-size: .77rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .empty-state  { text-align: center; padding: 2.5rem; color: var(--text-muted); }

    .score-chip { display: inline-block; padding: .18rem .5rem; border-radius: 6px; font-weight: 600; font-size: .79rem; }
    .score-high  { background: var(--green-bg);  color: var(--green);  }
    .score-mid   { background: var(--yellow-bg); color: var(--yellow); }
    .score-low   { background: var(--red-bg);    color: var(--red);    }

    .badge { display: inline-block; padding: .2rem .55rem; border-radius: 6px; font-size: .71rem; font-weight: 600; text-transform: capitalize; white-space: nowrap; }
    .badge-apply { background: var(--green-bg);  color: var(--green);  }
    .badge-cond  { background: var(--yellow-bg); color: var(--yellow); }
    .badge-skip  { background: var(--red-bg);    color: var(--red);    }
    .badge-si    { background: rgba(34,211,238,.12); color: #22D3EE; }
    .badge-no    { background: rgba(148,163,184,.1);  color: #94A3B8; }

    /* Pagination */
    .pagination { display: flex; align-items: center; justify-content: center; gap: .5rem; padding: .9rem; border-top: 1px solid var(--border); }
    .page-btn { background: var(--bg-card2); border: 1px solid var(--border); color: var(--text-main); border-radius: 7px; padding: .32rem .7rem; font-size: .79rem; cursor: pointer; font-family: inherit; transition: background .15s, border-color .15s; }
    .page-btn:hover   { background: #334155; border-color: #475569; }
    .page-btn.active  { background: #1D4ED8; border-color: #2563EB; color: #fff; }
    .page-btn:disabled{ opacity: .4; cursor: default; }

    /* Collapsible */
    .collapse-btn { display: inline-flex; align-items: center; gap: .4rem; background: none; border: 1px solid var(--border); color: var(--text-muted); border-radius: 8px; padding: .35rem .75rem; font-size: .8rem; font-family: inherit; cursor: pointer; transition: border-color .2s, color .2s; }
    .collapse-btn:hover { border-color: #475569; color: var(--text-main); }
    .collapse-icon { transition: transform .25s; }
    .collapse-icon.open { transform: rotate(180deg); }

    /* Interpretation Tabs */
    .tab-bar { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: .75rem; }
    .tab-btn { background: var(--bg-card2); border: 1px solid var(--border); color: var(--text-muted); border-radius: 8px; padding: .45rem 1.1rem; font-size: .82rem; font-family: inherit; cursor: pointer; transition: all .15s; display: inline-flex; align-items: center; gap: .4rem; }
    .tab-btn:hover { border-color: #475569; color: var(--text-main); }
    .tab-btn.tab-apply.active  { background: var(--green-bg);  border-color: var(--green);  color: var(--green); }
    .tab-btn.tab-cond.active   { background: var(--yellow-bg); border-color: var(--yellow); color: var(--yellow); }
    .tab-btn.tab-skip.active   { background: var(--red-bg);    border-color: var(--red);    color: var(--red); }
    .tab-count { font-size: .72rem; opacity: .8; }

    /* Collapsible sections */
    .chart-section { margin-bottom: 1.25rem; }
    .chart-section-header { display: flex; align-items: center; justify-content: space-between; padding: .55rem .9rem; background: rgba(30,41,59,.7); border: 1px solid var(--border); border-radius: 10px; cursor: pointer; user-select: none; transition: background .15s, border-color .15s; margin-bottom: .75rem; }
    .chart-section-header:hover { background: rgba(51,65,85,.6); border-color: #475569; }
    .chart-section-title { font-size: .82rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; display: flex; align-items: center; gap: .65rem; }
    .chart-section-hint { font-size: .72rem; font-style: italic; color: #475569; font-weight: 400; text-transform: none; letter-spacing: 0; }
    .collapse-arrow { width: 16px; height: 16px; color: var(--text-muted); transition: transform .25s; flex-shrink: 0; }
    .chart-section.collapsed .collapse-arrow { transform: rotate(-90deg); }
    .chart-section-body { overflow: hidden; transition: max-height .3s ease, opacity .25s ease; max-height: 2000px; opacity: 1; }
    .chart-section.collapsed .chart-section-body { max-height: 0; opacity: 0; }

    /* Footer */
    .footer { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border); text-align: center; font-size: .75rem; color: var(--text-muted); }
  </style>
</head>
<body>
<div class="shell">

  <!-- Header -->
  <div class="page-header">
    <div>
      <h1>Job Search Dashboard</h1>
      <p style="font-size:.85rem;color:var(--text-muted);margin-top:.3rem">Data Science roles</p>
    </div>
    <div class="header-meta">
      <span class="header-badge" id="candidateBadge">Job Search</span>
      <span class="updated-label" id="updatedLabel"></span>
      <a id="sheetLink" href="#" target="_blank" class="sheet-link">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        Ver Sheet
      </a>
    </div>
  </div>

  <!-- KPI Cards -->
  <div class="kpi-grid">
    <div class="kpi-card accent-blue">
      <div class="kpi-label">Total analizadas</div>
      <div class="kpi-value" id="kpiTotal">—</div>
      <div class="kpi-sub" id="kpiTotalSub">—</div>
    </div>
    <div class="kpi-card accent-green">
      <div class="kpi-label">Fit Score promedio</div>
      <div class="kpi-value" id="kpiAvg">—</div>
      <div class="kpi-sub">Sobre ofertas activas</div>
    </div>
    <div class="kpi-card accent-yellow">
      <div class="kpi-label">Tasa Apply</div>
      <div class="kpi-value" id="kpiApplyRate">—</div>
      <div class="kpi-sub" id="kpiApplySub">—</div>
    </div>
    <div class="kpi-card accent-purple">
      <div class="kpi-label">Activas vs Total</div>
      <div class="kpi-value" id="kpiActiveRate">—</div>
      <div class="kpi-sub" id="kpiActiveSub">—</div>
    </div>
  </div>

  <!-- Global filter bar -->
  <div style="display:flex;align-items:center;justify-content:flex-end;gap:.5rem;margin-bottom:1rem">
    <span style="font-size:.78rem;color:var(--text-muted);font-weight:500">Apliqué</span>
    <select class="filter-select" id="filterApliqueQGlobal" onchange="setFilter('apliqueQ', this.value)">
      <option value="">Todos</option>
      <option value="Si">Sí</option>
      <option value="No">No</option>
      <option value="__empty__">Vacío</option>
    </select>
    <button class="clear-all-btn" id="globalClearAllBtn" onclick="clearAllFilters()" style="display:none">Limpiar todo</button>
  </div>

  <!-- Charts Row 1: Rec / Score / Timeline -->
  <div class="chart-section" id="sec-dist">
    <div class="chart-section-header" onclick="toggleSection('sec-dist')">
      <span class="chart-section-title">Distribución <span class="chart-section-hint">· click para filtrar · click múltiple para selección múltiple</span></span>
      <svg class="collapse-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <div class="chart-section-body">
      <div class="charts-grid">
        <div class="chart-card clickable" id="cardRec">
          <div class="chart-title-row">
            <span class="chart-title">Recommendation</span>
          </div>
          <div class="chart-wrap"><canvas id="chartRec"></canvas></div>
        </div>
        <div class="chart-card clickable" id="cardRanges">
          <div class="chart-title-row">
            <span class="chart-title">Distribución Fit Score</span>
          </div>
          <div class="chart-wrap"><canvas id="chartRanges"></canvas></div>
        </div>
        <div class="chart-card">
          <div class="chart-title-row">
            <span id="cardTimeline" class="chart-title" style="cursor:pointer;" title="Click para filtrar por semana">Aplicaciones por semana</span>
          </div>
          <div class="chart-wrap"><canvas id="chartTimeline"></canvas></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Charts Row 2: Role types / Modality -->
  <div class="chart-section" id="sec-roles">
    <div class="chart-section-header" onclick="toggleSection('sec-roles')">
      <span class="chart-section-title">Roles &amp; Modalidad <span class="chart-section-hint">· click para filtrar · click múltiple para selección múltiple</span></span>
      <svg class="collapse-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <div class="chart-section-body">
      <div class="charts-grid-2">
        <div class="chart-card clickable" id="cardRoles">
          <div class="chart-title-row">
            <span class="chart-title">Distribución por Tipo de Rol</span>
            <select class="skill-select" id="rolesFamilySelect" onchange="updateRolesChart(this.value)">
              <option value="__all__">Todas las familias</option>
            </select>
          </div>
          <div class="chart-wrap-tall"><canvas id="chartRoles"></canvas></div>
        </div>
        <div class="chart-card clickable" id="cardModality">
          <div class="chart-title-row">
            <span class="chart-title">Modalidad</span>
          </div>
          <div class="chart-wrap-tall"><canvas id="chartModality"></canvas></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Charts Row 3: Skills -->
  <div class="chart-section" id="sec-skills">
    <div class="chart-section-header" onclick="toggleSection('sec-skills')">
      <span class="chart-section-title">Top Skills</span>
      <svg class="collapse-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <div class="chart-section-body">
      <div class="charts-grid-full">
        <div class="chart-card">
          <div class="chart-title-row">
            <span class="chart-title">Top Skills</span>
            <div class="select-group">
              <div class="skills-type-checks">
                <label class="skill-check-label"><input type="checkbox" id="skillsCheckMust"   value="must"   checked onchange="updateSkillsChart()"> <span style="color:rgba(96,165,250,.9)">Must-Have</span></label>
                <label class="skill-check-label"><input type="checkbox" id="skillsCheckShould" value="should"         onchange="updateSkillsChart()"> <span style="color:rgba(52,211,153,.9)">Should</span></label>
                <label class="skill-check-label"><input type="checkbox" id="skillsCheckNice"   value="nice"           onchange="updateSkillsChart()"> <span style="color:rgba(251,191,36,.9)">Nice</span></label>
              </div>
              <select class="skill-select" id="skillsRoleSelect" onchange="updateSkillsChart()">
                <option value="__all__">Todos los roles</option>
              </select>
            </div>
          </div>
          <div class="chart-wrap-skills"><canvas id="chartSkills"></canvas></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Charts Row 4: Exp. Requirements (semantic themes) -->
  <div class="chart-section" id="sec-expreqs">
    <div class="chart-section-header" onclick="toggleSection('sec-expreqs')">
      <span class="chart-section-title">Top Exp. Requirements <span class="chart-section-hint">· se actualiza con los filtros activos</span></span>
      <svg class="collapse-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <div class="chart-section-body">
      <div class="tab-bar" style="margin-top:.5rem">
        <button id="expTab-all"         class="tab-btn tab-apply active" onclick="setExpTab('__all__')">Todas</button>
        <button id="expTab-apply"       class="tab-btn tab-apply"        onclick="setExpTab('apply')">✓ Apply <span class="tab-count" id="exp-count-apply"></span></button>
        <button id="expTab-conditional" class="tab-btn tab-cond"         onclick="setExpTab('conditional')">⚠ Conditional <span class="tab-count" id="exp-count-conditional"></span></button>
        <button id="expTab-skip"        class="tab-btn tab-skip"         onclick="setExpTab('skip')">✕ Skip <span class="tab-count" id="exp-count-skip"></span></button>
      </div>
      <div class="chart-card" style="margin-top:.75rem">
        <div style="display:flex;justify-content:flex-end;margin-bottom:.75rem">
          <select class="skill-select" id="expRoleSelect" onchange="renderExpChart()">
            <option value="__all__">Todos los roles</option>
          </select>
        </div>
        <div class="chart-wrap-tall"><canvas id="chartExpReqs"></canvas></div>
      </div>
    </div>
  </div>

  <!-- Interpretation Patterns Panel -->
  <div class="chart-section" id="sec-interp" style="margin-bottom:2.5rem">
    <div class="chart-section-header" onclick="toggleSection('sec-interp')">
      <span class="chart-section-title">Patrones en Interpretaciones <span class="chart-section-hint">· se actualiza con los filtros activos</span></span>
      <svg class="collapse-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <div class="chart-section-body">
      <div class="tab-bar" style="margin-top:.5rem">
        <button class="tab-btn tab-apply active" onclick="setInterpTab('apply')">
          ✓ Apply <span class="tab-count" id="interp-count-apply"></span>
        </button>
        <button class="tab-btn tab-cond" onclick="setInterpTab('conditional')">
          ⚠ Conditional <span class="tab-count" id="interp-count-conditional"></span>
        </button>
        <button class="tab-btn tab-skip" onclick="setInterpTab('skip')">
          ✕ Skip <span class="tab-count" id="interp-count-skip"></span>
        </button>
      </div>
      <div class="chart-card" style="margin-top:.75rem">
        <div class="chart-wrap-tall"><canvas id="chartInterp"></canvas></div>
      </div>
    </div>
  </div>

  <!-- Posting Intelligence -->
  <div class="chart-section" id="sec-posting" style="margin-bottom:2.5rem">
    <div class="chart-section-header" onclick="toggleSection('sec-posting')">
      <span class="chart-section-title">Posting Intelligence <span class="chart-section-hint">· antigüedad y competencia al momento del batch</span></span>
      <svg class="collapse-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <div class="chart-section-body">
      <div id="postingNoData" style="display:none;text-align:center;padding:2rem;color:var(--text-muted);font-size:.85rem">
        Sin datos de posting aún. Corré el backfill o procesá nuevas ofertas con /apply-all.
      </div>
      <div id="postingCharts">
        <!-- KPIs -->
        <div style="display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap">
          <div class="kpi-card" style="flex:1;min-width:140px">
            <div class="kpi-label">Avg. días publicado</div>
            <div class="kpi-value" id="postingAvgDays">—</div>
          </div>
          <div class="kpi-card" style="flex:1;min-width:140px">
            <div class="kpi-label">Avg. aplicantes</div>
            <div class="kpi-value" id="postingAvgApp">—</div>
          </div>
        </div>
        <!-- Charts -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
          <div class="chart-card" id="cardDpDist">
            <span class="chart-title">Antigüedad al momento del batch</span>
            <div class="chart-wrap"><canvas id="chartDpDist"></canvas></div>
          </div>
          <div class="chart-card" id="cardAppDist">
            <span class="chart-title">Aplicantes al momento del batch</span>
            <div class="chart-wrap"><canvas id="chartAppDist"></canvas></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Unified Offers Table -->
  <div style="margin-bottom:2.5rem">
    <div class="section-head">
      <div style="display:flex;align-items:center;gap:.75rem">
        <h2>Todas las Ofertas</h2>
        <span class="count-badge" id="activeCountBadge">—</span>
      </div>
    </div>
    <!-- Rec tabs -->
    <div class="tab-bar" style="margin-bottom:.75rem">
      <button class="tab-btn tab-apply active" id="tblTab-all"         onclick="setTableRec('__all__')">Todas</button>
      <button class="tab-btn tab-apply"         id="tblTab-apply"       onclick="setTableRec('apply')">✓ Apply</button>
      <button class="tab-btn tab-cond"          id="tblTab-conditional" onclick="setTableRec('conditional')">⚠ Conditional</button>
      <button class="tab-btn tab-skip"          id="tblTab-skip"        onclick="setTableRec('skip')">✕ Skip</button>
    </div>
    <!-- Filters -->
    <div class="filters-row">
      <input type="text"  class="search-box" id="searchActive"       placeholder="Buscar empresa…"    style="width:180px" oninput="setFilter('search', this.value)" />
      <input type="text"  class="search-box" id="filterRoleSearch"   placeholder="Buscar rol…"        style="width:180px" oninput="setTableFilter('tableRoleSearch', this.value)" />
      <select class="filter-select" id="filterTableRole" onchange="setTableFilter('tableRoleType', this.value)">
        <option value="__all__">Tipo de rol: Todos</option>
      </select>
      <select class="filter-select" id="filterApliqueQ" onchange="setFilter('apliqueQ', this.value)">
        <option value="">Apliqué: Todos</option>
        <option value="Si">Apliqué: Sí</option>
        <option value="No">Apliqué: No</option>
        <option value="__empty__">Apliqué: Vacío</option>
      </select>
      <select class="filter-select" id="filterAplicacion" onchange="setFilter('aplicacion', this.value)">
        <option value="">Aplicación: Todas</option>
        <option value="Web">Web</option>
        <option value="Sencilla LI">Sencilla LI</option>
        <option value="Contactado por LinkedIn">Contactado por LinkedIn</option>
        <option value="__empty__">Vacío</option>
      </select>
    </div>
    <!-- Active filter pills -->
    <div class="pills-row" id="pillsRow"></div>
    <div class="table-wrap">
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th style="width:120px">Empresa</th><th style="width:120px">Rol</th><th>Fecha</th><th>Score</th>
              <th>Rec.</th><th>Modalidad</th><th style="width:55px">Apliqué</th><th style="width:100px">Aplicación</th>
              <th>Interpretation</th><th>Fortalezas</th><th>Gaps</th>
            </tr>
          </thead>
          <tbody id="tbodyActive"></tbody>
        </table>
      </div>
      <div class="pagination" id="paginationActive"></div>
    </div>
  </div>

  <div class="footer">Auto-generated · Job Search Automation</div>

</div><!-- /shell -->

<script>
/*__JSDATA__*/

// ── State ──────────────────────────────────────────────────────────────────────
const state = {
  search:          '',
  recommendation:  new Set(),
  scoreRange:      new Set(),
  roleType:        new Set(),
  modality:        new Set(),
  selectedWeek:    new Set(),
  dpBucket:        new Set(),
  appBucket:       new Set(),
  apliqueQ:        '',
  aplicacion:      '',
  activePage:      1,
  interpTab:       'apply',
  expTab:          '__all__',
  tableRec:        '__all__',
  tableRoleType:   '__all__',
  tableRoleSearch: '',
};

const expandedRows = new Set();
let currentPageRows = [];

const PAGE_SIZE = 15;
const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

// Chart instances
let chartRec, chartRanges, chartTimeline, chartRoles, chartModality;
let chartSkills, chartExpReqs, chartInterp;
let chartDpDist, chartAppDist;

const COLORS_REC = [
  'rgba(74,222,128,.8)', 'rgba(250,204,21,.8)', 'rgba(248,113,113,.8)'
];
const COLORS_RANGES = [
  'rgba(248,113,113,.75)', 'rgba(251,146,60,.75)',
  'rgba(250,204,21,.75)',  'rgba(74,222,128,.75)', 'rgba(34,211,238,.75)',
];
const COLORS_ROLES_PALETTE = [
  'rgba(96,165,250,.8)', 'rgba(167,139,250,.8)', 'rgba(52,211,153,.8)',
  'rgba(251,191,36,.8)', 'rgba(251,113,133,.8)', 'rgba(34,211,238,.8)',
  'rgba(129,140,248,.8)','rgba(74,222,128,.8)',  'rgba(248,113,113,.8)',
  'rgba(250,204,21,.8)', 'rgba(196,181,253,.8)', 'rgba(110,231,183,.8)',
];
const COLORS_MODALITY_PALETTE = [
  'rgba(96,165,250,.8)', 'rgba(52,211,153,.8)', 'rgba(251,191,36,.8)',
  'rgba(167,139,250,.8)', 'rgba(248,113,113,.8)',
];

// Stopwords for interpretation keyword extraction (ES + EN)
const INTERP_STOPWORDS = new Set([
  'para','como','pero','con','una','los','las','del','que','este','esta','esto',
  'más','puede','tiene','muy','bien','hay','cuando','sobre','también','aunque',
  'desde','sido','está','hacia','nivel','área','forma','tanto','cada','todo',
  'todos','dicho','mismo','mientras','través','entre','donde','cual','porque',
  'sería','siendo','tener','hacer','haber','ahora','solo','además','antes',
  'algo','algún','perfil','cargo','puesto','aunque','seria','parte','mayor',
  'buena','buen','gran','tiene','queda','hace','falta','cuenta','campo',
  // English
  'that','this','with','from','have','they','their','there','will','been',
  'some','would','could','should','which','about','into','than','what','when',
  'where','while','other','more','also','only','very','well','most','good',
  'role','does','need','like','make','such','work','show','high','data','skill',
  'skills','years','year','strong','great','solid','good','team','position',
  'company','experience','candidate','profile',
]);

// ── Init ───────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('updatedLabel').textContent = 'Actualizado: ' + UPDATED;
  document.getElementById('sheetLink').href = SHEET_URL;

  initCharts();
  populateSelects();
  renderAll();
});

// ── KPIs (dynamic — recomputed on every filter change) ─────────────────────────
function updateKPIs() {
  const filtered  = DATA.filter(r => matchesFilters(r));
  const total     = filtered.length;
  const active    = filtered.filter(r => r.sheet === 'active');
  const skip      = filtered.filter(r => r.sheet === 'skip');
  const applyRows = active.filter(r => r.recommendation === 'apply');
  const condRows  = active.filter(r => r.recommendation === 'conditional');
  const scores    = active.map(r => r.scoreInt).filter(s => s !== null);
  const avgScore  = scores.length
    ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length * 10) / 10
    : 0;
  const applyRate  = total > 0 ? Math.round(applyRows.length / total * 1000) / 10 : 0;
  const activeRate = total > 0 ? Math.round(active.length  / total * 1000) / 10 : 0;

  document.getElementById('kpiTotal').textContent      = total;
  document.getElementById('kpiTotalSub').textContent   = active.length + ' activas · ' + skip.length + ' descartadas';
  document.getElementById('kpiAvg').textContent        = avgScore;
  document.getElementById('kpiApplyRate').textContent  = applyRate + '%';
  document.getElementById('kpiApplySub').textContent   = applyRows.length + ' apply · ' + condRows.length + ' conditional';
  document.getElementById('kpiActiveRate').textContent = activeRate + '%';
  document.getElementById('kpiActiveSub').textContent  = 'De las ' + total + ' ofertas analizadas';
}

// ── Collapsible sections ───────────────────────────────────────────────────────
function toggleSection(id) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle('collapsed');
}

// ── Charts ────────────────────────────────────────────────────────────────────
Chart.defaults.color       = '#94A3B8';
Chart.defaults.font.family = 'Inter, sans-serif';

// ── Posting Intelligence — bucket helpers ────────────────────────────────────
const DP_LABELS  = ['0–1', '2–3', '4–5', '6–7', '7+'];
const APP_LABELS = ['0–24', '25–49', '50–74', '75–99', '>100'];

function getDpBucket(dp) {
  if (dp === null || dp === undefined || dp === '') return null;
  const n = parseInt(dp); if (isNaN(n)) return null;
  if (n <= 1) return '0–1'; if (n <= 3) return '2–3';
  if (n <= 5) return '4–5'; if (n <= 7) return '6–7';
  return '7+';
}

function getAppBucket(raw) {
  if (!raw) return null;
  const s = String(raw).trim(); if (!s) return null;
  if (!/^\d+$/.test(s)) return '>100';
  const n = parseInt(s);
  if (n <= 24) return '0–24'; if (n <= 49) return '25–49';
  if (n <= 74) return '50–74'; if (n <= 99) return '75–99';
  return '>100';
}

// Dim non-selected colors, leaving selected bright
function dimColors(originals, activeSet, labels) {
  if (!activeSet || activeSet.size === 0) return labels.map((_, i) => originals[i % originals.length]);
  return labels.map((lbl, i) => {
    const match = activeSet.has(lbl) || activeSet.has((lbl || '').toLowerCase());
    if (match) return originals[i % originals.length];
    return originals[i % originals.length].replace(/[0-9.]+\)$/, '0.18)');
  });
}

// Tooltip callback that shows count + percentage of total in current dataset
function pctTooltip(label) {
  return {
    callbacks: {
      label: ctx => {
        const val   = ctx.raw || 0;
        const total = ctx.dataset.data.reduce((a, b) => a + (b || 0), 0);
        const pct   = total > 0 ? Math.round(val * 100 / total) : 0;
        return ` ${label}: ${val} (${pct}%)`;
      }
    }
  };
}

function initCharts() {
  const m = METRICS;

  // Recommendation donut
  chartRec = new Chart(document.getElementById('chartRec'), {
    type: 'doughnut',
    data: {
      labels: ['Apply', 'Conditional', 'Skip'],
      datasets: [{
        data: [m.apply_count, m.cond_count, m.skip_count],
        backgroundColor: [...COLORS_REC],
        borderColor:     ['#4ADE80','#FACC15','#F87171'],
        borderWidth: 1.5, hoverOffset: 6,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { padding: 16, boxWidth: 12 } },
        tooltip: pctTooltip('Ofertas'),
      },
      cutout: '62%',
      onClick: (event, elements) => {
        if (!elements.length) return;
        const lbl = chartRec.data.labels[elements[0].index].toLowerCase();
        if (state.recommendation.has(lbl)) state.recommendation.delete(lbl);
        else state.recommendation.add(lbl);
        state.activePage = state.skipPage = 1;
        renderAll();
      },
    }
  });

  // Score ranges bar
  chartRanges = new Chart(document.getElementById('chartRanges'), {
    type: 'bar',
    data: {
      labels: Object.keys(m.score_ranges),
      datasets: [{
        label: 'Ofertas',
        data:  Object.values(m.score_ranges),
        backgroundColor: [...COLORS_RANGES],
        borderRadius: 6, borderSkipped: false,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: pctTooltip('Ofertas') },
      scales: {
        x: { grid: { color: '#334155' }, ticks: { font: { size: 11 } } },
        y: { grid: { color: '#334155' }, ticks: { stepSize: 1, font: { size: 11 } } },
      },
      onClick: (event, elements) => {
        if (!elements.length) return;
        const lbl = chartRanges.data.labels[elements[0].index];
        if (state.scoreRange.has(lbl)) state.scoreRange.delete(lbl);
        else state.scoreRange.add(lbl);
        state.activePage = state.skipPage = 1;
        renderAll();
      },
    }
  });

  // Timeline bar (weekly)
  chartTimeline = new Chart(document.getElementById('chartTimeline'), {
    type: 'bar',
    data: {
      labels: m.timeline_labels,
      datasets: [{
        label: 'Ofertas', data: m.timeline_values,
        backgroundColor: 'rgba(96,165,250,.75)',
        borderRadius: 4, borderSkipped: false,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: pctTooltip('Ofertas') },
      scales: {
        x: { grid: { color: '#334155' }, ticks: { font: { size: 10 }, maxRotation: 45, minRotation: 30 } },
        y: { grid: { color: '#334155' }, ticks: { stepSize: 1, font: { size: 11 } } },
      },
      onClick: (event, elements) => {
        if (!elements.length) return;
        const lbl = chartTimeline.data.labels[elements[0].index];
        if (state.selectedWeek.has(lbl)) state.selectedWeek.delete(lbl);
        else state.selectedWeek.add(lbl);
        state.activePage = 1;
        renderAll();
      },
    }
  });

  // Role types bar (horizontal)
  const roleLabels = Object.keys(m.role_type_dist);
  const roleValues = Object.values(m.role_type_dist);
  const roleColors = roleLabels.map((_, i) => COLORS_ROLES_PALETTE[i % COLORS_ROLES_PALETTE.length]);
  chartRoles = new Chart(document.getElementById('chartRoles'), {
    type: 'bar',
    data: {
      labels: roleLabels,
      datasets: [{
        label: 'Ofertas', data: roleValues,
        backgroundColor: roleColors,
        borderRadius: 5, borderSkipped: false,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: pctTooltip('Ofertas') },
      scales: {
        x: { grid: { color: '#334155' }, ticks: { stepSize: 1, font: { size: 11 } } },
        y: { grid: { color: 'transparent' }, ticks: { font: { size: 11 } } },
      },
      onClick: (event, elements) => {
        if (!elements.length) return;
        const lbl = chartRoles.data.labels[elements[0].index];
        if (state.roleType.has(lbl)) state.roleType.delete(lbl);
        else state.roleType.add(lbl);
        state.activePage = state.skipPage = 1;
        renderAll();
      },
    }
  });

  // Modality donut
  const modLabels = Object.keys(m.modality_dist);
  const modValues = Object.values(m.modality_dist);
  const modColors = modLabels.map((_, i) => COLORS_MODALITY_PALETTE[i % COLORS_MODALITY_PALETTE.length]);
  chartModality = new Chart(document.getElementById('chartModality'), {
    type: 'doughnut',
    data: {
      labels: modLabels,
      datasets: [{
        data: modValues,
        backgroundColor: modColors,
        borderWidth: 1.5, hoverOffset: 6,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { padding: 14, boxWidth: 12 } },
        tooltip: pctTooltip('Ofertas'),
      },
      cutout: '55%',
      onClick: (event, elements) => {
        if (!elements.length) return;
        const lbl = chartModality.data.labels[elements[0].index];
        if (state.modality.has(lbl)) state.modality.delete(lbl);
        else state.modality.add(lbl);
        state.activePage = state.skipPage = 1;
        renderAll();
      },
    }
  });

  // Skills horizontal stacked bar (initial datasets populated by updateSkillsChart())
  chartSkills = new Chart(document.getElementById('chartSkills'), {
    type: 'bar',
    data: { labels: [], datasets: [] },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'bottom', labels: { padding: 12, boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${ctx.raw}`
          }
        }
      },
      scales: {
        x: { stacked: true, grid: { color: '#334155' }, ticks: { stepSize: 1, font: { size: 11 } } },
        y: { stacked: true, grid: { color: 'transparent' }, ticks: { font: { size: 11 } } },
      },
    }
  });

  // Exp. Requirements horizontal bar (populated dynamically by renderExpChart())
  chartExpReqs = new Chart(document.getElementById('chartExpReqs'), {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Frecuencia', data: [], backgroundColor: 'rgba(167,139,250,.75)', borderRadius: 4, borderSkipped: false }] },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: pctTooltip('Frecuencia') },
      scales: {
        x: { grid: { color: '#334155' }, ticks: { stepSize: 1, font: { size: 11 } } },
        y: { grid: { color: 'transparent' }, ticks: { font: { size: 11 } } },
      },
    }
  });

  // ── Posting Intelligence charts ──────────────────────────────────────────────
  if (POSTING.has_data) {
    document.getElementById('postingNoData').style.display  = 'none';
    document.getElementById('postingCharts').style.display  = 'block';

    document.getElementById('postingAvgDays').textContent = POSTING.avg_days_posted !== null ? POSTING.avg_days_posted + 'd' : '—';
    document.getElementById('postingAvgApp').textContent  = POSTING.avg_applicants  !== null ? POSTING.avg_applicants : '—';

    const _postingColors = [
      'rgba(34,211,238,.8)', 'rgba(74,222,128,.8)',
      'rgba(250,204,21,.8)', 'rgba(251,146,60,.8)', 'rgba(248,113,113,.8)'
    ];

    chartDpDist = new Chart(document.getElementById('chartDpDist'), {
      type: 'bar',
      data: {
        labels: DP_LABELS,
        datasets: [{
          label: 'Ofertas',
          data: DP_LABELS.map(l => (POSTING.dp_buckets[l] || 0)),
          backgroundColor: _postingColors.slice(),
          borderRadius: 4, borderSkipped: false,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ' ' + ctx.parsed.y + ' ofertas' } } },
        scales: {
          x: { grid: { color: '#334155' }, ticks: { font: { size: 11 } } },
          y: { grid: { color: '#334155' }, ticks: { stepSize: 1, font: { size: 11 } }, beginAtZero: true },
        },
        onClick: (event, elements) => {
          if (!elements.length) return;
          const lbl = chartDpDist.data.labels[elements[0].index];
          if (state.dpBucket.has(lbl)) state.dpBucket.delete(lbl);
          else state.dpBucket.add(lbl);
          state.activePage = state.skipPage = 1;
          renderAll();
        },
      }
    });

    chartAppDist = new Chart(document.getElementById('chartAppDist'), {
      type: 'bar',
      data: {
        labels: APP_LABELS,
        datasets: [{
          label: 'Ofertas',
          data: APP_LABELS.map(l => ((POSTING.app_buckets || {})[l] || 0)),
          backgroundColor: _postingColors.slice(),
          borderRadius: 4, borderSkipped: false,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ' ' + ctx.parsed.y + ' ofertas' } } },
        scales: {
          x: { grid: { color: '#334155' }, ticks: { font: { size: 11 } } },
          y: { grid: { color: '#334155' }, ticks: { stepSize: 1, font: { size: 11 } }, beginAtZero: true },
        },
        onClick: (event, elements) => {
          if (!elements.length) return;
          const lbl = chartAppDist.data.labels[elements[0].index];
          if (state.appBucket.has(lbl)) state.appBucket.delete(lbl);
          else state.appBucket.add(lbl);
          state.activePage = state.skipPage = 1;
          renderAll();
        },
      }
    });
  } else {
    document.getElementById('postingNoData').style.display  = 'block';
    document.getElementById('postingCharts').style.display  = 'none';
  }

  // Interpretation chart (initialized empty, populated by renderInterpretationChart)
  chartInterp = new Chart(document.getElementById('chartInterp'), {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Frecuencia', data: [], backgroundColor: 'rgba(74,222,128,.75)', borderRadius: 4, borderSkipped: false }] },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: pctTooltip('Frecuencia') },
      scales: {
        x: { grid: { color: '#334155' }, ticks: { stepSize: 1, font: { size: 11 } } },
        y: { grid: { color: 'transparent' }, ticks: { font: { size: 11 } } },
      },
    }
  });
}

// ── Populate selects ───────────────────────────────────────────────────────────
function populateSelects() {
  const selSkillsRole  = document.getElementById('skillsRoleSelect');
  const selExpRole     = document.getElementById('expRoleSelect');
  const selRolesFamily = document.getElementById('rolesFamilySelect');
  const selTableRole   = document.getElementById('filterTableRole');

  // Role types from skills data (base types, no seniority)
  const roleTypes = Object.keys(SKILLS_BY_ROLE).sort();
  roleTypes.forEach(rt => {
    [selSkillsRole, selExpRole].forEach(sel => {
      const opt = document.createElement('option');
      opt.value = rt; opt.textContent = rt;
      sel.appendChild(opt.cloneNode(true));
    });
  });

  // Family filter uses base role types too
  roleTypes.forEach(rt => {
    const opt = document.createElement('option');
    opt.value = rt; opt.textContent = rt;
    selRolesFamily.appendChild(opt);
  });

  // Table role type filter: derive from all DATA rows
  const tblRoleTypes = [...new Set(DATA.map(r => r.roleType))].sort();
  tblRoleTypes.forEach(rt => {
    if (!rt) return;
    const opt = document.createElement('option');
    opt.value = rt; opt.textContent = rt;
    selTableRole.appendChild(opt);
  });
}

// ── Skills chart update (multi-select, stacked) ────────────────────────────────
function updateSkillsChart() {
  const roleType = document.getElementById('skillsRoleSelect').value;
  const checks = [
    { id: 'skillsCheckMust',   key: 'must',   label: 'Must-Have', color: 'rgba(96,165,250,.8)',  allMap: METRICS.top_skills,  byRole: SKILLS_BY_ROLE },
    { id: 'skillsCheckShould', key: 'should', label: 'Should',    color: 'rgba(52,211,153,.8)',  allMap: METRICS.top_should,  byRole: SHOULD_BY_ROLE },
    { id: 'skillsCheckNice',   key: 'nice',   label: 'Nice',      color: 'rgba(251,191,36,.8)',  allMap: METRICS.top_nice,    byRole: NICE_BY_ROLE },
  ].filter(c => document.getElementById(c.id)?.checked);

  if (!checks.length) {
    chartSkills.data.labels   = [];
    chartSkills.data.datasets = [];
    chartSkills.update();
    return;
  }

  const dataMaps = checks.map(c => roleType === '__all__' ? c.allMap : (c.byRole[roleType] || {}));

  // Union of skill names, sorted by total frequency desc, top 15
  const totalBySkill = {};
  dataMaps.forEach(m => Object.entries(m).forEach(([s, v]) => { totalBySkill[s] = (totalBySkill[s] || 0) + v; }));
  const sortedSkills = Object.entries(totalBySkill)
    .sort((a, b) => b[1] - a[1]).slice(0, 15).map(e => e[0]).reverse();

  chartSkills.data.labels   = sortedSkills;
  chartSkills.data.datasets = checks.map((c, i) => ({
    label:           c.label,
    data:            sortedSkills.map(s => dataMaps[i][s] || 0),
    backgroundColor: c.color,
    borderRadius:    i === checks.length - 1 ? 4 : 0,
    borderSkipped:   false,
  }));
  chartSkills.update();
}

// ── Exp. Requirements chart: semantic themes ──────────────────────────────────
function computeExpThemes() {
  const roleType = document.getElementById('expRoleSelect').value;
  const recFilter = state.expTab;
  const counts = {};
  DATA
    .filter(r => {
      if (!matchesFiltersExcept(r, 'recommendation')) return false;
      if (recFilter !== '__all__' && r.recommendation !== recFilter) return false;
      if (roleType !== '__all__' && r.roleType !== roleType) return false;
      return true;
    })
    .forEach(r => {
      (r.expThemes || []).forEach(t => { counts[t] = (counts[t] || 0) + 1; });
    });
  return Object.entries(counts).sort((a, b) => b[1] - a[1]);
}

function renderExpChart() {
  const entries = computeExpThemes();
  const labels  = entries.map(e => e[0]).reverse();
  const values  = entries.map(e => e[1]).reverse();
  const tab     = state.expTab;
  const color   = tab === 'apply' ? 'rgba(74,222,128,.75)' :
                  tab === 'conditional' ? 'rgba(250,204,21,.75)' :
                  tab === 'skip' ? 'rgba(248,113,113,.75)' :
                  'rgba(167,139,250,.75)';
  chartExpReqs.data.labels                      = labels;
  chartExpReqs.data.datasets[0].data            = values;
  chartExpReqs.data.datasets[0].backgroundColor = color;
  chartExpReqs.update('none');

  // Update count badges
  ['apply', 'conditional', 'skip'].forEach(rec => {
    const count = DATA.filter(r => matchesFiltersExcept(r, 'recommendation') && r.recommendation === rec).length;
    const el = document.getElementById('exp-count-' + rec);
    if (el) el.textContent = '(' + count + ')';
  });
}

function setExpTab(tab) {
  state.expTab = tab;
  ['all', 'apply', 'conditional', 'skip'].forEach(r => {
    const btn = document.getElementById('expTab-' + r);
    if (btn) btn.classList.toggle('active', (r === 'all' ? '__all__' : r) === tab);
  });
  renderExpChart();
}

// ── Role family filter ─────────────────────────────────────────────────────────
function updateRolesChart(family) {
  _refreshRolesChart(family);
}

// Internal: recompute role chart data, optionally filtered by family
function _refreshRolesChart(family) {
  family = family !== undefined ? family : (document.getElementById('rolesFamilySelect')?.value || '__all__');
  const base    = DATA.filter(r => matchesFiltersExcept(r, 'roleType'));
  const roleDist = {};
  base.forEach(r => {
    if (family === '__all__' || r.roleType === family) {
      roleDist[r.roleFull] = (roleDist[r.roleFull] || 0) + 1;
    }
  });
  const entries    = Object.entries(roleDist).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const roleLabels = entries.map(e => e[0]);
  const roleColors = roleLabels.map((_, i) => COLORS_ROLES_PALETTE[i % COLORS_ROLES_PALETTE.length]);
  chartRoles.data.labels                      = roleLabels;
  chartRoles.data.datasets[0].data            = entries.map(e => e[1]);
  chartRoles.data.datasets[0].backgroundColor = dimColors(roleColors, state.roleType, roleLabels);
  document.getElementById('cardRoles').classList.toggle('filter-active', state.roleType.size > 0);
  chartRoles.update('none');
}

// ── Interpretation themes panel ───────────────────────────────────────────────
function computeInterpThemes(recFilter) {
  const counts = {};
  DATA
    .filter(r => matchesFiltersExcept(r, 'recommendation') && r.recommendation === recFilter)
    .forEach(r => {
      (r.interpThemes || []).forEach(t => { counts[t] = (counts[t] || 0) + 1; });
    });
  return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 15);
}

function renderInterpretationChart() {
  const tab      = state.interpTab;
  const entries  = computeInterpThemes(tab);
  const labels   = entries.map(e => e[0]).reverse();
  const values   = entries.map(e => e[1]).reverse();
  const color    = tab === 'apply' ? 'rgba(74,222,128,.75)' :
                   tab === 'conditional' ? 'rgba(250,204,21,.75)' :
                   'rgba(248,113,113,.75)';

  chartInterp.data.labels                       = labels;
  chartInterp.data.datasets[0].data             = values;
  chartInterp.data.datasets[0].backgroundColor  = color;
  chartInterp.update('none');

  // Update count badges in tabs
  ['apply', 'conditional', 'skip'].forEach(rec => {
    const count = DATA.filter(r => matchesFiltersExcept(r, 'recommendation') && r.recommendation === rec).length;
    const el = document.getElementById('interp-count-' + rec);
    if (el) el.textContent = '(' + count + ')';
  });
}

function setInterpTab(tab) {
  state.interpTab = tab;
  const tabClass  = tab === 'conditional' ? 'cond' : tab;
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelector('.tab-btn.tab-' + tabClass)?.classList.add('active');
  renderInterpretationChart();
}

// ── Cross-filtering ────────────────────────────────────────────────────────────
// Like matchesFilters but skips one filter dimension (for cross-filtering).
function matchesFiltersExcept(row, skipKey) {
  if (skipKey !== 'search' && state.search) {
    const q = state.search.toLowerCase();
    if (!row.company.toLowerCase().includes(q) &&
        !row.role.toLowerCase().includes(q) &&
        !row.interpretation.toLowerCase().includes(q)) return false;
  }
  if (skipKey !== 'recommendation' && state.recommendation.size > 0 && !state.recommendation.has(row.recommendation)) return false;
  if (skipKey !== 'scoreRange'     && state.scoreRange.size > 0     && !state.scoreRange.has(row.scoreRange))         return false;
  if (skipKey !== 'roleType'       && state.roleType.size > 0       && !state.roleType.has(row.roleFull))             return false;
  if (skipKey !== 'modality'       && state.modality.size > 0       && !state.modality.has(row.modality))             return false;
  if (skipKey !== 'selectedWeek'   && state.selectedWeek.size > 0   && !state.selectedWeek.has(_dateToWeekKey(row.date))) return false;
  if (skipKey !== 'apliqueQ' && state.apliqueQ) {
    if (state.apliqueQ === '__empty__') { if (row.apliqueQ) return false; }
    else if (row.apliqueQ !== state.apliqueQ) return false;
  }
  if (skipKey !== 'aplicacion' && state.aplicacion) {
    if (state.aplicacion === '__empty__') { if (row.aplicacion) return false; }
    else if (row.aplicacion !== state.aplicacion) return false;
  }
  if (skipKey !== 'dpBucket'  && state.dpBucket.size > 0  && !state.dpBucket.has(getDpBucket(row.daysPosted)))   return false;
  if (skipKey !== 'appBucket' && state.appBucket.size > 0 && !state.appBucket.has(getAppBucket(row.applicants))) return false;
  return true;
}

// Update all charts from filtered data. Each chart's data excludes its own filter dimension.
function updateChartsData() {
  const RANGE_KEYS = ['0-29', '30-49', '50-69', '70-89', '90-100'];

  // --- Recommendation donut ---
  const forRec    = DATA.filter(r => matchesFiltersExcept(r, 'recommendation'));
  const recCounts = { apply: 0, conditional: 0, skip: 0 };
  forRec.forEach(r => { if (r.recommendation in recCounts) recCounts[r.recommendation]++; });
  chartRec.data.datasets[0].data             = [recCounts.apply, recCounts.conditional, recCounts.skip];
  chartRec.data.datasets[0].backgroundColor  = dimColors(COLORS_REC, state.recommendation, ['apply', 'conditional', 'skip']);
  document.getElementById('cardRec').classList.toggle('filter-active', state.recommendation.size > 0);
  chartRec.update('none');

  // --- Score ranges bar ---
  const forRanges  = DATA.filter(r => matchesFiltersExcept(r, 'scoreRange'));
  const rangeCounts = Object.fromEntries(RANGE_KEYS.map(k => [k, 0]));
  forRanges.forEach(r => { if (r.scoreRange) rangeCounts[r.scoreRange]++; });
  chartRanges.data.datasets[0].data             = RANGE_KEYS.map(k => rangeCounts[k]);
  chartRanges.data.datasets[0].backgroundColor  = dimColors(COLORS_RANGES, state.scoreRange, RANGE_KEYS);
  document.getElementById('cardRanges').classList.toggle('filter-active', state.scoreRange.size > 0);
  chartRanges.update('none');

  // --- Timeline weekly (filters everything except selectedWeek itself) ---
  const forTL = DATA.filter(r => matchesFiltersExcept(r, 'selectedWeek'));
  const tlMap = {};
  forTL.forEach(r => {
    const key = _dateToWeekKey(r.date);
    if (key) tlMap[key] = (tlMap[key] || 0) + 1;
  });
  const tlEntries = Object.entries(tlMap).sort((a, b) => _weekKeyToMs(a[0]) - _weekKeyToMs(b[0]));
  const tlLabels = tlEntries.map(e => e[0]);
  chartTimeline.data.labels = tlLabels;
  chartTimeline.data.datasets[0].data = tlEntries.map(e => e[1]);
  chartTimeline.data.datasets[0].backgroundColor = dimColors(
    tlLabels.map(() => 'rgba(96,165,250,.75)'), state.selectedWeek, tlLabels
  );
  document.getElementById('cardTimeline').style.fontWeight = state.selectedWeek.size > 0 ? 'bold' : '';
  chartTimeline.update('none');

  // --- Role types bar ---
  _refreshRolesChart();

  // --- Modality donut ---
  const forMod  = DATA.filter(r => matchesFiltersExcept(r, 'modality'));
  const modDist = {};
  forMod.forEach(r => { const m = r.modality || 'Unknown'; modDist[m] = (modDist[m] || 0) + 1; });
  const modEntries = Object.entries(modDist).sort((a, b) => b[1] - a[1]);
  const modLabels  = modEntries.map(e => e[0]);
  const modColors  = modLabels.map((_, i) => COLORS_MODALITY_PALETTE[i % COLORS_MODALITY_PALETTE.length]);
  chartModality.data.labels                      = modLabels;
  chartModality.data.datasets[0].data            = modEntries.map(e => e[1]);
  chartModality.data.datasets[0].backgroundColor = dimColors(modColors, state.modality, modLabels);
  document.getElementById('cardModality').classList.toggle('filter-active', state.modality.size > 0);
  chartModality.update('none');

  // --- Antigüedad (Days Posted buckets) ---
  if (chartDpDist) {
    const _dpColors = ['rgba(34,211,238,.8)','rgba(74,222,128,.8)','rgba(250,204,21,.8)','rgba(251,146,60,.8)','rgba(248,113,113,.8)'];
    const forDp = DATA.filter(r => matchesFiltersExcept(r, 'dpBucket'));
    const dpCounts = Object.fromEntries(DP_LABELS.map(l => [l, 0]));
    forDp.forEach(r => { const b = getDpBucket(r.daysPosted); if (b) dpCounts[b]++; });
    chartDpDist.data.datasets[0].data = DP_LABELS.map(l => dpCounts[l]);
    chartDpDist.data.datasets[0].backgroundColor = dimColors(_dpColors, state.dpBucket, DP_LABELS);
    document.getElementById('cardDpDist').classList.toggle('filter-active', state.dpBucket.size > 0);
    chartDpDist.update('none');
  }

  // --- Aplicantes (Applicants buckets) ---
  if (chartAppDist) {
    const _appColors = ['rgba(34,211,238,.8)','rgba(74,222,128,.8)','rgba(250,204,21,.8)','rgba(251,146,60,.8)','rgba(248,113,113,.8)'];
    const forApp = DATA.filter(r => matchesFiltersExcept(r, 'appBucket'));
    const appCounts = Object.fromEntries(APP_LABELS.map(l => [l, 0]));
    forApp.forEach(r => { const b = getAppBucket(r.applicants); if (b) appCounts[b]++; });
    chartAppDist.data.datasets[0].data = APP_LABELS.map(l => appCounts[l]);
    chartAppDist.data.datasets[0].backgroundColor = dimColors(_appColors, state.appBucket, APP_LABELS);
    document.getElementById('cardAppDist').classList.toggle('filter-active', state.appBucket.size > 0);
    chartAppDist.update('none');
  }
}

// Helper: "2026-03-15" → "W12 09 Mar 2026" (ISO week key)
function _dateToWeekKey(dateStr) {
  if (!dateStr || dateStr.length < 10) return null;
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  // ISO week number
  const day = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = day.getUTCDay() || 7;
  day.setUTCDate(day.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(day.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((day - yearStart) / 86400000) + 1) / 7);
  // Monday of the week
  const monday = new Date(d);
  monday.setDate(d.getDate() - (d.getDay() || 7) + 1);
  const dd = String(monday.getDate()).padStart(2, '0');
  return `W${String(weekNo).padStart(2,'0')} ${dd} ${MONTH_NAMES[monday.getMonth()]} ${monday.getFullYear()}`;
}

// Helper: "W12 09 Mar 2026" → ms timestamp for sorting
function _weekKeyToMs(key) {
  try {
    const parts = (key || '').split(' ');
    // parts: ["W12", "09", "Mar", "2026"]
    return new Date(`${parts[2]} ${parts[1]}, ${parts[3]}`).getTime();
  } catch { return 0; }
}

// ── Filters ───────────────────────────────────────────────────────────────────
function setFilter(key, value) {
  state[key] = typeof value === 'string' ? value.trim() : value;
  state.activePage = 1;
  if (key === 'apliqueQ') {
    ['filterApliqueQ', 'filterApliqueQGlobal'].forEach(id => {
      const el = document.getElementById(id);
      if (el && el.value !== state[key]) el.value = state[key];
    });
  }
  renderAll();
}

function setTableFilter(key, value) {
  state[key] = typeof value === 'string' ? value.trim() : value;
  state.activePage = 1;
  renderTable('active');
  renderPills();
}

function setTableRec(rec) {
  state.tableRec = rec;
  state.activePage = 1;
  // Update tab active styles
  ['all', 'apply', 'conditional', 'skip'].forEach(r => {
    const btn = document.getElementById('tblTab-' + r);
    if (btn) btn.classList.toggle('active', (r === 'all' ? '__all__' : r) === rec);
  });
  renderTable('active');
  renderPills();
}

function clearFilter(key) {
  const setKeys = ['recommendation', 'scoreRange', 'roleType', 'modality', 'selectedWeek', 'dpBucket', 'appBucket'];
  if (setKeys.includes(key)) state[key] = new Set();
  else state[key] = (key === 'apliqueQ' || key === 'search' || key === 'aplicacion') ? '' : null;
  if (key === 'search')     document.getElementById('searchActive').value = '';
  if (key === 'apliqueQ') {
    document.getElementById('filterApliqueQ').value = '';
    document.getElementById('filterApliqueQGlobal').value = '';
  }
  if (key === 'aplicacion') document.getElementById('filterAplicacion').value = '';
  state.activePage = 1;
  renderAll();
}

function clearAllFilters() {
  state.search = state.apliqueQ = state.aplicacion = '';
  state.recommendation = new Set();
  state.scoreRange = new Set();
  state.roleType = new Set();
  state.modality = new Set();
  state.selectedWeek = new Set();
  state.dpBucket = new Set();
  state.appBucket = new Set();
  state.tableRec = '__all__';
  state.tableRoleType = '__all__';
  state.tableRoleSearch = '';
  document.getElementById('searchActive').value = '';
  document.getElementById('filterApliqueQ').value = '';
  document.getElementById('filterApliqueQGlobal').value = '';
  document.getElementById('filterAplicacion').value = '';
  document.getElementById('filterRoleSearch').value = '';
  document.getElementById('filterTableRole').value = '__all__';
  document.getElementById('rolesFamilySelect').value = '__all__';
  setTableRec('__all__');
  state.activePage = 1;
  renderAll();
}

// ── Filter pills ──────────────────────────────────────────────────────────────
const FILTER_LABELS = {
  recommendation: 'Rec',
  scoreRange:     'Score',
  roleType:       'Rol',
  modality:       'Modalidad',
  selectedWeek:   'Semana',
  apliqueQ:       'Apliqué',
  search:         'Buscar',
  aplicacion:     'Aplicación',
  dpBucket:       'Antigüedad',
  appBucket:      'Aplicantes',
};

function renderPills() {
  const container = document.getElementById('pillsRow');
  const pills = [];

  const checks = [
    { key: 'recommendation', val: state.recommendation },
    { key: 'scoreRange',     val: state.scoreRange },
    { key: 'roleType',       val: state.roleType },
    { key: 'modality',       val: state.modality },
    { key: 'selectedWeek',   val: state.selectedWeek },
    { key: 'apliqueQ',       val: state.apliqueQ },
    { key: 'search',         val: state.search },
    { key: 'aplicacion',     val: state.aplicacion },
    { key: 'dpBucket',       val: state.dpBucket },
    { key: 'appBucket',      val: state.appBucket },
  ];

  checks.forEach(({ key, val }) => {
    let displayVal;
    if (val instanceof Set) {
      if (val.size === 0) return;
      displayVal = [...val].join(', ');
    } else {
      if (!val) return;
      displayVal = val === '__empty__' ? 'Vacío' : val;
    }
    pills.push(
      `<span class="pill">${FILTER_LABELS[key]}: <strong>${displayVal}</strong>` +
      `<span class="pill-x" onclick="clearFilter('${key}')">✕</span></span>`
    );
  });

  if (pills.length > 1) {
    pills.push(`<button class="clear-all-btn" onclick="clearAllFilters()">Limpiar todo</button>`);
  }

  // Show/hide global clear-all button
  const globalClearBtn = document.getElementById('globalClearAllBtn');
  if (globalClearBtn) globalClearBtn.style.display = pills.length ? '' : 'none';

  container.innerHTML = pills.join('');
}

// ── Row matching ──────────────────────────────────────────────────────────────
function matchesFilters(row) {
  if (state.search) {
    const q = state.search.toLowerCase();
    if (!row.company.toLowerCase().includes(q) &&
        !row.role.toLowerCase().includes(q) &&
        !row.interpretation.toLowerCase().includes(q)) return false;
  }
  if (state.recommendation.size > 0 && !state.recommendation.has(row.recommendation)) return false;
  if (state.scoreRange.size > 0     && !state.scoreRange.has(row.scoreRange))         return false;
  if (state.roleType.size > 0       && !state.roleType.has(row.roleFull))             return false;
  if (state.modality.size > 0       && !state.modality.has(row.modality))             return false;
  if (state.selectedWeek.size > 0   && !state.selectedWeek.has(_dateToWeekKey(row.date))) return false;
  if (state.apliqueQ) {
    if (state.apliqueQ === '__empty__') { if (row.apliqueQ) return false; }
    else if (row.apliqueQ !== state.apliqueQ) return false;
  }
  if (state.aplicacion) {
    if (state.aplicacion === '__empty__') { if (row.aplicacion) return false; }
    else if (row.aplicacion !== state.aplicacion) return false;
  }
  if (state.dpBucket.size > 0  && !state.dpBucket.has(getDpBucket(row.daysPosted)))   return false;
  if (state.appBucket.size > 0 && !state.appBucket.has(getAppBucket(row.applicants))) return false;
  return true;
}

// ── Table rendering ───────────────────────────────────────────────────────────
function scoreChip(row) {
  const s = row.scoreInt;
  const cls = s === null ? '' : s >= 70 ? 'score-high' : s >= 50 ? 'score-mid' : 'score-low';
  return `<span class="score-chip ${cls}">${esc(row.score)}</span>`;
}

function recBadge(rec) {
  const cls = rec === 'apply' ? 'badge-apply' : rec === 'conditional' ? 'badge-cond' : 'badge-skip';
  return `<span class="badge ${cls}">${rec}</span>`;
}

function apliqueBadge(val) {
  if (!val) return '<span style="color:var(--text-muted)">—</span>';
  const cls = val.toLowerCase().startsWith('s') ? 'badge-si' : 'badge-no';
  return `<span class="badge ${cls}">${esc(val)}</span>`;
}

function esc(t) {
  return String(t || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function rowKey(row) {
  return row.company + '||' + row.role + '||' + (row.date || '');
}

function toggleRowByIndex(idx) {
  const row = currentPageRows[idx];
  if (!row) return;
  const key = rowKey(row);
  if (expandedRows.has(key)) expandedRows.delete(key);
  else expandedRows.add(key);
  renderTable();
}

function makeActiveRow(row, idx) {
  const key        = rowKey(row);
  const isExpanded = expandedRows.has(key);
  const expCls     = isExpanded ? ' row-expanded' : '';
  let html = `<tr class="data-row${expCls}" onclick="toggleRowByIndex(${idx})">
    <td class="col-company">${esc(row.company)}</td>
    <td class="col-role">${esc(row.role)}</td>
    <td class="col-date">${esc(row.date)}</td>
    <td class="col-score">${scoreChip(row)}</td>
    <td>${recBadge(row.recommendation)}</td>
    <td class="col-modality">${esc(row.modality)}</td>
    <td class="col-aplique">${apliqueBadge(row.apliqueQ)}</td>
    <td class="col-app">${esc(row.aplicacion)}</td>
    <td class="col-long">${esc(row.interpretation)}</td>
    <td class="col-long">${esc(row.strengths)}</td>
    <td class="col-long">${esc(row.gaps)}</td>
  </tr>`;
  if (isExpanded) {
    html += `<tr class="detail-row"><td colspan="11" class="detail-cell">
      <div class="detail-grid">
        <div><div class="detail-label">📋 Interpretation</div><div class="detail-text">${esc(row.interpretation) || '<em style="color:var(--text-muted)">—</em>'}</div></div>
        <div><div class="detail-label">✓ Fortalezas</div><div class="detail-text">${esc(row.strengths) || '<em style="color:var(--text-muted)">—</em>'}</div></div>
        <div><div class="detail-label">✕ Gaps</div><div class="detail-text">${esc(row.gaps) || '<em style="color:var(--text-muted)">—</em>'}</div></div>
      </div>
    </td></tr>`;
  }
  return html;
}

function makeSkipRow(row) {
  return `<tr>
    <td class="col-company">${esc(row.company)}</td>
    <td class="col-role">${esc(row.role)}</td>
    <td class="col-date">${esc(row.date)}</td>
    <td class="col-score">${scoreChip(row)}</td>
    <td class="col-modality">${esc(row.modality)}</td>
    <td class="col-long">${esc(row.interpretation)}</td>
    <td class="col-long">${esc(row.strengths)}</td>
    <td class="col-long">${esc(row.gaps)}</td>
  </tr>`;
}

function matchesTableFilters(row) {
  // Apply global filters first
  if (!matchesFilters(row)) return false;
  // Table-local: rec tab
  if (state.tableRec !== '__all__' && row.recommendation !== state.tableRec) return false;
  // Table-local: role type dropdown
  if (state.tableRoleType !== '__all__' && row.roleType !== state.tableRoleType) return false;
  // Table-local: role text search
  if (state.tableRoleSearch) {
    const q = state.tableRoleSearch.toLowerCase();
    if (!row.role.toLowerCase().includes(q)) return false;
  }
  return true;
}

function renderTable() {
  const page = state.activePage;
  const filtered = DATA.filter(r => matchesTableFilters(r));
  const total    = filtered.length;
  const pages    = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const cur      = Math.min(page, pages);
  state.activePage = cur;

  const start = (cur - 1) * PAGE_SIZE;
  const rows  = filtered.slice(start, start + PAGE_SIZE);

  document.getElementById('activeCountBadge').textContent = total;

  currentPageRows = rows;
  const tbody = document.getElementById('tbodyActive');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty-state">Sin registros para los filtros activos</td></tr>';
  } else {
    tbody.innerHTML = rows.map((r, i) => makeActiveRow(r, i)).join('');
  }

  // Pagination
  const pg = document.getElementById('paginationActive');
  pg.innerHTML = '';
  if (pages <= 1) return;

  const prev = document.createElement('button');
  prev.className = 'page-btn'; prev.textContent = '←'; prev.disabled = cur === 1;
  prev.onclick = () => { state.activePage--; renderTable(); };
  pg.appendChild(prev);

  const range = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - cur) <= 2) range.push(i);
    else if (range[range.length - 1] !== '…') range.push('…');
  }
  range.forEach(p => {
    if (p === '…') {
      const sp = document.createElement('span');
      sp.textContent = '…'; sp.style.cssText = 'color:var(--text-muted);padding:0 .25rem';
      pg.appendChild(sp);
    } else {
      const btn = document.createElement('button');
      btn.className = 'page-btn' + (p === cur ? ' active' : '');
      btn.textContent = p;
      btn.onclick = () => { state.activePage = p; renderTable(); };
      pg.appendChild(btn);
    }
  });

  const next = document.createElement('button');
  next.className = 'page-btn'; next.textContent = '→'; next.disabled = cur === pages;
  next.onclick = () => { state.activePage++; renderTable(); };
  pg.appendChild(next);
}

function renderAll() {
  renderTable();
  renderPills();
  updateChartsData();
  updateSkillsChart();
  renderExpChart();
  renderInterpretationChart();
  updateKPIs();
}
</script>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Leyendo datos del Google Sheet...")
    active, skip = fetch_data()
    print(f"  Active: {len(active)} filas | Skip: {len(skip)} filas")

    metrics = compute_metrics(active, skip)
    html    = generate_html(active, skip, metrics)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard generado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
