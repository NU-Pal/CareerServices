import json
from datetime import datetime, timezone
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.dotnet_mongo_bridge import dotnet_data_to_api_dict
from app.core.mongo_db import job_fit_collection, resume_collection
from app.core.security import get_student_email, require_service_api_key
from app.services.job_description.schemas import (
    JobFitAnalyzeRequest,
    JobFitAnalyzeResponse,
    JobFitHistoryItem,
)
from app.services.job_description.service import analyze_job_fit_llm, fetch_job_page_text, resume_to_text_blob

router = APIRouter(prefix="/resume/job-fit", tags=["job-fit"])


async def _load_resume_for_student(
    student_email: str,
    resume_id: str | None,
) -> dict[str, Any]:
    coll = resume_collection()
    import re
    email_regex = {"$regex": f"^{re.escape(student_email)}$", "$options": "i"}
    if resume_id:
        if not ObjectId.is_valid(resume_id):
            raise HTTPException(status_code=404, detail="Resume not found")
        doc = await coll.find_one({"_id": ObjectId(resume_id), "$or": [{"StudentEmail": email_regex}, {"studentEmail": email_regex}]})
        if not doc:
            raise HTTPException(status_code=404, detail="Resume not found")
        return dotnet_data_to_api_dict(doc.get("Data") or {})
    cursor = coll.find({"$or": [{"StudentEmail": email_regex}, {"studentEmail": email_regex}]}).sort("AnalyzedAt", -1).limit(1)
    docs = await cursor.to_list(1)
    if not docs:
        raise HTTPException(
            status_code=400,
            detail="No resume found for analysis. Please upload your resume first.",
        )
    return dotnet_data_to_api_dict(docs[0].get("Data") or {})


@router.post("/analyze", response_model=JobFitAnalyzeResponse)
async def analyze_job_fit(
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: JobFitAnalyzeRequest,
) -> JobFitAnalyzeResponse:
    if not (body.jobUrl or "").strip() and not (body.jobDescription or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Either Job URL or Job Description is required.",
        )

    job_text = (body.jobDescription or "").strip()
    job_url = (body.jobUrl or "").strip()
    if job_url and not job_text:
        try:
            job_text = await fetch_job_page_text(job_url)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not fetch job URL: {e!s}",
            ) from e
    if not job_text:
        raise HTTPException(status_code=400, detail="Provide jobDescription or a reachable jobUrl")

    api_resume = await _load_resume_for_student(student_email, body.resumeId)
    resume_blob = resume_to_text_blob(api_resume)

    try:
        analysis = analyze_job_fit_llm(settings, resume_blob, job_text)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    analysis_dict: dict[str, Any] = analysis.model_dump()
    job_url_to_store = job_url if job_url else "Manual Entry"

    coll = job_fit_collection()
    now = datetime.now(timezone.utc)
    doc = {
        "StudentEmail": student_email,
        "JobUrl": job_url_to_store,
        "AnalyzedAt": now,
        "AnalysisJson": json.dumps(analysis_dict),
    }
    res = await coll.insert_one(doc)
    return JobFitAnalyzeResponse(id=str(res.inserted_id), analysis=analysis_dict)


@router.get("/history", response_model=list[JobFitHistoryItem])
async def job_fit_history(
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
) -> list[JobFitHistoryItem]:
    coll = job_fit_collection()
    import re
    email_regex = {"$regex": f"^{re.escape(student_email)}$", "$options": "i"}
    cursor = coll.find({"$or": [{"StudentEmail": email_regex}, {"studentEmail": email_regex}]}).sort("AnalyzedAt", -1)
    out: list[JobFitHistoryItem] = []
    async for doc in cursor:
        raw = doc.get("AnalysisJson") or "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
        except json.JSONDecodeError:
            data = {}
        at = doc.get("AnalyzedAt")
        analyzed = at.isoformat() if hasattr(at, "isoformat") else str(at)
        out.append(
            JobFitHistoryItem(
                id=str(doc["_id"]),
                jobTitle=data.get("jobTitle"),
                companyName=data.get("companyName"),
                overallScore=int(data.get("overallScore") or 0),
                matchStatus=data.get("matchStatus"),
                jobUrl=doc.get("JobUrl") or "",
                analyzedAt=analyzed,
            )
        )
    return out


@router.get("/{job_fit_id}")
async def get_job_fit(
    job_fit_id: str,
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
) -> dict[str, Any]:
    if not ObjectId.is_valid(job_fit_id):
        raise HTTPException(status_code=404, detail="Job fit not found")
    coll = job_fit_collection()
    import re
    email_regex = {"$regex": f"^{re.escape(student_email)}$", "$options": "i"}
    record = await coll.find_one({"_id": ObjectId(job_fit_id), "$or": [{"StudentEmail": email_regex}, {"studentEmail": email_regex}]})
    if not record:
        raise HTTPException(status_code=404, detail="Job fit not found")
    raw = record.get("AnalysisJson") or "{}"
    try:
        analysis = json.loads(raw) if isinstance(raw, str) else {}
    except json.JSONDecodeError:
        analysis = {}
    at = record.get("AnalyzedAt")
    analyzed = at.isoformat() if hasattr(at, "isoformat") else str(at)
    return {
        "id": str(record["_id"]),
        "analysis": analysis,
        "jobUrl": record.get("JobUrl") or "",
        "analyzedAt": analyzed,
    }


@router.delete("/{job_fit_id}", status_code=204)
async def delete_job_fit(
    job_fit_id: str,
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
) -> None:
    if not ObjectId.is_valid(job_fit_id):
        raise HTTPException(status_code=404, detail="Job fit not found")
    coll = job_fit_collection()
    import re
    email_regex = {"$regex": f"^{re.escape(student_email)}$", "$options": "i"}
    result = await coll.delete_one({"_id": ObjectId(job_fit_id), "$or": [{"StudentEmail": email_regex}, {"studentEmail": email_regex}]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job fit not found")
