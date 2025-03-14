import os
import tweepy
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import re
import yt_dlp
import uuid
from dotenv import load_dotenv
from itertools import cycle

app = FastAPI()

# List of Bearer tokens (replace with your tokens)
# Load environment variables from .env
load_dotenv()

# Grab tokens from environment
BEARER_TOKENS = [
    os.getenv("TWITTER_BEARER_TOKEN_1"),
    os.getenv("TWITTER_BEARER_TOKEN_2")
]

# Debug: print tokens temporarily (remove later!)
print("Loaded tokens:", BEARER_TOKENS)

# Check that tokens are loaded properly
if not all(BEARER_TOKENS):
    raise ValueError("One or more Twitter bearer tokens are missing in the .env file.")

# Tweepy clients with multiple tokens
clients = [tweepy.Client(bearer_token=token) for token in BEARER_TOKENS]
client_cycle = cycle(clients)

class TweetURL(BaseModel):
    url: HttpUrl

def download_video(video_url: str, output_folder: str = "videos") -> str:
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    filename = os.path.join(output_folder, f"tweet_video_{uuid.uuid4()}.mp4")

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': filename,
        'merge_output_format': 'mp4'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    return filename

def fetch_tweet_with_retry(tweet_id: str, retries: int = len(clients)):
    for _ in range(retries):
        client = next(client_cycle)
        try:
            tweet_response = client.get_tweet(
                tweet_id,
                tweet_fields=["conversation_id", "author_id", "attachments"],
                expansions=["attachments.media_keys"],
                media_fields=["url", "preview_image_url", "variants", "type"]
            )
            return tweet_response
        except tweepy.TooManyRequests:
            continue
        except tweepy.TweepyException as e:
            raise HTTPException(status_code=500, detail=f"Twitter API error: {str(e)}")
    raise HTTPException(status_code=429, detail="All tokens have hit rate limits. Please try again later.")

@app.post("/scrape_tweet")
def scrape_tweet(tweet_url: TweetURL):
    tweet_id_match = re.search(r"/status/(\d+)", str(tweet_url.url))
    if not tweet_id_match:
        raise HTTPException(status_code=400, detail="Invalid tweet URL")

    tweet_id = tweet_id_match.group(1)

    tweets_data = []
    videos_downloaded = []

    tweet_response = fetch_tweet_with_retry(tweet_id)

    if tweet_response.errors:
        raise HTTPException(status_code=400, detail=str(tweet_response.errors))

    if tweet_response.data:
        tweets_data.append(tweet_response.data.text)

    media = {m.media_key: m for m in tweet_response.includes.get('media', [])}

    if 'attachments' in tweet_response.data:
        for media_key in tweet_response.data.attachments.get('media_keys', []):
            media_item = media[media_key]

            if media_item.type in ['video', 'animated_gif']:
                video_variants = media_item.variants
                video_mp4_variants = [v for v in video_variants if v.get('content_type') == 'video/mp4']
                if video_mp4_variants:
                    highest_quality_video = sorted(video_mp4_variants,
                                                   key=lambda x: x.get('bit_rate', 0),
                                                   reverse=True)[0]
                    downloaded_video = download_video(highest_quality_video['url'])
                    videos_downloaded.append(downloaded_video)

    return {
        "tweets": tweets_data,
        "videos": videos_downloaded
    }
