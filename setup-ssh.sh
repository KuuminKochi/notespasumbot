#!/bin/bash
# Helper script to add SSH key to remote server
# Run this once to set up key-based authentication

SERVER="root@152.42.245.71"
SSH_KEY="$HOME/.ssh/notespasumbot_deploy"
PUB_KEY="$HOME/.ssh/notespasumbot_deploy.pub"

echo "🔐 Setting up SSH key-based authentication for $SERVER"
echo ""
echo "⚠️  You'll be asked for your server password this one time only"
echo ""

# Create .ssh directory and add key
ssh-copy-copy() {
  ssh-copy-id -i "$PUB_KEY" -o StrictHostKeyChecking=no "$SERVER" 2>/dev/null
  if [ $? -eq 0 ]; then
    return 0
  fi

  # Fallback method if ssh-copy-id is not available
  echo "📋 Copying SSH key using manual method..."
  PUB_KEY_CONTENT=$(cat "$PUB_KEY")
  ssh -o StrictHostKeyChecking=no "$SERVER" "
    mkdir -p ~/.ssh
    chmod 700 ~/.ssh
    echo '$PUB_KEY_CONTENT' >> ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys
    echo '✅ SSH key added successfully'
  "
}

# Try to add the key
ssh-copy-copy

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ SSH key setup complete!"
  echo "🚀 You can now run './deploy.sh' to deploy without entering a password"
else
  echo ""
  echo "❌ Failed to add SSH key automatically"
  echo "📝 Please add this key manually to ~/.ssh/authorized_keys on the server:"
  echo ""
  cat "$PUB_KEY"
  echo ""
fi
