import os
import random
import base64
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    Request,
    Response,
    Depends,
    HTTPException,
    status,
    Form,
    UploadFile,
    File
)
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import (
    BASE_DIR,
    UPLOADS_DIR,
    get_admin_password,
    get_api_key,
    SESSION_SECRET_KEY
)
from app.database import engine, Base, get_db
from app.models import Photo, BlockedIP, SecurityLog
from app.security import (
    HighSecurityMiddleware,
    get_client_ip,
    record_failed_api_attempt,
    unblock_ip
)
from app.image_utils import compress_and_save_image, DEFAULT_TARGET_KB

# 1. Create DB tables
Base.metadata.create_all(bind=engine)

# 2. Initialize FastAPI
app = FastAPI(
    title="High-Security Photo Compression & Random API Engine",
    description="FastAPI service with smart 1KB-100KB compression, anti-DDoS, SQLi firewall, and API key protection.",
    version="1.1.0"
)

# 3. Attach High-Security Middleware
app.add_middleware(HighSecurityMiddleware)

# 4. Mount Static and Templates
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ==========================================
# Helpers & Auth Dependencies
# ==========================================

def is_admin_authenticated(request: Request) -> bool:
    """Verify session cookie against expected session token"""
    cookie_token = request.cookies.get("admin_session")
    if not cookie_token:
        return False
    # Expected signature based on current admin key and secret
    expected_token = f"auth_{hash(get_admin_password() + SESSION_SECRET_KEY)}"
    return cookie_token == expected_token

def resolve_photo_path(photo: Photo) -> Optional[str]:
    """
    Resolve the on-disk JPG for a stored photo row.

    The absolute path saved in the database is environment specific (local dev
    vs Docker container, or a database backup restored on a VPS). If that path
    no longer exists, fall back to <UPLOADS_DIR>/<filename> so deployments keep
    serving the photos that live in the mounted uploads folder.
    """
    if photo.file_path and os.path.exists(photo.file_path):
        return photo.file_path

    if photo.filename:
        fallback_path = UPLOADS_DIR / photo.filename
        if fallback_path.exists():
            return str(fallback_path)

    return None


def verify_api_key_dep(request: Request):
    """
    Validates api_key from query parameter or header against apikey.txt.
    Tracks failures and triggers IP blocking if abuse is detected.
    """
    client_ip = get_client_ip(request)
    configured_key = get_api_key()

    # Query param: ?api_key=... or Header: X-API-Key: ...
    provided_key = request.query_params.get("api_key") or request.headers.get("x-api-key")

    if not provided_key or provided_key.strip() != configured_key:
        record_failed_api_attempt(client_ip, request.url.path)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": False,
                "error": "Forbidden: Invalid or missing API key."
            }
        )
    return provided_key


# ==========================================
# Admin Web Portal Routes
# ==========================================

@app.get("/", response_class=HTMLResponse)
def root_index(request: Request):
    """Homepage: redirect to dashboard if authenticated, else show login page"""
    if is_admin_authenticated(request):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None}
    )

@app.post("/login")
def process_login(request: Request, password: str = Form(...)):
    """Authenticate admin using adminkey.txt"""
    correct_password = get_admin_password()

    if password.strip() == correct_password:
        expected_token = f"auth_{hash(correct_password + SESSION_SECRET_KEY)}"
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="admin_session",
            value=expected_token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7  # 7 days
        )
        return response

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid administrator password. Access denied."},
        status_code=status.HTTP_401_UNAUTHORIZED
    )

@app.get("/logout")
def process_logout():
    """Clear admin session"""
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("admin_session")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def view_dashboard(request: Request, db: Session = Depends(get_db)):
    """Admin Dashboard with upload form, copy buttons, and photo gallery"""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    photos = db.query(Photo).order_by(Photo.created_at.desc()).all()
    blocked_ips = db.query(BlockedIP).order_by(BlockedIP.blocked_at.desc()).all()
    api_key = get_api_key()

    base_url = str(request.base_url).rstrip("/")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "photos": photos,
            "blocked_ips": blocked_ips,
            "api_key": api_key,
            "base_url": base_url
        }
    )


# ==========================================
# Admin Actions (Upload & Delete)
# ==========================================

@app.post("/api/admin/upload")
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    target_size_kb: int = Form(DEFAULT_TARGET_KB),
    db: Session = Depends(get_db)
):
    """Compress and upload a photo (Requires Admin Session)"""
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be an image")

    # Read uploaded file bytes
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    try:
        # Compress to 1KB - 100KB and save as JPG with unique ID
        metadata = compress_and_save_image(
            file_bytes=file_bytes,
            original_filename=file.filename or "uploaded.jpg",
            target_size_kb=target_size_kb,
            uploads_dir=UPLOADS_DIR
        )

        # Store in database
        photo = Photo(
            id=metadata["id"],
            original_name=metadata["original_name"],
            filename=metadata["filename"],
            file_path=metadata["file_path"],
            file_size_kb=metadata["file_size_kb"],
            target_size_kb=metadata["target_size_kb"],
            width=metadata["width"],
            height=metadata["height"]
        )
        db.add(photo)
        db.commit()
        db.refresh(photo)

        return {
            "status": True,
            "message": "Photo uploaded and compressed successfully",
            "photo": photo.to_dict()
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Image processing failed: {str(e)}")

@app.delete("/api/admin/photo/{photo_id}")
def delete_photo(photo_id: str, request: Request, db: Session = Depends(get_db)):
    """Delete a photo from disk and database (Requires Admin Session)"""
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required")

    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    # Delete physical file
    try:
        if os.path.exists(photo.file_path):
            os.remove(photo.file_path)
    except Exception:
        pass

    db.delete(photo)
    db.commit()

    return {"status": True, "message": "Photo deleted successfully", "id": photo_id}

@app.post("/api/admin/unblock-ip/{ip_address}")
def admin_unblock_ip(ip_address: str, request: Request):
    """Unblock an IP address (Requires Admin Session)"""
    if not is_admin_authenticated(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required")

    success = unblock_ip(ip_address)
    if success:
        return {"status": True, "message": f"IP {ip_address} has been unblocked"}
    return {"status": False, "message": f"IP {ip_address} not found in blocked list"}


# ==========================================
# Public APIs (Protected by apikey.txt)
# ==========================================

@app.get("/api/v1/photo/random")
def get_random_photo_file(
    api_key: str = Depends(verify_api_key_dep),
    db: Session = Depends(get_db)
):
    """
    Download Photo API:
    Returns a direct stream of a random JPG file.
    Requires ?api_key=... parameter matching apikey.txt.
    """
    photos = db.query(Photo).all()
    if not photos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": False, "error": "No photos available in library. Please upload photos from admin dashboard first."}
        )

    random_photo = random.choice(photos)

    photo_path = resolve_photo_path(random_photo)
    if photo_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": False, "error": "Photo file missing on server."}
        )

    return FileResponse(
        path=photo_path,
        media_type="image/jpeg",
        filename=f"{random_photo.id}.jpg"
    )

@app.get("/api/v1/photo/random/json")
def get_random_photo_json(
    api_key: str = Depends(verify_api_key_dep),
    db: Session = Depends(get_db)
):
    """
    JSON API:
    Returns random picture encoded in Base64 according to the requested schema:
    {
      "status": true,
      "fileFormat": "jpg",
      "encode": "base64",
      "size": <length of base64 data string>,
      "data": "<base64 encoded string>"
    }
    """
    photos = db.query(Photo).all()
    if not photos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": False, "error": "No photos available. Please upload photos first."}
        )

    random_photo = random.choice(photos)

    photo_path = resolve_photo_path(random_photo)
    if photo_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": False, "error": "Photo file missing on server."}
        )

    with open(photo_path, "rb") as f:
        raw_bytes = f.read()

    b64_data = base64.b64encode(raw_bytes).decode("utf-8")

    return {
        "status": True,
        "fileFormat": "jpg",
        "encode": "base64",
        "size": len(b64_data),
        "data": b64_data
    }

@app.get("/api/v1/photo/{photo_id}")
def get_photo_by_id(
    photo_id: str,
    api_key: str = Depends(verify_api_key_dep),
    db: Session = Depends(get_db)
):
    """Direct download for a specific photo by its unique ID"""
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    photo_path = resolve_photo_path(photo) if photo else None
    if photo_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    return FileResponse(
        path=photo_path,
        media_type="image/jpeg",
        filename=f"{photo.id}.jpg"
    )

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Server starting on http://127.0.0.1:8000")
    print("📖 Swagger Docs: http://127.0.0.1:8000/docs\n")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)