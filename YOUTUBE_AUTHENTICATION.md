# YouTube Authentication Setup

## Problem

You are seeing this error:
```
Error: 400: Download error: ERROR: [youtube] _YGZVPUziyA: Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication.
```

This happens because YouTube requires authentication to confirm the server is not a bot. This is common when:
1. The server makes too many requests to YouTube
2. YouTube detects automated access patterns
3. The IP address of the server is shared/from a datacenter

## Solution

### Option 1: Use Browser Cookies (Recommended)

The application has been updated to automatically use cookies from Chrome on the server. For this to work:

1. SSH into your server
2. Log in to YouTube in Chrome on the server:
   ```bash
   # Install Chrome if not already installed
   sudo apt update
   sudo apt install -y curl
   curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
   echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
   sudo apt update
   sudo apt install -y google-chrome-stable

   # Install X virtual framebuffer to run Chrome headlessly
   sudo apt install -y xvfb

   # Start X virtual framebuffer
   Xvfb :99 -screen 0 1024x768x16 &
   export DISPLAY=:99

   # Launch Chrome and log in to YouTube
   google-chrome --no-sandbox https://youtube.com
   ```

3. Follow prompts to log in to YouTube
4. Restart the FastAPI service:
   ```bash
   sudo systemctl restart fastapi
   ```

### Option 2: Use a Cookies File

If Option 1 doesn't work or you prefer not to install Chrome on the server:

1. On your local machine, install a browser extension to export cookies:
   - For Chrome: "Get cookies.txt" or "EditThisCookie"
   - For Firefox: "Cookie Quick Manager"

2. Go to YouTube and log in
3. Export cookies to a .txt file using the extension
4. Upload the cookies file to your server:
   ```bash
   scp cookies.txt user@your-server:/var/www/fetch_transcribe/youtube_cookies.txt
   ```

5. Update the yt-dlp configuration in `run.py`:
   ```python
   ydl_opts = {
       # ... other options ...
       'cookiefile': '/var/www/fetch_transcribe/youtube_cookies.txt',
       # Comment out the cookiesfrombrowser line
       # 'cookiesfrombrowser': ('chrome',),
   }
   ```

6. Restart the FastAPI service:
   ```bash
   sudo systemctl restart fastapi
   ```

### Option 3: Use a YouTube API Key (Alternative Solution)

For a more permanent solution, consider using the YouTube Data API:

1. Create a Google Developer account
2. Create a new project in the Google Cloud Console
3. Enable the YouTube Data API
4. Create API credentials
5. Update your application to use the YouTube API for data retrieval

## Troubleshooting

If you're still experiencing issues:

1. Check that the cookies are valid and not expired:
   ```bash
   # When using cookiesfrombrowser
   yt-dlp --list-extractors | grep -i cookie
   yt-dlp --cookies-from-browser chrome https://www.youtube.com/watch?v=dQw4w9WgXcQ --dump-headers

   # When using a cookies file
   yt-dlp --cookies /var/www/fetch_transcribe/youtube_cookies.txt https://www.youtube.com/watch?v=dQw4w9WgXcQ --dump-headers
   ```

2. Try using a VPN or proxy to access YouTube from a different IP address
3. Consider implementing a rate limiter to prevent too many requests to YouTube

## Reference

For more details, see the yt-dlp documentation:
https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp