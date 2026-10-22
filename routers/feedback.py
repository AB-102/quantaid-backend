import csv
import io
import logging
from datetime import UTC, datetime
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, UploadFile, status
from gridfs import NoFile

from core.uploads import require_image
from database.db import db, fs
from dependencies.auth import OptionalUser, require_admin
from routers.files import gridfs_file_response
from schemas.feedback import FeedbackStatusUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Feedback"])
admin_router = APIRouter(prefix="/api/admin", tags=["Feedback admin"], dependencies=[Depends(require_admin)])

# The admin dashboard can filter by ?status=, which would shadow fastapi's `status` module as a parameter name
StatusFilter = Annotated[str | None, Query(alias="status")]


def _csv_cell(value: str) -> str:
    """Stop spreadsheet apps from running visitor-written text as a formula."""
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def _object_id(value: str, label: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {label} ID")
    return ObjectId(value)


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def create_feedback(
    user: OptionalUser,
    category: Annotated[str, Form()],
    feedback: Annotated[str, Form()],
    screenshot: UploadFile | None = None,
):
    """Feedback from any visitor, signed in or not. The optional screenshot is only visible to admins."""
    feedback_text = feedback.strip()
    if not category or not feedback_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category and feedback text are required")
    screenshot_id = None
    if screenshot is not None and screenshot.filename:
        require_image(screenshot)
        screenshot_id = await fs.put(
            await screenshot.read(),
            filename=screenshot.filename,
            content_type=screenshot.content_type,
            visibility="admin",
        )
    now = datetime.now(UTC)
    result = await db.feedback.insert_one(
        {
            "user_id": user.email if user else "anonymous",
            "category": category,
            "feedback": feedback_text,
            "screenshot_id": screenshot_id,
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
    )
    logger.debug("Feedback submitted, category %s", category)
    return {"message": "Feedback submitted successfully", "id": str(result.inserted_id)}


@admin_router.get("/feedback")
async def list_feedback(
    status_filter: StatusFilter = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    skip: Annotated[int, Query(ge=0)] = 0,
):
    query = {"status": status_filter} if status_filter else {}
    feedback_list = (
        await db.feedback.find(
            query,
            {"_id": 1, "user_id": 1, "category": 1, "feedback": 1, "status": 1, "created_at": 1, "screenshot_id": 1},
        )
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list()
    )
    total_count = await db.feedback.count_documents(query)
    return {
        "feedback": [
            {
                "id": str(item["_id"]),
                "userId": item.get("user_id", "anonymous"),
                "category": item.get("category", ""),
                "feedback": item.get("feedback", ""),
                "status": item.get("status", "open"),
                "createdAt": item.get("created_at"),
                "hasScreenshot": bool(item.get("screenshot_id")),
            }
            for item in feedback_list
        ],
        "totalCount": total_count,
        "hasMore": skip + len(feedback_list) < total_count,
    }


@admin_router.get("/feedback/export")
async def export_feedback_csv(request: Request, status_filter: StatusFilter = None):
    """All feedback as a CSV download."""
    query = {"status": status_filter} if status_filter else {}
    feedback_list = (
        await db.feedback.find(
            query, {"user_id": 1, "category": 1, "feedback": 1, "status": 1, "created_at": 1, "screenshot_id": 1}
        )
        .sort("created_at", -1)
        .to_list()
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "User", "Category", "Status", "Feedback", "Screenshot URL"])
    for item in feedback_list:
        created = item.get("created_at", "")
        if isinstance(created, datetime):
            created = created.strftime("%Y-%m-%d %H:%M:%S UTC")
        screenshot_url = ""
        if item.get("screenshot_id"):
            screenshot_url = f"{request.base_url}api/admin/feedback/{item['_id']}/screenshot"
        writer.writerow(
            [
                created,
                _csv_cell(item.get("user_id", "anonymous")),
                _csv_cell(item.get("category", "")),
                item.get("status", "open"),
                _csv_cell(item.get("feedback", "")),
                screenshot_url,
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=feedback_export.csv"},
    )


@admin_router.get("/feedback/{feedback_id}/screenshot")
async def get_feedback_screenshot(feedback_id: str):
    """A feedback entry's screenshot. Screenshots are admin-only, so /api/files/{id} doesn't serve them."""
    feedback = await db.feedback.find_one({"_id": _object_id(feedback_id, "feedback")}, {"screenshot_id": 1})
    if feedback is None or not feedback.get("screenshot_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenshot not found")
    try:
        grid_out = await fs.get(feedback["screenshot_id"])
    except NoFile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenshot not found") from None
    return await gridfs_file_response(grid_out)


@admin_router.patch("/feedback/{feedback_id}")
async def update_feedback(feedback_id: str, body: FeedbackStatusUpdate):
    result = await db.feedback.update_one(
        {"_id": _object_id(feedback_id, "feedback")},
        {"$set": {"status": body.status, "updated_at": datetime.now(UTC)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    return {"message": "Status updated", "status": body.status}


@admin_router.delete("/feedback/{feedback_id}")
async def delete_feedback(feedback_id: str):
    """Delete a feedback entry and its screenshot."""
    oid = _object_id(feedback_id, "feedback")
    feedback = await db.feedback.find_one({"_id": oid}, {"screenshot_id": 1})
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    if feedback.get("screenshot_id"):
        await fs.delete(feedback["screenshot_id"])
    await db.feedback.delete_one({"_id": oid})
    return {"message": "Feedback deleted successfully"}
