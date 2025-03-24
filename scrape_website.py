from fastapi import FastAPI, HTTPException
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerConfig
import requests
from bs4 import BeautifulSoup

app = FastAPI()

async def scrape_and_clean(url: str):
    """
    Scrape a website and return cleaned content using Crawl4AI

    Args:
        url: The URL to scrape

    Returns:
        Cleaned markdown content from the website
    """
    try:
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

        try:
            async with AsyncWebCrawler(browser_config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=crawler_config)

                # Ensure we have content
                if not result or not result.markdown or result.markdown.strip() == "":
                    raise ValueError("No content extracted")

                return result.markdown
        except Exception as crawler_error:
            print(f"Crawl4AI error: {str(crawler_error)}. Falling back to simple scraper.")
            # Fall back to simple requests + BeautifulSoup approach
            return fallback_scrape(url)

    except Exception as e:
        error_message = str(e)
        print(f"Error scraping website: {error_message}")
        raise HTTPException(status_code=500, detail=f"Error scraping website: {error_message}")

def fallback_scrape(url: str) -> str:
    """Fallback scraping function using requests and BeautifulSoup"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove unwanted elements
        for element in soup(["script", "style", "header", "footer", "nav", "aside", "form"]):
            element.decompose()

        # Extract and clean text
        text = soup.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = '\n'.join(lines)

        return clean_text
    except Exception as e:
        print(f"Fallback scraper error: {str(e)}")
        raise ValueError(f"Failed to scrape URL: {str(e)}")

# The endpoint in the standalone module should also be async
@app.post("/scrape")
async def scrape_url(url: str):
    cleaned_content = await scrape_and_clean(url)
    return {"cleaned_content": cleaned_content}
