"""Which uploads are accepted. Files are served from the API's own origin, so nothing a browser could run is stored."""

from fastapi import HTTPException, UploadFile, status

# No SVG: it can contain scripts
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def require_image(upload: UploadFile) -> None:
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Images must be PNG, JPEG, GIF or WebP"
        )
