#!/bin/bash

# Exit on error
set -e

# Variables - change these as needed
APP_NAME="gpt_transcribe"
APP_PATH="/path/to/gpt_transcribe"
DOMAIN="your_domain.com"
USER="your_username"

echo "Deploying $APP_NAME to server..."

# 1. Update system
echo "Updating system..."
sudo apt update
sudo apt upgrade -y

# 2. Install dependencies
echo "Installing dependencies..."
sudo apt install -y python3 python3-pip python3-venv nginx ffmpeg git

# 3. Clone repository (uncomment if deploying from git)
# echo "Cloning repository..."
# git clone https://github.com/yourusername/gpt_transcribe.git $APP_PATH
# cd $APP_PATH

# 4. Set up virtual environment
echo "Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Configure systemd service
echo "Configuring systemd service..."
# Update service file with correct paths and username
sed -i "s|/path/to/gpt_transcribe|$APP_PATH|g" gpt_transcribe.service
sed -i "s|your_username|$USER|g" gpt_transcribe.service

# Copy service file to systemd
sudo cp gpt_transcribe.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gpt_transcribe.service
sudo systemctl start gpt_transcribe.service

# 6. Configure Nginx
echo "Configuring Nginx..."
# Update Nginx config with correct domain
sed -i "s|your_domain.com|$DOMAIN|g" gpt_transcribe_nginx.conf

# Copy Nginx config
sudo cp gpt_transcribe_nginx.conf /etc/nginx/sites-available/$APP_NAME
sudo ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 7. Set up folder for videos
mkdir -p videos
chmod 755 videos

echo "Deployment complete! Your app is now running at http://$DOMAIN"
echo "Check status with: sudo systemctl status gpt_transcribe.service"