# GPT Transcribe API

A multi-purpose API for transcribing YouTube videos, scraping Twitter/X videos, and extracting clean content from websites.

## Features

- **Video Transcription**: Transcribe YouTube videos using Whisper AI
- **Twitter Video Scraping**: Extract videos from tweets
- **Website Content Scraping**: Clean and extract text content from websites

## API Endpoints

### Standard Endpoints

#### Transcribe YouTube Videos
**Endpoint**: `/transcribe`
**Method**: POST
**Preferred Request Format**:
```json
{
  "query": {
    "url": "https://www.youtube.com/watch?v=example"
  }
}
```

**Alternative Request Format**:
```json
{
  "url": "https://www.youtube.com/watch?v=example"
}
```

#### Extract Videos from Tweets
**Endpoint**: `/scrape_tweet`
**Method**: POST
**Preferred Request Format**:
```json
{
  "query": {
    "url": "https://twitter.com/username/status/123456789"
  }
}
```

**Alternative Request Format**:
```json
{
  "url": "https://twitter.com/username/status/123456789"
}
```

#### Extract Content from Websites
**Endpoint**: `/scrape`
**Method**: POST
**Preferred Request Format**:
```json
{
  "query": {
    "url": "https://example.com/article"
  }
}
```

**Alternative Request Format**:
```json
{
  "url": "https://example.com/article"
}
```

#### Health Check
**Endpoint**: `/health`
**Method**: GET

### Debug/Troubleshooting Endpoints

If you're experiencing validation errors with the standard endpoints, you can use these alternatives that bypass the FastAPI validation system:

#### Debug Request Endpoint
**Endpoint**: `/debug`
**Method**: POST
Returns detailed information about your request for troubleshooting.

#### Raw Transcribe Endpoint
**Endpoint**: `/raw_transcribe`
**Method**: POST
Same as `/transcribe` but with raw request handling.

#### Raw Tweet Scraping Endpoint
**Endpoint**: `/raw_scrape_tweet`
**Method**: POST
Same as `/scrape_tweet` but with raw request handling.

#### Raw Website Scraping Endpoint
**Endpoint**: `/raw_scrape`
**Method**: POST
Same as `/scrape` but with raw request handling.

## Request Format Notes

- All endpoints accept two JSON formats:
  1. A JSON object with a `query` object containing a `url` field (preferred)
  2. A JSON object with a direct `url` field
- The URL should be a complete URL including the protocol (http:// or https://)
- The API has fallback mechanisms to handle alternative formats like arrays
- If experiencing validation errors, try using the raw endpoints (e.g., `/raw_scrape_tweet` instead of `/scrape_tweet`)

## Requirements

- Python 3.8+
- FastAPI
- Whisper AI
- FFmpeg
- Twitter API tokens (for tweet scraping)

## Deployment

Use the included deployment scripts to easily deploy on a Linux server with Nginx:

1. Update variables in `deploy.sh`
2. Run `./deploy.sh`

## Configuration

- Update `.env` with your Twitter API tokens
- Modify Nginx configuration for production use
- Set up SSL for secure connections

## License

MIT