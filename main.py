from fastapi import FastAPI, HTTPException, Body, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, validator
from typing import Dict, Any, Optional, Union
import traceback
import re
import os
import json
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from fastapi.exceptions import RequestValidationError
from starlette.routing import Route
from starlette.requests import Request as StarletteRequest

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

class DirectUrlModel(BaseModel):
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

# Define a union type for request validation
class AlternativeRequestModel(BaseModel):
    query: Optional[QueryModel] = None
    url: Optional[str] = None

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
async def transcribe_route(body: Union[RequestModel, DirectUrlModel, Dict[str, Any], Any] = Body(...)):
    """
    Transcribe a YouTube video to text.

    Expected request format:
    ```json
    {
      "query": {
        "url": "https://www.youtube.com/watch?v=example"
      }
    }
    ```

    Alternatively, you can also use:
    ```json
    {
      "url": "https://www.youtube.com/watch?v=example"
    }
    ```

    Returns the transcription text and metadata.
    """
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

            # If body is a Pydantic model
            if hasattr(body, "url") and body.url:
                # Direct URL in the body
                url = body.url
            elif hasattr(body, "query") and body.query and hasattr(body.query, "url"):
                # URL in the query object
                url = body.query.url
            # If body is a dict
            elif isinstance(body, dict):
                # Try direct URL
                if "url" in body and body["url"]:
                    url = body["url"]
                # Try URL in query object
                elif "query" in body and isinstance(body["query"], dict):
                    url = body["query"].get("url")

            if not url:
                error_msg = "URL is required either directly in the body or in a query object"
                sentry_sdk.capture_message(error_msg, level="error")
                raise HTTPException(status_code=400, detail=error_msg)

            # Add schema if missing
            if not re.match(r'^https?://', url):
                url = 'https://' + url

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
async def scrape_tweet_route(body: Union[RequestModel, DirectUrlModel, Dict[str, Any], Any] = Body(...)):
    """
    Extract videos from a Twitter/X tweet.

    Expected request format:
    ```json
    {
      "query": {
        "url": "https://twitter.com/username/status/123456789"
      }
    }
    ```

    Alternatively, you can also use:
    ```json
    {
      "url": "https://twitter.com/username/status/123456789"
    }
    ```

    Returns tweet text and extracted video URLs.
    """
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

            # If body is a Pydantic model
            if hasattr(body, "url") and body.url:
                # Direct URL in the body
                url = body.url
            elif hasattr(body, "query") and body.query and hasattr(body.query, "url"):
                # URL in the query object
                url = body.query.url
            # If body is a dict
            elif isinstance(body, dict):
                # Try direct URL
                if "url" in body and body["url"]:
                    url = body["url"]
                # Try URL in query object
                elif "query" in body and isinstance(body["query"], dict):
                    url = body["query"].get("url")

            if not url:
                error_msg = "URL is required either directly in the body or in a query object"
                sentry_sdk.capture_message(error_msg, level="error")
                raise HTTPException(status_code=400, detail=error_msg)

            # Add schema if missing
            if not re.match(r'^https?://', url):
                url = 'https://' + url

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
async def scrape_website_route(body: Union[RequestModel, DirectUrlModel, Dict[str, Any], Any] = Body(...)):
    """
    Extract clean, formatted content from a website.

    Expected request format:
    ```json
    {
      "query": {
        "url": "https://example.com/article"
      }
    }
    ```

    Alternatively, you can also use:
    ```json
    {
      "url": "https://example.com/article"
    }
    ```

    Returns the extracted content in Markdown format.
    """
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
                # If body is a Pydantic model
                if hasattr(body, "url") and body.url:
                    # Direct URL in the body
                    url = body.url
                elif hasattr(body, "query") and body.query and hasattr(body.query, "url"):
                    # URL in the query object
                    url = body.query.url
                # If body is a dict
                elif isinstance(body, dict):
                    # Try direct URL
                    if "url" in body and body["url"]:
                        url = body["url"]
                    # Try URL in query object
                    elif "query" in body and isinstance(body["query"], dict):
                        url = body["query"].get("url")
            except Exception as e:
                error_msg = f"Error extracting URL: {str(e)}"
                print(error_msg)
                sentry_sdk.capture_message(error_msg, level="error")

            # Validate URL
            if not url:
                error_msg = "URL is required either directly in the body or in a query object"
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

# Add diagnostic endpoint
@app.post("/debug")
async def debug_endpoint(request: Request):
    """
    Debug endpoint that logs the raw request body to Sentry.
    Use this to diagnose issues with request handling.
    """
    # Create a transaction
    with sentry_sdk.start_transaction(op="debug", name="Debug Request"):
        try:
            # Get raw body
            body = await request.body()
            body_str = body.decode('utf-8')

            # Try to parse as JSON
            try:
                json_body = json.loads(body_str)
                parsed = True
            except:
                json_body = {"error": "Could not parse as JSON"}
                parsed = False

            # Log to console
            print(f"DEBUG ENDPOINT - Raw body: {body_str}")

            # Add breadcrumb in Sentry
            sentry_sdk.add_breadcrumb(
                category="debug",
                message="Received debug request",
                level="info",
                data={
                    "raw_body": body_str,
                    "parsed_json": json_body,
                    "headers": dict(request.headers)
                }
            )

            # Send event to Sentry
            sentry_sdk.capture_message(
                "Debug request received",
                level="info",
            )

            # Return debug info
            return {
                "received": {
                    "raw_body": body_str,
                    "parsed_as_json": parsed,
                    "json_body": json_body,
                    "headers": dict(request.headers)
                },
                "message": "Debug request logged to Sentry"
            }
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return {"error": str(e)}

# Add raw version of the scrape_tweet endpoint that bypasses model validation
@app.post("/raw_scrape_tweet")
async def raw_scrape_tweet_route(request: Request):
    """
    Raw version of the scrape_tweet endpoint that bypasses model validation.
    This is for troubleshooting validation issues.

    Expected request format (either of these):
    ```json
    {
      "query": {
        "url": "https://twitter.com/username/status/123456789"
      }
    }
    ```

    ```json
    {
      "url": "https://twitter.com/username/status/123456789"
    }
    ```
    """
    try:
        # Start transaction for Sentry
        with sentry_sdk.start_transaction(op="raw_scrape_tweet", name="Raw Scrape Tweet"):
            # Get raw request body
            body_bytes = await request.body()
            body_str = body_bytes.decode('utf-8')

            # Log to console
            print(f"[/raw_scrape_tweet] Raw request body: {body_str}")

            try:
                # Parse JSON manually
                body = json.loads(body_str)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON: {str(e)}"
                sentry_sdk.capture_message(error_msg, level="error")
                return JSONResponse(
                    status_code=400,
                    content={"detail": error_msg}
                )

            # Log parsed body
            sentry_sdk.add_breadcrumb(
                category="twitter",
                message=f"Parsed request body: {body}",
                level="info"
            )

            # Handle list format
            if isinstance(body, list) and len(body) > 0:
                body = body[0]
                sentry_sdk.add_breadcrumb(
                    category="twitter",
                    message=f"Extracted from list: {body}",
                    level="info"
                )

            # Extract URL
            url = None

            # If direct URL in body
            if isinstance(body, dict):
                if "url" in body and body["url"]:
                    url = body["url"]
                # If URL in query object
                elif "query" in body and isinstance(body["query"], dict) and "url" in body["query"]:
                    url = body["query"]["url"]

            # Validate URL
            if not url:
                error_msg = "URL is required (either as 'url' field or inside 'query' object)"
                sentry_sdk.capture_message(error_msg, level="error")
                return JSONResponse(
                    status_code=400,
                    content={"detail": error_msg}
                )

            # Add schema if missing
            if not re.match(r'^https?://', url):
                url = 'https://' + url

            # Log URL
            sentry_sdk.add_breadcrumb(
                category="twitter",
                message=f"Extracted URL: {url}",
                level="info"
            )

            # Call the scrape function
            from twitter import scrape_tweet
            result = scrape_tweet(url)

            return result
    except Exception as e:
        # Capture exception
        sentry_sdk.set_tag("error_type", "raw_tweet_scraping_error")
        sentry_sdk.capture_exception(e)

        # Log the error
        traceback_str = traceback.format_exc()
        print(f"[/raw_scrape_tweet] Error: {str(e)}\n{traceback_str}")

        # Return error response
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error: {str(e)}"}
        )

# Add raw version of the transcribe endpoint
@app.post("/raw_transcribe")
async def raw_transcribe_route(request: Request):
    """
    Raw version of the transcribe endpoint that bypasses model validation.
    This is for troubleshooting validation issues.
    """
    try:
        # Start transaction for Sentry
        with sentry_sdk.start_transaction(op="raw_transcribe", name="Raw Transcribe"):
            # Get raw request body
            body_bytes = await request.body()
            body_str = body_bytes.decode('utf-8')

            # Log to console
            print(f"[/raw_transcribe] Raw request body: {body_str}")

            try:
                # Parse JSON manually
                body = json.loads(body_str)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON: {str(e)}"
                sentry_sdk.capture_message(error_msg, level="error")
                return JSONResponse(
                    status_code=400,
                    content={"detail": error_msg}
                )

            # Handle list format
            if isinstance(body, list) and len(body) > 0:
                body = body[0]

            # Extract URL
            url = None

            # If direct URL in body
            if isinstance(body, dict):
                if "url" in body and body["url"]:
                    url = body["url"]
                # If URL in query object
                elif "query" in body and isinstance(body["query"], dict) and "url" in body["query"]:
                    url = body["query"]["url"]

            # Validate URL
            if not url:
                error_msg = "URL is required (either as 'url' field or inside 'query' object)"
                sentry_sdk.capture_message(error_msg, level="error")
                return JSONResponse(
                    status_code=400,
                    content={"detail": error_msg}
                )

            # Add schema if missing
            if not re.match(r'^https?://', url):
                url = 'https://' + url

            # Call the transcribe function
            from run import transcribe_video
            result = transcribe_video(url)

            return result
    except Exception as e:
        # Capture exception
        sentry_sdk.set_tag("error_type", "raw_transcription_error")
        sentry_sdk.capture_exception(e)

        # Return error response
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error: {str(e)}"}
        )

# Add raw version of the scrape endpoint
@app.post("/raw_scrape")
async def raw_scrape_route(request: Request):
    """
    Raw version of the scrape endpoint that bypasses model validation.
    This is for troubleshooting validation issues.
    """
    try:
        # Start transaction for Sentry
        with sentry_sdk.start_transaction(op="raw_scrape", name="Raw Scrape"):
            # Get raw request body
            body_bytes = await request.body()
            body_str = body_bytes.decode('utf-8')

            # Log to console
            print(f"[/raw_scrape] Raw request body: {body_str}")

            try:
                # Parse JSON manually
                body = json.loads(body_str)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON: {str(e)}"
                sentry_sdk.capture_message(error_msg, level="error")
                return JSONResponse(
                    status_code=400,
                    content={"detail": error_msg}
                )

            # Handle list format
            if isinstance(body, list) and len(body) > 0:
                body = body[0]

            # Extract URL
            url = None

            # If direct URL in body
            if isinstance(body, dict):
                if "url" in body and body["url"]:
                    url = body["url"]
                # If URL in query object
                elif "query" in body and isinstance(body["query"], dict) and "url" in body["query"]:
                    url = body["query"]["url"]

            # Validate URL
            if not url:
                error_msg = "URL is required (either as 'url' field or inside 'query' object)"
                sentry_sdk.capture_message(error_msg, level="error")
                return JSONResponse(
                    status_code=400,
                    content={"detail": error_msg}
                )

            # Add schema if missing
            if not re.match(r'^https?://', url):
                url = 'https://' + url

            # Call the scrape function
            from scrape_website import scrape_and_clean
            result = await scrape_and_clean(url)

            return {"cleaned_content": result}
    except Exception as e:
        # Capture exception
        sentry_sdk.set_tag("error_type", "raw_scraping_error")
        sentry_sdk.capture_exception(e)

        # Return error response
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)