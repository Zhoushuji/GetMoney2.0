from __future__ import annotations

import csv
from io import BytesIO, StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.leads import _lead_field_value, _style_workbook
from app.database import get_db
from app.models.lead import Lead
from app.models.lead_review import LeadReview
from app.schemas.review import LeadReviewListResponse, LeadReviewRecord

router = APIRouter(prefix="/reviews", tags=["reviews"])


async def _load_review_records(db: AsyncSession, task_id: UUID) -> list[LeadReviewRecord]:
    result = await db.execute(
        select(LeadReview, Lead)
        .join(Lead, Lead.id == LeadReview.lead_id)
        .where(Lead.task_id == task_id)
        .order_by(Lead.created_at.asc(), LeadReview.updated_at.desc())
    )
    records: list[LeadReviewRecord] = []
    for review, lead in result.all():
        records.append(
            LeadReviewRecord(
                lead_id=lead.id,
                field_key=review.field_key,
                company_name=lead.company_name,
                current_value=_lead_field_value(lead, review.field_key),
                verdict=review.verdict,
                source_path=review.source_path,
                note=review.note,
                reviewed_at=review.updated_at,
            )
        )
    return records


@router.get("", response_model=LeadReviewListResponse)
async def list_reviews(task_id: UUID = Query(...), db: AsyncSession = Depends(get_db)) -> LeadReviewListResponse:
    items = await _load_review_records(db, task_id)
    return LeadReviewListResponse(items=items, total=len(items))


@router.get("/export")
async def export_reviews(
    task_id: UUID,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: AsyncSession = Depends(get_db),
):
    items = await _load_review_records(db, task_id)
    headers = ["Company", "Field", "Current Value", "Verdict", "Source Path", "Note", "Reviewed At"]
    if format == "csv":
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for item in items:
            writer.writerow(
                [
                    item.company_name or "",
                    item.field_key,
                    item.current_value or "",
                    item.verdict,
                    item.source_path,
                    item.note or "",
                    item.reviewed_at.isoformat() if item.reviewed_at else "",
                ]
            )
        return Response(content=buffer.getvalue(), media_type="text/csv")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lead Reviews"
    sheet.append(headers)
    for item in items:
        sheet.append(
            [
                item.company_name,
                item.field_key,
                item.current_value,
                item.verdict,
                item.source_path,
                item.note,
                item.reviewed_at.isoformat() if item.reviewed_at else "",
            ]
        )
    _style_workbook(sheet)
    data = BytesIO()
    workbook.save(data)
    data.seek(0)
    return StreamingResponse(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
