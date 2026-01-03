#!/bin/bash
set -e

SERVER="root@152.42.245.71"
SSH_KEY="$HOME/.ssh/notespasumbot_deploy"
REPO_DIR="/root/notespasumbot"
SERVICE_NAME="notespasumbot"

echo "📦 Deploying NotesPASUMBot to server..."

# Test SSH connection
echo "🔌 Testing SSH connection..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SERVER" "echo '✅ Connected successfully'"

# Ensure git is installed
echo "📥 Checking git installation..."
ssh -i "$SSH_KEY" "$SERVER" "which git || (apt-get update && apt-get install -y git)"

# Clone or update repo
echo "🔄 Syncing repository..."
ssh -i "$SSH_KEY" "$SERVER" "
  if [ -d '$REPO_DIR' ]; then
    cd '$REPO_DIR'
    git fetch origin
    git reset --hard origin/main
    echo '✅ Repository updated'
  else
    git clone https://github.com/KuuminKochi/notespasumbot.git '$REPO_DIR'
    echo '✅ Repository cloned'
  fi
"

# Upload service-account.json if it exists locally
if [ -f "service-account.json" ]; then
  echo "🔐 Uploading service-account.json..."
  scp -i "$SSH_KEY" service-account.json "$SERVER:$REPO_DIR/"
fi

# Upload .env if it exists locally
if [ -f ".env" ]; then
  echo "🔐 Uploading .env file..."
  scp -i "$SSH_KEY" .env "$SERVER:$REPO_DIR/"
else
  echo "⚠️  Warning: .env file not found. Creating from example..."
  ssh -i "$SSH_KEY" "$SERVER" "
    cd '$REPO_DIR'
    if [ ! -f .env ]; then
      cp .env.example .env
      echo '⚠️  Please edit .env on server with actual credentials'
    fi
  "
fi

# Install dependencies
echo "📦 Installing Python dependencies (minimal version)..."
ssh -i "$SSH_KEY" "$SERVER" "
  cd '$REPO_DIR'
  which python3 || apt-get install -y python3 python3-pip
  pip3 install --upgrade pip
  pip3 install -r requirements-minimal.txt || echo '⚠️  Some packages may have failed to install'
"

# Create systemd service
echo "🔧 Setting up systemd service..."
ssh -i "$SSH_KEY" "$SERVER" "cat > /etc/systemd/system/$SERVICE_NAME.service << 'EOF'
[Unit]
Description=NotesPASUMBot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$REPO_DIR
ExecStart=/usr/bin/python3 $REPO_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF"

# Enable and start service
echo "🚀 Enabling and starting service..."
ssh -i "$SSH_KEY" "$SERVER" "
  systemctl daemon-reload
  systemctl enable $SERVICE_NAME
  systemctl restart $SERVICE_NAME
  systemctl status $SERVICE_NAME --no-pager
"

echo "✅ Deployment complete!"
echo "📊 Bot is now running and will auto-restart on server reboot"
