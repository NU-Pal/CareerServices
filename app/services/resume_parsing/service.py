import json
import re
from io import BytesIO

from groq import Groq
from pypdf import PdfReader

from app.core.config import Settings
from app.core.groq_helpers import call_groq_with_fallback
from app.services.resume_parsing.schemas import ParsedResume

_PROMPT_TEMPLATE = """You are a professional resume parser. Your goal is to extract ALL information from the provided resume text with 100% accuracy.

CRITICAL:
- Extracts must be VERBATIM. Do NOT summarize. Do NOT change phrasing. Do NOT shorten.
- If ANY section (like Experience, Education, Projects) is MISSING from the resume, you MUST return an empty array [] or null for it. DO NOT hallucinate or pull text from other sections.
- For both 'experience[].bullets' and 'projects[].bullets', copy each bullet point verbatim exactly as written.
- If a project does not have bullets, use a single concise summary in 'description'.
- Return ONLY a valid JSON object — no markdown, no explanation, just raw JSON.

Return this exact JSON structure (use null for missing fields, empty arrays [] for missing lists):
{{
  "firstName": "string or null (Extract ONLY the first name. If NO name is found, return null. DO NOT use section headers like 'Professional Summary')",
  "lastName": "string or null (Extract ONLY the last name. If NO name is found, return null. DO NOT use section headers)",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "linkedIn": "string or null",
  "gitHub": "string or null",
  "website": "string or null",
  "summary": "string or null. Extract ONLY the text explicitly written under the 'Summary' or 'Profile' section. STOP at the next heading. If the section is empty or missing, return null. DO NOT summarize the resume yourself.",
  "technicalSkills": ["skill1", "skill2"],
  "softSkills": ["skill1", "skill2"],
  "experience": [
    {{
      "title": "string or null",
      "company": "string or null",
      "location": "string or null",
      "startDate": "string or null",
      "endDate": "string or null",
      "isCurrent": false,
      "bullets": ["bullet1", "bullet2"]
    }}
  ],
  "education": [
    {{
      "degree": "string or null",
      "field": "string or null",
      "institution": "string or null",
      "location": "string or null",
      "startDate": "string or null",
      "endDate": "string or null",
      "gpa": "string or null"
    }}
  ],
  "projects": [
    {{
      "name": "string or null",
      "description": "A single-string summary of the project. If already using bullets, this can be null or a brief overview.",
      "bullets": ["bullet1", "bullet2 (CRITICAL: COPY-PASTE character-for-character every detail. Do NOT rephrase.)"],
      "technologies": ["tech1", "tech2"],
      "link": "string or null (CRITICAL: Extract ONLY the actual URL. If the text says 'GitHub' find the URL associated with it. Do NOT return just 'GitHub' or 'View'.)"
    }}
  ],
  "certifications": ["cert1"],
  "languages": ["Arabic", "English"],
  "awards": ["award1"]
}}

RESUME TEXT:
{resume_text}
"""


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError("Could not extract text from PDF (empty or scanned image)")
    # 30 000 chars — enough for even very long CVs without cutting late sections
    return text[:30_000]


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _clean_link(link: str | None) -> str | None:
    if not link:
        return None
    # If LLM returns markdown [Text](URL), extract URL
    match = re.search(r"\]\((https?://[^\s\)]+)\)", link)
    if match:
        return match.group(1)
    
    # Simple regex to find the first string that looks like a URL or domain
    # and strip common junk
    link = link.strip().strip("()[]\"'")
    if " " in link:
        # If there's a space, try to find the part that looks like a domain
        parts = link.split()
        for p in parts:
            if "." in p and not p.endswith(".") and not p.startswith("."):
                return p.strip(".,")
    return link


def parse_resume_with_llm(settings: Settings, raw_text: str) -> ParsedResume:
    prompt = _PROMPT_TEMPLATE.format(resume_text=raw_text)

    completion = call_groq_with_fallback(
        settings=settings,
        model="llama-3.1-8b-instant",   # fast + accurate for structured extraction
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("Empty model response")

    data = json.loads(_strip_json_fence(content))

    # Build fullName from firstName + lastName if not present
    full = data.get("fullName") or ""
    first = data.get("firstName") or ""
    last = data.get("lastName") or ""
    if not full and (first or last):
        data["fullName"] = f"{first} {last}".strip()

    # Strip common LLM artifacts from name
    if data.get("fullName"):
        data["fullName"] = data["fullName"].replace("|", "").strip(" ,")

    # Clean project links
    if data.get("projects"):
        for p in data["projects"]:
            p["link"] = _clean_link(p.get("link"))

    return ParsedResume.model_validate(data)
