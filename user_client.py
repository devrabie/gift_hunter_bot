"""
Pyrogram user client — إدارة حساب الفحص وحساب الشراء لـ قنص الهدايا المميزة المعاد بيعها.
"""
import asyncio
import logging
import os
import time
from pyrogram import Client
from pyrogram.enums import GiftForResaleOrder
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(BASE_DIR, "data/sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

# الثوابت الصارمة الخاصة بالحسابات
API_ID = 28420416
API_HASH = "a7ef28e693edc68e81905fccc83f7ff7"

_checker_client: Client = None
_buyer_client: Client = None
_pending: dict[int, dict] = {}

# ذاكرة تخزين مؤقتة لمعرفة حالة الحسابات بسرعة في واجهة البوت
_accounts_cache = {"checker": None, "buyer": None}

# متغيرات لحفظ الكتالوج في الذاكرة وعدم طلبه بشكل متكرر وتجنب الـ FloodWait
_cached_limited_gifts = []
_last_catalog_update = 0


def _make_client(session_name: str, phone: str = None, session_string: str = None) -> Client:
    s_string = session_string.strip() if session_string else None
    return Client(
        name=os.path.join(SESSION_DIR, session_name),
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=phone,
        session_string=s_string,
        device_model="GiftSniper Checker",
        system_version="Android 13",
        app_version="Telegram 11.12.0",
        no_updates=True
    )


def _extract_gift_name(gift) -> str | None:
    title = getattr(gift, "title", None)
    if title:
        return str(title)
    return None


def _gift_matches_name(gift_name: str | None, search: str) -> bool:
    if not gift_name:
        return False
    return search.strip().lower() in gift_name.lower()


# ─── فحص حالة الحسابات لعرضها في البوت ────────────────────────────────────────

async def get_account_status(client_type: str) -> dict | None:
    if _accounts_cache.get(client_type):
        return _accounts_cache[client_type]
        
    session_path = os.path.join(SESSION_DIR, f"account_{client_type}.session")
    if not os.path.exists(session_path) or os.path.getsize(session_path) == 0:
        return None
        
    try:
        global _checker_client, _buyer_client
        if client_type == "checker":
            if _checker_client is None: _checker_client = _make_client("account_checker")
            target_client = _checker_client
        else:
            if _buyer_client is None: _buyer_client = _make_client("account_buyer")
            target_client = _buyer_client
            
        was_connected = target_client.is_connected
        if not was_connected:
            await target_client.connect()
            
        me = await target_client.get_me()
        
        if not was_connected:
            await target_client.disconnect()
            
        info = {"name": f"{me.first_name or ''} {me.last_name or ''}".strip(), "username": me.username}
        _accounts_cache[client_type] = info
        return info
    except Exception as e:
        logger.error("Error loading %s status: %s", client_type, e)
        return None


# ─── تسجيل الدخول المباشر عن طريق الـ Session String ──────────────────────────

async def set_session_directly(bot_user_id: int, session_string: str, client_type: str = "checker") -> dict:
    session_name = f"account_{client_type}"
    
    old_session_path = os.path.join(SESSION_DIR, f"{session_name}.session")
    if os.path.exists(old_session_path):
        try: os.remove(old_session_path)
        except Exception: pass
            
    client = _make_client(session_name, session_string=session_string)
    try:
        await client.connect()
        me = await client.get_me()
        
        exported_string = await client.export_session_string()
        
        import storage
        if hasattr(storage, "save_client_session"):
            storage.save_client_session(client_type, exported_string)
        else:
            storage.set_session_string(f"signed_in_{client_type}")
            
        await client.disconnect()
        
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        _accounts_cache[client_type] = {"name": name, "username": me.username}
        return {"ok": True, "name": name, "username": me.username}
    except Exception as e:
        try: await client.disconnect()
        except Exception: pass
        logger.error("set_session_directly failed for %s: %s", client_type, e)
        return {"ok": False, "error": f"الجلسة النصية غير صالحة: {str(e)}"}


# ─── تسجيل الدخول برقم الهاتف ──────────────────────────────────────────────────

async def start_phone_login(bot_user_id: int, phone: str, client_type: str = "checker") -> dict:
    session_name = f"account_{client_type}"
    old_session_path = os.path.join(SESSION_DIR, f"{session_name}.session")
    if os.path.exists(old_session_path):
        try: os.remove(old_session_path)
        except Exception: pass

    client = _make_client(session_name, phone=phone.strip())
    
    try:
        await client.connect()
        sent_code = await client.send_code(phone.strip())
        _pending[bot_user_id] = {
            "client": client,
            "phone": phone.strip(),
            "code_hash": sent_code.phone_code_hash,
            "type": client_type
        }
        return {"ok": True}
    except Exception as e:
        try: await client.disconnect()
        except Exception: pass
        return {"ok": False, "error": str(e)}


async def complete_phone_login(bot_user_id: int, code: str) -> dict:
    data = _pending.get(bot_user_id)
    if not data:
        return {"ok": False, "error": "لا توجد جلسة نشطة. ابدأ من جديد."}
    
    client: Client = data["client"]
    client_type = data["type"]
    try:
        clean_code = code.strip().replace(" ", "")
        await client.sign_in(
            phone_number=data["phone"],
            phone_code_hash=data["code_hash"],
            phone_code=clean_code
        )
        me = await client.get_me()
        exported_string = await client.export_session_string()
        await client.disconnect()
        _pending.pop(bot_user_id, None)
        
        import storage
        if hasattr(storage, "save_client_session"):
            storage.save_client_session(client_type, exported_string)
        else:
            storage.set_session_string(f"signed_in_{client_type}")
        
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        _accounts_cache[client_type] = {"name": name, "username": me.username}
        return {"ok": True, "name": name, "username": me.username}
    except SessionPasswordNeeded:
        return {"ok": False, "need_password": True}
    except (PhoneCodeInvalid, PhoneCodeExpired):
        return {"ok": False, "error": "رمز التحقق غير صحيح أو منتهي."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def complete_2fa(bot_user_id: int, password: str) -> dict:
    data = _pending.get(bot_user_id)
    if not data:
        return {"ok": False, "error": "لا توجد جلسة نشطة."}
    
    client: Client = data["client"]
    client_type = data["type"]
    try:
        await client.check_password(password.strip())
        me = await client.get_me()
        exported_string = await client.export_session_string()
        await client.disconnect()
        _pending.pop(bot_user_id, None)
        
        import storage
        if hasattr(storage, "save_client_session"):
            storage.save_client_session(client_type, exported_string)
        else:
            storage.set_session_string(f"signed_in_{client_type}")
        
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        _accounts_cache[client_type] = {"name": name, "username": me.username}
        return {"ok": True, "name": name, "username": me.username}
    except Exception as e:
        return {"ok": False, "error": f"كلمة المرور غير صحيحة: {str(e)}"}


async def cancel_login(bot_user_id: int) -> None:
    data = _pending.pop(bot_user_id, None)
    if data:
        try: await data["client"].disconnect()
        except Exception: pass


# ─── إدارة وتهيئة الجلسات المستمرة لحساب الفحص والشراء ───────────────────────

async def initialize_all_clients() -> bool:
    global _checker_client, _buyer_client
    try:
        if _checker_client is None: _checker_client = _make_client("account_checker")
        if _buyer_client is None: _buyer_client = _make_client("account_buyer")
            
        if not _checker_client.is_connected: await _checker_client.start()
        if not _buyer_client.is_connected: await _buyer_client.start()
        return True
    except Exception as e:
        logger.error("تعذر تهيئة الحسابين معاً: %s", e)
        await close_all_clients()
        return False


async def close_all_clients():
    global _checker_client, _buyer_client
    try:
        if _checker_client and _checker_client.is_connected: await _checker_client.stop()
    except Exception: pass
    try:
        if _buyer_client and _buyer_client.is_connected: await _buyer_client.stop()
    except Exception: pass
    _checker_client = None
    _buyer_client = None


async def logout() -> None:
    await close_all_clients()
    global _accounts_cache, _cached_limited_gifts
    _accounts_cache = {"checker": None, "buyer": None}
    _cached_limited_gifts = []
    
    import storage
    storage.clear_session()
    for mode in ["checker", "buyer"]:
        p = os.path.join(SESSION_DIR, f"account_{mode}.session")
        if os.path.exists(p):
            try: os.remove(p)
            except Exception: pass


# ─── الفحص عبر حساب الـ Checker والاستخراج المعزز والشامل ───────────────────

async def get_available_gifts() -> list[dict]:
    global _checker_client, _cached_limited_gifts, _last_catalog_update
    if _checker_client is None or not _checker_client.is_connected:
        success = await initialize_all_clients()
        if not success:
            return []

    gifts_found = []
    current_time = time.time()
    
    try:
        # 1. جلب الكتالوج وتحديثه بحذر مع نظام (Timeout) لمنع التجمد
        if not _cached_limited_gifts or (current_time - _last_catalog_update > 3600):
            logger.info("🔄 جاري طلب كتالوج الهدايا من تيليجرام...")
            
            async def fetch_catalog_task():
                if hasattr(_checker_client, "get_star_gifts"):
                    return await _checker_client.get_star_gifts()
                elif hasattr(_checker_client, "get_gifts"):
                    return await _checker_client.get_gifts()
                else:
                    try:
                        from pyrogram.raw.functions.payments import GetStarGifts
                        res = await _checker_client.invoke(GetStarGifts(hash=0))
                        return getattr(res, "gifts", [])
                    except ImportError:
                        pass
                    try:
                        from pyrogram.raw.functions.payments import GetGifts
                        res = await _checker_client.invoke(GetGifts(hash=0))
                        return getattr(res, "gifts", [])
                    except ImportError:
                        return []

            try:
                catalog_gifts = await asyncio.wait_for(fetch_catalog_task(), timeout=15.0)
                logger.info("✅ استجاب السيرفر وتم جلب الكتالوج.")
            except asyncio.TimeoutError:
                logger.error("❌ انتهى وقت طلب الكتالوج (Timeout). سيرفر تيليجرام لا يستجيب حالياً.")
                return []

            new_limited = []
            for g in catalog_gifts:
                is_limited = getattr(g, "is_limited", False) or getattr(g, "limited", False)
                g_id = getattr(g, "id", None)
                if is_limited and g_id is not None:
                    new_limited.append(g_id)
            
            if new_limited:
                _cached_limited_gifts = new_limited
                _last_catalog_update = current_time
                logger.info("✅ تم تخزين %d هدية محدودة في الذاكرة لفحصها.", len(_cached_limited_gifts))

        if not _cached_limited_gifts:
            return []

        # 2. فحص سوق إعادة البيع مع التحليل المتقدم للـ JSON والسمات
        total_gifts = len(_cached_limited_gifts)
        logger.info("🚀 [وضع التطوير والفلترة العميقة] جاري تفتيش صفقات P2P المتاحة...")
        
        for index, g_id in enumerate(_cached_limited_gifts, start=1):
            try:
                async def fetch_resale_task():
                    results = []
                    async for resale_gift in _checker_client.search_gifts_for_resale(gift_id=g_id, order=GiftForResaleOrder.PRICE, limit=15):
                        results.append(resale_gift)
                    return results

                resale_items = await asyncio.wait_for(fetch_resale_task(), timeout=10.0)

                for resale_gift in resale_items:
                    resale_id = getattr(resale_gift, "id", None)
                    resale_params = getattr(resale_gift, "resale_parameters", None)
                    
                    if resale_params is None or resale_id is None:
                        continue
                        
                    # أ) استخراج بيانات الأسعار المباشرة (نجوم وتون)
                    stars = getattr(resale_params, "star_count", None)
                    ton_cents = getattr(resale_params, "toncoin_cent_count", None)
                    ton_val = (ton_cents / 1_000_000_000.0) if ton_cents else None
                    
                    # ب) استخراج الهوية الفنية وأرقام الـ Mint الفريدة
                    gift_obj = getattr(resale_gift, "gift", resale_gift)
                    title = getattr(resale_gift, "title", str(resale_id))
                    full_name = getattr(resale_gift, "name", title)
                    mint_number = getattr(resale_gift, "unique_gift_number", 0)
                    
                    # ج) استخراج بيانات الندرة والسمات الفنية للتطوير
                    model = getattr(resale_gift, "model", None)
                    rarity_obj = getattr(model, "rarity", None) if model else None
                    rarity_per_mille = getattr(rarity_obj, "per_mille", None) if rarity_obj else 9999

                    # طباعة تقرير حي تفصيلي للمطور في الـ Logs لمتابعة دقة الاستخراج والتحليل
                    logger.info("📡 [%d/%d] اللقطة: %s | النجوم: %s ⭐ | الـ TON: %s 💎 | رقم النسخة: #%s | الندرة: %s‰",
                                index, total_gifts, full_name, stars, ton_val, mint_number, rarity_per_mille)

                    gifts_found.append({
                        "id": resale_id,
                        "stars": int(stars) if stars else None,
                        "ton": ton_val,
                        "name": str(full_name),
                        "base_name": str(title),
                        "mint_number": int(mint_number),
                        "rarity": int(rarity_per_mille),
                        "link": getattr(resale_gift, "gift_address", "")
                    })
                
                # استراحة تكتيكية ثابتة بين فحص كل هدية وأخرى لحماية الحساب من الـ Flood
                await asyncio.sleep(2.0)

            except asyncio.TimeoutError:
                await asyncio.sleep(2.0)
                continue
            except Exception as e:
                logger.debug("تخطي الهدية رقم %d بسبب خطأ: %s", index, e)
                await asyncio.sleep(2.0)
                continue

        return gifts_found

    except Exception as e:
        logger.error("🚨 خطأ عام في الرادار: %s", e)
        if "429" in str(e) or "FLOOD_WAIT" in str(e):
            await asyncio.sleep(30)
        return []


async def buy_gift_to_self(gift_id: int, gift_link: str = "", use_ton: bool = False) -> dict:
    global _buyer_client
    if _buyer_client is None or not _buyer_client.is_connected:
        success = await initialize_all_clients()
        if not success:
            return {"ok": False, "error": "حساب الشراء غير متصل."}
            
    try:
        me = await _buyer_client.get_me()
        if not me:
            return {"ok": False, "error": "تعذر جلب بيانات المشتري."}
            
        link = gift_link or f"https://t.me/nft/{gift_id}"
        await _buyer_client.send_resold_gift(
            gift_link=link,
            peer=me.id,
            use_ton=use_ton
        )
        logger.info("✅ حساب الـ Buyer نفذ أمر اقتناص على الهدية رقم: %s بنجاح! (استخدام تون: %s)", gift_id, use_ton)
        return {"ok": True}
    except Exception as e:
        logger.error("❌ فشل حساب الشراء في القنص: %s", e)
        return {"ok": False, "error": str(e)}

