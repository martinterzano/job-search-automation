"""
update_tracker.py — Registra una postulación en Google Sheets (Job Applications Tracker).

Uso:
    python update_tracker.py <ruta_a_analysis.json>

Sheets:
  "Active"  → recommendation: apply | conditional
  "Skip"    → recommendation: skip

Columnas (21):
  Company | Role | Date | Fit Score | Recommendation |
  Language | Salary Range | Company Summary | Role Summary | Modality |
  Must Skills | Should Skills | Nice Skills | Exp. Requirements |
  Strengths | Gaps | Interpretation |
  Comments | Applied? | Application | Status

Primera ejecución (sin GOOGLE_SHEETS_SPREADSHEET_ID en .env):
  → Importa applications_tracker.xlsx a Drive como Google Sheet
  → Re-aplica colores a todas las filas existentes
  → Imprime la URL y el ID para guardar en .env
"""

import json
import os
import sys
from datetime import date as _date_cls
from pathlib import Path

# ── Dependencias opcionales (informar claramente si faltan) ───────────────────
try:
    import gspread
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError as e:
    print(
        f"ERROR: Dependencia faltante — {e}\n"
        "Instalar con: pip install gspread google-auth-oauthlib google-api-python-client"
    )
    sys.exit(1)

# ── Rutas ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT      = Path(__file__).parents[4]
XLSX_PATH         = PROJECT_ROOT / "applications_tracker.xlsx"
CREDENTIALS_PATH  = PROJECT_ROOT / "assets" / "google" / "credentials.json"
TOKEN_PATH        = PROJECT_ROOT / "assets" / "google" / "token.json"
ENV_PATH          = PROJECT_ROOT / ".env"

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

SHEET_MAP = {
    "apply":       "Active",
    "conditional": "Active",
    "skip":        "Skip",
}

# Colores RGB normalizados (0–1) para la Sheets API
ROW_COLORS = {
    "apply":       {"red": 0.776, "green": 0.937, "blue": 0.808},  # #C6EFCE
    "conditional": {"red": 1.0,   "green": 0.922, "blue": 0.612},  # #FFEB9C
    "skip":        {"red": 1.0,   "green": 0.780, "blue": 0.808},  # #FFC7CE
}

HEADER_BG_COLOR = {"red": 0.122, "green": 0.306, "blue": 0.475}   # #1F4E79


# ── Auth ──────────────────────────────────────────────────────────────────────

def _get_credentials() -> Credentials:
    """Obtiene credenciales OAuth2, refrescando o lanzando el flujo si es necesario."""
    if not CREDENTIALS_PATH.exists():
        print(
            f"ERROR: No se encontró {CREDENTIALS_PATH}\n"
            "Seguir las instrucciones en assets/google/SETUP.md"
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


# ── Helpers de formato ────────────────────────────────────────────────────────

def _color_row_request(sheet_id: int, row_index: int, color: dict) -> dict:
    """Genera un repeatCell request para colorear una fila completa (0-indexed)."""
    return {
        "repeatCell": {
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    row_index,
                "endRowIndex":      row_index + 1,
                "startColumnIndex": 0,
                "endColumnIndex":   len(HEADERS),
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": color
                }
            },
            "fields": "userEnteredFormat.backgroundColor",
        }
    }


def _header_format_requests(sheet_id: int) -> list:
    """Requests para formatear el header (fila 0): fondo azul, texto blanco bold."""
    return [
        {
            "repeatCell": {
                "range": {
                    "sheetId":          sheet_id,
                    "startRowIndex":    0,
                    "endRowIndex":      1,
                    "startColumnIndex": 0,
                    "endColumnIndex":   len(HEADERS),
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": HEADER_BG_COLOR,
                        "textFormat": {
                            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "bold": True,
                            "fontSize": 11,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment":   "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId":    sheet_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
    ]


def _sync_headers(ws, spreadsheet_id: str, service) -> None:
    """Actualiza la fila de encabezados si el Sheet tiene menos columnas que HEADERS."""
    current = ws.row_values(1)
    if current == HEADERS:
        return
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{ws.title}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [HEADERS]},
    ).execute()
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": _header_format_requests(ws.id)},
    ).execute()
    print(f"[sync_headers] Headers actualizados en sheet '{ws.title}'")


# ── Importación inicial desde xlsx ────────────────────────────────────────────

def _import_xlsx_to_drive(creds: Credentials) -> str:
    """
    Importa applications_tracker.xlsx a Google Drive como Google Sheet.
    Retorna el spreadsheet ID del archivo creado.
    """
    if not XLSX_PATH.exists():
        print(
            f"ERROR: No se encontró {XLSX_PATH} para importar.\n"
            "Asegurarse de que el tracker local existe antes del primer run."
        )
        sys.exit(1)

    print(f"Importando {XLSX_PATH.name} a Google Drive como Google Sheet...")

    drive_service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name":     "Job Applications Tracker",
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }
    media = MediaFileUpload(
        str(XLSX_PATH),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        resumable=False,
    )
    uploaded = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id,webViewLink",
    ).execute()

    spreadsheet_id = uploaded["id"]
    url            = uploaded["webViewLink"]
    print(f"Sheet creado exitosamente: {url}")
    print(f"\nSpreadsheet ID: {spreadsheet_id}")
    print("\nGuardar en .env:")
    print(f"  GOOGLE_SHEETS_SPREADSHEET_ID={spreadsheet_id}\n")

    return spreadsheet_id


def _recolor_existing_rows(service, spreadsheet_id: str, gc: gspread.Client) -> None:
    """Re-aplica colores a todas las filas de datos existentes según su Recommendation (col E)."""
    print("Aplicando colores a filas existentes...")
    spreadsheet = gc.open_by_key(spreadsheet_id)
    requests = []

    for sheet_name in ("Active", "Skip"):
        try:
            ws = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            continue

        sheet_id = ws.id
        # Re-aplicar formato de header
        requests.extend(_header_format_requests(sheet_id))

        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            continue

        # Col E (índice 4) es Recommendation
        for row_idx, row in enumerate(all_values[1:], start=1):
            rec = row[4].strip().lower() if len(row) > 4 else ""
            color = ROW_COLORS.get(rec)
            if color:
                requests.append(_color_row_request(sheet_id, row_idx, color))

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()
        print("Colores aplicados a filas existentes.")


# ── Carga del spreadsheet ID desde .env ──────────────────────────────────────

def _load_env() -> dict:
    """Lee el archivo .env y retorna un dict con las variables."""
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def _get_spreadsheet_id(creds: Credentials, gc: gspread.Client) -> str:
    """
    Retorna el spreadsheet ID desde .env.
    Si no existe, importa el xlsx local y retorna el ID recién creado.
    """
    env = _load_env()
    spreadsheet_id = env.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()

    if spreadsheet_id:
        return spreadsheet_id

    # Primera ejecución: importar xlsx
    spreadsheet_id = _import_xlsx_to_drive(creds)
    service = build("sheets", "v4", credentials=creds)
    _recolor_existing_rows(service, spreadsheet_id, gc)
    return spreadsheet_id


# ── Helpers de datos ──────────────────────────────────────────────────────────

def _to_sheets_date(date_str: str):
    """Convierte 'YYYY-MM-DD' al número serial de Google Sheets (días desde 1899-12-30).
    Escribir la fecha como número con formato DATE garantiza que sortRange ordene correctamente.
    """
    if not date_str:
        return ""
    try:
        d = _date_cls.fromisoformat(str(date_str).strip())
        return (d - _date_cls(1899, 12, 30)).days
    except (ValueError, AttributeError):
        return date_str  # fallback: escribir como texto si no se puede parsear


def join_list(items) -> str:
    if not items:
        return ""
    return ", ".join(str(x).strip() for x in items if x)


def _build_row(analysis: dict) -> tuple[list, str]:
    """Construye la fila de datos y retorna (row, recommendation)."""
    company      = analysis.get("company",        "Unknown")
    role         = analysis.get("role",           "Unknown")
    date         = _to_sheets_date(analysis.get("date_processed", ""))
    fit_score    = analysis.get("fit_score",      "")
    rec          = analysis.get("recommendation", "")
    language     = (analysis.get("language",  "") or "").upper()
    modality     = (analysis.get("modality",  "") or "").title()
    co_summary   = analysis.get("company_summary", "")
    role_summary = analysis.get("role_summary",    "")

    skills    = analysis.get("skills", {})
    must_sk   = join_list(skills.get("must",   []))
    should_sk = join_list(skills.get("should", []))
    nice_sk   = join_list(skills.get("nice",   []))

    exp_req  = analysis.get("experience_requirements", {})
    exp_str  = join_list(exp_req.get("must", []) + exp_req.get("should", []))

    strengths = join_list(analysis.get("strengths", []))

    gaps_data = analysis.get("gaps", {})
    gaps_str  = join_list(
        gaps_data.get("must",   []) +
        gaps_data.get("should", []) +
        gaps_data.get("nice",   [])
    )

    interpretation = analysis.get("interpretation", "")

    # Salary Posted: verbatim from posting, empty if not explicitly stated
    salary_raw = (analysis.get("salary", "") or "").strip()
    salary_posted = "" if not salary_raw or "no especif" in salary_raw.lower() else salary_raw

    # Salary Target: candidate's recommended conservative/mid ask range
    # Prefer dedicated field; fall back to salary_range for backward compat
    salary_target = (
        analysis.get("salary_target", "")
        or analysis.get("salary_range", "")
        or ""
    )

    days_posted     = analysis.get("days_posted", "")
    if days_posted is None:
        days_posted = ""
    applicants      = analysis.get("applicants_label", "") or ""

    row = [
        company, role, date, fit_score, rec,
        language, co_summary, role_summary, modality,
        must_sk, should_sk, nice_sk, exp_str,
        strengths, gaps_str, interpretation,
        salary_posted, salary_target,
        "", "", "", "",  # columnas manuales — siempre vacías
        days_posted, applicants,
    ]
    return row, rec


# ── Función principal ─────────────────────────────────────────────────────────

def _resolve_language(analysis: dict, analysis_path: Path) -> str:
    """
    Intenta obtener el idioma de la postulación.
    Orden de búsqueda:
      1. Campo 'language' en analysis.json
      2. Campo 'language' en el cv json del mismo directorio (cv_*.json)
      3. Cadena vacía
    """
    lang = (analysis.get("language", "") or "").strip().upper()
    if lang:
        return lang

    parent = analysis_path.parent
    cv_files = sorted(parent.glob("cv_*.json"))
    for cv_file in cv_files:
        try:
            with open(cv_file, encoding="utf-8") as f:
                cv_data = json.load(f)
            lang = (cv_data.get("language", "") or "").strip().upper()
            if lang:
                return lang
        except Exception:
            continue

    return ""


def append_row(analysis_path: Path) -> None:
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    # Inyectar language desde cv json si no está en analysis
    if not analysis.get("language"):
        analysis["language"] = _resolve_language(analysis, analysis_path)

    row, rec = _build_row(analysis)
    target_sheet = SHEET_MAP.get(rec.lower(), "Active")

    # Auth
    creds = _get_credentials()
    gc    = gspread.authorize(creds)

    # Spreadsheet (importar si es la primera vez)
    spreadsheet_id = _get_spreadsheet_id(creds, gc)
    spreadsheet    = gc.open_by_key(spreadsheet_id)

    # Asegurarse de que la sheet destino existe
    try:
        ws = spreadsheet.worksheet(target_sheet)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=target_sheet, rows=1000, cols=len(HEADERS))
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
        # Formatear header
        service = build("sheets", "v4", credentials=creds)
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": _header_format_requests(ws.id)},
        ).execute()

    # Contar filas antes del append para saber el índice exacto de la nueva fila
    rows_before = len(ws.get_all_values())

    # Escribir fila en rango explícito (evita el bug de gspread que desplaza columnas)
    target_row_1indexed = rows_before + 1
    service = build("sheets", "v4", credentials=creds)
    _sync_headers(ws, spreadsheet_id, service)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{target_sheet}'!A{target_row_1indexed}",
        valueInputOption="USER_ENTERED",
        body={"values": [row]},
    ).execute()

    requests = []

    # Aplicar formato DATE a la celda Date (col C, índice 2) de la nueva fila
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId":          ws.id,
                "startRowIndex":    rows_before,
                "endRowIndex":      rows_before + 1,
                "startColumnIndex": 2,
                "endColumnIndex":   3,
            },
            "cell": {
                "userEnteredFormat": {
                    "numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}
                }
            },
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # Colorear la nueva fila según recommendation
    color = ROW_COLORS.get(rec.lower())
    if color:
        requests.append(_color_row_request(ws.id, rows_before, color))

    # Ordenar toda la sheet por Date desc + Fit Score desc
    # Ahora todas las fechas son tipo DATE → sortRange funciona correctamente
    rows_after = rows_before + 1
    requests.append({
        "sortRange": {
            "range": {
                "sheetId":          ws.id,
                "startRowIndex":    1,          # skip header
                "endRowIndex":      rows_after,
                "startColumnIndex": 0,
                "endColumnIndex":   len(HEADERS),
            },
            "sortSpecs": [
                {"dimensionIndex": 2, "sortOrder": "DESCENDING"},  # Date (col C)
                {"dimensionIndex": 3, "sortOrder": "DESCENDING"},  # Fit Score (col D)
            ],
        }
    })

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    company   = analysis.get("company", "?")
    role      = analysis.get("role",    "?")
    print(f"Tracker actualizado [{target_sheet}] — {company} / {role}")
    print(f"Sheet: {sheet_url}")


# ── Backfill: parchear filas existentes ──────────────────────────────────────

def patch_row(analysis_path: Path) -> bool:
    """
    Actualiza solo las columnas Days Posted / Applicants en la fila de Google
    Sheets que corresponde a analysis_path.

    Busca la fila por Company (col A) + Role (col B) en la sheet correspondiente.
    Retorna True si encontró y actualizó la fila, False si no la encontró.
    """
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    company     = analysis.get("company", "")
    role        = analysis.get("role",    "")
    rec         = analysis.get("recommendation", "apply").lower()
    target_sheet = SHEET_MAP.get(rec, "Active")

    days_posted  = analysis.get("days_posted",     "")
    if days_posted is None:
        days_posted = ""
    applicants   = analysis.get("applicants_label", "") or ""

    creds = _get_credentials()
    gc    = gspread.authorize(creds)
    spreadsheet_id = _get_spreadsheet_id(creds, gc)
    spreadsheet    = gc.open_by_key(spreadsheet_id)

    try:
        ws = spreadsheet.worksheet(target_sheet)
    except gspread.WorksheetNotFound:
        return False

    all_values = ws.get_all_values()
    if not all_values:
        return False

    # Encontrar la fila por Company + Role (comparación case-insensitive)
    row_index = None
    for i, row in enumerate(all_values[1:], start=2):  # 1-indexed, skip header
        if (row[0].strip().lower() == company.lower() and
                row[1].strip().lower() == role.lower()):
            row_index = i
            break

    if row_index is None:
        return False

    # HEADERS tiene 24 items; Days Posted = índice 22 → col W (1-indexed)
    col_days       = 23  # col W
    col_applicants = 24  # col X

    ws.update_cell(row_index, col_days,       days_posted)
    ws.update_cell(row_index, col_applicants, applicants)

    print(f"[patch_row] Actualizado {company} / {role} — days={days_posted} | applicants={applicants}")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python update_tracker.py <ruta_a_analysis.json>")
        sys.exit(1)

    analysis_path = Path(sys.argv[1])
    if not analysis_path.is_absolute():
        analysis_path = PROJECT_ROOT / analysis_path

    if not analysis_path.exists():
        print(f"ERROR: No se encontró el archivo {analysis_path}")
        sys.exit(1)

    append_row(analysis_path)
