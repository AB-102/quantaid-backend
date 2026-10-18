import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from database.db import db
from dependencies.auth import require_admin
from schemas.admin_users import UserUpdate

router = APIRouter(prefix="/api/admin", tags=["Admin users"], dependencies=[Depends(require_admin)])


@router.get("/users")
async def list_users(
    search: str = "",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    skip: Annotated[int, Query(ge=0)] = 0,
):
    """Users with metadata for admin review. `search` matches email or name, case-insensitively."""
    query: dict = {}
    search = search.strip()
    if search:
        # Escaped: the search box is plain text, not a regex
        pattern = {"$regex": re.escape(search), "$options": "i"}
        query["$or"] = [{"user_id": pattern}, {"name": pattern}]
    users = (
        await db.users.find(
            query,
            {
                "_id": 0,
                "user_id": 1,
                "name": 1,
                "google_sub": 1,
                "is_admin": 1,
                "profile_complete": 1,
                "disabled": 1,
                "createdAt": 1,
                "lastLoginAt": 1,
            },
        )
        .sort("createdAt", -1)
        .skip(skip)
        .limit(limit)
        .to_list()
    )
    total_count = await db.users.count_documents(query)
    total_users = await db.users.count_documents({})
    return {
        "users": [
            {
                "userId": user["user_id"],
                "name": user.get("name"),
                "isAdmin": user.get("is_admin", False),
                "profileComplete": user.get("profile_complete", False),
                "disabled": user.get("disabled", False),
                # Derived sign-in methods; google_sub itself stays private
                "authMethods": ["google"] if user.get("google_sub") else [],
                "createdAt": user.get("createdAt"),
                "lastLoginAt": user.get("lastLoginAt"),
            }
            for user in users
        ],
        "totalCount": total_count,
        "totalUsers": total_users,
        "hasMore": skip + len(users) < total_count,
    }


@router.patch("/users/{email:path}")
async def update_user(email: str, body: UserUpdate):
    """Disable or re-enable an account. A disabled user's existing sessions stop working immediately."""
    result = await db.users.update_one(
        {"user_id": email.strip().lower()},
        {"$set": {"disabled": body.disabled, "disabledAt": datetime.now(UTC) if body.disabled else None}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"message": f"User {'disabled' if body.disabled else 'enabled'}", "disabled": body.disabled}
