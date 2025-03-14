# GPT Transcribe API

A multi-purpose API for transcribing YouTube videos, scraping Twitter/X videos, and extracting clean content from websites.

## Features

- **Video Transcription**: Transcribe YouTube videos using Whisper AI
- **Twitter Video Scraping**: Extract videos from tweets
- **Website Content Scraping**: Clean and extract text content from websites

## API Endpoints

- `/transcribe`: Transcribe YouTube videos
- `/scrape_tweet`: Extract videos from tweets
- `/scrape`: Extract and clean content from websites
- `/health`: Health check endpoint

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