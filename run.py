from fastapi import FastAPI, HTTPException, Body
from typing import Dict, Any
import yt_dlp
import whisper
import os
import uuid
import re
import sentry_sdk
import traceback
import sys

# Ensure Sentry is initialized early
if not sentry_sdk.Hub.current.client:
    print("Initializing Sentry SDK in run.py...")
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN", ""),
        traces_sample_rate=1.0,
        enable_tracing=True,
        environment=os.getenv("ENVIRONMENT", "development"),
        debug=True,
    )
    # Set common attributes
    sentry_sdk.set_tag("service", "transcription")

app = FastAPI()

# Initialize Whisper model
model = whisper.load_model("base")  # Change to "small", "medium" or "large" for better accuracy

# Function to download video and extract audio
def download_audio(url: str) -> str:
    """
    Download audio from a video URL using yt-dlp

    Args:
        url: The URL of the video

    Returns:
        The path to the downloaded audio file
    """
    with sentry_sdk.start_span(op="download_audio", description=f"Download audio from {url}"):
        try:
            # Create a unique ID for the file
            file_id = str(uuid.uuid4())

            # Create output directory if it doesn't exist
            output_dir = os.path.join(os.getcwd(), "downloads")
            os.makedirs(output_dir, exist_ok=True)

            # Set output filename
            output_path = os.path.join(output_dir, f"{file_id}.mp3")

            # Configure yt-dlp options
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': output_path,
                'quiet': False,
                'no_warnings': False,
            }

            # Check if a cookies file exists in the current directory or a few common locations
            cookies_file_paths = [
                os.path.join(os.getcwd(), "youtube_cookies.txt"),
                os.path.join(os.getcwd(), "cookies.txt"),
                "/var/www/fetch_transcribe/youtube_cookies.txt",
                "/var/www/fetch_transcribe/cookies.txt"
            ]

            cookies_file = None
            for path in cookies_file_paths:
                if os.path.exists(path):
                    cookies_file = path
                    break

            # Add cookies configuration if available
            if cookies_file:
                ydl_opts['cookiefile'] = cookies_file
                sentry_sdk.add_breadcrumb(
                    category="download",
                    message=f"Using cookies file: {cookies_file}",
                    level="info"
                )
            elif os.path.exists(os.path.expanduser("~/.config/google-chrome")):
                # Only use Chrome cookies if the Chrome directory exists
                ydl_opts['cookiesfrombrowser'] = ('chrome',)
                sentry_sdk.add_breadcrumb(
                    category="download",
                    message="Using Chrome browser cookies",
                    level="info"
                )
            elif os.path.exists(os.path.expanduser("~/.mozilla/firefox")):
                # Try Firefox as fallback
                ydl_opts['cookiesfrombrowser'] = ('firefox',)
                sentry_sdk.add_breadcrumb(
                    category="download",
                    message="Using Firefox browser cookies",
                    level="info"
                )
            else:
                sentry_sdk.add_breadcrumb(
                    category="download",
                    message="No cookies configuration found, attempting download without authentication",
                    level="warning"
                )

            # Log detailed YouTube download attempt
            sentry_sdk.add_breadcrumb(
                category="download",
                message=f"Attempting to download audio from {url}",
                level="info",
                data={"url": url, "options": str(ydl_opts)}
            )

            # Try to download the video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Log successful download
            sentry_sdk.add_breadcrumb(
                category="download",
                message=f"Successfully downloaded audio from {url}",
                level="info",
                data={"output_path": output_path}
            )

            # Return the path to the audio file
            return output_path

        except Exception as e:
            error_message = str(e)
            error_trace = traceback.format_exc()

            # Print detailed error for debugging
            print(f"ERROR in download_audio: {error_message}")
            print(f"Traceback: {error_trace}")

            # Capture to Sentry directly first
            sentry_sdk.capture_exception(e)
            sentry_sdk.capture_message(f"YouTube download error: {error_message}", level="error")

            # Then add more context
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("operation", "download_audio")
                scope.set_tag("error_source", "youtube_download")
                scope.set_context("error_details", {
                    "message": error_message,
                    "traceback": error_trace,
                    "url": url
                })

                # Log detailed diagnostics
                if "chrome cookies" in error_message.lower():
                    chrome_path = os.path.expanduser("~/.config/google-chrome")
                    chrome_exists = os.path.exists(chrome_path)
                    scope.set_context("chrome_diagnostics", {
                        "chrome_path_exists": chrome_exists,
                        "home_directory": os.path.expanduser("~"),
                        "current_user": os.getenv("USER", "unknown"),
                    })

                # Capture exception again with enhanced context
                event_id = sentry_sdk.capture_exception(e)
                print(f"Sent to Sentry with ID: {event_id}")

            # Provide more detailed error message for YouTube authentication errors
            if "Sign in to confirm you're not a bot" in error_message:
                raise Exception(
                    "YouTube requires authentication. Please upload a cookies.txt file to the application directory."
                )
            elif "could not find chrome cookies" in error_message.lower():
                raise Exception(
                    "Chrome cookies not found. Please upload a cookies.txt file to the application directory."
                )
            else:
                raise Exception(f"Failed to download audio: {error_message}")

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
