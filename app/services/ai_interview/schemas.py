from typing import Any

from pydantic import BaseModel, Field


class GenerateQuestionsRequest(BaseModel):
    topic: str
    difficulty: str | None = None
    questionCount: int | None = None
    jobTitle: str | None = None
    companyName: str | None = None
    jobDescription: str | None = None


class InterviewQuestionItem(BaseModel):
    question: str
    category: str
    context: str | None = None


class GenerateFeedbackRequest(BaseModel):
    topic: str
    difficulty: str | None = None
    questions: list[Any] = Field(default_factory=list)
    answers: list[Any] = Field(default_factory=list)
    bodyLanguageSummary: str | None = None
    bodyLanguageMetrics: Any = None
    jobTitle: str | None = None
    companyName: str | None = None
    jobDescription: str | None = None


class VoiceAgentRequest(BaseModel):
    action: str
    formData: dict[str, Any] | None = None
    transcript: list[Any] | None = None
    bodyLanguageSummary: str | None = None
    bodyLanguageMetrics: Any = None
