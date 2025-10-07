from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import subprocess
import os
import json
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

@app.post("/download")
async def download_video(request: DownloadRequest):
    """Download YouTube video using yt-dlp and return metadata + video file"""
    
    try:
        temp_dir = Path("temp_downloads")
        temp_dir.mkdir(exist_ok=True)
        
        metadata_result = subprocess.run([
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--extractor-args", "youtube:player_client=android,web",
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
            "--extractor-args", "youtube:player_client=android,web",
            "--no-check-certificate",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "-o", output_template,
            request.url
        ], capture_output=True, text=True, check=True)
        
        def iterfile():
            with open(output_template, 'rb') as f:
                yield from f
            os.remove(output_template)
        
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        
        return StreamingResponse(
            iterfile(),
            media_type="video/mp4",
            headers={
                "X-Video-Title": title,
                "X-Video-Duration": str(duration),
                "X-Video-Duration-Formatted": f"{minutes}m {seconds}s",
                "X-Video-Thumbnail": thumbnail,
                "X-Video-ID": video_id,
                "Content-Disposition": f'attachment; filename="{video_id}.mp4"'
            }
        )
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"yt-dlp error: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
