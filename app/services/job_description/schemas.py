from typing import Any
from pydantic import BaseModel, Field, field_validator


class JobFitBreakdownMatchedSkill(BaseModel):
    skill: str
    evidence: str
    level: str


class JobFitBreakdownMissingSkill(BaseModel):
    skill: str
    importance: str
    fixable: str


class JobFitBreakdown(BaseModel):
    skills: int = 0
    experience: int = 0
    domain: int = 0
    credentials: int = 0
    readiness: int = 0

    @field_validator("skills", "experience", "domain", "credentials", "readiness", mode="before")
    @classmethod
    def convert_float_to_int(cls, v: Any) -> int:
        if isinstance(v, (float, int)):
            # If it's a decimal like 0.6, convert to 60
            if 0 < v <= 1.0 and isinstance(v, float):
                return int(v * 100)
            return int(v)
        return 0
    skillsNote: str | None = None
    experienceNote: str | None = None
    domainNote: str | None = None
    credentialsNote: str | None = None
    matchedSkills: list[JobFitBreakdownMatchedSkill] = Field(default_factory=list)
    missingSkills: list[JobFitBreakdownMissingSkill] = Field(default_factory=list)


class JobFitActionItem(BaseModel):
    title: str | None = None
    description: str | None = None
    targetGap: str | None = None
    expectedImpact: str | None = None
    priority: str = "Medium"
    status: str = "Do soon"


class JobFitAnalysisData(BaseModel):
    overallScore: int
    matchStatus: str
    detailedSummary: str
    highlights: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    breakdown: JobFitBreakdown
    actionPlan: list[JobFitActionItem] = Field(default_factory=list)
    interviewFocus: list[str] = Field(default_factory=list)
    suggestedLearning: list[str] = Field(default_factory=list)
    redFlags: list[str] | None = None
    jobTitle: str | None = None
    companyName: str | None = None


class JobFitAnalyzeRequest(BaseModel):
    jobUrl: str | None = None
    jobDescription: str | None = None
    resumeId: str | None = None


class JobFitAnalyzeResponse(BaseModel):
    id: str
    analysis: dict[str, Any]
    # Raw JD (paste or scraped) — used for job-specific technical interview prep
    jobDescriptionText: str | None = None


class JobFitHistoryItem(BaseModel):
    id: str
    jobTitle: str | None = None
    companyName: str | None = None
    overallScore: int = 0
    matchStatus: str | None = None
    jobUrl: str = ""
    analyzedAt: str
