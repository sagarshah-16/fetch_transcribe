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

            # Create output directory with proper permissions
            output_dir = os.path.join(os.getcwd(), "downloads")

            # Print diagnostic info about directories
            print(f"Current working directory: {os.getcwd()}")
            print(f"Output directory path: {output_dir}")

            # Create directory with proper permissions if it doesn't exist
            if not os.path.exists(output_dir):
                print(f"Creating downloads directory: {output_dir}")
                os.makedirs(output_dir, exist_ok=True)
                # Try to set directory permissions if running as root/sudo
                try:
                    os.chmod(output_dir, 0o777)  # Full permissions for troubleshooting
                    print(f"Set permissions on {output_dir}")
                except Exception as perm_error:
                    print(f"Warning: Could not set permissions on directory: {perm_error}")

            # Check if directory exists and is writable
            if not os.path.exists(output_dir):
                raise Exception(f"Failed to create downloads directory: {output_dir}")
            if not os.access(output_dir, os.W_OK):
                raise Exception(f"Downloads directory is not writable: {output_dir}")

            # Set output filename (use a temp filename without extension)
            temp_filename = f"{file_id}"
            output_path = os.path.join(output_dir, f"{file_id}.mp3")

            print(f"Will download to: {output_path}")

            # Configure yt-dlp options
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(output_dir, temp_filename),  # Download without extension
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

# Function to transcribe audio using Whisper
def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe an audio file using Whisper

    This function has been replaced by direct transcription in the transcribe_video function
    and will be removed in a future version.
    """
    # Record this operation in Sentry
    with sentry_sdk.start_span(op="transcribe_audio", description=f"Transcribe {audio_path}"):
        try:
            # Check if file exists before transcribing
            if not os.path.exists(audio_path):
                error_msg = f"Audio file not found: {audio_path}"
                print(error_msg)
                sentry_sdk.capture_message(error_msg, level="error")
                raise Exception(error_msg)

            print(f"Transcribing audio: {audio_path}")
            result = model.transcribe(audio_path)

            # Log successful transcription
            sentry_sdk.add_breadcrumb(
                category="transcription",
                message=f"Successfully transcribed audio at {audio_path}",
                level="info",
                data={"text_length": len(result["text"])}
            )

            # Clean up the file
            try:
                os.remove(audio_path)
                print(f"Deleted audio file: {audio_path}")
            except Exception as cleanup_error:
                print(f"Failed to delete audio file: {audio_path}, error: {cleanup_error}")
                # Record the error but continue
                sentry_sdk.add_breadcrumb(
                    category="cleanup",
                    message=f"Failed to delete audio file: {audio_path}",
                    level="warning"
                )
                sentry_sdk.capture_message(f"Error during file cleanup: {str(cleanup_error)}", level="warning")

            return result["text"]

        except Exception as e:
            error_msg = str(e)
            print(f"Transcription error: {error_msg}")

            # Record error with Sentry
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("operation", "transcribe_audio")
                scope.set_context("transcription_info", {
                    "audio_path": audio_path,
                    "file_exists": os.path.exists(audio_path),
                })
                sentry_sdk.capture_exception(e)

            raise Exception(f"Failed to transcribe audio: {error_msg}")

def transcribe_video(url: str) -> Dict[str, Any]:
    """
    Main function to download and transcribe a video
    """
    try:
        # Check if it's a TikTok URL
        is_tiktok = "tiktok.com" in url.lower()

        if is_tiktok:
            print(f"Processing TikTok video: {url}")
            sentry_sdk.set_tag("source", "tiktok")

        # Record the start of the operation in Sentry
        with sentry_sdk.start_transaction(op="transcribe", name="transcribe_video") as transaction:
            sentry_sdk.set_tag("url", url)

            # Step 1: Download the audio
            sentry_sdk.add_breadcrumb(
                category="transcription",
                message=f"Starting audio download from {url}",
                level="info"
            )

            audio_file = download_audio(url)
            print(f"Downloaded audio to: {audio_file}")

            # Verify the file exists before proceeding
            if not os.path.exists(audio_file):
                error_msg = f"Downloaded audio file not found at {audio_file}"
                print(error_msg)
                sentry_sdk.capture_message(error_msg, level="error")
                raise Exception(error_msg)

            # Get file size for debugging
            try:
                file_size = os.path.getsize(audio_file)
                print(f"Audio file size: {file_size} bytes")
                if file_size == 0:
                    print("Warning: Audio file is empty")
            except Exception as size_err:
                print(f"Could not check file size: {size_err}")

            # Step 2: Transcribe the audio
            sentry_sdk.add_breadcrumb(
                category="transcription",
                message=f"Starting transcription of {audio_file}",
                level="info"
            )

            with sentry_sdk.start_span(op="transcribe_with_whisper", description=f"Transcribe {audio_file}"):
                try:
                    result = model.transcribe(audio_file)

                    # Record successful transcription
                    sentry_sdk.add_breadcrumb(
                        category="transcription",
                        message=f"Successfully transcribed {audio_file}",
                        level="info"
                    )

                    # Step 3: Clean up the files
                    try:
                        os.remove(audio_file)
                        print(f"Removed audio file: {audio_file}")
                    except Exception as cleanup_error:
                        print(f"Warning: Could not remove audio file: {cleanup_error}")
                        # Continue despite cleanup error

                    # For TikTok videos, return only the transcription text
                    if is_tiktok:
                        return {
                            "transcription": result["text"]
                        }

                    # For other videos, return the full result
                    return {
                        "transcription": result["text"],
                        "segments": result["segments"],
                        "source_url": url,
                    }
                except Exception as whisper_error:
                    # Log detailed error with the file path
                    error_msg = str(whisper_error)
                    print(f"Whisper transcription error: {error_msg}")
                    with sentry_sdk.push_scope() as scope:
                        scope.set_tag("operation", "whisper_transcribe")
                        scope.set_context("file_info", {
                            "path": audio_file,
                            "exists": os.path.exists(audio_file),
                            "size": os.path.getsize(audio_file) if os.path.exists(audio_file) else "N/A",
                            "directory": os.path.dirname(audio_file)
                        })
                        sentry_sdk.capture_exception(whisper_error)

                    raise Exception(f"Transcription failed: {error_msg}")

    except Exception as e:
        print(f"Transcription processing error: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

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
