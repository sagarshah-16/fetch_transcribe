# Server Setup for Transcription Service

This document provides instructions for setting up and maintaining the transcription service on your server.

## Directory Permissions

The application needs write access to the downloads directory. Follow these steps:

```bash
# SSH into your server
ssh ubuntu@your-server-ip

# Navigate to the application directory
cd /var/www/fetch_transcribe

# Create the downloads directory if it doesn't exist
mkdir -p downloads

# Set proper permissions (allow web server to write)
sudo chown -R www-data:www-data downloads
sudo chmod 775 downloads

# If you're running the app as another user, adjust permissions accordingly
# For example, if running as ubuntu user:
# sudo chown -R ubuntu:www-data downloads
```

## YouTube Authentication

To handle YouTube authentication, you need to upload cookies:

1. From your local computer, export YouTube cookies using a browser extension
2. Upload the cookies file to your server:
   ```bash
   scp cookies.txt ubuntu@your-server-ip:/var/www/fetch_transcribe/youtube_cookies.txt
   ```
3. Set proper permissions:
   ```bash
   sudo chown www-data:www-data /var/www/fetch_transcribe/youtube_cookies.txt
   sudo chmod 644 /var/www/fetch_transcribe/youtube_cookies.txt
   ```

## Deploying Updates

After making changes, deploy them to your server:

```bash
# SSH into your server
ssh ubuntu@your-server-ip

# Navigate to the application directory
cd /var/www/fetch_transcribe

# Pull the latest changes
git pull

# Restart the service
sudo systemctl restart fastapi

# Check the logs to verify everything is working
sudo journalctl -u fastapi -f
```

## Logging and Debugging

To troubleshoot issues:

```bash
# View real-time logs
sudo journalctl -u fastapi -f

# Check error logs
sudo tail -f /var/log/syslog | grep fastapi

# Check disk space for downloads
df -h /var/www/fetch_transcribe/downloads
```

## Memory and CPU Usage

The Whisper model requires significant memory. If you're experiencing memory issues:

```bash
# Check memory usage
free -h

# Check CPU load
top

# If necessary, add swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Checking Sentry Integration

Verify that Sentry is working correctly:

```bash
# Check if SENTRY_DSN is set in your environment
grep SENTRY_DSN /var/www/fetch_transcribe/.env

# Test Sentry integration
cd /var/www/fetch_transcribe
python3 -c "import sentry_sdk; sentry_sdk.init('$SENTRY_DSN'); sentry_sdk.capture_message('Test message from server');"
```

Check your Sentry dashboard to confirm the test message is received.