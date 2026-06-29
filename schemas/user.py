from pydantic import BaseModel


class UserOut(BaseModel):
    email: str
    is_admin: bool


class GoogleSSORequest(BaseModel):
    access_token: str
