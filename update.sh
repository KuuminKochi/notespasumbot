#!/bin/bash
# Quick update script - just pull latest changes and restart service

SERVER="root@152.42.245.71"
SSH_KEY="$HOME/.ssh/notespasumbot_deploy"
REPO_DIR="/root/notespasumbot"
SERVICE_NAME="notespasumbot"

echo "🔄 Updating NotesPASUMBot..."

ssh -i "$SSH_KEY" "$SERVER" "
  cd '$REPO_DIR'
  git fetch origin
  git reset --hard origin/main
  
  # Ensure venv exists
  if [ ! -d 'venv' ]; then
    python3 -m venv venv
  fi
  
  ./venv/bin/pip install -r requirements-minimal.txt
  systemctl restart '$SERVICE_NAME'
  systemctl status '$SERVICE_NAME' --no-pager
"

echo "✅ Update complete!"
