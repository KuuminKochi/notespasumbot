#!/bin/bash
# Infinite loop wrapper to keep the bot alive
# This provides an extra layer of crash resistance above systemd

echo "🔄 Starting Bot Loop..."

while true; do
    echo "🚀 Launching Python process..."
    
    # Run the bot using virtual environment
    if [ -f "venv/bin/python" ]; then
        ./venv/bin/python main.py
    else
        echo "⚠️  venv not found! Falling back to system python..."
        python3 main.py
    fi
    
    EXIT_CODE=$?
    echo "⚠️  Bot exited with code $EXIT_CODE"
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Clean exit. Restarting in 1s..."
        sleep 1
    else
        echo "❌ Crash detected! Restarting in 5s..."
        sleep 5
    fi
done
