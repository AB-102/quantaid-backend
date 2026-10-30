from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pymongo.errors import DuplicateKeyError

from core.file_urls import file_url
from core.quiz_links import BLOCK_ID_PATTERN
from core.uploads import require_image
from data.default_dashboard_config import DEFAULT_DASHBOARD_CONFIG
from database.db import db, fs
from dependencies.auth import AdminUser, require_admin
from schemas.content import DashboardConfigUpdate, LessonCreate, LessonUpdate

router = APIRouter(prefix="/api", tags=["Content"])
admin_router = APIRouter(prefix="/api/admin", tags=["Content admin"], dependencies=[Depends(require_admin)])

ALLOWED_BLOCK_TYPES = {"heading", "subheading", "paragraph", "image"}


def validate_blocks(blocks: list[dict]) -> str | None:
    """Return an error message for the first invalid block, or None if every block is valid."""
    labels: set[str] = set()
    for i, block in enumerate(blocks):
        block_type = block.get("type")
        if block_type not in ALLOWED_BLOCK_TYPES:
            return f'block {i} has invalid type "{block_type}"'
        if block_type == "image":
            if not block.get("fileId"):
                return f'block {i} (image) requires "fileId"'
        elif not block.get("text"):
            return f'block {i} ({block_type}) requires "text"'
        label = block.get("id")
        if label is not None:
            if not isinstance(label, str) or not BLOCK_ID_PATTERN.match(label):
                return f'block {i} has invalid label "{label}": use lowercase letters, digits, "-", "_" or ":"'
            if label in labels:
                return f'label "{label}" is used by more than one block'
            labels.add(label)
    return None


def validate_quiz(quiz: list[dict], blocks: list[dict]) -> str | None:
    """Return an error message for the first question that reviews a label no block has, or None."""
    labels = {block["id"] for block in blocks if block.get("id")}
    for i, question in enumerate(quiz):
        for label in question.get("lessonBlockIds", []):
            if label not in labels:
                return f'question {i + 1} reviews label "{label}", which no block has'
    return None


async def _save_revision(lesson: dict) -> None:
    """Keep a copy of a lesson version before it's replaced or deleted, so it can be restored."""
    await db.lesson_revisions.insert_one(
        {
            "courseId": lesson["courseId"],
            "title": lesson.get("title", ""),
            "blocks": lesson.get("blocks", []),
            "quiz": lesson.get("quiz", []),
            "interactiveTerms": lesson.get("interactiveTerms", {}),
            # When this version was saved and by whom; lessons saved before revisions existed have no saved_by
            "saved_at": lesson.get("updated_at") or lesson.get("created_at"),
            "saved_by": lesson.get("updated_by"),
        }
    )


def _revision_out(doc: dict, full: bool) -> dict:
    out = {
        "id": str(doc["_id"]),
        "title": doc["title"],
        "savedAt": doc["saved_at"],
        "savedBy": doc["saved_by"],
    }
    if full:
        return {
            **out,
            "courseId": doc["courseId"],
            "blocks": doc["blocks"],
            "quiz": doc["quiz"],
            "interactiveTerms": doc["interactiveTerms"],
        }
    return {**out, "blockCount": len(doc["blocks"]), "questionCount": len(doc["quiz"])}


def _lesson_out(doc: dict) -> dict:
    """A stored lesson as the API returns it: camelCase `id`, `createdAt` and `updatedAt`, and no admin email."""
    lesson = {key: value for key, value in doc.items() if key not in ("_id", "created_at", "updated_at", "updated_by")}
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
async def create_lesson(body: LessonCreate, admin: AdminUser):
    error = validate_blocks(body.blocks) or validate_quiz(body.quiz, body.blocks)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    now = datetime.now(UTC)
    try:
        # courseId has a unique index (database/seeding.py), so two creates at once can't both succeed
        result = await db.lessons_v2.insert_one(
            {**body.model_dump(), "created_at": now, "updated_at": now, "updated_by": admin.email}
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Lesson with courseId {body.courseId} already exists"
        ) from None
    return {"message": "Lesson created", "id": str(result.inserted_id)}


# /export is declared before /{course_id} so it's never read as a courseId.
# There's no reorder: a lesson's courseId is what topics and students' quiz results point at, so it never changes.


@admin_router.get("/lessons/export")
async def export_lessons():
    """All lessons in full, for backup or transfer."""
    lessons = await db.lessons_v2.find({}).sort("courseId", 1).to_list()
    return [_lesson_out(lesson) for lesson in lessons]


@admin_router.patch("/lessons/{course_id}")
async def update_lesson(course_id: int, body: LessonUpdate, admin: AdminUser):
    """Change only the fields present in the request. The version it replaces is kept as a revision."""
    current = await db.lessons_v2.find_one({"courseId": course_id})
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    update = body.model_dump(exclude_none=True)
    if "blocks" in update or "quiz" in update:
        # Questions and the labels they review must agree, whichever of the two this request changes
        blocks = update.get("blocks", current.get("blocks", []))
        error = validate_blocks(blocks) or validate_quiz(update.get("quiz", current.get("quiz", [])), blocks)
        if error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    await _save_revision(current)
    update["updated_at"] = datetime.now(UTC)
    update["updated_by"] = admin.email
    await db.lessons_v2.update_one({"_id": current["_id"]}, {"$set": update})
    return {"message": "Lesson updated"}


@admin_router.delete("/lessons/{course_id}")
async def delete_lesson(course_id: int):
    """Delete a lesson. Its last version is kept as a revision."""
    lesson = await db.lessons_v2.find_one({"courseId": course_id})
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    await _save_revision(lesson)
    await db.lessons_v2.delete_one({"_id": lesson["_id"]})
    return {"message": "Lesson deleted"}


@admin_router.get("/lessons/{course_id}/revisions")
async def list_revisions(course_id: int):
    """Earlier versions of a lesson, newest first."""
    revisions = await db.lesson_revisions.find({"courseId": course_id}).sort("_id", -1).to_list()
    return [_revision_out(revision, full=False) for revision in revisions]


@admin_router.get("/lessons/{course_id}/revisions/{revision_id}")
async def get_revision(course_id: int, revision_id: str):
    """One earlier version in full, to preview or load back into the editor."""
    try:
        object_id = ObjectId(revision_id)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found") from None
    revision = await db.lesson_revisions.find_one({"_id": object_id, "courseId": course_id})
    if revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    return _revision_out(revision, full=True)


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
