from fastapi import FastAPI, UploadFile, File
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.auth import router as auth_router
from backend.routes.process import router as process_router
from backend.services.upload_service import upload_to_cloudinary
from backend.db import collection
import backend.config  # initializes Cloudinary

app = FastAPI()
app.include_router(auth_router, prefix="/auth")
app.include_router(process_router)
# ── CORS ── allow frontend to call this API ──────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # replace * with your frontend URL before deploying
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────

# ── Health check ──────────────────────────────────────────────
@app.get("/")
def home():
    return {"message": "API is running 🚀"}

# ── Legacy upload (no OCR) ────────────────────────────────────
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    result = upload_to_cloudinary(file.file)
    data = {
        "filename":  file.filename,
        "url":       result["url"],
        "public_id": result["public_id"],
        "status":    "uploaded"
    }
    collection.insert_one(data)
    return {
        "message":        "✅ Uploaded successfully",
        "filename":       file.filename,
        "cloudinary_url": result["url"]
    }

# ── Custom OpenAPI (Bearer auth) ──────────────────────────────
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Receipt API",
        version="1.0.0",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer"}
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
