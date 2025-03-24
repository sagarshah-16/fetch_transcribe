from fastapi import FastAPI, HTTPException, Body
from typing import Dict, Any
import yt_dlp
import whisper
import os
import uuid
import re
import sentry_sdk

app = FastAPI()

# Initialize Whisper model
model = whisper.load_model("base")  # Change to "small", "medium" or "large" for better accuracy

# Function to download video and extract audio
def download_audio(url: str) -> str:
    print(f"Downloading audio from URL: {url}")
    filename = f"video_{uuid.uuid4()}"
    output_audio = f"{filename}.mp3"

    # Record this operation in Sentry
    sentry_sdk.add_breadcrumb(
        category="transcription",
        message=f"Starting audio download from {url}",
        level="info",
        data={"filename": output_audio}
    )

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

        # Record successful download
        sentry_sdk.add_breadcrumb(
            category="transcription",
            message=f"Successfully downloaded audio to {output_audio}",
            level="info"
        )
        return output_audio
    except Exception as e:
        error_msg = str(e)
        print(f"Download error: {error_msg}")

        # Record the error with Sentry
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("operation", "download_audio")
            scope.set_context("download_options", ydl_opts)
            sentry_sdk.capture_exception(e)

        raise HTTPException(status_code=400, detail=f"Download error: {error_msg}")

# Function to transcribe audio and clean up files
def transcribe_audio(audio_path: str) -> str:
    print(f"Transcribing audio file: {audio_path}")

    # Record this operation in Sentry
    sentry_sdk.add_breadcrumb(
        category="transcription",
        message=f"Starting transcription of {audio_path}",
        level="info"
    )

    try:
        # Start a transaction for performance monitoring
        with sentry_sdk.start_transaction(op="transcribe", name=f"Transcribe {audio_path}"):
            result = model.transcribe(audio_path)

            # Record successful transcription
            sentry_sdk.add_breadcrumb(
                category="transcription",
                message=f"Successfully transcribed {audio_path}",
                level="info",
                data={"text_length": len(result['text'])}
            )

            return result['text']
    except Exception as e:
        error_msg = str(e)
        print(f"Transcription error: {error_msg}")

        # Record the error with Sentry
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("operation", "transcribe_audio")
            scope.set_context("audio_file", {"path": audio_path})
            sentry_sdk.capture_exception(e)

        raise HTTPException(status_code=500, detail=f"Transcription error: {error_msg}")
    finally:
        # Remove audio file after transcription
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                sentry_sdk.add_breadcrumb(
                    category="cleanup",
                    message=f"Removed audio file: {audio_path}",
                    level="info"
                )

            # Remove original video files if still present
            video_extensions = ['webm', 'mp4', 'mkv', 'mov', 'avi', 'm4a']
            base_filename = os.path.splitext(audio_path)[0]
            for ext in video_extensions:
                video_file = f"{base_filename}.{ext}"
                if os.path.exists(video_file):
                    os.remove(video_file)
                    sentry_sdk.add_breadcrumb(
                        category="cleanup",
                        message=f"Removed video file: {video_file}",
                        level="info"
                    )
        except Exception as cleanup_error:
            # Record but don't raise cleanup errors
            sentry_sdk.capture_message(f"Error during file cleanup: {str(cleanup_error)}", level="warning")

def transcribe_video(url: str):
    # Start a transaction for the whole operation
    with sentry_sdk.start_transaction(op="transcribe", name="Transcribe Video"):
        # Validate and normalize URL
        if not url:
            sentry_sdk.capture_message("Empty URL provided to transcribe_video", level="error")
            raise HTTPException(status_code=400, detail="URL is required")

        # Ensure URL has proper scheme
        if not re.match(r'^https?://', url):
            original_url = url
            url = 'https://' + url
            sentry_sdk.add_breadcrumb(
                category="transcription",
                message=f"Added https:// scheme to URL: {original_url} → {url}",
                level="info"
            )

        print(f"Processing transcription request for URL: {url}")

        try:
            audio_file = download_audio(url)
            transcription = transcribe_audio(audio_file)

            # Record successful operation
            sentry_sdk.add_breadcrumb(
                category="transcription",
                message=f"Successfully transcribed video from {url}",
                level="info",
                data={"text_length": len(transcription)}
            )

            return {"transcription": transcription}
        except Exception as e:
            # This exception should be already captured by the individual functions
            # Just re-raise it
            raise

@app.post("/transcribe")
async def transcribe_route(body: Dict[str, Any] = Body(...)):
    try:
        print(f"Received transcription request: {body}")

        # Extract URL from nested structure
        query = body.get("query")
        if not query or not isinstance(query, dict):
            error_msg = "Request must include a 'query' object"
            sentry_sdk.capture_message(error_msg, level="error")
            raise HTTPException(status_code=400, detail=error_msg)

        url = query.get("url")
        if not url:
            error_msg = "URL is required in query object"
            sentry_sdk.capture_message(error_msg, level="error")
            raise HTTPException(status_code=400, detail=error_msg)

        return transcribe_video(url)
    except HTTPException as he:
        # Record HTTP exceptions with Sentry
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_type", "http_exception")
            scope.set_context("request_body", body)
            sentry_sdk.capture_exception(he)
        # Re-raise HTTP exceptions
        print(f"HTTP Exception: {he.detail}")
        raise
    except Exception as e:
        # Catch all other exceptions
        error_msg = str(e)
        print(f"Error in transcribe_route: {error_msg}")

        # Record with Sentry
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_type", "unexpected_error")
            scope.set_context("request_body", body)
            sentry_sdk.capture_exception(e)

        raise HTTPException(status_code=500, detail=f"Error processing request: {error_msg}")
