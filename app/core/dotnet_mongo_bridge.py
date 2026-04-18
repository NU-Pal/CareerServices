"""
BSON shape for `Data` matches NUPAL.Core.Domain ResumeData (PascalCase in Mongo),
as written by the C# driver. API responses use camelCase for the Next.js client.
"""

from __future__ import annotations

from typing import Any


def _g(d: dict[str, Any], pascal: str, camel: str) -> Any:
    if pascal in d:
        return d[pascal]
    return d.get(camel)


def _exp_in(x: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _g(x, "Title", "title"),
        "company": _g(x, "Company", "company"),
        "location": _g(x, "Location", "location"),
        "startDate": _g(x, "StartDate", "startDate"),
        "endDate": _g(x, "EndDate", "endDate"),
        "isCurrent": _g(x, "IsCurrent", "isCurrent"),
        "bullets": list(_g(x, "Bullets", "bullets") or x.get("points") or x.get("highlights") or []),
    }


def _edu_in(x: dict[str, Any]) -> dict[str, Any]:
    return {
        "degree": _g(x, "Degree", "degree"),
        "field": _g(x, "Field", "field"),
        "institution": _g(x, "Institution", "institution"),
        "location": _g(x, "Location", "location"),
        "startDate": _g(x, "StartDate", "startDate"),
        "endDate": _g(x, "EndDate", "endDate"),
        "gpa": _g(x, "GPA", "gpa"),
    }


def _proj_in(x: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _g(x, "Name", "name"),
        "description": _g(x, "Description", "description") or x.get("summary") or x.get("about"),
        "bullets": list(_g(x, "Bullets", "bullets") or x.get("points") or x.get("highlights") or []),
        "technologies": list(_g(x, "Technologies", "technologies") or x.get("stack") or []),
        "link": _g(x, "Link", "link") or x.get("url"),
    }


def dotnet_data_to_api_dict(data: Any) -> dict[str, Any]:
    """Mongo `Data` → camelCase dict for ParsedResume / frontend."""
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {
        "fullName": _g(data, "FullName", "fullName"),
        "email": _g(data, "Email", "email"),
        "phone": _g(data, "Phone", "phone"),
        "location": _g(data, "Location", "location"),
        "linkedIn": _g(data, "LinkedIn", "linkedIn"),
        "gitHub": _g(data, "GitHub", "gitHub"),
        "website": _g(data, "Website", "website"),
        "summary": _g(data, "Summary", "summary"),
        "technicalSkills": list(_g(data, "TechnicalSkills", "technicalSkills") or []),
        "softSkills": list(_g(data, "SoftSkills", "softSkills") or []),
        "certifications": list(_g(data, "Certifications", "certifications") or []),
        "languages": list(_g(data, "Languages", "languages") or []),
        "awards": list(_g(data, "Awards", "awards") or []),
    }
    fn = _g(data, "FirstName", "firstName")
    ln = _g(data, "LastName", "lastName")
    if fn and not out.get("fullName"):
        out["fullName"] = f"{fn} {ln or ''}".strip()
    ex = data.get("Experience") or data.get("experience") or []
    out["experience"] = [_exp_in(e) for e in ex if isinstance(e, dict)]
    ed = data.get("Education") or data.get("education") or []
    out["education"] = [_edu_in(e) for e in ed if isinstance(e, dict)]
    pr = data.get("Projects") or data.get("projects") or []
    out["projects"] = [_proj_in(e) for e in pr if isinstance(e, dict)]
    return out


def _exp_out(x: dict[str, Any]) -> dict[str, Any]:
    return {
        "Title": x.get("title"),
        "Company": x.get("company"),
        "Location": x.get("location"),
        "StartDate": x.get("startDate"),
        "EndDate": x.get("endDate"),
        "IsCurrent": x.get("isCurrent"),
        "Bullets": x.get("bullets") or [],
    }


def _edu_out(x: dict[str, Any]) -> dict[str, Any]:
    return {
        "Degree": x.get("degree"),
        "Field": x.get("field"),
        "Institution": x.get("institution"),
        "Location": x.get("location"),
        "StartDate": x.get("startDate"),
        "EndDate": x.get("endDate"),
        "GPA": x.get("gpa"),
    }


def _proj_out(x: dict[str, Any]) -> dict[str, Any]:
    return {
        "Name": x.get("name"),
        "Description": x.get("description"),
        "Bullets": x.get("bullets") or [],
        "Technologies": x.get("technologies") or [],
        "Link": x.get("link"),
    }


def api_dict_to_dotnet_data(d: dict[str, Any]) -> dict[str, Any]:
    """camelCase ParsedResume dump → BSON `Data` for resume_analyses (C#-compatible)."""
    return {
        "FirstName": d.get("firstName"),
        "LastName": d.get("lastName"),
        "FullName": d.get("fullName"),
        "Email": d.get("email"),
        "Phone": d.get("phone"),
        "Location": d.get("location"),
        "LinkedIn": d.get("linkedIn"),
        "GitHub": d.get("gitHub"),
        "Website": d.get("website"),
        "Summary": d.get("summary"),
        "TechnicalSkills": d.get("technicalSkills") or [],
        "SoftSkills": d.get("softSkills") or [],
        "Experience": [_exp_out(e) for e in (d.get("experience") or []) if isinstance(e, dict)],
        "Education": [_edu_out(e) for e in (d.get("education") or []) if isinstance(e, dict)],
        "Projects": [_proj_out(e) for e in (d.get("projects") or []) if isinstance(e, dict)],
        "Certifications": d.get("certifications") or [],
        "Languages": d.get("languages") or [],
        "Awards": d.get("awards") or [],
    }
