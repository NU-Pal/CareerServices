from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import Settings


def _base_url(settings: Settings) -> str:
    base = settings.core_backend_url.strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=503,
            detail="CORE_BACKEND_URL is not configured",
        )
    return base


async def _request(
    *,
    settings: Settings,
    method: str,
    path: str,
    authorization: str | None,
    student_email: str,
    json_body: dict[str, Any] | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if authorization:
        headers["Authorization"] = authorization
    if settings.core_backend_api_key.strip():
        headers["X-Core-Api-Key"] = settings.core_backend_api_key.strip()

    url = f"{_base_url(settings)}{path}"
    params = {"studentEmail": student_email}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Core backend unreachable: {exc!s}",
        ) from exc

    if response.status_code >= 400:
        detail: Any = response.text
        try:
            payload = response.json()
            if isinstance(payload, dict) and "detail" in payload:
                detail = payload["detail"]
            else:
                detail = payload
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)

    if response.status_code == 204 or not response.content:
        return None
    return response.json()


async def create_resume_analysis(
    settings: Settings,
    authorization: str | None,
    student_email: str,
    *,
    file_name: str,
    data: dict[str, Any],
) -> str:
    payload = await _request(
        settings=settings,
        method="POST",
        path="/api/career-data/resume-analyses",
        authorization=authorization,
        student_email=student_email,
        json_body={"fileName": file_name, "data": data},
    )
    return str(payload.get("id") or "")


async def list_resume_analyses(
    settings: Settings,
    authorization: str | None,
    student_email: str,
) -> list[dict[str, Any]]:
    payload = await _request(
        settings=settings,
        method="GET",
        path="/api/career-data/resume-analyses",
        authorization=authorization,
        student_email=student_email,
    )
    return payload if isinstance(payload, list) else []


async def get_resume_analysis(
    settings: Settings,
    authorization: str | None,
    student_email: str,
    resume_id: str,
) -> dict[str, Any]:
    payload = await _request(
        settings=settings,
        method="GET",
        path=f"/api/career-data/resume-analyses/{resume_id}",
        authorization=authorization,
        student_email=student_email,
    )
    return payload if isinstance(payload, dict) else {}


async def delete_resume_analysis(
    settings: Settings,
    authorization: str | None,
    student_email: str,
    resume_id: str,
) -> None:
    await _request(
        settings=settings,
        method="DELETE",
        path=f"/api/career-data/resume-analyses/{resume_id}",
        authorization=authorization,
        student_email=student_email,
    )


async def create_job_fit_result(
    settings: Settings,
    authorization: str | None,
    student_email: str,
    *,
    job_url: str,
    job_text: str,
    analysis_json: str,
) -> str:
    payload = await _request(
        settings=settings,
        method="POST",
        path="/api/career-data/job-fit-results",
        authorization=authorization,
        student_email=student_email,
        json_body={
            "jobUrl": job_url,
            "jobText": job_text,
            "analysisJson": analysis_json,
        },
    )
    return str(payload.get("id") or "")


async def list_job_fit_results(
    settings: Settings,
    authorization: str | None,
    student_email: str,
) -> list[dict[str, Any]]:
    payload = await _request(
        settings=settings,
        method="GET",
        path="/api/career-data/job-fit-results",
        authorization=authorization,
        student_email=student_email,
    )
    return payload if isinstance(payload, list) else []


async def get_job_fit_result(
    settings: Settings,
    authorization: str | None,
    student_email: str,
    job_fit_id: str,
) -> dict[str, Any]:
    payload = await _request(
        settings=settings,
        method="GET",
        path=f"/api/career-data/job-fit-results/{job_fit_id}",
        authorization=authorization,
        student_email=student_email,
    )
    return payload if isinstance(payload, dict) else {}


async def delete_job_fit_result(
    settings: Settings,
    authorization: str | None,
    student_email: str,
    job_fit_id: str,
) -> None:
    await _request(
        settings=settings,
        method="DELETE",
        path=f"/api/career-data/job-fit-results/{job_fit_id}",
        authorization=authorization,
        student_email=student_email,
    )
