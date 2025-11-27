#!/bin/bash
set -e

echo "Updating package list..."
pacman -Sy --noconfirm

echo "Installing dependencies..."
pacman -S --noconfirm git python python-pip

TARGET_DIR="/opt/paintbooth"

echo "Setting up repository at $TARGET_DIR..."
if [ -d "$TARGET_DIR" ]; then
    echo "Directory exists, pulling latest changes..."
    cd "$TARGET_DIR"
    git pull
else
    echo "Cloning repository..."
    git clone https://github.com/davidjrb/paintbooth.git "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

echo "Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

echo "Installing Python requirements..."
./venv/bin/pip install -r requirements.txt

echo "Creating systemd service..."
cat <<EOF > /etc/systemd/system/paintbooth.service
[Unit]
Description=Paint Booth Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=$TARGET_DIR
ExecStart=$TARGET_DIR/venv/bin/python3 $TARGET_DIR/paintbooth.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "Enabling and starting service..."
systemctl daemon-reload
systemctl enable paintbooth
systemctl restart paintbooth

echo "Deployment complete. Service status:"
systemctl status paintbooth --no-pager
