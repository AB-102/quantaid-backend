from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from core.file_urls import file_url
from core.uploads import require_image
from data.default_dashboard_config import DEFAULT_DASHBOARD_CONFIG
from database.db import db, fs
from dependencies.auth import require_admin
from schemas.content import DashboardConfigUpdate, LessonCreate, LessonUpdate, ReorderRequest

router = APIRouter(prefix="/api", tags=["Content"])
admin_router = APIRouter(prefix="/api/admin", tags=["Content admin"], dependencies=[Depends(require_admin)])

ALLOWED_BLOCK_TYPES = {"heading", "subheading", "paragraph", "image"}


def validate_blocks(blocks: list[dict]) -> str | None:
    """Return an error message for the first invalid block, or None if every block is valid."""
    for i, block in enumerate(blocks):
        block_type = block.get("type")
        if block_type not in ALLOWED_BLOCK_TYPES:
            return f'block {i} has invalid type "{block_type}"'
        if block_type == "image":
            if not block.get("fileId"):
                return f'block {i} (image) requires "fileId"'
        elif not block.get("text"):
            return f'block {i} ({block_type}) requires "text"'
    return None


def _lesson_out(doc: dict) -> dict:
    """A stored lesson as the API returns it: camelCase `id`, `createdAt` and `updatedAt`."""
    lesson = {key: value for key, value in doc.items() if key not in ("_id", "created_at", "updated_at")}
    lesson["id"] = str(doc["_id"])
    if "created_at" in doc:
        lesson["createdAt"] = doc["created_at"]
    if "updated_at" in doc:
        lesson["updatedAt"] = doc["updated_at"]
    return lesson


async def _get_dashboard_config() -> dict:
    """The dashboard config from the database, or the default if it hasn't been seeded yet."""
    doc = await db.dashboard_config.find_one({}, {"_id": 0, "updated_at": 0, "updated_by": 0})
    return doc or DEFAULT_DASHBOARD_CONFIG


# --- Public ---


@router.get("/lessons")
async def list_lessons():
    """All lessons (id, courseId, title) ordered by courseId."""
    lessons = await db.lessons_v2.find({}, {"_id": 1, "courseId": 1, "title": 1}).sort("courseId", 1).to_list()
    return [_lesson_out(lesson) for lesson in lessons]


@router.get("/lessons/{course_id}")
async def get_lesson(course_id: int):
    """One lesson by courseId, including blocks and quiz."""
    lesson = await db.lessons_v2.find_one({"courseId": course_id})
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return _lesson_out(lesson)


@router.get("/dashboard-config")
async def get_dashboard_config():
    return await _get_dashboard_config()


# --- Admin ---


@admin_router.post("/images", status_code=status.HTTP_201_CREATED)
async def upload_image(image: UploadFile):
    """Upload an image for a lesson image block. Returns the fileId the block stores."""
    if not image.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty filename")
    require_image(image)
    file_id = await fs.put(
        await image.read(),
        filename=image.filename,
        content_type=image.content_type,
        visibility="public",
    )
    return {"fileId": str(file_id), "url": file_url(file_id)}


@admin_router.post("/lessons", status_code=status.HTTP_201_CREATED)
async def create_lesson(body: LessonCreate):
    if await db.lessons_v2.find_one({"courseId": body.courseId}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Lesson with courseId {body.courseId} already exists"
        )
    error = validate_blocks(body.blocks)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    now = datetime.now(UTC)
    result = await db.lessons_v2.insert_one({**body.model_dump(), "created_at": now, "updated_at": now})
    return {"message": "Lesson created", "id": str(result.inserted_id)}


# /reorder and /export are declared before /{course_id} so they're never read as a courseId


@admin_router.post("/lessons/reorder")
async def reorder_lessons(body: ReorderRequest):
    """Reassign courseIds: the position of each old courseId in `order` becomes its new courseId."""
    existing_ids = set(await db.lessons_v2.distinct("courseId"))
    missing = [course_id for course_id in body.order if course_id not in existing_ids]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown courseIds: {missing}")
    # Move every lesson to a temporary courseId first, so two lessons never share a courseId mid-reorder
    temp_offset = 10000
    now = datetime.now(UTC)
    for new_id, old_id in enumerate(body.order):
        await db.lessons_v2.update_one(
            {"courseId": old_id}, {"$set": {"courseId": temp_offset + new_id, "updated_at": now}}
        )
    for new_id in range(len(body.order)):
        await db.lessons_v2.update_one({"courseId": temp_offset + new_id}, {"$set": {"courseId": new_id}})
    return {"message": "Lessons reordered"}


@admin_router.get("/lessons/export")
async def export_lessons():
    """All lessons in full, for backup or transfer."""
    lessons = await db.lessons_v2.find({}).sort("courseId", 1).to_list()
    return [_lesson_out(lesson) for lesson in lessons]


@admin_router.patch("/lessons/{course_id}")
async def update_lesson(course_id: int, body: LessonUpdate):
    """Change only the fields present in the request."""
    update = body.model_dump(exclude_none=True)
    if "blocks" in update:
        error = validate_blocks(update["blocks"])
        if error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    update["updated_at"] = datetime.now(UTC)
    result = await db.lessons_v2.update_one({"courseId": course_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return {"message": "Lesson updated"}


@admin_router.delete("/lessons/{course_id}")
async def delete_lesson(course_id: int):
    result = await db.lessons_v2.delete_one({"courseId": course_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return {"message": "Lesson deleted"}


@admin_router.get("/dashboard-config")
async def admin_get_dashboard_config():
    return await _get_dashboard_config()


@admin_router.put("/dashboard-config")
async def admin_update_dashboard_config(body: DashboardConfigUpdate):
    """Replace the whole dashboard config."""
    await db.dashboard_config.replace_one(
        {}, {"sections": body.sections, "courses": body.courses, "updated_at": datetime.now(UTC)}, upsert=True
    )
    return {"message": "Dashboard config updated"}
