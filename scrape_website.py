from fastapi import FastAPI, HTTPException
import asyncio
from crawl4ai import AsyncWebCrawler

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
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            return result.markdown
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scraping website: {str(e)}")



@app.post("/scrape")
def scrape_url(url: str):
    cleaned_content = scrape_and_clean(url)
    return {"cleaned_content": cleaned_content}
