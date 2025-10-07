from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
import json
import requests
from pathlib import Path

app = FastAPI()

# Allow CORS from your Vercel domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: str

@app.post("/download")
async def download_video(request: DownloadRequest):
    """Download YouTube video using yt-dlp and upload to Vercel Blob"""
    
    try:
        # Create temp directory for downloads
        temp_dir = Path("temp_downloads")
        temp_dir.mkdir(exist_ok=True)
        
        metadata_result = subprocess.run([
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--extractor-args", "youtube:player_client=android,web",
            "--no-check-certificate",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            request.url
        ], capture_output=True, text=True, check=True)
        
        # Parse metadata JSON
        metadata = json.loads(metadata_result.stdout)
        title = metadata.get("title", "video")
        duration = metadata.get("duration", 0)
        thumbnail = metadata.get("thumbnail", "")
        
        # Download video using yt-dlp
        output_template = str(temp_dir / "%(id)s.%(ext)s")
        
        # Run yt-dlp command with bot bypass options
        download_result = subprocess.run([
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--extractor-args", "youtube:player_client=android,web",
            "--no-check-certificate",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "-o", output_template,
            "--print", "after_move:filepath",
            request.url
        ], capture_output=True, text=True, check=True)
        
        # Get filepath from output
        filepath = download_result.stdout.strip().split('\n')[-1]
        
        # Upload to Vercel Blob
        blob_token = os.getenv("BLOB_READ_WRITE_TOKEN")
        if not blob_token:
            raise HTTPException(status_code=500, detail="BLOB_READ_WRITE_TOKEN not configured")
        
        filename = f"{Path(filepath).stem}.mp4"
        
        with open(filepath, 'rb') as f:
            blob_response = requests.post(
                f"https://blob.vercel-storage.com/{filename}",
                headers={
                    "Authorization": f"Bearer {blob_token}",
                    "x-content-type": "video/mp4",
                },
                data=f
            )
        
        if blob_response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Blob upload failed: {blob_response.text}")
        
        blob_data = blob_response.json()
        
        # Clean up downloaded file
        os.remove(filepath)
        
        # Format duration
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_formatted = f"{minutes}m {seconds}s"
        
        return {
            "success": True,
            "video": {
                "url": blob_data["url"],
                "title": title,
                "duration": duration,
                "durationFormatted": duration_formatted,
                "thumbnail": thumbnail,
                "size": blob_data.get("size", 0)
            }
        }
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"yt-dlp error: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
