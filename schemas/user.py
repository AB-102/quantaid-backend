from pydantic import BaseModel


class UserOut(BaseModel):
    email: str
    is_admin: bool


class GoogleSSORequest(BaseModel):
    accessToken: str


class SaveProfileRequest(BaseModel):
    """Onboarding / profile form. Field names match the frontend's JSON keys."""

    whereHeard: list[str] = []
    otherWhereHeard: str = ""
    educationCategory: str = ""
    educationLevel: str = ""
    otherEducationLevel: str = ""
    subjects: list[str] = []
    otherSubject: str = ""
    favoriteHobbies: list[str] = []
    customHobbies: str = ""
    codingExperience: str = ""
    hobbyPersonalization: bool = True
