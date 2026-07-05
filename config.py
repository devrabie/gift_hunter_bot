import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env المخفي
load_dotenv()

# ═══════════════════════════════════════════════
#   ⚙️  الإعدادات المستدعاة من متغيرات البيئة
# ═══════════════════════════════════════════════

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# جلب المعرف وتحويله إلى رقم (int)
DEVELOPER_ID_STR: str = os.getenv("DEVELOPER_ID", "0")
DEVELOPER_ID: int = int(DEVELOPER_ID_STR) if DEVELOPER_ID_STR.isdigit() else 0

# جلب بيانات الـ API
TELEGRAM_API_ID_STR: str = os.getenv("TELEGRAM_API_ID", "0")
TELEGRAM_API_ID: int = int(TELEGRAM_API_ID_STR) if TELEGRAM_API_ID_STR.isdigit() else 0
TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")

# ═══════════════════════════════════════════════
#   ⚙️  إعدادات النظام — لا تعدّل هذا القسم
# ═══════════════════════════════════════════════
DATA_FILE: str = "data/data.json"
HUNT_INTERVAL: int = 20

# التحقق من وجود البيانات الأساسية لمنع تشغيل البوت بخطأ
if not BOT_TOKEN:
    raise ValueError("❌ خطأ: لم يتم العثور على BOT_TOKEN في ملف .env")

if DEVELOPER_ID == 0:
    raise ValueError("❌ خطأ: لم يتم العثور على DEVELOPER_ID في ملف .env")

