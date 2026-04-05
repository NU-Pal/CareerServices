from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.config import Settings, get_settings
from app.core.dotnet_mongo_bridge import api_dict_to_dotnet_data, dotnet_data_to_api_dict
from app.core.mongo_db import resume_collection
from app.core.security import get_student_email, require_service_api_key
from app.services.resume_parsing.schemas import ParseResponse, ParsedResume, ResumeHistoryItem
from app.services.resume_parsing.service import extract_pdf_text, parse_resume_with_llm

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/parse", response_model=ParseResponse)
async def parse_resume(
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
) -> ParseResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    body = await file.read()
    if len(body) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    try:
        raw = extract_pdf_text(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        data = parse_resume_with_llm(settings, raw)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    coll = resume_collection()
    now = datetime.now(timezone.utc)
    doc = {
        "StudentEmail": student_email,
        "FileName": file.filename,
        "AnalyzedAt": now,
        "Data": api_dict_to_dotnet_data(data.model_dump(mode="json")),
    }
    res = await coll.insert_one(doc)
    return ParseResponse(id=str(res.inserted_id), data=data)


@router.get("/history", response_model=list[ResumeHistoryItem])
async def resume_history(
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
) -> list[ResumeHistoryItem]:
    coll = resume_collection()
    cursor = coll.find({"StudentEmail": student_email}).sort("AnalyzedAt", -1)
    out: list[ResumeHistoryItem] = []
    async for doc in cursor:
        data = doc.get("Data") or {}
        api_data = dotnet_data_to_api_dict(data)
        at = doc.get("AnalyzedAt")
        analyzed = at.isoformat() if hasattr(at, "isoformat") else str(at)
        out.append(
            ResumeHistoryItem(
                id=str(doc["_id"]),
                fileName=doc.get("FileName") or "",
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
) -> ParsedResume:
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=404, detail="Resume not found")
    coll = resume_collection()
    doc = await coll.find_one({"_id": ObjectId(resume_id), "StudentEmail": student_email})
    if not doc:
        raise HTTPException(status_code=404, detail="Resume not found")
    api_data = dotnet_data_to_api_dict(doc.get("Data") or {})
    return ParsedResume.model_validate(api_data)


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: str,
    _: Annotated[None, Depends(require_service_api_key)],
    student_email: Annotated[str, Depends(get_student_email)],
) -> None:
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=404, detail="Resume not found")
    coll = resume_collection()
    result = await coll.delete_one({"_id": ObjectId(resume_id), "StudentEmail": student_email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Resume not found")
