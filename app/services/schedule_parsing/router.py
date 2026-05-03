from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from app.core.config import Settings, get_settings
from app.services.schedule_parsing.service import extract_pdf_text, parse_schedule_with_llm
from app.services.schedule_parsing.schemas import ParsedSchedule

router = APIRouter(prefix="/schedule", tags=["Schedule Parsing"])

@router.post("/parse", response_model=ParsedSchedule)
async def parse_schedule(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        content = await file.read()
        raw_text = extract_pdf_text(content)
        parsed = parse_schedule_with_llm(settings, raw_text)
        return parsed
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
