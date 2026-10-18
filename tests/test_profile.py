"""Profile form transformation, profile routes, and profile picture uploads."""

from schemas.user import SaveProfileRequest
from services.profile_service import build_profile_update


class TestBuildProfileUpdate:
    def test_college_level_and_custom_hobbies(self):
        update = build_profile_update(
            SaveProfileRequest(
                educationCategory="College",
                educationLevel="Junior",
                favoriteHobbies=["Reading"],
                customHobbies=" chess, , hiking ",
            )
        )
        assert update["profile"]["education_level"] == "College - Junior"
        assert update["profile"]["favorite_hobbies"] == ["Reading", "chess", "hiking"]
        assert update["profile"]["custom_hobbies"] == "chess, , hiking"
        assert update["onboarding_responses"]["favorite_hobbies"] == ["Reading"]
        assert update["profile_complete"] is True

    def test_high_school_level(self):
        update = build_profile_update(SaveProfileRequest(educationCategory="HighSchool", educationLevel="Senior"))
        assert update["profile"]["education_level"] == "High School - Senior"

    def test_other_education_uses_the_typed_level(self):
        update = build_profile_update(SaveProfileRequest(educationCategory="Other", otherEducationLevel="Bootcamp"))
        assert update["profile"]["education_level"] == "Bootcamp"

    def test_other_education_without_a_typed_level_is_blank(self):
        update = build_profile_update(SaveProfileRequest(educationCategory="Other"))
        assert update["profile"]["education_level"] == ""

    def test_typed_subject_replaces_the_other_checkbox(self):
        update = build_profile_update(
            SaveProfileRequest(subjects=["Physics", "Other (please specify)"], otherSubject="Chemistry")
        )
        assert update["profile"]["subjects_studied"] == ["Physics", "Chemistry"]
        assert update["onboarding_responses"]["subjects"] == ["Physics", "Other (please specify)"]

    def test_other_checkbox_without_a_typed_subject_is_kept(self):
        update = build_profile_update(SaveProfileRequest(subjects=["Other (please specify)"]))
        assert update["profile"]["subjects_studied"] == ["Other (please specify)"]

    def test_empty_custom_hobbies(self):
        update = build_profile_update(SaveProfileRequest(favoriteHobbies=["Gaming"], customHobbies=""))
        assert update["profile"]["favorite_hobbies"] == ["Gaming"]

    def test_personalization_defaults_to_on(self):
        assert build_profile_update(SaveProfileRequest())["hobby_personalization"] is True


class TestProfileRoutes:
    def test_save_and_get_profile(self, client, login_as):
        login_as("profile", name="Profile User", google_sub="sub-profile")
        res = client.put(
            "/api/me/profile",
            json={
                "user_id": "ignored extra field",
                "educationCategory": "College",
                "educationLevel": "Sophomore",
                "subjects": ["Computer Science"],
                "codingExperience": "1-2 year",
                "favoriteHobbies": ["Reading"],
                "customHobbies": "chess",
                "hobbyPersonalization": False,
            },
        )
        assert res.status_code == 200
        assert client.get("/api/me/profile").json() == {
            "name": "Profile User",
            "profilePicture": "",
            "educationCategory": "College",
            "educationLevel": "College - Sophomore",
            "subjectsStudied": ["Computer Science"],
            "codingExperience": "1-2 year",
            "favoriteHobbies": ["Reading", "chess"],
            "customHobbies": "chess",
            "hobbyPersonalization": False,
            "hasGoogle": True,
        }

    def test_profile_requires_login(self, client):
        assert client.get("/api/me/profile").status_code == 401
        assert client.put("/api/me/profile", json={}).status_code == 401

    def test_picture_upload_is_served_and_replaced(self, client, login_as, test_db):
        email = login_as("picture")
        first = client.put("/api/me/profile-picture", files={"picture": ("_test_one.png", b"one", "image/png")})
        assert first.status_code == 200
        first_url = first.json()["url"]
        assert first_url.startswith("/api/files/")
        served = client.get(first_url)
        assert served.status_code == 200
        assert served.content == b"one"
        assert served.headers["content-type"] == "image/png"

        second = client.put("/api/me/profile-picture", files={"picture": ("_test_two.png", b"two", "image/png")})
        assert client.get(first_url).status_code == 404  # the old upload is deleted
        assert test_db.users.find_one({"user_id": email})["picture"] == second.json()["url"]
