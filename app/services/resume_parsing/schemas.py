from typing import Any

from pydantic import BaseModel, Field


class ParsedResumeExperience(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    isCurrent: bool | None = None
    bullets: list[str] = Field(default_factory=list)


class ParsedResumeEducation(BaseModel):
    degree: str | None = None
    field: str | None = None
    institution: str | None = None
    location: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    gpa: str | None = None


class ParsedResumeProject(BaseModel):
    name: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    link: str | None = None


class ParsedResume(BaseModel):
    model_config = {"extra": "ignore"}

    firstName: str | None = None
    lastName: str | None = None
    fullName: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedIn: str | None = None
    gitHub: str | None = None
    website: str | None = None
    summary: str | None = None
    technicalSkills: list[str] = Field(default_factory=list)
    softSkills: list[str] = Field(default_factory=list)
    experience: list[ParsedResumeExperience] = Field(default_factory=list)
    education: list[ParsedResumeEducation] = Field(default_factory=list)
    projects: list[ParsedResumeProject] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)


class ResumeHistoryItem(BaseModel):
    id: str
    fileName: str
    analyzedAt: str
    fullName: str | None = None


class ParseResponse(BaseModel):
    id: str
    data: ParsedResume

    model_config = {"populate_by_name": True}


def parsed_resume_from_dict(data: dict[str, Any]) -> ParsedResume:
    return ParsedResume.model_validate(data)
