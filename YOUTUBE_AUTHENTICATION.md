# YouTube Authentication Setup

## Problem

You are seeing this error:
```
ERROR: [youtube] Sign in to confirm you're not a bot
```

OR

```
ERROR: could not find chrome cookies database
```

These errors happen because YouTube requires authentication to confirm the server is not a bot. This is common when:
1. The server makes too many requests to YouTube
2. YouTube detects automated access patterns
3. The IP address of the server is shared/from a datacenter

## Quick Solution (Recommended)

The simplest way to fix this issue is to upload a YouTube cookies file to the server:

1. On your local computer (not the server), install a browser extension to export cookies:
   - For Chrome: "Get cookies.txt" or "EditThisCookie"
   - For Firefox: "Cookie Quick Manager"

2. Go to YouTube in your browser and log in (make sure you're logged in)

3. Use the extension to export cookies to a .txt file (make sure to include YouTube cookies)

4. Upload the cookies file to the server:
   ```bash
   # Replace with your actual server details
   scp cookies.txt user@your-server:/var/www/fetch_transcribe/youtube_cookies.txt
   ```

5. Make sure the cookies file is readable by the application:
   ```bash
   sudo chown www-data:www-data /var/www/fetch_transcribe/youtube_cookies.txt
   sudo chmod 644 /var/www/fetch_transcribe/youtube_cookies.txt
   ```

6. Restart the service:
   ```bash
   sudo systemctl restart fastapi
   ```

The application will automatically detect and use this cookies file when downloading from YouTube.

## Alternative Solutions

### 1. Install Chrome and Log in on the Server

If you have GUI access to the server or can run a virtual display:

```bash
# Install Chrome
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

### 2. Use a YouTube API Key

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
   # Test if your cookies file works
   yt-dlp --cookies /var/www/fetch_transcribe/youtube_cookies.txt https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

2. Make sure the cookies file contains YouTube cookies
3. Try logging in again and exporting fresh cookies
4. Check file permissions on the cookies file
5. Try using a different browser to export cookies

## Reference

For more details, see the yt-dlp documentation:
https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp