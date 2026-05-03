import json
import re
from io import BytesIO
from pypdf import PdfReader
from app.core.config import Settings
from app.core.groq_helpers import call_groq_with_fallback
from app.services.schedule_parsing.schemas import ParsedSchedule

_PROMPT_TEMPLATE = """You are a university schedule parser. Your goal is to extract scheduling block information from the provided raw text with 100% accuracy.

CRITICAL:
- Extract all courses, their instructors, days, start times, end times, sections, rooms, and subtypes (Lecture/Tutorial/Lab).
- Return ONLY a valid JSON object. No markdown, no explanation.
- Use this exact JSON structure:
{{
  "blockId": "string (Extract the block identifier like CS-JR-1A or similar if found, otherwise null)",
  "semester": "Fall 2025",
  "courses": [
    {{
      "courseName": "string",
      "instructor": "string (Use 'TBA' if not found)",
      "day": "string (Monday, Tuesday, etc. - Full name)",
      "start": "string (HH:mm - 24h format)",
      "end": "string (HH:mm - 24h format)",
      "section": "string",
      "room": "string",
      "subtype": "string (Lecture/Tutorial/Lab)"
    }}
  ]
}}

TEXT TO PARSE:
{raw_text}
"""

def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()

def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()

def parse_schedule_with_llm(settings: Settings, raw_text: str) -> ParsedSchedule:
    prompt = _PROMPT_TEMPLATE.format(raw_text=raw_text)

    completion = call_groq_with_fallback(
        settings=settings,
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("Empty model response")

    data = json.loads(_strip_json_fence(content))
    return ParsedSchedule.model_validate(data)
