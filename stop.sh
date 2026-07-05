#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/bot.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        rm "$PID_FILE"
        echo "⏹️  تم إيقاف البوت (PID: $PID)"
    else
        echo "⚠️  البوت غير شغّال"
        rm -f "$PID_FILE"
    fi
else
    pkill -f "main.py" 2>/dev/null && echo "⏹️  تم إيقاف البوت" || echo "⚠️  البوت غير شغّال"
fi
