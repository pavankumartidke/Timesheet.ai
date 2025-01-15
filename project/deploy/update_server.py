# update_server.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import os
import json
import hashlib
from datetime import datetime

app = FastAPI()

UPDATES_DIR = "updates"
VERSION_FILE = os.path.join(UPDATES_DIR, "version.json")

def get_file_hash(file_path):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

@app.get("/updates/version.json")
async def get_version_info():
    """Return the latest version information"""
    if not os.path.exists(VERSION_FILE):
        raise HTTPException(status_code=404, detail="Version info not found")
    
    with open(VERSION_FILE) as f:
        return json.load(f)

@app.get("/updates/download/{version}")
async def download_update(version: str):
    """Download specific version of the update"""
    update_file = os.path.join(UPDATES_DIR, f"tracker_{version}.exe")
    
    if not os.path.exists(update_file):
        raise HTTPException(status_code=404, detail="Update file not found")
    
    return FileResponse(
        update_file,
        media_type="application/octet-stream",
        filename=f"tracker_{version}.exe"
    )

@app.post("/admin/publish_update")
async def publish_update(version: str, file_path: str):
    """Publish a new update (admin only)"""
    update_info = {
        "version": version,
        "release_date": datetime.now().isoformat(),
        "download_url": f"https://your-update-server.com/updates/download/{version}",
        "file_hash": get_file_hash(file_path),
        "changelog": "Update description goes here"
    }
    
    # Save version info
    with open(VERSION_FILE, "w") as f:
        json.dump(update_info, f, indent=4)
    
    return {"status": "success", "message": f"Version {version} published"}