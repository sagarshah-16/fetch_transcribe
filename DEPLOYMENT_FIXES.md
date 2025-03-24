# Deployment Fixes

## 1. CrawlerConfig Fix for Crawl4AI Compatibility

**Issue:** The code was trying to import `CrawlerConfig` from the `crawl4ai` package, but this class doesn't exist in version 0.5.0.post4 which is installed on the server.

**Error:**
```
ImportError: cannot import name 'CrawlerConfig' from 'crawl4ai' (/var/www/fetch_transcribe/env/lib/python3.12/site-packages/crawl4ai/__init__.py). Did you mean: 'BrowserConfig'?
```

**Fix:**
- Created a custom `CrawlerConfig` class to replace the missing one
- Modified the `AsyncWebCrawler.arun()` call to handle version differences with a fallback mechanism
- Added Sentry logging for better visibility of the fallback

## 2. API Request Format Improvements

**Issue:** The API was having validation errors with certain request formats.

**Fix:**
- Added support for both request formats:
  ```json
  {"query": {"url": "https://example.com"}}
  ```
  and
  ```json
  {"url": "https://example.com"}
  ```
- Added raw/debug endpoints that bypass validation:
  - `/raw_transcribe`
  - `/raw_scrape_tweet`
  - `/raw_scrape`
  - `/debug`

## 3. Sentry Integration

**Issue:** Validation errors were not being captured in Sentry.

**Fix:**
- Added a dedicated RequestValidationError exception handler
- Enhanced error context for better Sentry reporting
- Improved logging and breadcrumbs for debugging

## Deployment Instructions

1. Pull the latest changes:
   ```bash
   cd /var/www/fetch_transcribe
   git pull
   ```

2. Update the environment if needed:
   ```bash
   source env/bin/activate
   pip install -r requirements.txt
   ```

3. Restart the service:
   ```bash
   sudo systemctl restart fastapi
   ```

4. Check the logs to ensure everything starts correctly:
   ```bash
   sudo journalctl -u fastapi -f
   ```

5. If issues persist, try the raw endpoints with the same request format:
   ```
   /raw_transcribe
   /raw_scrape_tweet
   /raw_scrape
   ```