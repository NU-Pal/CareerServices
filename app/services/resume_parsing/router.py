from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile

from app.core.config import Settings, get_settings
from app.core.core_backend_client import (
    create_resume_analysis,
    delete_resume_analysis,
    get_resume_analysis,
    list_resume_analyses,
)
from app.core.dotnet_mongo_bridge import dotnet_data_to_api_dict
from app.core.security import get_student_email, require_service_api_key
from app.services.resume_parsing.schemas import ParseResponse, ParsedResume, ResumeHistoryItem
from app.services.resume_parsing.service import extract_pdf_text, parse_resume_with_llm

router = APIRouter(prefix="/resume", tags=["resume"])


def _pick(doc: dict, *keys: str):
    for k in keys:
        if k in doc and doc[k] is not None:
            return doc[k]
    return None


@router.post("/parse", response_model=ParseResponse)
async def parse_resume(
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(None),
    file: UploadFile = File(...),
) -> ParseResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    body = await file.read()
    if len(body) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    try:
        raw = extract_pdf_text(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {str(e)}") from e
    
    try:
        data = parse_resume_with_llm(settings, raw)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM parsing failed: {str(e)}") from e

    resume_id = await create_resume_analysis(
        settings,
        authorization,
        student_email,
        file_name=file.filename,
        # C# ResumeData uses [JsonPropertyName("camelCase")] – send camelCase directly
        data=data.model_dump(mode="json"),
    )
    return ParseResponse(id=resume_id, data=data)


@router.get("/history", response_model=list[ResumeHistoryItem])
async def resume_history(
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(None),
) -> list[ResumeHistoryItem]:
    docs = await list_resume_analyses(settings, authorization, student_email)
    out: list[ResumeHistoryItem] = []
    for doc in docs:
        data = _pick(doc, "Data", "data") or {}
        api_data = dotnet_data_to_api_dict(data)
        at = _pick(doc, "AnalyzedAt", "analyzedAt")
        analyzed = str(at or "")
        out.append(
            ResumeHistoryItem(
                id=str(_pick(doc, "Id", "id") or ""),
                fileName=str(_pick(doc, "FileName", "fileName") or ""),
                analyzedAt=analyzed,
                fullName=api_data.get("fullName"),
            )
        )
    return out


@router.get("/{resume_id}", response_model=ParsedResume)
async def get_resume(
    resume_id: str,
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(None),
) -> ParsedResume:
    doc = await get_resume_analysis(settings, authorization, student_email, resume_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Resume not found")
    api_data = dotnet_data_to_api_dict(_pick(doc, "Data", "data") or {})
    return ParsedResume.model_validate(api_data)


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: str,
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(None),
) -> None:
    await delete_resume_analysis(settings, authorization, student_email, resume_id)
