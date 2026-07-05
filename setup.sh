#!/bin/bash
# ═══════════════════════════════════════════════
#   بوت الهدايا — سكريبت الإعداد التلقائي
# ═══════════════════════════════════════════════
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/venv"

echo ""
echo "══════════════════════════════════"
echo "  🤖 إعداد بوت الهدايا الرقمية"
echo "══════════════════════════════════"
echo ""

# تحقق من Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 غير موجود. ثبّته أولاً:"
    echo "   apt update && apt install -y python3 python3-venv python3-pip"
    exit 1
fi

echo "✅ Python3: $(python3 --version)"
echo ""

# إنشاء البيئة الافتراضية
echo "📦 إنشاء البيئة الافتراضية..."
python3 -m venv "$VENV"

echo "📥 تثبيت المكتبات (قد يأخذ دقيقة)..."
"$VENV/bin/pip" install --upgrade pip --quiet
"$VENV/bin/pip" install -r "$DIR/requirements.txt" --quiet

echo ""
echo "══════════════════════════════════"
echo "  ✅ تم الإعداد بنجاح!"
echo "══════════════════════════════════"
echo ""
echo "📝 الخطوة التالية:"
echo "   عدّل ملف config.py وضع توكن البوت ومعرّفك"
echo ""
echo "▶️  لتشغيل البوت:"
echo "   bash $DIR/run.sh"
echo ""
