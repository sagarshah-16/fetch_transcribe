# GPT Transcribe API

A multi-purpose API for transcribing YouTube videos, scraping Twitter/X videos, and extracting clean content from websites.

## Features

- **Video Transcription**: Transcribe YouTube videos using Whisper AI
- **Twitter Video Scraping**: Extract videos from tweets
- **Website Content Scraping**: Clean and extract text content from websites

## API Endpoints

### Transcribe YouTube Videos
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

### Extract Videos from Tweets
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

### Extract Content from Websites
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

### Health Check
**Endpoint**: `/health`
**Method**: GET

## Request Format Notes

- All endpoints accept two JSON formats:
  1. A JSON object with a `query` object containing a `url` field (preferred)
  2. A JSON object with a direct `url` field
- The URL should be a complete URL including the protocol (http:// or https://)
- The API has fallback mechanisms to handle alternative formats like arrays

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