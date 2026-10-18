from pydantic import BaseModel


class UserUpdate(BaseModel):
    disabled: bool
