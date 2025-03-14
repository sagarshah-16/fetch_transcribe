from fastapi import FastAPI, HTTPException
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl

app = FastAPI()

class URLRequest(BaseModel):
    url: HttpUrl


def scrape_and_clean(url: str):
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

    except requests.exceptions.RequestException as e:
        raise Exception(f"Request error: {e}")



@app.post("/scrape")
def scrape_url(request: URLRequest):
    cleaned_content = scrape_and_clean(request.url)
    return {"cleaned_content": cleaned_content}
