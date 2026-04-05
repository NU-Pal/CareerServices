import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from groq import Groq

from app.core.config import Settings, get_settings
from app.core.security import require_service_api_key
from app.services.ai_interview.posture import merge_posture_into_feedback
from app.services.ai_interview.schemas import (
    GenerateFeedbackRequest,
    GenerateQuestionsRequest,
    VoiceAgentRequest,
)

router = APIRouter(prefix="/interview", tags=["interview"])


@router.get("/voice-agent")
async def voice_agent_get_api_key(
    _: Annotated[None, Depends(require_service_api_key)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Same contract as legacy GET /api/interview/voice-agent — returns Deepgram client key."""
    if not settings.deepgram_api_key:
        raise HTTPException(status_code=503, detail="DEEPGRAM_API_KEY is not configured")
    return {"success": True, "apiKey": settings.deepgram_api_key}


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


@router.post("/generate-questions")
async def generate_questions(
    _: Annotated[None, Depends(require_service_api_key)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: GenerateQuestionsRequest,
) -> dict[str, Any]:
    if not body.topic or not isinstance(body.topic, str):
        raise HTTPException(status_code=400, detail="Topic is required")
    interview_api_key = settings.groq_api_key_2 or settings.groq_api_key
    if not interview_api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured on the server")

    count = min(10, max(1, int(body.questionCount or 5)))
    difficulty_context: dict[str, str] = {
        "beginner": "entry-level, basic questions focusing on fundamentals",
        "intermediate": "mid-level questions requiring practical experience",
        "advanced": "senior-level questions testing deep expertise and leadership",
    }
    diff_key = body.difficulty or "intermediate"
    if diff_key == "mid":
        diff_key = "intermediate"
    elif diff_key == "entry":
        diff_key = "beginner"
    elif diff_key == "senior":
        diff_key = "advanced"
    ctx = difficulty_context.get(diff_key, difficulty_context["intermediate"])

    prompt = f"""Generate {count} interview questions for a {body.topic} position ({diff_key} level).

Context: {ctx}

For each question, provide:
1. The question text
2. A category (e.g., Technical, Behavioral, Situational, Problem-Solving)
3. Optional context or scenario setup

Return ONLY valid JSON in this format:
[
  {{
    "question": "Question text here",
    "category": "Category name",
    "context": "Optional context or scenario"
  }}
]"""

    client = Groq(api_key=interview_api_key)
    completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert recruiter and interview coach. "
                    "Generate realistic, relevant interview questions. Return only valid JSON array."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        model=settings.groq_model,
        temperature=0.7,
        max_tokens=2000,
    )
    response = completion.choices[0].message.content
    if not response:
        raise HTTPException(status_code=502, detail="Empty model response")
    questions = json.loads(_strip_json_fence(response))
    if not isinstance(questions, list):
        raise HTTPException(status_code=502, detail="Invalid questions format")
    return {"success": True, "questions": questions}


@router.post("/generate-feedback")
async def generate_feedback(
    _: Annotated[None, Depends(require_service_api_key)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: GenerateFeedbackRequest,
) -> dict[str, Any]:
    interview_api_key = settings.groq_api_key_2 or settings.groq_api_key
    if not interview_api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured on the server")
    if not body.topic or not isinstance(body.questions, list) or not isinstance(body.answers, list):
        raise HTTPException(status_code=400, detail="topic, questions[], and answers[] are required")

    body_note = ""
    if isinstance(body.bodyLanguageSummary, str) and body.bodyLanguageSummary.strip():
        body_note = (
            "\n\nWebcam pose summary (approximate, from MediaPipe — use as soft signal only):\n"
            + body.bodyLanguageSummary.strip()
        )

    answers_text = "\n\n".join(
        f"Q{i + 1}: {(a.get('question') if isinstance(a, dict) else '') or ''}\nAnswer: "
        f"{(a.get('answer') if isinstance(a, dict) else '') or '(no answer)'}"
        for i, a in enumerate(body.answers)
    )

    prompt = f"""Analyze this interview practice session for a {body.topic} position ({body.difficulty or 'intermediate'} level).

{answers_text}
{body_note}

Provide constructive feedback in JSON format:
{{
  "overall": "2-3 sentence assessment: lead with answers; use POSE METRICS only if present — follow RULES in that block, no generic body-language praise.",
  "bodyLanguageComment": "3-5 sentences. When POSE METRICS exist, cite averages or percentages. Do NOT claim strong eye contact unless metrics allow. If NO_POSE_DATA, state posture was not measured.",
  "questionFeedback": [
    {{
      "question": "Question text",
      "strengths": "What was done well",
      "improvements": "What could be improved"
    }}
  ],
  "recommendations": [
    "Specific actionable recommendation 1",
    "Specific actionable recommendation 2",
    "Specific actionable recommendation 3"
  ],
  "scores": {{
    "technical": 0,
    "communication": 0,
    "presence": 0
  }}
}}

Rules: scores are integers 0-100. "presence" must align with pose metrics when provided (lower if facing/symmetry/headPitch averages are poor per RULES in the metrics block).

Return ONLY the JSON object, no markdown formatting."""

    client = Groq(api_key=interview_api_key)
    completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a rigorous interview coach. You do not contradict numeric pose data with vague compliments. "
                    "Return only valid JSON without markdown code blocks."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        model=settings.groq_model,
        temperature=0.35,
        max_tokens=3000,
    )
    response = completion.choices[0].message.content or ""
    response = _strip_json_fence(response.replace("```json\n", "").replace("```", ""))
    feedback = json.loads(response)
    if isinstance(feedback, dict):
        merge_posture_into_feedback(feedback, body.bodyLanguageMetrics)
    return {"success": True, "feedback": feedback}


@router.post("/voice-agent")
async def voice_agent(
    _: Annotated[None, Depends(require_service_api_key)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: VoiceAgentRequest,
) -> dict[str, Any]:
    difficulty_map = {"entry": "entry-level", "mid": "mid-level", "senior": "senior-level"}

    if body.action == "start":
        if not settings.deepgram_api_key:
            raise HTTPException(status_code=503, detail="DEEPGRAM_API_KEY is not configured")
        fd = body.formData or {}
        level = difficulty_map.get(str(fd.get("difficulty")), "") or fd.get("difficulty") or "mid-level"
        topic = fd.get("topic") or "technical"
        half_min = max(1, int((float(fd.get("interviewDuration") or 15)) // 2))
        cv_text = fd.get("cvText") or ""

        system_prompt = f"""You are an experienced technical interviewer conducting a {level} interview for a {topic} position.

Interview Guidelines:
- Ask thoughtful, relevant questions appropriate for {level} candidates
- Listen carefully to responses and ask follow-up questions
- Be professional, encouraging, and constructive
- Give the candidate time to think and respond
- Ask one question at a time
- Keep responses concise and conversational (2-3 sentences max per response)
- After {half_min} minutes, start wrapping up
- Conclude with brief encouragement

{f"Candidate's Background:\\n{cv_text}\\n\\nPersonalize your questions based on their experience." if cv_text else ""}

Start by warmly greeting the candidate and asking them to briefly introduce themselves."""

        return {
            "success": True,
            "config": {
                "type": "Settings",
                "audio": {
                    "input": {"encoding": "linear16", "sample_rate": 16000},
                    "output": {"encoding": "linear16", "sample_rate": 16000, "container": "none"},
                },
                "agent": {
                    "listen": {"provider": {"type": "deepgram", "model": "nova-2"}},
                    "think": {
                        "provider": {"type": "open_ai", "model": "gpt-4o-mini"},
                        "prompt": system_prompt,
                        "functions": [],
                    },
                    "speak": {"provider": {"type": "deepgram", "model": "aura-asteria-en"}},
                    "greeting": (
                        "Hello! I'm excited to conduct your interview today. Let's begin — "
                        "could you please introduce yourself and tell me a bit about your background?"
                    ),
                },
            },
        }

    if body.action == "feedback":
        interview_api_key = settings.groq_api_key_2 or settings.groq_api_key
        if not interview_api_key:
            raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured")
        transcript = body.transcript or []
        if not transcript:
            raise HTTPException(status_code=400, detail="No transcript provided")

        conversation_text = "\n\n".join(
            f"{'Interviewer' if (isinstance(item, dict) and item.get('speaker') == 'interviewer') else 'Candidate'}: "
            f"{(item.get('text') if isinstance(item, dict) else '') or ''}"
            for item in transcript
        )
        fd = body.formData or {}
        topic = fd.get("topic") or "the role"
        level = fd.get("difficulty") or "intermediate"
        posture_block = ""
        if isinstance(body.bodyLanguageSummary, str) and body.bodyLanguageSummary.strip():
            posture_block = (
                "\n\nWEBCAM POSE SUMMARY (approximate MediaPipe — use as one signal among others):\n"
                + body.bodyLanguageSummary.strip()
            )

        prompt = f"""Analyze this live voice interview practice for a {topic} position ({level} level).

FULL TRANSCRIPT:
{conversation_text}
{posture_block}

Return JSON only (no markdown) in this exact shape:
{{
  "overall": "2-3 sentence assessment: prioritize transcript; reference posture ONLY using the numeric rules in the POSE METRICS block — never generic praise.",
  "bodyLanguageComment": "3-5 sentences. MUST reference specific averages or percentages from POSE METRICS when that block is present. If rules forbid claiming strong eye contact, do not claim it. If averages are weak, say so clearly. If NO_POSE_DATA, say posture was not measured.",
  "questionFeedback": [
    {{
      "question": "Question text",
      "strengths": "What went well",
      "improvements": "What to improve"
    }}
  ],
  "recommendations": ["tip 1", "tip 2", "tip 3"],
  "scores": {{
    "technical": 0,
    "communication": 0,
    "presence": 0
  }}
}}

scores: integers 0-100. "presence" must reflect BOTH voice and (when given) pose metrics — lower presence if facing/headPitch/symmetry averages are poor per the RULES in the metrics block.

Return ONLY the JSON object."""

        client = Groq(api_key=interview_api_key)
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a rigorous interview coach. You never give vague encouragement about body language "
                        "when numeric pose data contradicts it. Return only valid JSON, no markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model=settings.groq_model,
            temperature=0.35,
            max_tokens=3200,
        )
        response = completion.choices[0].message.content or ""
        response = _strip_json_fence(response.replace("```json\n", "").replace("```", ""))
        feedback = json.loads(response)
        if isinstance(feedback, dict):
            merge_posture_into_feedback(feedback, body.bodyLanguageMetrics)
        return {"success": True, "feedback": feedback}

    raise HTTPException(status_code=400, detail="Invalid action")
