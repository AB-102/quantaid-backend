"""Feedback submissions and the admin feedback review."""

from bson import ObjectId

from tests.conftest import TEST_PREFIX

CATEGORY = f"{TEST_PREFIX}bug"


def _submit_with_screenshot(client) -> str:
    res = client.post(
        "/api/feedback",
        data={"category": CATEGORY, "feedback": "  Broken button  "},
        files={"screenshot": ("_test_shot.png", b"shot", "image/png")},
    )
    assert res.status_code == 201
    assert res.json()["message"] == "Feedback submitted successfully"
    return res.json()["id"]


class TestSubmitFeedback:
    def test_anonymous_feedback_with_a_screenshot(self, client, test_db):
        feedback_id = _submit_with_screenshot(client)
        doc = test_db.feedback.find_one({"_id": ObjectId(feedback_id)})
        assert doc["user_id"] == "anonymous"
        assert doc["feedback"] == "Broken button"
        assert doc["status"] == "open"
        # Screenshots are admin-only, so the public file route hides them
        assert client.get(f"/api/files/{doc['screenshot_id']}").status_code == 404

    def test_signed_in_feedback_without_a_screenshot(self, client, login_as, test_db):
        email = login_as("feedback-user")
        res = client.post("/api/feedback", data={"category": CATEGORY, "feedback": "Nice"})
        doc = test_db.feedback.find_one({"_id": ObjectId(res.json()["id"])})
        assert doc["user_id"] == email
        assert doc["screenshot_id"] is None

    def test_blank_feedback_is_rejected(self, client):
        res = client.post("/api/feedback", data={"category": CATEGORY, "feedback": "   "})
        assert res.status_code == 400

    def test_non_image_screenshot_is_rejected(self, client, test_db):
        res = client.post(
            "/api/feedback",
            data={"category": CATEGORY, "feedback": "Look"},
            files={"screenshot": ("_test_page.html", b"<script>alert(1)</script>", "text/html")},
        )
        assert res.status_code == 415
        assert test_db.feedback.count_documents({"category": CATEGORY, "feedback": "Look"}) == 0


class TestFeedbackAdmin:
    def test_review_flow(self, client, login_as):
        feedback_id = _submit_with_screenshot(client)
        login_as("feedback-admin", is_admin=True)

        listing = client.get("/api/admin/feedback").json()
        item = next(fb for fb in listing["feedback"] if fb["id"] == feedback_id)
        assert set(item) == {"id", "userId", "category", "feedback", "status", "createdAt", "hasScreenshot"}
        assert item["hasScreenshot"] is True
        assert item["userId"] == "anonymous"
        assert item["category"] == CATEGORY
        assert listing["totalCount"] >= 1
        assert "hasMore" in listing

        screenshot_url = f"/api/admin/feedback/{feedback_id}/screenshot"
        screenshot = client.get(screenshot_url)
        assert screenshot.status_code == 200
        assert screenshot.content == b"shot"

        res = client.patch(f"/api/admin/feedback/{feedback_id}", json={"status": "resolved"})
        assert res.json() == {"message": "Status updated", "status": "resolved"}
        assert client.patch(f"/api/admin/feedback/{feedback_id}", json={"status": "done"}).status_code == 422
        resolved = client.get("/api/admin/feedback", params={"status": "resolved"}).json()["feedback"]
        assert any(fb["id"] == feedback_id for fb in resolved)

        csv = client.get("/api/admin/feedback/export", params={"status": "resolved"})
        assert csv.headers["content-type"].startswith("text/csv")
        assert CATEGORY in csv.text
        assert screenshot_url in csv.text

        assert client.delete(f"/api/admin/feedback/{feedback_id}").status_code == 200
        assert client.get(screenshot_url).status_code == 404
        assert client.delete(f"/api/admin/feedback/{feedback_id}").status_code == 404

    def test_export_escapes_formulas(self, client, login_as):
        client.post("/api/feedback", data={"category": CATEGORY, "feedback": '=HYPERLINK("x")'})
        login_as("feedback-csv-admin", is_admin=True)
        assert "'=HYPERLINK" in client.get("/api/admin/feedback/export").text

    def test_feedback_without_a_screenshot_has_no_screenshot(self, client, login_as):
        res = client.post("/api/feedback", data={"category": CATEGORY, "feedback": "No picture"})
        login_as("feedback-noshot-admin", is_admin=True)
        assert client.get(f"/api/admin/feedback/{res.json()['id']}/screenshot").status_code == 404

    def test_invalid_ids(self, client, login_as):
        login_as("feedback-ids-admin", is_admin=True)
        assert client.delete("/api/admin/feedback/not-an-id").status_code == 400
        assert client.get("/api/admin/feedback/not-an-id/screenshot").status_code == 400

    def test_students_cannot_review_feedback(self, client, login_as):
        login_as("feedback-student")
        assert client.get("/api/admin/feedback").status_code == 403
        assert client.get(f"/api/admin/feedback/{ObjectId()}/screenshot").status_code == 403
