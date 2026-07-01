# Setup: Google Sheets Tracker

Instrucciones para conectar el tracker al Google Drive. Es un proceso de una sola vez (~10 minutos).

---

## Paso 1 — Crear proyecto en Google Cloud Console

1. Ir a [console.cloud.google.com](https://console.cloud.google.com)
2. Click en el selector de proyecto (arriba a la izquierda) → **New Project**
3. Nombre: `job-search-tracker` → **Create**
4. Asegurarse de tener el nuevo proyecto seleccionado en el selector

---

## Paso 2 — Habilitar las APIs necesarias

En el menú lateral: **APIs & Services → Library**

Buscar y habilitar:
- **Google Sheets API** → Enable
- **Google Drive API** → Enable

---

## Paso 3 — Configurar OAuth Consent Screen

En el menú lateral: **APIs & Services → OAuth consent screen**

1. User Type: **External** → Create
2. App name: `job-tracker-local`
3. User support email: tu email de Gmail
4. Developer contact email: tu email de Gmail
5. Click **Save and Continue** en todos los pasos (Scopes y Test Users pueden dejarse por defecto)
6. En la pantalla final, ir a **Test users** → **Add users** → agregar tu email de Gmail
7. **Save**

---

## Paso 4 — Crear credenciales OAuth

En el menú lateral: **APIs & Services → Credentials**

1. Click **+ Create Credentials → OAuth client ID**
2. Application type: **Desktop app**
3. Name: `job-tracker-local`
4. Click **Create**
5. En el popup: **Download JSON**
6. Renombrar el archivo descargado a `credentials.json`
7. Mover a: `assets/google/credentials.json` (este directorio)

---

## Paso 5 — Primera ejecución (autorización)

Instalar dependencias si no están instaladas:
```bash
pip install gspread google-auth-oauthlib google-api-python-client
```

Correr el tracker con cualquier analysis.json existente:
```bash
python .claude/skills/apply/scripts/update_tracker.py outputs/applied/Accenture_Data_Scientist/analysis.json
```

- Se abrirá el browser automáticamente
- Iniciar sesión con tu cuenta de Gmail
- Click **Allow** en los permisos solicitados
- El browser mostrará "Authentication successful" → cerrar

El script:
1. Importa el `applications_tracker.xlsx` local a Google Drive como Google Sheet
2. Re-aplica colores a todas las filas históricas
3. Agrega la nueva fila con su color correspondiente
4. Imprime la URL y el Spreadsheet ID

---

## Paso 6 — Guardar el Spreadsheet ID en .env

Copiar el ID que imprimió el script (la parte larga de la URL entre `/d/` y `/edit`) y pegarlo en `.env`:

```bash
GOOGLE_SHEETS_SPREADSHEET_ID=1ABC...xyz
```

A partir de ahora, todos los runs futuros se conectarán directamente a ese Sheet sin volver a pedir autorización.

---

## Archivos generados (no versionar)

```
assets/google/credentials.json   ← descargado de Google Cloud Console
assets/google/token.json         ← generado automáticamente en el primer run
```

Ambos están en `.gitignore`. Nunca commitear ni compartir estos archivos.
