"""Quiz results, level unlocking, and progress reads."""

from services.progress_service import MAX_COURSE_ID, compute_level_unlock


class TestComputeLevelUnlock:
    def test_pass_unlocks_the_next_course(self):
        assert compute_level_unlock(0, passed=True) == 1

    def test_fail_unlocks_nothing(self):
        assert compute_level_unlock(0, passed=False) is None

    def test_second_to_last_course_unlocks_the_last(self):
        assert compute_level_unlock(MAX_COURSE_ID - 1, passed=True) == MAX_COURSE_ID

    def test_last_course_unlocks_nothing(self):
        assert compute_level_unlock(MAX_COURSE_ID, passed=True) is None


class TestProgressRoutes:
    def test_passing_twice_records_both_attempts_but_unlocks_once(self, client, login_as, test_db):
        email = login_as("quiz")
        for _ in range(2):
            res = client.post("/api/me/quiz-results", json={"courseId": 0, "score": 5, "passed": True})
            assert res.status_code == 201
            assert res.json() == {"message": "Quiz result saved successfully", "unlockedLevels": [0, 1]}
        quizzes = test_db.users.find_one({"user_id": email})["completedQuizzes"]
        assert [(q["courseId"], q["score"], q["passed"]) for q in quizzes] == [(0, 5, True), (0, 5, True)]

    def test_failed_quiz_is_recorded_without_unlocking(self, client, login_as):
        login_as("quiz-fail")
        res = client.post("/api/me/quiz-results", json={"courseId": 0, "score": 1, "passed": False})
        assert res.json()["unlockedLevels"] == [0]

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
            "unlockedLevels": [0],
            "completedQuizzes": [],
            "hasViewedFirstLesson": True,
            "email": email,
            "name": "Progress User",
            "picture": "",
        }

    def test_progress_requires_login(self, client):
        assert client.get("/api/me/progress").status_code == 401
        assert client.post("/api/me/quiz-results", json={"courseId": 0, "score": 5, "passed": True}).status_code == 401
