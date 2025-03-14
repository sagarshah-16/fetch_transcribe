from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import yt_dlp
import whisper
import os
import uuid

app = FastAPI()

# Initialize Whisper model
model = whisper.load_model("base")  # Change to "small", "medium" or "large" for better accuracy

class VideoURL(BaseModel):
    url: HttpUrl

# Function to download video and extract audio
def download_audio(url: str) -> str:
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
        raise HTTPException(status_code=400, detail=f"Download error: {str(e)}")

# Function to transcribe audio and clean up files
def transcribe_audio(audio_path: str) -> str:
    try:
        result = model.transcribe(audio_path)
        return result['text']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")
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

@app.post("/transcribe")
def transcribe_video(video_url: VideoURL):
    audio_file = download_audio(str(video_url.url))
    transcription = transcribe_audio(audio_file)
    return {"transcription": transcription}
