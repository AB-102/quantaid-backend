"""Quiz results and progress reads."""


class TestProgressRoutes:
    def test_passing_twice_records_both_attempts(self, client, login_as, test_db):
        email = login_as("quiz")
        for _ in range(2):
            res = client.post("/api/me/quiz-results", json={"courseId": 0, "score": 5, "passed": True})
            assert res.status_code == 201
            assert res.json() == {"message": "Quiz result saved successfully"}
        quizzes = test_db.users.find_one({"user_id": email})["completedQuizzes"]
        assert [(q["courseId"], q["score"], q["passed"]) for q in quizzes] == [(0, 5, True), (0, 5, True)]

    def test_failed_quiz_is_recorded(self, client, login_as, test_db):
        email = login_as("quiz-fail")
        res = client.post("/api/me/quiz-results", json={"courseId": 0, "score": 1, "passed": False})
        assert res.status_code == 201
        assert test_db.users.find_one({"user_id": email})["completedQuizzes"][0]["passed"] is False

    def test_invalid_quiz_result_is_rejected(self, client, login_as):
        login_as("quiz-invalid")
        res = client.post("/api/me/quiz-results", json={"courseId": "first", "score": 5, "passed": True})
        assert res.status_code == 422

    def test_progress_and_first_lesson_view(self, client, login_as, test_db):
        email = login_as("progress", name="Progress User")
        for _ in range(2):  # PUT is safe to repeat
            res = client.put("/api/me/onboarding", json={"hasViewedFirstLesson": True})
            assert res.json() == {"message": "Onboarding state saved"}
        assert "firstLessonViewedAt" in test_db.users.find_one({"user_id": email})
        assert client.put("/api/me/onboarding", json={}).status_code == 422
        assert client.get("/api/me/progress").json() == {
            "completedQuizzes": [],
            "hasViewedFirstLesson": True,
            "email": email,
            "name": "Progress User",
            "picture": "",
        }

    def test_progress_requires_login(self, client):
        assert client.get("/api/me/progress").status_code == 401
        assert client.post("/api/me/quiz-results", json={"courseId": 0, "score": 5, "passed": True}).status_code == 401
