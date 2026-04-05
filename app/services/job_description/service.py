import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from groq import Groq

from app.core.config import Settings
from app.services.job_description.schemas import JobFitAnalysisData


async def fetch_job_page_text(url: str, timeout: float = 20.0) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CareerServices/1.0; +https://huggingface.co)",
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        html = r.text
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:25_000]


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


# --------------------------------------------------------------------------- #
# Step 1 prompt: lightweight JD extraction (runs on 8B model to save TPM)     #
# --------------------------------------------------------------------------- #
_JD_EXTRACTION_PROMPT = """You are a precise technical requirements extractor. Your ONLY job is to read the Job Description below and extract information WITHOUT losing or omitting any detail.

CRITICAL RULES:
- Copy EVERY technology, tool, language, framework, library, platform, methodology, and skill EXACTLY as written in the JD. Do NOT paraphrase, merge, or drop any keyword.
- List ALL requirements even if they seem minor or repeated.
- Preserve the exact names (e.g. "React.js" not "React", "PostgreSQL" not "SQL").
- Separate must-have from nice-to-have if explicitly stated; otherwise list everything under requirements.
- Include Job Title, Company Name, and Location if mentioned.
- CRITICAL: Use the actual Position Title as the JOB TITLE. Do NOT use generic placeholders.
- If the company name is missing, look for phrases like "Welcome to [Name]", "At [Name]", or "[Name] is seeking".
- Include experience level, education requirements, soft skills, domain context, and any tools/processes mentioned.

--- JOB TITLE ---
[exact title]

--- COMPANY NAME ---
[name if mentioned, else "Unknown"]

--- LOCATION ---
[location if mentioned]

--- REQUIRED SKILLS & TECHNOLOGIES (list every single one) ---
[exhaustive comma-separated list]

--- EXPERIENCE & SENIORITY ---
[exact wording from JD]

--- EDUCATION REQUIREMENTS ---
[exact wording from JD]

--- DOMAIN / INDUSTRY CONTEXT ---
[company domain, industry, product type]

--- RESPONSIBILITIES ---
[bullet list of all responsibilities mentioned]

--- NICE-TO-HAVE / PREFERRED ---
[list if mentioned, else write "Not specified"]

Job Description:
{job_text}
"""

# --------------------------------------------------------------------------- #
# Step 2 prompt: deep analysis (runs on 70B model)                             #
# --------------------------------------------------------------------------- #
_JOB_FIT_PROMPT = """You are an expert career analyst and talent evaluator with experience across ALL industries,
roles, and seniority levels — from internships to executive positions,
from software engineering to marketing, finance, design, operations, and beyond.

YOUR MISSION:
Carefully read the provided CV and Job Description, then produce a thorough, honest,
and highly specific Job Fit Analysis. You are NOT filling a template blindly —
you are THINKING like a senior hiring manager who has read thousands of CVs.

TONE & PERSPECTIVE (CRITICAL):
- You MUST speak DIRECTLY to the user as if you are having a 1-on-1 mentoring session.
- Use "you", "your CV", "your experience" instead of "the candidate", "the applicant", or "they".
- Every single field must be phrased as direct feedback to the user.

SCORING — use ONLY this strict weighted formula:
  - Skills match:         30%  → count matched vs total JD keywords
  - Experience match:     30%  → compare years/level required vs candidate actual
  - Domain/Industry fit:  20%  → how closely does background match this industry?
  - Credentials:          10%  → education level required vs candidate's current status
  - Day-1 Readiness:      10%  → can they contribute from day one?
overallScore = round((skills×0.3) + (experience×0.3) + (domain×0.2) + (credentials×0.1) + (readiness×0.1))

FIELD RULES:
- matchedSkills: List EVERY keyword/technology/tool that appears in BOTH the JD and the CV. Do NOT group. Include ALL.
- missingSkills: List EVERY keyword/technology/tool in the JD that does NOT appear in the CV. Include ALL.
- skillsNote: Format EXACTLY as 'AI Reviewed [Total] priority keywords and confirmed [Matched] as covered.'
- interviewFocus: Each item tied to real content in the JD or CV.
- suggestedLearning: Each item must name a SPECIFIC resource (course + platform + time estimate).
- redFlags: Short, plain sentence per concern. Empty array [] if none.
- recommendations: 3-5 HIGH-QUALITY, ACTIONABLE paragraphs addressing real gaps.

Candidate CV (structured text):
---
{resume_summary}
---

Job Description (extracted requirements):
---
{job_text}
---

RETURN ONLY VALID JSON — no markdown, no text outside JSON:
{{
  "jobTitle": "Official Job Title from JD",
  "companyName": "Company Name from JD",
  "overallScore": 0,
  "matchStatus": "<Strong match | Partial match | Stretch role>",
  "detailedSummary": "3-5 sentences speaking directly to the candidate using 'you'/'your'.",
  "breakdown": {{
    "skills":      0,
    "experience":  0,
    "domain":      0,
    "credentials": 0,
    "readiness":   0,
    "skillsNote":      "AI Reviewed X priority keywords and confirmed Y as covered.",
    "experienceNote":  "Your exact professional experience vs JD requirement.",
    "domainNote":      "Your industry/domain alignment.",
    "credentialsNote": "Your degree status vs JD requirements.",
    "matchedSkills": [{{"skill": "...", "evidence": "...", "level": "Exposure | Practical | Advanced"}}],
    "missingSkills": [{{"skill": "...", "importance": "Critical | High | Medium | Low", "fixable": "..."}}]
  }},
  "highlights": ["Unique strength 1", "Unique strength 2", "Unique strength 3"],
  "opportunities": ["Major gap 1 with why it matters", "Major gap 2"],
  "redFlags": ["Short concern sentence. Empty array if none."],
  "recommendations": ["3-5 focused paragraphs addressing gaps or career growth."],
  "actionPlan": [{{"targetGap": "...", "expectedImpact": "...", "priority": "Critical | High | Medium | Low", "status": "Do now | Do soon | Do later"}}],
  "interviewFocus": ["Specific preparation tip tied to real JD/CV content."],
  "suggestedLearning": ["Specific resource name on platform — addresses gap. Estimated time: X hours."]
}}
"""


def _call_groq(client: Groq, model: str, prompt: str, json_mode: bool, max_tokens: int) -> str:
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=max_tokens,
        **({"response_format": {"type": "json_object"}} if json_mode else {}),
    )
    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("Empty model response from Groq")
    return content


def analyze_job_fit_llm(
    settings: Settings,
    resume_summary: str,
    job_text: str,
) -> JobFitAnalysisData:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    client = Groq(api_key=settings.groq_api_key)

    # Step 1: Summarise / extract JD with fast 8B model (saves TPM)
    jd_extraction_prompt = _JD_EXTRACTION_PROMPT.format(job_text=job_text[:8_000])
    extracted_jd = _call_groq(client, "llama-3.1-8b-instant", jd_extraction_prompt, False, 1500)

    # Step 2: Deep analysis with powerful 70B model
    analysis_prompt = _JOB_FIT_PROMPT.format(
        resume_summary=resume_summary[:12_000],
        job_text=extracted_jd,
    )
    raw = _call_groq(client, "llama-3.3-70b-versatile", analysis_prompt, True, 4096)

    data = json.loads(_strip_json_fence(raw))
    return JobFitAnalysisData.model_validate(data)


def resume_to_text_blob(parsed: dict[str, Any]) -> str:
    parts: list[str] = []
    if parsed.get("fullName"):
        parts.append(f"Name: {parsed['fullName']}")
    if parsed.get("summary"):
        parts.append(f"Summary: {parsed['summary']}")
    if parsed.get("technicalSkills"):
        parts.append("Technical skills: " + ", ".join(parsed["technicalSkills"][:80]))
    if parsed.get("softSkills"):
        parts.append("Soft skills: " + ", ".join(parsed["softSkills"][:20]))
    if parsed.get("experience"):
        for ex in parsed["experience"][:12]:
            line = f"- {ex.get('title')} at {ex.get('company')}: " + " ".join(ex.get("bullets") or [])[:500]
            parts.append(line)
    if parsed.get("education"):
        for ed in parsed["education"][:6]:
            parts.append(f"- {ed.get('degree')} {ed.get('field')} @ {ed.get('institution')}")
    if parsed.get("projects"):
        for p in parsed["projects"][:8]:
            parts.append(f"Project {p.get('name')}: {p.get('description')}")
    if parsed.get("certifications"):
        parts.append("Certifications: " + ", ".join(parsed["certifications"][:10]))
    return "\n".join(parts)[:18_000]
