from urllib.parse import quote

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Response, status
from gridfs import AsyncGridOut, NoFile

from database.db import fs

router = APIRouter(prefix="/api", tags=["Files"])


async def gridfs_file_response(grid_out: AsyncGridOut) -> Response:
    """Send a GridFS file inline with its stored content type."""
    # filename* with percent-encoding allows any filename (e.g. macOS screenshot names contain non-Latin-1 spaces)
    filename = quote(grid_out.filename or "file")
    return Response(
        content=await grid_out.read(),
        media_type=grid_out.content_type or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename*=utf-8''{filename}"},
    )


@router.get("/files/{file_id}")
async def get_file(file_id: str):
    """Serve a public GridFS file (lesson images, profile pictures). Admin-only files are reported as not found."""
    if not ObjectId.is_valid(file_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    try:
        grid_out = await fs.get(ObjectId(file_id))
    except NoFile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found") from None
    # Files uploaded before visibility tags existed are public
    if getattr(grid_out, "visibility", "public") == "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return await gridfs_file_response(grid_out)
