from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin

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

# Default structure returned when no config exists in the DB yet.
# Mirrors the hardcoded courses[] array from Dashboard.tsx.
DEFAULT_DASHBOARD_CONFIG = {
    "sections": [
        {"id": "foundations", "title": "Foundations", "order": 0, "courses": [0, 1, 2]},
        {"id": "in-action", "title": "Quantum computing in action", "order": 1, "courses": [3, 4, 5]},
        {"id": "deep-dive", "title": "Deep dive into quantum theory", "order": 2, "courses": [6, 7, 8]},
    ],
    "courses": [
        {
            "id": 0,
            "title": "Introduction to Quantum Computing",
            "description": "Discover what quantum computing is and how it differs from classical computing.",
            "image": "lesson-0",
            "concepts": [
                {
                    "id": "basics",
                    "title": "Quantum Computing Fundamentals",
                    "topics": [
                        {
                            "id": 0,
                            "title": "Welcome to Quantum Computing",
                            "description": "Discover what quantum computing is and how it differs from classical computing.",
                            "implemented": True,
                        },
                        {
                            "id": 50,
                            "title": "Classical Computing Review",
                            "description": "Review the fundamentals of classical computing before diving into quantum.",
                            "implemented": False,
                        },
                        {
                            "id": 51,
                            "title": "Quantum Advantage",
                            "description": "Learn about quantum supremacy and where quantum computers excel.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 1,
            "title": "Basic Quantum Principles",
            "description": "Understand wave-particle duality, superposition, entanglement, and more.",
            "image": "lesson-1",
            "concepts": [
                {
                    "id": "core-concepts",
                    "title": "Qubits, Superposition, and Entanglement",
                    "topics": [
                        {
                            "id": 1,
                            "title": "Basic Quantum Principles",
                            "description": "Understand wave-particle duality, superposition, entanglement, and more.",
                            "implemented": True,
                        },
                        {
                            "id": 52,
                            "title": "Qubits: A Quick Recap",
                            "description": "Deep dive into the fundamental unit of quantum information.",
                            "implemented": False,
                        },
                        {
                            "id": 53,
                            "title": "Superposition in Detail",
                            "description": "Explore how quantum states can exist in multiple configurations.",
                            "implemented": False,
                        },
                    ],
                },
                {
                    "id": "measurements",
                    "title": "Quantum Measurements",
                    "topics": [
                        {
                            "id": 54,
                            "title": "Measurement Basics",
                            "description": "Learn how quantum measurements collapse superposition states.",
                            "implemented": False,
                        },
                        {
                            "id": 55,
                            "title": "Measurement Effects",
                            "description": "Understand the probabilistic nature of quantum measurements.",
                            "implemented": False,
                        },
                        {
                            "id": 56,
                            "title": "Practical Measurements",
                            "description": "Explore real-world quantum measurement techniques.",
                            "implemented": False,
                        },
                    ],
                },
                {
                    "id": "applications",
                    "title": "Real-world Applications",
                    "topics": [
                        {
                            "id": 57,
                            "title": "Quantum Sensing",
                            "description": "Discover how quantum mechanics enables ultra-precise measurements.",
                            "implemented": False,
                        },
                        {
                            "id": 58,
                            "title": "Quantum Communication",
                            "description": "Learn about quantum teleportation and secure communication.",
                            "implemented": False,
                        },
                        {
                            "id": 59,
                            "title": "Early Quantum Computers",
                            "description": "Explore the first generation of quantum computing devices.",
                            "implemented": False,
                        },
                    ],
                },
            ],
        },
        {
            "id": 2,
            "title": "Quantum Gates and Circuits (Basics)",
            "description": "Explore how quantum gates form the building blocks of quantum circuits.",
            "image": "lesson-2",
            "concepts": [
                {
                    "id": "single-gates",
                    "title": "Single Qubit Gates",
                    "topics": [
                        {
                            "id": 2,
                            "title": "Quantum Gates and Circuits (Basics)",
                            "description": "Explore how quantum gates form the building blocks of quantum circuits.",
                            "implemented": True,
                        },
                        {
                            "id": 60,
                            "title": "Pauli Gates",
                            "description": "Learn about the fundamental X, Y, and Z quantum gates.",
                            "implemented": False,
                        },
                        {
                            "id": 61,
                            "title": "Hadamard Gate",
                            "description": "Understand the gate that creates quantum superposition.",
                            "implemented": False,
                        },
                    ],
                },
                {
                    "id": "multi-gates",
                    "title": "Multi-Qubit Gates",
                    "topics": [
                        {
                            "id": 62,
                            "title": "CNOT Gate",
                            "description": "Master the controlled-NOT gate for quantum entanglement.",
                            "implemented": False,
                        },
                        {
                            "id": 63,
                            "title": "Toffoli Gate",
                            "description": "Explore reversible quantum computing with the Toffoli gate.",
                            "implemented": False,
                        },
                        {
                            "id": 64,
                            "title": "Controlled Operations",
                            "description": "Learn how to build complex controlled quantum operations.",
                            "implemented": False,
                        },
                    ],
                },
                {
                    "id": "circuits",
                    "title": "Building Circuits",
                    "topics": [
                        {
                            "id": 65,
                            "title": "Circuit Basics",
                            "description": "Understand how to construct and read quantum circuits.",
                            "implemented": False,
                        },
                        {
                            "id": 66,
                            "title": "Circuit Analysis",
                            "description": "Learn to analyze and optimize quantum circuit performance.",
                            "implemented": False,
                        },
                        {
                            "id": 67,
                            "title": "Simple Algorithms",
                            "description": "Build your first quantum algorithms using basic gates.",
                            "implemented": False,
                        },
                    ],
                },
            ],
        },
        {
            "id": 3,
            "title": "Getting Hands-On",
            "description": "Learn practical quantum computing with real-world examples.",
            "image": "lesson-0",
            "concepts": [
                {
                    "id": "practical",
                    "title": "Practical Implementation",
                    "topics": [
                        {
                            "id": 3,
                            "title": "Getting Hands-on",
                            "description": "Learn practical quantum computing with real-world examples.",
                            "implemented": True,
                        },
                        {
                            "id": 68,
                            "title": "Qiskit Basics",
                            "description": "Get started with IBM's quantum computing framework.",
                            "implemented": False,
                        },
                        {
                            "id": 69,
                            "title": "Running on Real Hardware",
                            "description": "Execute quantum circuits on actual quantum computers.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 4,
            "title": "Foundations for Quantum Computing",
            "description": "Dive deeper into the essential math and physics behind quantum computing.",
            "image": "lesson-1",
            "concepts": [
                {
                    "id": "foundations",
                    "title": "Mathematical Foundations",
                    "topics": [
                        {
                            "id": 4,
                            "title": "Foundations for Quantum Computing",
                            "description": "Dive deeper into the essential math and physics behind quantum computing.",
                            "implemented": True,
                        },
                        {
                            "id": 70,
                            "title": "Linear Algebra Review",
                            "description": "Master the mathematical tools needed for quantum mechanics.",
                            "implemented": False,
                        },
                        {
                            "id": 71,
                            "title": "Complex Numbers",
                            "description": "Understand complex numbers and their role in quantum states.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 5,
            "title": "Quantum Cryptography & Security",
            "description": "Learn how quantum computing impacts cryptography, encryption and security protocols.",
            "image": "lesson-2",
            "concepts": [
                {
                    "id": "cryptography",
                    "title": "Quantum Security",
                    "topics": [
                        {
                            "id": 5,
                            "title": "Quantum Cryptography & Security",
                            "description": "Learn how quantum computing impacts cryptography, encryption and security protocols.",
                            "implemented": True,
                        },
                        {
                            "id": 72,
                            "title": "BB84 Protocol",
                            "description": "Discover the first quantum key distribution protocol.",
                            "implemented": False,
                        },
                        {
                            "id": 73,
                            "title": "Post-Quantum Cryptography",
                            "description": "Explore encryption methods that resist quantum attacks.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 6,
            "title": "Adiabatic Quantum Computing",
            "description": "Explore the adiabatic model and quantum annealing techniques.",
            "image": "lesson-0",
            "concepts": [
                {
                    "id": "adiabatic",
                    "title": "Adiabatic Computing",
                    "topics": [
                        {
                            "id": 6,
                            "title": "Adiabatic Quantum Computing",
                            "description": "Explore the adiabatic model and quantum annealing techniques.",
                            "implemented": True,
                        },
                        {
                            "id": 74,
                            "title": "D-Wave Systems",
                            "description": "Learn about commercial quantum annealing systems.",
                            "implemented": False,
                        },
                        {
                            "id": 75,
                            "title": "Optimization Problems",
                            "description": "Apply quantum annealing to solve complex optimization challenges.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 7,
            "title": "Quantum Signal Processing & Simulation",
            "description": "Understand how quantum systems simulate complex physical processes.",
            "image": "lesson-1",
            "concepts": [
                {
                    "id": "signal-processing",
                    "title": "Signal Processing & Simulation",
                    "topics": [
                        {
                            "id": 7,
                            "title": "Quantum Signal Processing & Simulation",
                            "description": "Understand how quantum systems simulate complex physical processes.",
                            "implemented": True,
                        },
                        {
                            "id": 76,
                            "title": "Phase Estimation",
                            "description": "Master the quantum phase estimation algorithm.",
                            "implemented": False,
                        },
                        {
                            "id": 77,
                            "title": "Quantum Fourier Transform",
                            "description": "Learn the quantum version of the discrete Fourier transform.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
        {
            "id": 8,
            "title": "Quantum Hardware & Future Trends",
            "description": "Discover the cutting-edge hardware behind quantum computers.",
            "image": "lesson-2",
            "concepts": [
                {
                    "id": "hardware",
                    "title": "Hardware & Future",
                    "topics": [
                        {
                            "id": 8,
                            "title": "Quantum Hardware & Future Trends",
                            "description": "Discover the cutting-edge hardware behind quantum computers.",
                            "implemented": True,
                        },
                        {
                            "id": 78,
                            "title": "Superconducting Qubits",
                            "description": "Explore superconducting quantum computing architectures.",
                            "implemented": False,
                        },
                        {
                            "id": 79,
                            "title": "Trapped Ion Systems",
                            "description": "Learn about trapped ion quantum computing platforms.",
                            "implemented": False,
                        },
                    ],
                }
            ],
        },
    ],
}


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
