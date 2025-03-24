from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, validator
from typing import Dict, Any, Optional
import traceback
import re
import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from fastapi.exceptions import RequestValidationError

# Initialize Sentry SDK
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),  # Set your SENTRY_DSN in .env file
    integrations=[
        FastApiIntegration(),
        StarletteIntegration(),
    ],
    # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring
    traces_sample_rate=1.0,
    # Performance monitoring
    enable_tracing=True,
    # Environment name
    environment=os.getenv("ENVIRONMENT", "development"),
    # Release version
    release=os.getenv("RELEASE", "0.1.0"),
)

# Create request models
class QueryModel(BaseModel):
    url: str

    @validator('url')
    def validate_url(cls, v):
        if not v:
            raise ValueError('URL cannot be empty')
        # Add schema if missing
        if not re.match(r'^https?://', v):
            v = 'https://' + v
        return v

class RequestModel(BaseModel):
    query: QueryModel

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

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_message = str(exc)

    # Capture exception in Sentry with request info
    with sentry_sdk.push_scope() as scope:
        # Add request info
        scope.set_context("request", {
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else None,
        })

        # Add custom tags
        scope.set_tag("endpoint", request.url.path)

        # Capture exception
        sentry_sdk.capture_exception(exc)

    # Return error response to client
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {error_message}"}
    )

# Add validation error handler to capture these errors in Sentry
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = exc.errors()
    error_message = "Validation error"

    # Get raw request body
    try:
        body = await request.json()
    except:
        body = "Could not parse request body"

    # Capture exception in Sentry with request info
    with sentry_sdk.push_scope() as scope:
        # Add request info
        scope.set_context("request", {
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else None,
            "body": body
        })

        # Add validation error details
        scope.set_context("validation_errors", error_details)

        # Add custom tags
        scope.set_tag("endpoint", request.url.path)
        scope.set_tag("error_type", "validation_error")

        # Capture exception
        sentry_sdk.capture_exception(exc)

    # Return validation error response
    return JSONResponse(
        status_code=422,
        content={"detail": error_details}
    )

# Import route for transcription
@app.post("/transcribe", tags=["Transcription"])
async def transcribe_route(body: Any = Body(...)):
    try:
        with sentry_sdk.start_transaction(op="http.server", name="transcribe_video"):
            # Handle both array and object formats
            if isinstance(body, list) and len(body) > 0:
                # Handle array format with first item
                sentry_sdk.add_breadcrumb(
                    category="request",
                    message="Received array request body format, using first item",
                    level="info"
                )
                body = body[0]

            # Extract URL with robust checking
            url = None
            if isinstance(body, dict):
                query = body.get("query")
                if isinstance(query, dict):
                    url = query.get("url")

            if not url:
                error_msg = "URL is required in query object"
                sentry_sdk.capture_message(error_msg, level="error")
                raise HTTPException(status_code=400, detail=error_msg)

            # Set breadcrumb for debugging
            sentry_sdk.add_breadcrumb(
                category="transcribe",
                message=f"Transcribing video from URL: {url}",
                level="info"
            )

            return transcribe_video(url)
    except Exception as e:
        # Tag the error
        sentry_sdk.set_tag("error_type", "transcription_error")
        # Re-raise to let the global handler capture it
        raise

# Import route for tweet scraping
@app.post("/scrape_tweet", tags=["Twitter"])
async def scrape_tweet_route(body: Any = Body(...)):
    try:
        with sentry_sdk.start_transaction(op="http.server", name="scrape_tweet"):
            # Handle both array and object formats
            if isinstance(body, list) and len(body) > 0:
                # Handle array format with first item
                sentry_sdk.add_breadcrumb(
                    category="request",
                    message="Received array request body format, using first item",
                    level="info"
                )
                body = body[0]

            # Extract URL with robust checking
            url = None
            if isinstance(body, dict):
                query = body.get("query")
                if isinstance(query, dict):
                    url = query.get("url")

            if not url:
                error_msg = "URL is required in query object"
                sentry_sdk.capture_message(error_msg, level="error")
                raise HTTPException(status_code=400, detail=error_msg)

            # Set breadcrumb for debugging
            sentry_sdk.add_breadcrumb(
                category="twitter",
                message=f"Scraping tweet from URL: {url}",
                level="info"
            )

            return scrape_tweet(url)
    except Exception as e:
        # Tag the error
        sentry_sdk.set_tag("error_type", "tweet_scraping_error")
        # Re-raise to let the global handler capture it
        raise

# Add website scraping endpoint - both accepting dict and RequestModel
@app.post("/scrape", tags=["Web Scraping"])
async def scrape_website_route(body: Any = Body(...)):
    try:
        with sentry_sdk.start_transaction(op="http.server", name="scrape_website"):
            # Print the request for debugging
            print(f"[/scrape] Received request body: {body}")

            # Handle both array and object formats
            if isinstance(body, list) and len(body) > 0:
                # Handle array format with first item
                sentry_sdk.add_breadcrumb(
                    category="request",
                    message="Received array request body format, using first item",
                    level="info"
                )
                body = body[0]
                print(f"[/scrape] Extracted first item from array: {body}")

            # Extract URL with robust checking
            url = None
            try:
                # Try to get URL from query object
                if isinstance(body, dict):
                    query = body.get("query")
                    if isinstance(query, dict):
                        url = query.get("url")
                    elif query is None:
                        # Maybe the body itself is the query?
                        url = body.get("url")
            except Exception as e:
                error_msg = f"Error extracting URL: {str(e)}"
                print(error_msg)
                sentry_sdk.capture_message(error_msg, level="error")

            # Validate URL
            if not url:
                error_msg = "URL is required in the request"
                sentry_sdk.capture_message(error_msg, level="error")
                raise HTTPException(status_code=400, detail=error_msg)

            print(f"[/scrape] Extracted URL: {url}")

            # Add schema if missing
            if not re.match(r'^https?://', url):
                url = 'https://' + url
                print(f"[/scrape] Added schema to URL: {url}")

            # Set breadcrumb for debugging
            sentry_sdk.add_breadcrumb(
                category="scraping",
                message=f"Scraping website from URL: {url}",
                level="info"
            )

            # Call scraping function
            print(f"[/scrape] Calling scrape_and_clean with URL: {url}")
            markdown_content = await scrape_and_clean(url)

            # Set another breadcrumb after successful scraping
            sentry_sdk.add_breadcrumb(
                category="scraping",
                message=f"Successfully scraped {len(markdown_content)} characters from {url}",
                level="info"
            )

            # Return response
            return {"cleaned_content": markdown_content}
    except HTTPException as he:
        # Re-raise HTTP exceptions with more info
        print(f"[/scrape] HTTP Exception: {str(he.detail)}")

        # Capture HTTP exceptions with context
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("error_type", "http_exception")
            scope.set_tag("status_code", he.status_code)
            sentry_sdk.capture_exception(he)

        raise he
    except Exception as e:
        # Log detailed error for other exceptions
        error_trace = traceback.format_exc()
        print(f"[/scrape] Error: {str(e)}\n{error_trace}")

        # Tag the error and capture
        sentry_sdk.set_tag("error_type", "scraping_error")
        sentry_sdk.capture_exception(e)

        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

# Add a simple health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    # Record a breadcrumb for this health check
    sentry_sdk.add_breadcrumb(
        category="health",
        message="Health check endpoint accessed",
        level="info"
    )
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)