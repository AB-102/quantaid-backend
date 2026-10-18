from bson import ObjectId
from fastapi import APIRouter, HTTPException, UploadFile, status

from core.file_urls import file_url, uploaded_file_id
from database.db import db, fs
from dependencies.auth import CurrentUser
from schemas.user import SaveProfileRequest
from services.profile_service import build_profile_update

router = APIRouter(prefix="/api/me", tags=["Me"])


@router.get("/profile")
async def get_profile(user: CurrentUser):
    user_doc = await db.users.find_one(
        {"user_id": user.email},
        {"_id": 0, "profile": 1, "name": 1, "picture": 1, "hobby_personalization": 1, "google_sub": 1},
    )
    if user_doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    profile = user_doc.get("profile") or {}
    return {
        "name": user_doc.get("name", "User"),
        "profilePicture": user_doc.get("picture", ""),
        "educationCategory": profile.get("education_category", ""),
        "educationLevel": profile.get("education_level", ""),
        "subjectsStudied": profile.get("subjects_studied", []),
        "codingExperience": profile.get("coding_experience", ""),
        "favoriteHobbies": profile.get("favorite_hobbies", []),
        "customHobbies": profile.get("custom_hobbies", ""),
        "hobbyPersonalization": user_doc.get("hobby_personalization", True),
        "hasGoogle": bool(user_doc.get("google_sub")),
    }


@router.put("/profile")
async def replace_profile(body: SaveProfileRequest, user: CurrentUser):
    """Replace the profile with the submitted form."""
    await db.users.update_one({"user_id": user.email}, {"$set": build_profile_update(body)})
    return {"message": "Profile data saved successfully"}


@router.put("/profile-picture")
async def replace_profile_picture(picture: UploadFile, user: CurrentUser):
    """Replace the profile picture with an uploaded image."""
    if not picture.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty filename")
    # Delete the previous upload. Google picture URLs aren't ours to delete.
    user_doc = await db.users.find_one({"user_id": user.email}, {"picture": 1})
    old_file_id = uploaded_file_id((user_doc or {}).get("picture"))
    if old_file_id:
        await fs.delete(ObjectId(old_file_id))
    picture_id = await fs.put(
        await picture.read(),
        filename=picture.filename,
        content_type=picture.content_type or "image/png",
        user_id=user.email,
        visibility="public",
    )
    picture_url = file_url(picture_id)
    await db.users.update_one({"user_id": user.email}, {"$set": {"picture": picture_url}})
    return {"url": picture_url}
