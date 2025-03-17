from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

# Create base query model
class URLRequest(BaseModel):
    url: str

# Direct imports for functions
from run import transcribe_video
from twitter import scrape_tweet
from scrape_website import scrape_and_clean

# Create main FastAPI app
app = FastAPI(title="GPT Transcribe API", description="API for transcribing videos and scraping tweets")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import route for transcription
@app.post("/transcribe", tags=["Transcription"])
async def transcribe_route(url: URLRequest):
    return transcribe_video(url.url)

# Import route for tweet scraping
@app.post("/scrape_tweet", tags=["Twitter"])
async def scrape_tweet_route(url: URLRequest):
    return scrape_tweet(url.url)

# Add website scraping endpoint
@app.post("/scrape", tags=["Web Scraping"])
async def scrape_website_route(url: URLRequest):
    cleaned_content = scrape_and_clean(url.url)
    return {"cleaned_content": cleaned_content}

# Add a simple health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)