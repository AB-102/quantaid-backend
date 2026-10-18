"""Profile form → stored profile."""

from datetime import UTC, datetime

from schemas.user import SaveProfileRequest

OTHER_SUBJECT_OPTION = "Other (please specify)"


def build_profile_update(data: SaveProfileRequest) -> dict:
    """Turn the onboarding/profile form into the `$set` update for the user's document."""
    if data.educationCategory == "HighSchool":
        education_level = f"High School - {data.educationLevel}"
    elif data.educationCategory == "College":
        education_level = f"College - {data.educationLevel}"
    elif data.educationCategory == "Other" and data.otherEducationLevel:
        education_level = data.otherEducationLevel
    else:
        education_level = ""

    # Replace the "Other (please specify)" checkbox with what the user typed
    subjects = list(data.subjects)
    if OTHER_SUBJECT_OPTION in subjects and data.otherSubject:
        subjects = [s for s in subjects if s != OTHER_SUBJECT_OPTION]
        subjects.append(data.otherSubject)

    # Custom hobbies arrive as one comma-separated string
    custom_hobbies = data.customHobbies.strip()
    hobbies = list(data.favoriteHobbies)
    if custom_hobbies:
        hobbies.extend(h.strip() for h in custom_hobbies.split(",") if h.strip())

    now = datetime.now(UTC)
    return {
        "profile": {
            "where_heard": data.whereHeard,
            "other_where_heard": data.otherWhereHeard,
            "education_category": data.educationCategory,
            "education_level": education_level,
            "subjects_studied": subjects,
            "other_subject": data.otherSubject,
            "coding_experience": data.codingExperience,
            "favorite_hobbies": hobbies,
            "custom_hobbies": custom_hobbies,
        },
        "profile_complete": True,
        "hobby_personalization": data.hobbyPersonalization,
        "profileLastUpdatedAt": now,
        # The form exactly as submitted
        "onboarding_responses": {
            "where_heard": data.whereHeard,
            "other_where_heard": data.otherWhereHeard,
            "education_category": data.educationCategory,
            "subjects": data.subjects,
            "other_subject": data.otherSubject,
            "favorite_hobbies": data.favoriteHobbies,
            "custom_hobbies": custom_hobbies,
            "coding_experience": data.codingExperience,
            "completed_at": now,
        },
    }
