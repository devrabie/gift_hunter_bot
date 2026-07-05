#!/bin/bash
# ═══════════════════════════════════════════════
#   بوت الهدايا — سكريبت التشغيل
# ═══════════════════════════════════════════════

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/venv"
LOG="$DIR/bot.log"
PID_FILE="$DIR/bot.pid"

if [ ! -f "$VENV/bin/python" ]; then
    echo "❌ البيئة غير مثبّتة. شغّل أولاً:"
    echo "   bash $DIR/setup.sh"
    exit 1
fi

# أوقف النسخة القديمة إن وُجدت
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⏹️  إيقاف النسخة القديمة (PID: $OLD_PID)..."
        kill "$OLD_PID"
        sleep 1
    fi
fi

echo "🚀 تشغيل البوت..."
nohup "$VENV/bin/python" "$DIR/main.py" >> "$LOG" 2>&1 &
echo $! > "$PID_FILE"

echo "✅ البوت يعمل — PID: $(cat $PID_FILE)"
echo "📋 اللوق: tail -f $LOG"
