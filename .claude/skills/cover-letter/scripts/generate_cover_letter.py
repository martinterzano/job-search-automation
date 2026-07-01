"""
Tool: generate_cover_letter.py
Responsabilidad: Generar cover letter personalizada usando la API de Claude.
Input: análisis de la oferta, CV adaptado, contexto de la empresa
Output: texto de cover letter (250-350 palabras) + metadata
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic


ASSETS_DIR = Path(__file__).parents[4] / "assets"  # scripts/ > cover-letter/ > skills/ > .claude/ > project root
COVER_LETTERS_EXAMPLES_DIR = ASSETS_DIR / "cover_letters_examples"

LANGUAGE_NAMES = {
    "en": "inglés",
    "es": "español",
}

GREETINGS = {
    "en": "Dear {company} Hiring Team,",
    "es": "Estimado equipo de {company},",
}

SIGNATURES = {
    "en": "Wishing you a great day,",
    "es": "Que tengas un excelente día,",
}


def generate_cover_letter(
    analysis: dict,
    cv_adapted: dict,
    company_context: str,
    output_dir: str = "outputs",
    assets_dir: str | None = None,
) -> dict:
    """
    Genera una cover letter personalizada usando Claude.

    Args:
        analysis: dict con el análisis completo de la oferta
        cv_adapted: dict con el CV adaptado para esta empresa
        company_context: texto libre con información sobre la empresa
        output_dir: directorio raíz de outputs
        assets_dir: ruta alternativa al directorio assets/ (para tests)

    Returns:
        dict con la cover letter y metadata
    """
    company = analysis.get("company", "UNKNOWN")
    role = analysis.get("role", "UNKNOWN")
    language = analysis.get("language", "en")

    examples_dir = Path(assets_dir) / "cover_letters_examples" if assets_dir else COVER_LETTERS_EXAMPLES_DIR
    style_examples = _load_cover_letter_examples(examples_dir)

    prompt = _build_prompt(analysis, cv_adapted, company_context, style_examples, language=language)
    cover_letter_text = _call_claude(prompt)

    _validate_cover_letter(cover_letter_text)

    word_count = len(cover_letter_text.split())
    skills_mentioned = _find_mentioned_skills(
        cover_letter_text,
        analysis.get("skills", {}).get("must", []),
    )

    include_greeting = _is_traditional_company(company)
    output_path = _save_cover_letter(cover_letter_text, company, role, output_dir, include_greeting=include_greeting, language=language)

    result = {
        "company": company,
        "role": role,
        "date_generated": str(date.today()),
        "word_count": word_count,
        "skills_mentioned": skills_mentioned,
        "cover_letter_path": str(output_path),
        "cover_letter_text": cover_letter_text,
    }

    return result


def _load_cover_letter_examples(examples_dir: Path) -> str:
    """
    Carga las cartas de presentación modelo del candidato como referencia de estilo.
    Soporta .txt y .docx. Retorna string vacío si no hay ejemplos.
    """
    if not examples_dir.exists():
        return ""

    texts = []

    for txt_file in sorted(examples_dir.glob("*.txt")):
        try:
            content = txt_file.read_text(encoding="utf-8").strip()
            if content:
                texts.append(f"--- Ejemplo: {txt_file.name} ---\n{content}")
        except Exception:
            pass

    for docx_file in sorted(examples_dir.glob("*.docx")):
        try:
            from docx import Document
            doc = Document(str(docx_file))
            content = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            if content:
                texts.append(f"--- Ejemplo: {docx_file.name} ---\n{content}")
        except Exception:
            pass

    if not texts:
        return ""

    print(f"[generate_cover_letter] Cargados {len(texts)} ejemplo(s) de cartas modelo.")
    return "\n\n".join(texts)


def _build_prompt(analysis: dict, cv_adapted: dict, company_context: str, style_examples: str = "", language: str = "en") -> str:
    role = analysis.get("role", "")
    is_senior_role = "senior" in role.lower()
    must_skills = ", ".join(analysis.get("skills", {}).get("must", []))
    fit_score = analysis.get("fit_score", "N/A")
    strengths = ", ".join(analysis.get("strengths", []))

    experience_summary = _summarize_experience(cv_adapted.get("experience", []))
    senior_note = (
        "NOTA PARA ROL SENIOR: El título del rol contiene 'Senior'. "
        "La carta debe incluir obligatoriamente al menos una referencia a: liderazgo técnico, mentoring, "
        "ownership de scope ampliado, o coordinación cross-functional. Sin esto, la carta no posiciona al candidato para ese nivel.\n\n"
        if is_senior_role else ""
    )

    style_section = ""
    if style_examples:
        style_section = f"""
CARTAS MODELO DEL CANDIDATO (referencia de estilo y voz):
{style_examples}

INSTRUCCIÓN DE ESTILO: Analiza las cartas anteriores para captar el tono, estructura y voz del candidato.
Mantén coherencia con ese estilo. NO copies frases directamente, úsalas solo como referencia de personalidad.
"""

    language_name = LANGUAGE_NAMES.get(language, "inglés")

    return f"""Eres un especialista en redacción de cover letters para roles de Data Science.

Escribe una cover letter profesional y natural con las siguientes características:
- Extensión: entre 250 y 350 palabras (OBLIGATORIO)
- Tono: directo y personal, sin construcciones artificiales ni frases efectistas
- Estructura: presentación honesta del perfil → proyectos concretos con resultados → interés genuino en la empresa → llamado a la acción
- Idioma: {language_name} (el aviso original está en {language_name}; el documento debe estar íntegramente en {language_name}, sin mezclar idiomas)
- Candidate name: use the name from profile.json when referring to the candidate in the body
{style_section}
INFORMACIÓN DE CONTEXTO (úsala para razonar, NO para citar textualmente):
- Empresa: {analysis.get('company')}
- Rol: {analysis.get('role')}
- Capacidades técnicas relevantes: {must_skills}

PERFIL DEL CANDIDATO:
- Fortalezas: {strengths}
- Experiencia relevante: {experience_summary}
- Resumen profesional: {cv_adapted.get('summary', '')}
- Documented industries: use ONLY industries from the candidate's real experience in profile.json

CONTEXTO DE LA EMPRESA:
{company_context}

STYLE EXAMPLES (reference for tone and approach — replace with examples from writing_voice.md):
Use the tone and sentence structures documented in assets/knowledge_base/writing_voice.md.
Load that file for concrete examples of how the candidate writes.

OPENING RULE — CANDIDATE-CENTRIC:
- The first paragraph establishes who the candidate is and what they build. Does NOT start by citing the role or posting requirements.
- PROHIBITED PHRASES in the opening (and throughout the letter):
  * "caught my attention" / "stood out to me"
  * "The [Role] opening" / "the [Role] role at [Company]"
  * "I am looking for a role where..." (seguido de lo que ofrece el anuncio)
  * "This is exactly the kind of work I've been doing" / "This is the setup I know well"
  * Cualquier variante de "el rol me interesa porque [requisito del anuncio]"
- BIEN: Abrir con una afirmación sobre el trabajo real del candidato, luego conectar con la empresa por algo concreto y verificable (producto, escala, stack conocido, mercado).
- MAL: "[Company]'s [Role] opening caught my attention for its focus on [stack from job posting]. This is the kind of technical work I have been building at [prev company]." (espejea el anuncio)
- Si no hay datos concretos de la empresa más allá del job posting, abrir con una afirmación del candidato y mencionar a la empresa al final del primer párrafo.

CLOSING RULE — CANDIDATE-CENTRIC:
- The final paragraph expresses the candidate's direction (what they want to build, what kind of impact they seek, what excites them about the domain) followed by a call to action.
- PROHIBITED in the closing:
  * Describing what the role gives the candidate: "this project model fits my direction", "this type of work is what I've been building toward", "this is the kind of environment I'm looking for"
  * Repetir atributos o lenguaje del job posting como motivación de interés
- BIEN: Cerrar con la proyección del candidato (lo que quiere construir, impacto que busca) y un CTA directo.

REGLA DE REFERENCIAS A LA EMPRESA:
- Cuando se mencione a la empresa para expresar interés, usar algo real: escala, producto o servicio concreto, stack público, posición de mercado. NO usar descriptores del job posting ("diverse", "fast-growing", "impact-driven", "passionate team") ni repetir texto del anuncio.
- Si no hay contexto de empresa disponible más allá del anuncio, NO inventar atributos. Preferir narrativa centrada en el candidato.

RESTRICCIONES DE CONTENIDO (crítico — la carta no debe parecer generada por IA):
- NO referenciar ni parafrasear lo que dice el anuncio. Nunca escribas "buscan a alguien que...", "lo que [empresa] hace es...", ni cites frases del anuncio entre comillas
- NO empezar con aperturas retóricas o metafóricas ("Reading your job posting felt familiar", "The parallel is hard to ignore", etc.)
- NO describir lo que la empresa busca o necesita desde la perspectiva del anuncio. La conexión con sus necesidades la debe hacer el lector, no la carta
- NO usar frases que expliquen al reclutador por qué la experiencia es relevante: "directly applicable to", "aligned with", "which maps to", "equivalent to", "mirrors this role". Mostrar el trabajo concreto; dejar que el lector conecte
- NO usar ":" como separador de ideas en mitad de una frase
- NO cerrar con un listado seco de credenciales (máster, certificaciones, ciudad, disponibilidad)
- Al mencionar interés en la empresa, expresarlo desde las afinidades e intereses propios del candidato, sin reflejar los requisitos del anuncio
- NO fabricar ni adaptar las industrias de los proyectos del candidato para que suenen más relevantes al job posting. Solo usar las industrias listadas arriba (insurance, fintech, healthcare, retail, marketing). Si el rol es de otro sector, no cambiar la industria de los proyectos — la transferibilidad la conecta el lector.
- NO afirmar experiencia directa con herramientas o dominios que no están respaldados por al menos un proyecto concreto en el CV. Skills en riesgo: GenAI/RAG implementation, EU AI Act, MLflow, PySpark, Azure (sin proyecto), NLP en pipelines (sin proyecto), experimentación A/B. Si no hay proyecto que lo respalde, usar framing de aprendizaje en curso: "I am actively building experience with [skill]" — nunca como experiencia directa probada.
- Para A/B testing específicamente: nunca afirmar experiencia pasada ni frameworks diseñados. Si el rol lo requiere, indicar como aprendizaje: "I am actively building knowledge in experimentation frameworks as an extension of my analytics work."
- Para habilidades sin proyecto concreto: nunca escribir "I work daily with [skill]" ni equivalente. Usar "actively building experience with X" o "deepening my work in X as a natural extension of [related skill]".
- NO afirmar resultados de negocio que no están documentados en el perfil (reducciones de X%, mejoras de Y%). Describir el propósito del proyecto, no el resultado, si el resultado no está explícitamente cuantificado en los datos fuente.
- NO reflejar adjetivos del job posting como razón de interés. Si la oferta describe a la empresa como "diverse, passionate, results-oriented" — no usar esas palabras como razón de aplicar.
- NO incluir fecha en ninguna parte del documento (ni encabezado ni cuerpo).
- Para empresas con foco explícito en impacto social, inclusión financiera o misión: ampliar la narrativa de motivación genuina y reducir la densidad técnica en el primer y segundo párrafo.

RESTRICCIONES DE FORMATO:
- NO usar rayas ni guiones (—, –) como separadores dentro de una frase
- NO usar listas con "•" ni numeradas. Todo debe ser prosa corrida
- NO usar clichés ni frases de plantilla de IA: "apasionado", "trabajo en equipo", "orientado a resultados", "proactivo", "actionable insights", "data-driven decisions", "leveraging", "seamless", "robust", "production-quality", "proven track record", "from day one", "I thrive in", "contribute meaningfully", "welcome the opportunity to discuss", "human-centered approach", "rigour and pragmatism"
- NO usar primera persona más de 8 veces en total
- El título académico del candidato es siempre "Executive Master in Business Analytics" — nunca "ESADE MBA", "MBA" ni variante
- SÍ escribir en párrafos completos y fluidos, con transiciones naturales entre ideas
- SÍ describir proyectos con tecnologías específicas y resultados concretos o métricas cuando estén disponibles
- SÍ terminar con un llamado a la acción claro y directo — específico al rol, no una frase de plantilla

{senior_note}Escribe SOLO el cuerpo de la cover letter. NO incluyas saludo inicial, firma, despedida ('Wishing you a great day', 'Best regards', etc.), ni datos de contacto. La firma se agrega automáticamente por el sistema. Si incluyes firma en el cuerpo, aparecerá duplicada."""


def _call_claude(prompt: str) -> str:
    """Llama a la API de Claude para generar el texto."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no está configurada en .env")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _validate_cover_letter(text: str) -> None:
    """Valida que la cover letter cumple los criterios mínimos."""
    word_count = len(text.split())
    if word_count < 200:
        raise ValueError(f"Cover letter demasiado corta: {word_count} palabras (mínimo 250)")
    if word_count > 400:
        raise ValueError(f"Cover letter demasiado larga: {word_count} palabras (máximo 350)")


def _find_mentioned_skills(text: str, must_skills: list) -> list:
    text_lower = text.lower()
    return [skill for skill in must_skills if skill.lower() in text_lower]


def _summarize_experience(experience: list) -> str:
    if not experience:
        return "No especificada"
    summaries = []
    for exp in experience[:3]:  # Top 3 experiencias
        if isinstance(exp, dict):
            title = exp.get("title", "")
            company = exp.get("company", "")
            if title or company:
                summaries.append(f"{title} en {company}".strip(" en"))
    return "; ".join(summaries) if summaries else "No especificada"


def _is_traditional_company(company: str) -> bool:
    """
    Detecta si la empresa es un banco, aseguradora o corporación tradicional.
    Retorna True → formato con saludo formal.
    Retorna False → formato directo sin saludo (startups, consultoras, tech).
    """
    traditional_keywords = [
        "banco", "bank", "insurance", "aseguradora", "zurich", "sabadell",
        "caixabank", "mapfre", "sanitas", "axa", "allianz", "mutua",
        "bbva", "santander", "caixa", "ibercaja", "kutxabank", "unicaja",
        "repsol", "iberdrola", "endesa", "generali", "prudential",
    ]
    company_lower = company.lower()
    return any(kw in company_lower for kw in traditional_keywords)


def _save_cover_letter(text: str, company: str, role: str, output_dir: str, include_greeting: bool = True, language: str = "en") -> Path:
    """
    Guarda la cover letter como archivo .docx (single-column, Calibri 11pt).
    Cada párrafo del texto se convierte en un párrafo Word separado.
    include_greeting=True → saludo formal adaptado al idioma (bancos/corporaciones)
    include_greeting=False → formato directo sin saludo (startups/consultoras)
    language → determina el texto del saludo y la firma
    """
    from docx import Document
    from docx.shared import Pt

    company_clean = re.sub(r"[^\w]", "_", company).lower()
    role_clean = re.sub(r"[^\w]", "_", role).lower()[:30]

    company_dir = Path(output_dir) / company_clean
    company_dir.mkdir(parents=True, exist_ok=True)

    filename = f"cover_letter_{company_clean}_{role_clean}.docx"
    filepath = company_dir / filename

    doc = Document()
    # Remove default blank paragraph
    for p in doc.paragraphs:
        p._element.getparent().remove(p._element)

    # Set Normal style
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after  = Pt(6)

    # Set page margins (1 inch)
    from docx.shared import Inches
    sec = doc.sections[0]
    sec.top_margin    = Inches(1.0)
    sec.bottom_margin = Inches(1.0)
    sec.left_margin   = Inches(1.25)
    sec.right_margin  = Inches(1.25)

    def _add_para(text_content, space_after=Pt(6)):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = space_after
        r = p.add_run(text_content)
        r.font.name = "Calibri"
        r.font.size = Pt(11)
        return p

    # Greeting: formal for banks/corps, skipped for startups/consultancies
    if include_greeting:
        greeting_template = GREETINGS.get(language, GREETINGS["en"])
        _add_para(greeting_template.format(company=company), space_after=Pt(12))

    # Body paragraphs
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        for i, line in enumerate(lines):
            if i > 0:
                p.add_run().add_break()
            r = p.add_run(line.strip())
            r.font.name = "Calibri"
            r.font.size = Pt(11)

    # Signature — read candidate name from profile.json
    candidate_name = "Your Name"
    profile_path = Path(__file__).parents[4] / "profile.json"
    if profile_path.exists():
        try:
            import json as _json
            with open(profile_path, encoding="utf-8") as pf:
                profile = _json.load(pf)
            candidate_name = profile.get("name", candidate_name)
        except Exception:
            pass
    signature_line = SIGNATURES.get(language, SIGNATURES["en"])
    _add_para(signature_line, space_after=Pt(0))
    _add_para(candidate_name, space_after=Pt(0))

    doc.save(str(filepath))
    print(f"[generate_cover_letter] Guardado en: {filepath}")
    return filepath


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python generate_cover_letter.py <analysis.json> <cv_adapted.json> <company_context.txt>")
        sys.exit(1)

    analysis = load_json(sys.argv[1])
    cv_adapted = load_json(sys.argv[2])
    context_path = Path(sys.argv[3])
    company_context = context_path.read_text(encoding="utf-8") if context_path.exists() else ""

    result = generate_cover_letter(analysis, cv_adapted, company_context)
    print(json.dumps(result, ensure_ascii=False, indent=2))
