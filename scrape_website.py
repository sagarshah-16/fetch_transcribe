from fastapi import FastAPI, HTTPException
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig
# Create a compatible CrawlerConfig since it's not in Crawl4AI version 0.5.0.post4
class CrawlerConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

import requests
from bs4 import BeautifulSoup
import re
import sentry_sdk
import traceback

app = FastAPI()

async def scrape_and_clean(url: str):
    """
    Scrape a website and return cleaned content using Crawl4AI

    Args:
        url: The URL to scrape

    Returns:
        Cleaned markdown content from the website
    """
    # Start a transaction for scraping
    with sentry_sdk.start_transaction(op="scrape", name=f"Scrape {url}"):
        try:
            # Validate and normalize URL
            if not re.match(r'^https?://', url):
                original_url = url
                url = 'https://' + url
                sentry_sdk.add_breadcrumb(
                    category="scraping",
                    message=f"Added https:// scheme to URL: {original_url} → {url}",
                    level="info"
                )

            print(f"Starting to scrape URL: {url}")
            sentry_sdk.add_breadcrumb(
                category="scraping",
                message=f"Starting to scrape URL: {url}",
                level="info"
            )

            # Try the fallback method first - it's more reliable
            try:
                print("Using fallback scraper first")
                sentry_sdk.add_breadcrumb(
                    category="scraping",
                    message="Attempting to use fallback scraper",
                    level="info"
                )

                content = fallback_scrape(url)

                if content and len(content) > 100:  # Only return if we got meaningful content
                    print(f"Fallback scraper succeeded with {len(content)} chars")
                    sentry_sdk.add_breadcrumb(
                        category="scraping",
                        message=f"Fallback scraper succeeded with {len(content)} chars",
                        level="info"
                    )
                    return content
            except Exception as fallback_error:
                print(f"Fallback scraper failed: {str(fallback_error)}")
                sentry_sdk.add_breadcrumb(
                    category="scraping",
                    message=f"Fallback scraper failed: {str(fallback_error)}",
                    level="warning"
                )

            # If fallback didn't work or didn't get enough content, try crawl4ai
            print("Trying Crawl4AI...")
            sentry_sdk.add_breadcrumb(
                category="scraping",
                message="Attempting to use Crawl4AI",
                level="info"
            )

            # Configure browser options for better compatibility
            browser_config = BrowserConfig(
                headless=True,
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )

            # Configure crawler options
            crawler_config = CrawlerConfig(
                wait_for_timeout=5000,  # 5 seconds wait for page load
                wait_for_selector="body",
                extract_text=True,
                extract_links=True
            )

            # Record the configurations in Sentry
            sentry_sdk.set_context("browser_config", browser_config.__dict__)
            sentry_sdk.set_context("crawler_config", crawler_config.__dict__)

            # Use Crawl4AI
            with sentry_sdk.start_span(op="crawl4ai", description=f"Crawl {url}"):
                async with AsyncWebCrawler(browser_config=browser_config) as crawler:
                    # With version 0.5.0.post4, we may need to pass config attributes directly
                    try:
                        result = await crawler.arun(url=url, config=crawler_config)
                    except TypeError:
                        # If the above fails, try passing the config attributes directly
                        sentry_sdk.capture_message("Falling back to direct config attributes", level="info")
                        result = await crawler.arun(
                            url=url,
                            wait_for_timeout=crawler_config.wait_for_timeout,
                            wait_for_selector=crawler_config.wait_for_selector,
                            extract_text=crawler_config.extract_text,
                            extract_links=crawler_config.extract_links
                        )

                    # Ensure we have content
                    if not result or not result.markdown or result.markdown.strip() == "":
                        error_msg = "No content extracted by Crawl4AI"
                        sentry_sdk.capture_message(error_msg, level="error")
                        raise ValueError(error_msg)

                    print(f"Crawl4AI succeeded with {len(result.markdown)} chars")
                    sentry_sdk.add_breadcrumb(
                        category="scraping",
                        message=f"Crawl4AI succeeded with {len(result.markdown)} chars",
                        level="info"
                    )
                    return result.markdown

        except Exception as e:
            error_message = str(e)
            print(f"Error scraping website: {error_message}")

            # Add error details to Sentry
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("operation", "scrape_website")
                scope.set_context("url", {"url": url})
                scope.set_context("error_details", {"message": error_message, "traceback": traceback.format_exc()})
                sentry_sdk.capture_exception(e)

            # Last resort fallback - try simple scraping again if we haven't already
            try:
                print("Last resort: trying fallback scraper again")
                sentry_sdk.add_breadcrumb(
                    category="scraping",
                    message="Last resort: trying fallback scraper again",
                    level="info"
                )
                return fallback_scrape(url)
            except Exception as fallback_error:
                # If all methods fail, capture the fallback error and raise the original error
                sentry_sdk.capture_exception(fallback_error)
                raise HTTPException(status_code=500, detail=f"Error scraping website: {error_message}")

def fallback_scrape(url: str) -> str:
    """Fallback scraping function using requests and BeautifulSoup"""
    # Start a span for the fallback scraper
    with sentry_sdk.start_span(op="fallback_scrape", description=f"Fallback scrape {url}"):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            print(f"Fallback scraper requesting: {url}")
            sentry_sdk.add_breadcrumb(
                category="scraping",
                message=f"Fallback scraper requesting: {url}",
                level="info"
            )

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Record response info
            sentry_sdk.add_breadcrumb(
                category="scraping",
                message=f"Received response: {response.status_code}",
                level="info",
                data={"status_code": response.status_code, "content_length": len(response.text)}
            )

            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove unwanted elements
            for element in soup(["script", "style", "header", "footer", "nav", "aside", "form"]):
                element.decompose()

            # Extract and clean text
            text = soup.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = '\n'.join(lines)

            # Record successful extraction
            sentry_sdk.add_breadcrumb(
                category="scraping",
                message=f"Successfully cleaned and extracted {len(clean_text)} chars",
                level="info"
            )

            return clean_text
        except Exception as e:
            print(f"Fallback scraper error: {str(e)}")

            # Record the error
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("operation", "fallback_scrape")
                scope.set_context("url", {"url": url})
                scope.set_context("headers", headers)
                sentry_sdk.capture_exception(e)

            raise ValueError(f"Failed to scrape URL: {str(e)}")

# The endpoint in the standalone module should also be async
@app.post("/scrape")
async def scrape_url(url: str):
    try:
        sentry_sdk.set_tag("endpoint", "scrape")
        sentry_sdk.add_breadcrumb(
            category="request",
            message=f"Received scrape request for URL: {url}",
            level="info"
        )
        cleaned_content = await scrape_and_clean(url)
        return {"cleaned_content": cleaned_content}
    except Exception as e:
        # Record the exception
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("operation", "scrape_url_endpoint")
            scope.set_context("url", {"url": url})
            sentry_sdk.capture_exception(e)

        # Re-raise as HTTP exception if not already
        if not isinstance(e, HTTPException):
            raise HTTPException(status_code=500, detail=str(e))
        raise
