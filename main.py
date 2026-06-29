from a2wsgi import WSGIMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from flask_app import app as flask_app
from routers import auth

app = FastAPI(title="Quantaid API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_headers=["Content-Type", "X-Requested-With"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)

app.include_router(auth.router)

# fallback: unmigrated routes handled by Flask until migration is complete
app.mount("/", WSGIMiddleware(flask_app))  # ty: ignore[invalid-argument-type]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
