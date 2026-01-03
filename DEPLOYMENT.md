# Deployment Guide for NotesPASUMBot

## Setup (One-Time Only)

### Step 1: Set up SSH Key Authentication

Run the setup script to add your SSH key to the server:

```bash
./setup-ssh.sh
```

You'll be prompted for your server password **one time only**. This sets up key-based authentication so you don't need passwords for future deployments.

### Step 2: Initial Deployment

Run the full deployment script:

```bash
./deploy.sh
```

This will:
- Clone/update the repository on the server
- Upload `service-account.json` and `.env` files securely
- Install Python dependencies
- Create a systemd service for the bot
- Start the bot service
- Enable auto-restart on server reboot

### Step 3: Configure Environment (if needed)

After deployment, you may need to edit the `.env` file on the server:

```bash
ssh -i ~/.ssh/notespasumbot_deploy root@152.42.245.71
nano /root/notespasumbot/.env
```

Update the values with your actual credentials:
- `API_KEY`: Your Telegram bot token
- `NOTES_PASUM`: Your group chat ID
- `ADMIN_NOTES`: Admin group chat ID
- `DEEPSEEK_API_KEY`: Deepseek API key
- `FIREBASE_CREDENTIALS`: service-account.json (already uploaded)

Restart the service after editing:

```bash
systemctl restart notespasumbot
```

## Ongoing Updates

### Quick Update (Code Changes Only)

For code changes, use the update script:

```bash
./update.sh
```

This pulls latest changes and restarts the bot without re-uploading config files.

### Full Deployment (Config Changes)

If you've changed `.env` or `service-account.json`, run:

```bash
./deploy.sh
```

This will upload updated config files and restart the service.

## Service Management

### Check Bot Status

```bash
ssh -i ~/.ssh/notespasumbot_deploy root@152.42.245.71 "systemctl status notespasumbot"
```

### View Bot Logs

```bash
ssh -i ~/.ssh/notespasumbot_deploy root@152.42.245.71 "journalctl -u notespasumbot -f"
```

### Restart Bot Manually

```bash
ssh -i ~/.ssh/notespasumbot_deploy root@152.42.245.71 "systemctl restart notespasumbot"
```

### Stop Bot

```bash
ssh -i ~/.ssh/notespasumbot_deploy root@152.42.245.71 "systemctl stop notespasumbot"
```

## Auto-Restart Configuration

The bot is configured to automatically restart on:
- System reboot (systemd `WantedBy=multi-user.target`)
- Bot crashes (systemd `Restart=always`)
- 10 seconds after failure (systemd `RestartSec=10`)

Logs are automatically logged to systemd journal.

## Files

### Local Files
- `deploy.sh` - Full deployment script
- `update.sh` - Quick update script
- `setup-ssh.sh` - SSH key setup script
- `service-account.json` - Firebase credentials (local only)
- `.env` - Environment variables (local only)

### Remote Files
- `/root/notespasumbot/` - Bot directory
- `/root/notespasumbot/service-account.json` - Firebase credentials
- `/root/notespasumbot/.env` - Environment variables
- `/etc/systemd/system/notespasumbot.service` - Systemd service file

## Troubleshooting

### Permission Denied

If you get permission errors, ensure the `.env` and `service-account.json` files have correct permissions:

```bash
ssh -i ~/.ssh/notespasumbot_deploy root@152.42.245.71 "cd /root/notespasumbot && chmod 600 .env service-account.json"
```

### Bot Not Starting

Check the service logs:

```bash
ssh -i ~/.ssh/notespasumbot_deploy root@152.42.245.71 "journalctl -u notespasumbot -n 50 --no-pager"
```

Common issues:
- Missing API keys in `.env`
- Python dependencies not installed
- Firebase credentials file missing or invalid

### SSH Connection Issues

Test SSH connection:

```bash
ssh -i ~/.ssh/notespasumbot_deploy root@152.42.245.71
```

If this fails, re-run:

```bash
./setup-ssh.sh
```

## Security Notes

- 🔐 SSH keys are used instead of passwords (more secure)
- 🔐 `service-account.json` is never committed to git
- 🔐 `.env` file contains sensitive credentials
- 🔐 Both config files are set to mode 600 on server
- 🔐 Bot runs as root (consider creating a dedicated user for production)

## Server Information

- **Host**: 152.42.245.71
- **User**: root
- **SSH Key**: ~/.ssh/notespasumbot_deploy
- **Bot Directory**: /root/notespasumbot
- **Service**: notespasumbot
