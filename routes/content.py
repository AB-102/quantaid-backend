from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin

from data.default_dashboard_config import DEFAULT_DASHBOARD_CONFIG
from database.mongo import db, fs
from routes import admin_required

content_bp = Blueprint("content", __name__)

# --- Validation ---

ALLOWED_BLOCK_TYPES = {"heading", "subheading", "paragraph", "image"}


def validate_blocks(blocks: list) -> tuple[bool, str]:
    """Validate that all blocks have allowed types and required fields."""
    if not isinstance(blocks, list):
        return False, "blocks must be an array"
    for i, block in enumerate(blocks):
        if not isinstance(block, dict):
            return False, f"block {i} must be an object"
        btype = block.get("type")
        if btype not in ALLOWED_BLOCK_TYPES:
            return False, f'block {i} has invalid type "{btype}"'
        if btype in ("heading", "subheading", "paragraph"):
            if not block.get("text"):
                return False, f'block {i} ({btype}) requires "text"'
        elif btype == "image":
            if not block.get("fileId"):
                return False, f'block {i} (image) requires "fileId"'
    return True, ""


# --- Public GET endpoints ---


@content_bp.route("/api/lessons", methods=["GET"])
@cross_origin(supports_credentials=True)
def list_lessons():
    """List all lessons (id, courseId, title) ordered by courseId."""
    lessons = list(db.lessons_v2.find({}, {"_id": 1, "courseId": 1, "title": 1}).sort("courseId", 1))
    for lesson in lessons:
        lesson["_id"] = str(lesson["_id"])
    return jsonify(lessons), 200


@content_bp.route("/api/lessons/<int:course_id>", methods=["GET"])
@cross_origin(supports_credentials=True)
def get_lesson(course_id: int):
    """Get a single lesson by courseId, including blocks and quiz."""
    lesson = db.lessons_v2.find_one({"courseId": course_id})
    if not lesson:
        return jsonify({"error": "Lesson not found"}), 404
    lesson["_id"] = str(lesson["_id"])
    return jsonify(lesson), 200


# --- Admin image upload ---


@content_bp.route("/admin/upload_content_image", methods=["POST", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def upload_content_image():
    """Upload an image for use in lesson content blocks. Returns the fileId."""
    if request.method == "OPTIONS":
        return "", 200
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    image_file = request.files["image"]
    if not image_file.filename:
        return jsonify({"error": "Empty filename"}), 400

    file_id = fs.put(
        image_file,
        filename=image_file.filename,
        content_type=image_file.content_type or "image/png",
        visibility="public",
    )
    return jsonify({"fileId": str(file_id), "url": f"/file/{str(file_id)}"}), 200


# --- Admin lesson CRUD ---


@content_bp.route("/admin/lessons", methods=["POST", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def create_lesson():
    """Create a new lesson with block-based content."""
    if request.method == "OPTIONS":
        return "", 200
    data = request.json or {}
    course_id = data.get("courseId")
    title = data.get("title", "")
    blocks = data.get("blocks", [])
    quiz = data.get("quiz", [])
    interactive_terms = data.get("interactiveTerms", {})

    if course_id is None:
        return jsonify({"error": "courseId is required"}), 400
    if not title:
        return jsonify({"error": "title is required"}), 400

    # Check for duplicate courseId
    if db.lessons_v2.find_one({"courseId": course_id}):
        return jsonify({"error": f"Lesson with courseId {course_id} already exists"}), 409

    valid, err = validate_blocks(blocks)
    if not valid:
        return jsonify({"error": err}), 400

    lesson = {
        "courseId": course_id,
        "title": title,
        "blocks": blocks,
        "quiz": quiz,
        "interactiveTerms": interactive_terms,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    result = db.lessons_v2.insert_one(lesson)
    return jsonify({"message": "Lesson created", "_id": str(result.inserted_id)}), 201


@content_bp.route("/admin/lessons/<int:course_id>", methods=["PUT", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def update_lesson(course_id: int):
    """Update an existing lesson's content blocks, quiz, or title."""
    if request.method == "OPTIONS":
        return "", 200
    data = request.json or {}

    update_fields: dict = {"updated_at": datetime.now(UTC)}

    if "title" in data:
        update_fields["title"] = data["title"]
    if "blocks" in data:
        valid, err = validate_blocks(data["blocks"])
        if not valid:
            return jsonify({"error": err}), 400
        update_fields["blocks"] = data["blocks"]
    if "quiz" in data:
        update_fields["quiz"] = data["quiz"]
    if "interactiveTerms" in data:
        update_fields["interactiveTerms"] = data["interactiveTerms"]

    result = db.lessons_v2.update_one({"courseId": course_id}, {"$set": update_fields})
    if result.matched_count == 0:
        return jsonify({"error": "Lesson not found"}), 404
    return jsonify({"message": "Lesson updated"}), 200


@content_bp.route("/admin/lessons/<int:course_id>", methods=["DELETE", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def delete_lesson(course_id: int):
    """Delete a lesson by courseId."""
    if request.method == "OPTIONS":
        return "", 200
    result = db.lessons_v2.delete_one({"courseId": course_id})
    if result.deleted_count == 0:
        return jsonify({"error": "Lesson not found"}), 404
    return jsonify({"message": "Lesson deleted"}), 200


@content_bp.route("/admin/lessons/reorder", methods=["POST", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def reorder_lessons():
    """Reorder lessons by reassigning courseIds.

    Expects: { "order": [oldCourseId, oldCourseId, ...] }
    The position in the array becomes the new courseId.
    """
    if request.method == "OPTIONS":
        return "", 200
    data = request.json or {}
    order = data.get("order", [])
    if not isinstance(order, list) or len(order) == 0:
        return jsonify({"error": "order must be a non-empty array of courseIds"}), 400

    # Validate all courseIds exist before reordering
    existing_ids = {doc["courseId"] for doc in db.lessons_v2.find({}, {"courseId": 1, "_id": 0})}
    missing = [cid for cid in order if cid not in existing_ids]
    if missing:
        return jsonify({"error": f"Unknown courseIds: {missing}"}), 400

    # Use a temporary offset to avoid duplicate courseId conflicts during swap
    temp_offset = 10000
    now = datetime.now(UTC)

    # Phase 1: move all to temp courseIds
    for new_idx, old_course_id in enumerate(order):
        db.lessons_v2.update_one(
            {"courseId": old_course_id}, {"$set": {"courseId": temp_offset + new_idx, "updated_at": now}}
        )

    # Phase 2: move from temp to final
    for new_idx in range(len(order)):
        db.lessons_v2.update_one({"courseId": temp_offset + new_idx}, {"$set": {"courseId": new_idx}})

    return jsonify({"message": "Lessons reordered"}), 200


@content_bp.route("/admin/lessons/export", methods=["GET", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def export_lessons():
    """Export all lessons as JSON (for backup/transfer)."""
    if request.method == "OPTIONS":
        return "", 200
    lessons = list(db.lessons_v2.find({}).sort("courseId", 1))
    for lesson in lessons:
        lesson["_id"] = str(lesson["_id"])
        for field in ("created_at", "updated_at"):
            val = lesson.get(field)
            if isinstance(val, datetime):
                lesson[field] = val.isoformat()
    return jsonify(lessons), 200


# --- Dashboard config ---


def _get_dashboard_config() -> dict:
    """Return the dashboard config from DB, or the default if not yet seeded."""
    doc = db.dashboard_config.find_one({}, {"_id": 0})
    if doc:
        doc.pop("updated_at", None)
        doc.pop("updated_by", None)
        return doc
    return DEFAULT_DASHBOARD_CONFIG


@content_bp.route("/api/dashboard-config", methods=["GET"])
@cross_origin(supports_credentials=True)
def get_dashboard_config():
    """Public endpoint: returns the dashboard structure for rendering."""
    return jsonify(_get_dashboard_config()), 200


@content_bp.route("/admin/dashboard-config", methods=["GET", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def admin_get_dashboard_config():
    """Admin endpoint: returns the dashboard structure for editing."""
    if request.method == "OPTIONS":
        return "", 200
    return jsonify(_get_dashboard_config()), 200


@content_bp.route("/admin/dashboard-config", methods=["PUT", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def admin_update_dashboard_config():
    """Replace the entire dashboard config."""
    if request.method == "OPTIONS":
        return "", 200
    data = request.json or {}

    sections = data.get("sections")
    courses = data.get("courses")
    if not isinstance(sections, list) or not isinstance(courses, list):
        return jsonify({"error": "sections and courses are required arrays"}), 400

    doc = {
        "sections": sections,
        "courses": courses,
        "updated_at": datetime.now(UTC),
    }

    db.dashboard_config.replace_one({}, doc, upsert=True)
    return jsonify({"message": "Dashboard config updated"}), 200


@content_bp.route("/admin/dashboard-config/seed", methods=["POST", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def seed_dashboard_config():
    """Seed the dashboard config from the default if not already present."""
    if request.method == "OPTIONS":
        return "", 200
    existing = db.dashboard_config.find_one()
    if existing:
        return jsonify({"message": "Config already exists", "seeded": False}), 200

    doc = {
        **DEFAULT_DASHBOARD_CONFIG,
        "updated_at": datetime.now(UTC),
    }
    db.dashboard_config.insert_one(doc)
    return jsonify({"message": "Dashboard config seeded", "seeded": True}), 201


# --- Legacy endpoints (kept for backwards compatibility) ---


@content_bp.route("/admin/upload_lesson", methods=["POST", "OPTIONS"])
@admin_required
@cross_origin(supports_credentials=True)
def legacy_upload_lesson():
    try:
        data = request.json or {}
        lesson = {
            "title": data.get("title"),
            "description": data.get("description"),
            "readings": data.get("readings", []),
            "quiz": data.get("quiz", None),
            "created_at": datetime.now(UTC),
        }
        db.lessons.insert_one(lesson)
        return jsonify({"message": "Lesson uploaded successfully"}), 200
    except Exception as e:
        print("Error uploading lesson:", e)
        return jsonify({"error": str(e)}), 500


@content_bp.route("/admin/upload_reading", methods=["POST", "OPTIONS"])
@admin_required
def legacy_upload_reading():
    if request.method == "OPTIONS":
        return "", 200
    try:
        title = request.form.get("title")
        content = request.form.get("content")
        image_id = None
        video_id = None
        if "image" in request.files:
            image_file = request.files["image"]
            image_id = fs.put(image_file, filename=image_file.filename, visibility="public")
        if "video" in request.files:
            video_file = request.files["video"]
            video_id = fs.put(video_file, filename=video_file.filename, visibility="public")
        reading = {
            "title": title,
            "content": content,
            "image_id": image_id,
            "video_id": video_id,
            "created_at": datetime.now(UTC),
        }
        db.readings.insert_one(reading)
        return jsonify({"message": "Reading uploaded successfully"}), 200
    except Exception as e:
        print("Error uploading reading:", e)
        return jsonify({"error": str(e)}), 500


@content_bp.route("/admin/upload_quiz", methods=["POST", "OPTIONS"])
@admin_required
def legacy_upload_quiz():
    if request.method == "OPTIONS":
        return "", 200
    try:
        data = request.json or {}
        quiz = {"questions": data.get("questions"), "created_at": datetime.now(UTC)}
        db.quizzes.insert_one(quiz)
        return jsonify({"message": "Quiz uploaded successfully"}), 200
    except Exception as e:
        print("Error uploading quiz:", e)
        return jsonify({"error": str(e)}), 500
