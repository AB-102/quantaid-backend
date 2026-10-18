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

    def test_reorder_and_export(self, client, login_as):
        login_as("reorder-admin", is_admin=True)
        before = client.get("/api/lessons").json()
        course_ids = [lesson["courseId"] for lesson in before]
        titles = [lesson["title"] for lesson in before]

        assert client.post("/api/admin/lessons/reorder", json={"order": list(reversed(course_ids))}).status_code == 200
        assert [lesson["title"] for lesson in client.get("/api/lessons").json()] == list(reversed(titles))

        # Put them back: the lesson that was first now has the last courseId
        restore = list(reversed(range(len(course_ids))))
        assert client.post("/api/admin/lessons/reorder", json={"order": restore}).status_code == 200
        assert [lesson["title"] for lesson in client.get("/api/lessons").json()] == titles

        exported = client.get("/api/admin/lessons/export").json()
        assert [lesson["title"] for lesson in exported] == titles
        assert isinstance(exported[0]["id"], str)
        assert "_id" not in exported[0]

    def test_reorder_with_unknown_course_id(self, client, login_as):
        login_as("reorder-unknown-admin", is_admin=True)
        res = client.post("/api/admin/lessons/reorder", json={"order": [987654]})
        assert res.status_code == 400

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

    def test_students_cannot_edit_content(self, client, login_as):
        login_as("content-student")
        assert client.post("/api/admin/lessons", json={"courseId": COURSE_ID, "title": "No"}).status_code == 403
        assert client.post("/api/admin/lessons/reorder", json={"order": [0]}).status_code == 403
        assert client.get("/api/admin/dashboard-config").status_code == 403
