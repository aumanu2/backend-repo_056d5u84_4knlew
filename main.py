import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# -------- File Upload Endpoints --------
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    safe_name = os.path.basename(file.filename)
    if safe_name == "":
        raise HTTPException(status_code=400, detail="Invalid filename")

    dest_path = os.path.join(UPLOAD_DIR, safe_name)

    size = 0
    with open(dest_path, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            out.write(chunk)

    # Save metadata to DB if available
    meta = {
        "filename": safe_name,
        "content_type": file.content_type,
        "size": size,
        "path": f"uploads/{safe_name}",
    }

    try:
        from database import create_document
        create_document("upload", meta)
    except Exception:
        # Database optional; continue without failing
        pass

    return {"status": "ok", "filename": safe_name, "size": size, "content_type": file.content_type}

@app.get("/api/uploads")
async def list_uploads():
    # Prefer DB list when available, otherwise list filesystem
    try:
        from database import db
        if db is not None:
            docs = list(db["upload"].find({}, {"_id": 0}).sort("created_at", -1).limit(50))
            return {"items": docs}
    except Exception:
        pass

    # Fallback to filesystem
    items: List[dict] = []
    try:
        for name in sorted(os.listdir(UPLOAD_DIR)):
            p = os.path.join(UPLOAD_DIR, name)
            if os.path.isfile(p):
                items.append({
                    "filename": name,
                    "size": os.path.getsize(p),
                    "path": f"uploads/{name}"
                })
    except FileNotFoundError:
        pass

    return {"items": list(reversed(items))[:50]}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
