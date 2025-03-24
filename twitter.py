import os
import tweepy
from fastapi import FastAPI, HTTPException, Body
from typing import Dict, Any
import re
import yt_dlp
import uuid
from dotenv import load_dotenv
from itertools import cycle
import sentry_sdk
import traceback

app = FastAPI()

# Load environment variables from .env
load_dotenv()

# Grab tokens from environment
BEARER_TOKENS = [
    os.getenv("TWITTER_BEARER_TOKEN_1"),
    os.getenv("TWITTER_BEARER_TOKEN_2")
]

# Check that tokens are loaded properly
if not all(BEARER_TOKENS):
    error_msg = "One or more Twitter bearer tokens are missing in the .env file."
    sentry_sdk.capture_message(error_msg, level="error")
    raise ValueError(error_msg)

# Tweepy clients with multiple tokens
clients = [tweepy.Client(bearer_token=token) for token in BEARER_TOKENS]
client_cycle = cycle(clients)

def download_video(video_url: str, output_folder: str = "videos") -> str:
    # Start a span for video download
    with sentry_sdk.start_span(op="twitter.download_video", description=f"Download video from {video_url}"):
        # Add breadcrumb for this operation
        sentry_sdk.add_breadcrumb(
            category="twitter",
            message=f"Downloading video from {video_url}",
            level="info",
            data={"output_folder": output_folder}
        )

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            sentry_sdk.add_breadcrumb(
                category="twitter",
                message=f"Created output folder: {output_folder}",
                level="info"
            )

        filename = os.path.join(output_folder, f"tweet_video_{uuid.uuid4()}.mp4")

        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': filename,
            'merge_output_format': 'mp4'
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            # Record successful download
            sentry_sdk.add_breadcrumb(
                category="twitter",
                message=f"Successfully downloaded video to {filename}",
                level="info"
            )

            return filename
        except Exception as e:
            error_msg = str(e)
            # Record the error
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("operation", "twitter_download_video")
                scope.set_context("download_options", ydl_opts)
                sentry_sdk.capture_exception(e)

            raise Exception(f"Failed to download Twitter video: {error_msg}")

def fetch_tweet_with_retry(tweet_id: str, retries: int = len(clients)):
    # Start a span for tweet fetching
    with sentry_sdk.start_span(op="twitter.fetch_tweet", description=f"Fetch tweet {tweet_id}"):
        sentry_sdk.add_breadcrumb(
            category="twitter",
            message=f"Fetching tweet ID: {tweet_id} with {retries} retries",
            level="info"
        )

        for attempt in range(retries):
            client = next(client_cycle)
            try:
                sentry_sdk.add_breadcrumb(
                    category="twitter",
                    message=f"Attempt {attempt+1}/{retries} to fetch tweet",
                    level="info"
                )

                tweet_response = client.get_tweet(
                    tweet_id,
                    tweet_fields=["conversation_id", "author_id", "attachments"],
                    expansions=["attachments.media_keys"],
                    media_fields=["url", "preview_image_url", "variants", "type"]
                )

                sentry_sdk.add_breadcrumb(
                    category="twitter",
                    message=f"Successfully fetched tweet on attempt {attempt+1}",
                    level="info"
                )

                return tweet_response
            except tweepy.TooManyRequests:
                sentry_sdk.add_breadcrumb(
                    category="twitter",
                    message=f"Rate limit exceeded on attempt {attempt+1}",
                    level="warning"
                )
                continue
            except tweepy.TweepyException as e:
                error_msg = str(e)

                # Record the error
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("operation", "fetch_tweet")
                    scope.set_context("tweet_id", {"id": tweet_id})
                    scope.set_context("attempt", {"current": attempt+1, "total": retries})
                    sentry_sdk.capture_exception(e)

                raise HTTPException(status_code=500, detail=f"Twitter API error: {error_msg}")

        # If we've exhausted all retries
        error_msg = "All tokens have hit rate limits. Please try again later."
        sentry_sdk.capture_message(error_msg, level="error")
        raise HTTPException(status_code=429, detail=error_msg)

def scrape_tweet(url: str):
    # Start a transaction for the whole tweet scraping process
    with sentry_sdk.start_transaction(op="twitter.scrape_tweet", name=f"Scrape Tweet {url}"):
        try:
            sentry_sdk.add_breadcrumb(
                category="twitter",
                message=f"Starting to scrape tweet: {url}",
                level="info"
            )

            # Extract tweet ID from URL
            tweet_id_match = re.search(r"/status/(\d+)", url)
            if not tweet_id_match:
                error_msg = "Invalid tweet URL"
                sentry_sdk.capture_message(error_msg, level="error")
                raise HTTPException(status_code=400, detail=error_msg)

            tweet_id = tweet_id_match.group(1)
            sentry_sdk.set_tag("tweet_id", tweet_id)

            tweets_data = []
            videos_downloaded = []

            # Fetch tweet with retry mechanism
            tweet_response = fetch_tweet_with_retry(tweet_id)

            # Check for errors in response
            if tweet_response.errors:
                error_msg = str(tweet_response.errors)
                sentry_sdk.capture_message(f"Tweet API returned errors: {error_msg}", level="error")
                raise HTTPException(status_code=400, detail=error_msg)

            # Extract tweet text
            if tweet_response.data:
                tweets_data.append(tweet_response.data.text)
                sentry_sdk.add_breadcrumb(
                    category="twitter",
                    message="Extracted tweet text",
                    level="info",
                    data={"text_length": len(tweet_response.data.text)}
                )

            # Extract media items
            media = {m.media_key: m for m in tweet_response.includes.get('media', [])} if 'includes' in tweet_response and 'media' in tweet_response.includes else {}

            if 'attachments' in tweet_response.data and tweet_response.data.attachments:
                sentry_sdk.add_breadcrumb(
                    category="twitter",
                    message=f"Found media attachments in tweet",
                    level="info",
                    data={"media_keys_count": len(tweet_response.data.attachments.get('media_keys', []))}
                )

                # Process each media attachment
                for media_key in tweet_response.data.attachments.get('media_keys', []):
                    if media_key not in media:
                        sentry_sdk.add_breadcrumb(
                            category="twitter",
                            message=f"Media key {media_key} not found in includes",
                            level="warning"
                        )
                        continue

                    media_item = media[media_key]
                    sentry_sdk.add_breadcrumb(
                        category="twitter",
                        message=f"Processing media item of type: {media_item.type}",
                        level="info"
                    )

                    # Download video or animated GIF
                    if media_item.type in ['video', 'animated_gif']:
                        with sentry_sdk.start_span(op="twitter.process_video", description=f"Process video from tweet"):
                            video_variants = media_item.variants
                            video_mp4_variants = [v for v in video_variants if v.get('content_type') == 'video/mp4']

                            if video_mp4_variants:
                                highest_quality_video = sorted(video_mp4_variants,
                                                           key=lambda x: x.get('bit_rate', 0),
                                                           reverse=True)[0]

                                sentry_sdk.add_breadcrumb(
                                    category="twitter",
                                    message=f"Selected highest quality video: {highest_quality_video.get('bit_rate', 0)} bit rate",
                                    level="info"
                                )

                                downloaded_video = download_video(highest_quality_video['url'])
                                videos_downloaded.append(downloaded_video)

                                sentry_sdk.add_breadcrumb(
                                    category="twitter",
                                    message=f"Added video to downloaded list: {downloaded_video}",
                                    level="info"
                                )

            # Record success with Sentry
            sentry_sdk.add_breadcrumb(
                category="twitter",
                message=f"Successfully scraped tweet {tweet_id}",
                level="info",
                data={
                    "tweets_count": len(tweets_data),
                    "videos_count": len(videos_downloaded)
                }
            )

            return {
                "tweets": tweets_data,
                "videos": videos_downloaded
            }
        except Exception as e:
            # This will capture any exceptions not already captured
            if not isinstance(e, HTTPException):
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("operation", "scrape_tweet")
                    scope.set_context("url", {"url": url})
                    sentry_sdk.capture_exception(e)

                # Convert to HTTPException
                if isinstance(e, Exception):
                    raise HTTPException(status_code=500, detail=str(e))

            # Re-raise HTTPExceptions as is
            raise

@app.post("/scrape_tweet")
async def scrape_tweet_endpoint(body: Dict[str, Any] = Body(...)):
    try:
        # Set Sentry tag for this endpoint
        sentry_sdk.set_tag("endpoint", "scrape_tweet")

        # Extract URL from request body
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

        # Log the request
        sentry_sdk.add_breadcrumb(
            category="request",
            message=f"Received scrape_tweet request for URL: {url}",
            level="info"
        )

        # Call the tweet scraping function
        return scrape_tweet(url)
    except HTTPException as he:
        # Record HTTP exceptions with Sentry
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_type", "http_exception")
            scope.set_context("request_body", body)
            sentry_sdk.capture_exception(he)

        # Re-raise the exception
        raise he
    except Exception as e:
        # Catch and record any unexpected exceptions
        error_msg = str(e)
        error_trace = traceback.format_exc()

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_type", "unexpected_error")
            scope.set_context("request_body", body)
            scope.set_context("error_details", {"message": error_msg, "traceback": error_trace})
            sentry_sdk.capture_exception(e)

        # Return a 500 error
        raise HTTPException(status_code=500, detail=f"Error processing request: {error_msg}")
