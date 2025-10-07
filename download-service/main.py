from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
import json
import requests
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: str

def generate_po_token():
    """Generate YouTube PoToken using youtube-po-token-generator"""
    try:
        result = subprocess.run(
            ["youtube-po-token-generator"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        token_data = json.loads(result.stdout)
        return token_data.get("visitorData"), token_data.get("poToken")
    except Exception as e:
        print(f"Warning: Failed to generate PoToken: {e}")
        return None, None

@app.post("/download")
async def download_video(request: DownloadRequest):
    """Download YouTube video using yt-dlp and send to Vercel for Blob upload"""
    
    try:
        temp_dir = Path("temp_downloads")
        temp_dir.mkdir(exist_ok=True)
        
        visitor_data, po_token = generate_po_token()
        
        extractor_args = "youtube:player_client=android,web"
        if visitor_data and po_token:
            extractor_args = f"youtube:player_client=android,web;po_token={po_token};visitor_data={visitor_data}"
        
        metadata_result = subprocess.run([
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--extractor-args", extractor_args,
            "--no-check-certificate",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            request.url
        ], capture_output=True, text=True, check=True)
        
        metadata = json.loads(metadata_result.stdout)
        title = metadata.get("title", "video")
        duration = metadata.get("duration", 0)
        thumbnail = metadata.get("thumbnail", "")
        video_id = metadata.get("id", "unknown")
        
        output_template = str(temp_dir / f"{video_id}.mp4")
        
        subprocess.run([
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--extractor-args", extractor_args,
            "--no-check-certificate",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "-o", output_template,
            request.url
        ], capture_output=True, text=True, check=True)
        
        vercel_upload_url = os.getenv("VERCEL_UPLOAD_URL", "https://your-app.vercel.app/api/upload-blob")
        
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
                detail=f"Vercel upload failed: {upload_response.text}"
            )
        
        os.remove(output_template)
        
        result = upload_response.json()
        
        return {
            "success": True,
            "video": result["video"]
        }
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"yt-dlp error: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
