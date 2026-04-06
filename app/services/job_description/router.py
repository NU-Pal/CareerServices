import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import Settings, get_settings
from app.core.core_backend_client import (
    create_job_fit_result,
    get_resume_analysis,
    list_job_fit_results,
    delete_job_fit_result,
    get_job_fit_result,
    list_resume_analyses,
)
from app.core.dotnet_mongo_bridge import dotnet_data_to_api_dict
from app.core.security import get_student_email, require_service_api_key
from app.services.job_description.schemas import (
    JobFitAnalyzeRequest,
    JobFitAnalyzeResponse,
    JobFitHistoryItem,
)
from app.services.job_description.service import analyze_job_fit_llm, fetch_job_page_text, resume_to_text_blob

router = APIRouter(prefix="/resume/job-fit", tags=["job-fit"])


async def _load_resume_for_student(
    settings: Settings,
    authorization: str | None,
    student_email: str,
    resume_id: str | None,
) -> dict[str, Any]:
    if resume_id:
        doc = await get_resume_analysis(settings, authorization, student_email, resume_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Resume not found")
        return dotnet_data_to_api_dict(doc.get("Data") or {})
    docs = await list_resume_analyses(settings, authorization, student_email)
    if not docs:
        raise HTTPException(
            status_code=400,
            detail="No resume found for analysis. Please upload your resume first.",
        )
    newest = docs[0]
    return dotnet_data_to_api_dict(newest.get("Data") or {})


@router.post("/analyze", response_model=JobFitAnalyzeResponse)
async def analyze_job_fit(
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: JobFitAnalyzeRequest,
    authorization: str | None = Header(None),
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

    api_resume = await _load_resume_for_student(settings, authorization, student_email, body.resumeId)
    resume_blob = resume_to_text_blob(api_resume)

    try:
        analysis = analyze_job_fit_llm(settings, resume_blob, job_text)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    analysis_dict: dict[str, Any] = analysis.model_dump()
    job_url_to_store = job_url if job_url else "Manual Entry"
    job_text_stored = job_text[:25_000]

    new_id = await create_job_fit_result(
        settings,
        authorization,
        student_email,
        job_url=job_url_to_store,
        job_text=job_text_stored,
        analysis_json=json.dumps(analysis_dict),
    )
    return JobFitAnalyzeResponse(
        id=new_id,
        analysis=analysis_dict,
        jobDescriptionText=job_text_stored,
    )


@router.get("/history", response_model=list[JobFitHistoryItem])
async def job_fit_history(
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(None),
) -> list[JobFitHistoryItem]:
    docs = await list_job_fit_results(settings, authorization, student_email)
    out: list[JobFitHistoryItem] = []
    for doc in docs:
        raw = doc.get("AnalysisJson") or "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
        except json.JSONDecodeError:
            data = {}
        at = doc.get("AnalyzedAt")
        analyzed = at.isoformat() if hasattr(at, "isoformat") else str(at)
        out.append(
            JobFitHistoryItem(
                id=str(doc.get("Id") or doc.get("id") or ""),
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
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    record = await get_job_fit_result(settings, authorization, student_email, job_fit_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job fit not found")
    raw = record.get("AnalysisJson") or "{}"
    try:
        analysis = json.loads(raw) if isinstance(raw, str) else {}
    except json.JSONDecodeError:
        analysis = {}
    at = record.get("AnalyzedAt")
    analyzed = at.isoformat() if hasattr(at, "isoformat") else str(at)
    job_text = record.get("JobText")
    if isinstance(job_text, str):
        jd_text = job_text
    else:
        jd_text = None

    return {
        "id": str(record.get("Id") or record.get("id") or ""),
        "analysis": analysis,
        "jobUrl": record.get("JobUrl") or "",
        "jobDescriptionText": jd_text,
        "analyzedAt": analyzed,
    }


@router.delete("/{job_fit_id}", status_code=204)
async def delete_job_fit(
    job_fit_id: str,
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(None),
) -> None:
    await delete_job_fit_result(settings, authorization, student_email, job_fit_id)
