from fastapi import FastAPI, HTTPException, Body
from typing import Dict, Any
import yt_dlp
import whisper
import os
import uuid
import re

app = FastAPI()

# Initialize Whisper model
model = whisper.load_model("base")  # Change to "small", "medium" or "large" for better accuracy

# Function to download video and extract audio
def download_audio(url: str) -> str:
    print(f"Downloading audio from URL: {url}")
    filename = f"video_{uuid.uuid4()}"
    output_audio = f"{filename}.mp3"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{filename}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return output_audio
    except Exception as e:
        error_msg = str(e)
        print(f"Download error: {error_msg}")
        raise HTTPException(status_code=400, detail=f"Download error: {error_msg}")

# Function to transcribe audio and clean up files
def transcribe_audio(audio_path: str) -> str:
    print(f"Transcribing audio file: {audio_path}")
    try:
        result = model.transcribe(audio_path)
        return result['text']
    except Exception as e:
        error_msg = str(e)
        print(f"Transcription error: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Transcription error: {error_msg}")
    finally:
        # Remove audio file after transcription
        if os.path.exists(audio_path):
            os.remove(audio_path)

        # Remove original video files if still present
        video_extensions = ['webm', 'mp4', 'mkv', 'mov', 'avi', 'm4a']
        base_filename = os.path.splitext(audio_path)[0]
        for ext in video_extensions:
            video_file = f"{base_filename}.{ext}"
            if os.path.exists(video_file):
                os.remove(video_file)

def transcribe_video(url: str):
    # Validate and normalize URL
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Ensure URL has proper scheme
    if not re.match(r'^https?://', url):
        url = 'https://' + url

    print(f"Processing transcription request for URL: {url}")
    audio_file = download_audio(url)
    transcription = transcribe_audio(audio_file)
    return {"transcription": transcription}

@app.post("/transcribe")
async def transcribe_route(body: Dict[str, Any] = Body(...)):
    try:
        print(f"Received transcription request: {body}")

        # Extract URL from nested structure
        query = body.get("query")
        if not query or not isinstance(query, dict):
            raise HTTPException(status_code=400, detail="Request must include a 'query' object")

        url = query.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL is required in query object")

        return transcribe_video(url)
    except HTTPException as he:
        # Re-raise HTTP exceptions
        print(f"HTTP Exception: {he.detail}")
        raise
    except Exception as e:
        # Catch all other exceptions
        error_msg = str(e)
        print(f"Error in transcribe_route: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {error_msg}")
