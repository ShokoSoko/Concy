from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import subprocess
import os
import json
import requests
from pathlib import Path
import traceback

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Ensure all errors return JSON instead of HTML"""
    error_detail = str(exc)
    if hasattr(exc, 'detail'):
        error_detail = exc.detail
    
    print(f"[ERROR] {error_detail}")
    print(traceback.format_exc())
    
    return JSONResponse(
        status_code=500,
        content={"detail": error_detail}
    )

class DownloadRequest(BaseModel):
    url: str

def setup_cookies():
    """Setup cookies file from environment variable if provided"""
    cookies_data = os.getenv("YOUTUBE_COOKIES")
    if cookies_data:
        try:
            cookies_file = Path("cookies.txt")
            with open(cookies_file, 'w') as f:
                # If it already starts with the Netscape header, write as-is
                if cookies_data.strip().startswith("# Netscape HTTP Cookie File"):
                    f.write(cookies_data)
                else:
                    # Otherwise, add the header
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write(cookies_data)
            print(f"[INFO] Cookies file created successfully")
            return str(cookies_file)
        except Exception as e:
            print(f"[WARNING] Failed to setup cookies: {e}")
    else:
        print("[WARNING] No YOUTUBE_COOKIES environment variable found")
    return None

@app.post("/download")
async def download_video(request: DownloadRequest):
    """Download YouTube video using yt-dlp and send to Vercel for Blob upload"""
    
    try:
        print(f"[INFO] Starting download for: {request.url}")
        
        vercel_upload_url = os.getenv("VERCEL_UPLOAD_URL")
        if not vercel_upload_url:
            raise HTTPException(
                status_code=500,
                detail="VERCEL_UPLOAD_URL environment variable is not set in Railway. Please add it in the Variables tab."
            )
        
        print(f"[INFO] Upload URL: {vercel_upload_url}")
        
        temp_dir = Path("temp_downloads")
        temp_dir.mkdir(exist_ok=True)
        
        cookies_file = setup_cookies()
        
        base_cmd = [
            "yt-dlp",
            "--no-check-certificate",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        ]
        
        if cookies_file:
            base_cmd.extend(["--cookies", cookies_file])
            print("[INFO] Using cookies for authentication")
        
        print("[INFO] Fetching video metadata...")
        metadata_result = subprocess.run(
            base_cmd + [
                "--dump-json",
                "--no-download",
                request.url
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        metadata = json.loads(metadata_result.stdout)
        title = metadata.get("title", "video")
        duration = metadata.get("duration", 0)
        thumbnail = metadata.get("thumbnail", "")
        video_id = metadata.get("id", "unknown")
        
        print(f"[INFO] Video: {title} ({video_id})")
        
        output_template = str(temp_dir / f"{video_id}.mp4")
        
        print("[INFO] Downloading video...")
        subprocess.run(
            base_cmd + [
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", output_template,
                request.url
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("[INFO] Video downloaded, uploading to Vercel...")
        
        filename = f"youtube-{video_id}-{int(os.path.getmtime(output_template) * 1000)}.mp4"
        
        with open(output_template, 'rb') as f:
            files = {'file': (filename, f, 'video/mp4')}
            data = {
                'filename': filename,
                'title': title,
                'duration': str(duration),
                'thumbnail': thumbnail,
                'videoId': video_id
            }
            
            upload_response = requests.post(
                vercel_upload_url,
                files=files,
                data=data,
                timeout=300
            )
        
        if upload_response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Vercel upload failed ({upload_response.status_code}): {upload_response.text}"
            )
        
        os.remove(output_template)
        print("[INFO] Upload complete!")
        
        result = upload_response.json()
        
        return {
            "success": True,
            "video": result["video"]
        }
        
    except subprocess.CalledProcessError as e:
        error_msg = f"yt-dlp error: {e.stderr}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] {error_msg}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
