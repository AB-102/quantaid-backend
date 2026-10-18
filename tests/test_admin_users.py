"""Admin user list and disabling accounts."""

from datetime import UTC, datetime
from urllib.parse import quote

from tests.conftest import TEST_PREFIX


class TestAdminUsers:
    def test_search_is_plain_text(self, client, login_as, test_db):
        target = f"{TEST_PREFIX}a.b+c@test.com"
        test_db.users.insert_one(
            {"user_id": target, "name": "Dot Plus", "google_sub": "sub-x", "createdAt": datetime.now(UTC)}
        )
        login_as("search-admin", is_admin=True)

        res = client.get("/api/admin/users", params={"search": "a.b+c"})
        users = res.json()["users"]
        assert [user["userId"] for user in users] == [target]
        assert users[0] == {
            "userId": target,
            "name": "Dot Plus",
            "isAdmin": False,
            "profileComplete": False,
            "disabled": False,
            "authMethods": ["google"],
            "createdAt": users[0]["createdAt"],
            "lastLoginAt": None,
        }
        assert set(res.json()) == {"users", "totalCount", "totalUsers", "hasMore"}
        # Regex syntax is searched for literally instead of breaking the query
        assert client.get("/api/admin/users", params={"search": "(("}).status_code == 200

    def test_paging_limits(self, client, login_as):
        login_as("paging-admin", is_admin=True)
        assert client.get("/api/admin/users", params={"limit": 0}).status_code == 422
        assert len(client.get("/api/admin/users", params={"limit": 1}).json()["users"]) == 1

    def test_disabling_a_user_ends_their_session(self, client, login_as):
        student = login_as("to-disable")
        student_token = client.cookies.get("quantaid_token")
        client.cookies.clear()
        login_as("disabler", is_admin=True)

        url = f"/api/admin/users/{quote(student, safe='')}"
        # Setting the state (not toggling it) makes a repeated request harmless
        for _ in range(2):
            res = client.patch(url, json={"disabled": True})
            assert res.json() == {"message": "User disabled", "disabled": True}

        client.cookies.clear()
        client.cookies.set("quantaid_token", student_token)
        assert client.get("/api/me/profile").status_code == 401

    def test_enable_again(self, client, login_as, test_db):
        test_db.users.insert_one({"user_id": f"{TEST_PREFIX}toggle@test.com", "disabled": True})
        login_as("toggler", is_admin=True)
        url = f"/api/admin/users/{quote(TEST_PREFIX + 'toggle@test.com', safe='')}"
        res = client.patch(url, json={"disabled": False})
        assert res.json() == {"message": "User enabled", "disabled": False}

    def test_unknown_user(self, client, login_as):
        login_as("unknown-admin", is_admin=True)
        assert client.patch("/api/admin/users/nobody%40test.com", json={"disabled": True}).status_code == 404
        assert client.patch("/api/admin/users/nobody%40test.com", json={}).status_code == 422
