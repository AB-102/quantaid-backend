"""Lessons, the dashboard config, and lesson images."""

from tests.conftest import TEST_COURSE_ID_START

COURSE_ID = TEST_COURSE_ID_START


class TestPublicContent:
    def test_lesson_list_and_detail(self, client):
        lessons = client.get("/api/lessons").json()
        assert lessons, "the test database should be seeded with the default lessons on startup"
        first = lessons[0]
        assert set(first) == {"id", "courseId", "title"}
        detail = client.get(f"/api/lessons/{first['courseId']}").json()
        assert detail["id"] == first["id"]
        assert detail["title"] == first["title"]
        assert {"blocks", "quiz", "createdAt", "updatedAt"} <= set(detail)
        assert not {"_id", "created_at", "updated_at"} & set(detail)

    def test_missing_lesson(self, client):
        assert client.get("/api/lessons/987654").status_code == 404

    def test_dashboard_config(self, client):
        config = client.get("/api/dashboard-config").json()
        assert "sections" in config
        assert "courses" in config
        assert "_id" not in config


class TestLessonAdmin:
    def test_create_update_delete(self, client, login_as, test_db):
        login_as("content-admin", is_admin=True)
        lesson = {"courseId": COURSE_ID, "title": "Test lesson", "blocks": [{"type": "paragraph", "text": "Hi"}]}
        res = client.post("/api/admin/lessons", json=lesson)
        assert res.status_code == 201
        assert res.json()["message"] == "Lesson created"
        assert set(res.json()) == {"message", "id"}
        assert client.post("/api/admin/lessons", json=lesson).status_code == 409

        assert client.patch(f"/api/admin/lessons/{COURSE_ID}", json={"title": "Renamed"}).status_code == 200
        # A partial update is a PATCH; there is no PUT on a lesson
        assert client.put(f"/api/admin/lessons/{COURSE_ID}", json={"title": "Renamed"}).status_code == 405
        stored = test_db.lessons_v2.find_one({"courseId": COURSE_ID})
        assert stored["title"] == "Renamed"
        assert stored["blocks"] == [{"type": "paragraph", "text": "Hi"}]  # untouched by the partial update

        assert client.delete(f"/api/admin/lessons/{COURSE_ID}").status_code == 200
        assert client.delete(f"/api/admin/lessons/{COURSE_ID}").status_code == 404
        assert client.patch(f"/api/admin/lessons/{COURSE_ID}", json={"title": "Gone"}).status_code == 404

    def test_invalid_blocks_are_rejected(self, client, login_as):
        login_as("blocks-admin", is_admin=True)
        res = client.post(
            "/api/admin/lessons", json={"courseId": COURSE_ID, "title": "Bad", "blocks": [{"type": "image"}]}
        )
        assert res.status_code == 400
        assert res.json() == {"detail": 'block 0 (image) requires "fileId"'}

    def test_unknown_block_fields_are_kept(self, client, login_as, test_db):
        login_as("fields-admin", is_admin=True)
        blocks = [{"type": "image", "fileId": "abc", "caption": "A caption", "align": "left", "width": 50}]
        client.post("/api/admin/lessons", json={"courseId": COURSE_ID, "title": "Image", "blocks": blocks})
        assert test_db.lessons_v2.find_one({"courseId": COURSE_ID})["blocks"] == blocks

    def test_export(self, client, login_as):
        login_as("export-admin", is_admin=True)
        titles = [lesson["title"] for lesson in client.get("/api/lessons").json()]
        exported = client.get("/api/admin/lessons/export").json()
        assert [lesson["title"] for lesson in exported] == titles
        assert isinstance(exported[0]["id"], str)
        assert "_id" not in exported[0]

    def test_lessons_cannot_be_renumbered(self, client, login_as):
        login_as("reorder-admin", is_admin=True)
        # Topics and students' quiz results point at a lesson's courseId, so there's no reorder route
        assert client.post("/api/admin/lessons/reorder", json={"order": [0]}).status_code == 405

    def test_dashboard_config_round_trip(self, client, login_as):
        login_as("config-admin", is_admin=True)
        config = client.get("/api/admin/dashboard-config").json()
        assert config == client.get("/api/dashboard-config").json()
        res = client.put(
            "/api/admin/dashboard-config", json={"sections": config["sections"], "courses": config["courses"]}
        )
        assert res.status_code == 200
        assert client.get("/api/dashboard-config").json() == config
        assert client.put("/api/admin/dashboard-config", json={"sections": "nope", "courses": []}).status_code == 422

    def test_uploaded_image_is_public(self, client, login_as):
        login_as("image-admin", is_admin=True)
        res = client.post("/api/admin/images", files={"image": ("_test_image.png", b"png-bytes", "image/png")})
        assert res.status_code == 201
        body = res.json()
        assert body["url"] == f"/api/files/{body['fileId']}"
        client.cookies.clear()  # lesson images load without signing in
        served = client.get(body["url"])
        assert served.status_code == 200
        assert served.content == b"png-bytes"

    def test_uploaded_image_must_be_an_image(self, client, login_as):
        login_as("image-type-admin", is_admin=True)
        res = client.post("/api/admin/images", files={"image": ("_test_page.html", b"<script>", "text/html")})
        assert res.status_code == 415

    def test_students_cannot_edit_content(self, client, login_as):
        login_as("content-student")
        assert client.post("/api/admin/lessons", json={"courseId": COURSE_ID, "title": "No"}).status_code == 403
        assert client.get(f"/api/admin/lessons/{COURSE_ID}/revisions").status_code == 403
        assert client.get("/api/admin/dashboard-config").status_code == 403


class TestQuizLinks:
    BLOCKS = [
        {"type": "subheading", "text": "Superposition", "id": "superposition"},
        {"type": "paragraph", "text": "A qubit can be in both states.", "id": "both-states"},
    ]

    def _question(self, *labels: str) -> dict:
        return {"question": "Q?", "options": ["a", "b"], "correctAnswer": 0, "lessonBlockIds": list(labels)}

    def test_questions_must_review_existing_labels(self, client, login_as):
        login_as("links-admin", is_admin=True)
        lesson = {"courseId": COURSE_ID, "title": "Links", "blocks": self.BLOCKS, "quiz": [self._question("nope")]}
        res = client.post("/api/admin/lessons", json=lesson)
        assert res.status_code == 400
        assert res.json() == {"detail": 'question 1 reviews label "nope", which no block has'}

        lesson["quiz"] = [self._question("superposition", "both-states")]
        assert client.post("/api/admin/lessons", json=lesson).status_code == 201

    def test_removing_a_reviewed_label_is_rejected(self, client, login_as):
        login_as("links-patch-admin", is_admin=True)
        lesson = {
            "courseId": COURSE_ID,
            "title": "Links",
            "blocks": self.BLOCKS,
            "quiz": [self._question("both-states")],
        }
        client.post("/api/admin/lessons", json=lesson)
        # Only the blocks change, but the stored quiz still reviews "both-states"
        res = client.patch(f"/api/admin/lessons/{COURSE_ID}", json={"blocks": self.BLOCKS[:1]})
        assert res.status_code == 400
        assert "both-states" in res.json()["detail"]
        # Only the quiz changes, and the stored blocks don't have the label
        res = client.patch(f"/api/admin/lessons/{COURSE_ID}", json={"quiz": [self._question("missing")]})
        assert res.status_code == 400

    def test_labels_must_be_unique_and_plain(self, client, login_as):
        login_as("labels-admin", is_admin=True)
        duplicate = [{"type": "paragraph", "text": "One", "id": "x"}, {"type": "paragraph", "text": "Two", "id": "x"}]
        res = client.post("/api/admin/lessons", json={"courseId": COURSE_ID, "title": "Dup", "blocks": duplicate})
        assert res.json() == {"detail": 'label "x" is used by more than one block'}
        spaced = [{"type": "paragraph", "text": "One", "id": "Has Spaces"}]
        res = client.post("/api/admin/lessons", json={"courseId": COURSE_ID, "title": "Bad", "blocks": spaced})
        assert res.status_code == 400
        assert "invalid label" in res.json()["detail"]


class TestRevisions:
    def test_each_save_keeps_the_version_it_replaces(self, client, login_as):
        first_admin = login_as("rev-first", is_admin=True)
        blocks = [{"type": "paragraph", "text": "Version one"}]
        client.post("/api/admin/lessons", json={"courseId": COURSE_ID, "title": "V1", "blocks": blocks})
        assert client.get(f"/api/admin/lessons/{COURSE_ID}/revisions").json() == []

        second_admin = login_as("rev-second", is_admin=True)
        client.patch(f"/api/admin/lessons/{COURSE_ID}", json={"title": "V2"})
        client.patch(f"/api/admin/lessons/{COURSE_ID}", json={"title": "V3"})

        revisions = client.get(f"/api/admin/lessons/{COURSE_ID}/revisions").json()
        # Newest first; each revision records who saved that version
        assert [(r["title"], r["savedBy"]) for r in revisions] == [("V2", second_admin), ("V1", first_admin)]
        assert revisions[0]["blockCount"] == 1
        assert revisions[0]["questionCount"] == 0

        full = client.get(f"/api/admin/lessons/{COURSE_ID}/revisions/{revisions[1]['id']}").json()
        assert full["title"] == "V1"
        assert full["blocks"] == blocks

    def test_deleted_lessons_keep_their_last_version(self, client, login_as):
        login_as("rev-delete", is_admin=True)
        client.post("/api/admin/lessons", json={"courseId": COURSE_ID, "title": "Doomed"})
        client.delete(f"/api/admin/lessons/{COURSE_ID}")
        assert [r["title"] for r in client.get(f"/api/admin/lessons/{COURSE_ID}/revisions").json()] == ["Doomed"]

    def test_unknown_revision(self, client, login_as):
        login_as("rev-unknown", is_admin=True)
        assert client.get(f"/api/admin/lessons/{COURSE_ID}/revisions/not-an-id").status_code == 404
        assert client.get(f"/api/admin/lessons/{COURSE_ID}/revisions/{'0' * 24}").status_code == 404

    def test_public_lessons_hide_who_saved_them(self, client, login_as):
        login_as("rev-public", is_admin=True)
        client.post("/api/admin/lessons", json={"courseId": COURSE_ID, "title": "Public"})
        assert "updatedBy" not in client.get(f"/api/lessons/{COURSE_ID}").json()
        assert "updated_by" not in client.get(f"/api/lessons/{COURSE_ID}").json()
