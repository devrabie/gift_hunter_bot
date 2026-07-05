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

_clients_pool: dict[int, Client] = {}  # key: acc_id
_pending: dict[int, dict] = {}

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


# ─── تسجيل الدخول المباشر عن طريق الـ Session String ──────────────────────────

async def set_session_directly(bot_user_id: int, session_string: str) -> dict:
    session_name = f"temp_{bot_user_id}_{int(time.time())}"
    client = _make_client(session_name, session_string=session_string)
    try:
        await client.connect()
        me = await client.get_me()
        
        exported_string = await client.export_session_string()
        
        import storage
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        storage.add_account_to_pool(exported_string, me.id, name, me.username)
            
        await client.disconnect()
        
        # التنظيف
        temp_path = os.path.join(SESSION_DIR, f"{session_name}.session")
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return {"ok": True, "name": name, "username": me.username}
    except Exception as e:
        try: await client.disconnect()
        except Exception: pass
        logger.error("set_session_directly failed: %s", e)
        return {"ok": False, "error": f"الجلسة النصية غير صالحة: {str(e)}"}


# ─── تسجيل الدخول برقم الهاتف ──────────────────────────────────────────────────

async def start_phone_login(bot_user_id: int, phone: str) -> dict:
    session_name = f"temp_{bot_user_id}"
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
            "code_hash": sent_code.phone_code_hash
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
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        storage.add_account_to_pool(exported_string, me.id, name, me.username, data["phone"])

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
    try:
        await client.check_password(password.strip())
        me = await client.get_me()
        exported_string = await client.export_session_string()
        await client.disconnect()
        _pending.pop(bot_user_id, None)
        
        import storage
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        storage.add_account_to_pool(exported_string, me.id, name, me.username, data["phone"])

        return {"ok": True, "name": name, "username": me.username}
    except Exception as e:
        return {"ok": False, "error": f"كلمة المرور غير صحيحة: {str(e)}"}


async def cancel_login(bot_user_id: int) -> None:
    data = _pending.pop(bot_user_id, None)
    if data:
        try:
            client = data["client"]
            session_name = client.name
            await client.disconnect()
            temp_path = f"{session_name}.session"
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception: pass


async def logout() -> None:
    await close_all_clients()
    global _cached_limited_gifts
    _cached_limited_gifts = []
    
    import storage
    pool = storage.get_account_pool()
    storage.clear_all_accounts()

    # حذف ملفات الجلسات من المجلد
    for acc in pool:
        p = os.path.join(SESSION_DIR, f"pool_{acc['id']}.session")
        if os.path.exists(p):
            try: os.remove(p)
            except Exception: pass

    # للملفات القديمة
    for mode in ["checker", "buyer"]:
        p = os.path.join(SESSION_DIR, f"account_{mode}.session")
        if os.path.exists(p):
            try: os.remove(p)
            except Exception: pass

# ─── إدارة وتهيئة الجلسات المستمرة لحساب الفحص والشراء ───────────────────────

async def initialize_all_clients() -> bool:
    global _clients_pool
    import storage

    # تحديد الحسابات التي يجب تشغيلها
    required_ids = storage.get_load().get("checker_ids", [])
    buyer_id = storage.get_buyer_account()
    if buyer_id:
        required_ids.append(buyer_id["id"])

    required_ids = list(set(required_ids))

    pool_accs = storage.get_account_pool()
    pool_dict = {a["id"]: a for a in pool_accs}

    # تشغيل الحسابات المطلوبة
    all_ok = True
    for req_id in required_ids:
        if req_id not in _clients_pool:
            if req_id not in pool_dict: continue
            acc_data = pool_dict[req_id]
            c = _make_client(f"pool_{req_id}", session_string=acc_data.get("session_string"))
            try:
                await c.start()
                _clients_pool[req_id] = c
            except Exception as e:
                logger.error("تعذر تشغيل الحساب %s: %s", req_id, e)
                all_ok = False
        else:
            if not _clients_pool[req_id].is_connected:
                try:
                    await _clients_pool[req_id].start()
                except Exception as e:
                    logger.error("تعذر تشغيل الحساب %s: %s", req_id, e)
                    all_ok = False

    # إيقاف الحسابات غير المطلوبة
    to_remove = []
    for cid, c in _clients_pool.items():
        if cid not in required_ids:
            try: await c.stop()
            except: pass
            to_remove.append(cid)
    for cid in to_remove:
        del _clients_pool[cid]

    return all_ok


async def close_all_clients():
    global _clients_pool
    for cid, c in _clients_pool.items():
        try:
            if c.is_connected: await c.stop()
        except: pass
    _clients_pool.clear()


# ─── الفحص عبر حسابات الفحص المتزامنة ───────────────────

async def _fetch_resale_for_gift(client: Client, g_id: int) -> list[dict]:
    gifts_found = []
    try:
        async def fetch_resale_task():
            results = []
            async for resale_gift in client.search_gifts_for_resale(gift_id=g_id, order=GiftForResaleOrder.PRICE, limit=15):
                results.append(resale_gift)
            return results

        resale_items = await asyncio.wait_for(fetch_resale_task(), timeout=10.0)

        for resale_gift in resale_items:
            resale_id = getattr(resale_gift, "id", None)
            resale_params = getattr(resale_gift, "resale_parameters", None)

            if resale_params is None or resale_id is None:
                continue

            stars = getattr(resale_params, "star_count", None)
            ton_cents = getattr(resale_params, "toncoin_cent_count", None)
            ton_val = (ton_cents / 1_000_000_000.0) if ton_cents else None

            gift_obj = getattr(resale_gift, "gift", resale_gift)
            title = getattr(resale_gift, "title", str(resale_id))
            full_name = getattr(resale_gift, "name", title)
            mint_number = getattr(resale_gift, "unique_gift_number", 0)

            model = getattr(resale_gift, "model", None)
            rarity_obj = getattr(model, "rarity", None) if model else None
            rarity_per_mille = getattr(rarity_obj, "per_mille", None) if rarity_obj else 9999

            logger.info("📡 اللقطة: %s | النجوم: %s ⭐ | الـ TON: %s 💎 | رقم النسخة: #%s | الندرة: %s‰",
                        full_name, stars, ton_val, mint_number, rarity_per_mille)

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
    except Exception as e:
        pass

    # حماية من الحظر
    await asyncio.sleep(2.0)
    return gifts_found

async def get_available_gifts() -> list[dict]:
    global _cached_limited_gifts, _last_catalog_update, _clients_pool
    import storage

    checker_accs = storage.get_checker_accounts()
    if not checker_accs:
        logger.warning("لا توجد حسابات فحص محددة.")
        return []

    active_checkers = [c for cid, c in _clients_pool.items() if any(a["id"] == cid for a in checker_accs) and c.is_connected]
    if not active_checkers:
        await initialize_all_clients()
        active_checkers = [c for cid, c in _clients_pool.items() if any(a["id"] == cid for a in checker_accs) and c.is_connected]
        if not active_checkers:
            return []

    gifts_found = []
    current_time = time.time()
    
    try:
        # جلب الكتالوج من الحساب الأول المتاح
        primary_client = active_checkers[0]
        if not _cached_limited_gifts or (current_time - _last_catalog_update > 3600):
            logger.info("🔄 جاري طلب كتالوج الهدايا من تيليجرام...")
            
            async def fetch_catalog_task():
                if hasattr(primary_client, "get_star_gifts"):
                    return await primary_client.get_star_gifts()
                elif hasattr(primary_client, "get_gifts"):
                    return await primary_client.get_gifts()
                else:
                    try:
                        from pyrogram.raw.functions.payments import GetStarGifts
                        res = await primary_client.invoke(GetStarGifts(hash=0))
                        return getattr(res, "gifts", [])
                    except ImportError:
                        pass
                    try:
                        from pyrogram.raw.functions.payments import GetGifts
                        res = await primary_client.invoke(GetGifts(hash=0))
                        return getattr(res, "gifts", [])
                    except ImportError:
                        return []

            try:
                catalog_gifts = await asyncio.wait_for(fetch_catalog_task(), timeout=15.0)
                logger.info("✅ استجاب السيرفر وتم جلب الكتالوج.")
            except asyncio.TimeoutError:
                logger.error("❌ انتهى وقت طلب الكتالوج (Timeout).")
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

        # الفحص المتزامن بين حسابات الفحص
        total_gifts = len(_cached_limited_gifts)
        logger.info("🚀 جاري الفحص المتزامن باستخدام %d حساب/حسابات...", len(active_checkers))
        
        # توزيع الهدايا على الحسابات
        # بدلاً من إطلاق جميع الطلبات مرة واحدة (DDoS)،
        # نقوم بتقسيم الهدايا بحيث يعالج كل حساب حصته بشكل متسلسل
        client_gift_lists = {cid: [] for cid in [c.name for c in active_checkers]}
        for i, g_id in enumerate(_cached_limited_gifts):
            client = active_checkers[i % len(active_checkers)]
            client_gift_lists[client.name].append((client, g_id))

        async def run_client_sequential(c_name, items):
            client_results = []
            for client, g_id in items:
                res = await _fetch_resale_for_gift(client, g_id)
                client_results.extend(res)
            return client_results

        gather_tasks = []
        for c_name, items in client_gift_lists.items():
            if items:
                gather_tasks.append(run_client_sequential(c_name, items))

        # تشغيل الحسابات بشكل متزامن
        results = await asyncio.gather(*gather_tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                gifts_found.extend(res)

        return gifts_found

    except Exception as e:
        logger.error("🚨 خطأ عام في الرادار: %s", e)
        return []


async def buy_gift_to_self(gift_id: int, gift_link: str = "", use_ton: bool = False) -> dict:
    global _clients_pool
    import storage

    buyer_acc = storage.get_buyer_account()
    if not buyer_acc:
        return {"ok": False, "error": "لا يوجد حساب شراء محدد."}

    buyer_id = buyer_acc["id"]
    client = _clients_pool.get(buyer_id)
    if not client or not client.is_connected:
        await initialize_all_clients()
        client = _clients_pool.get(buyer_id)
        if not client or not client.is_connected:
            return {"ok": False, "error": "حساب الشراء غير متصل."}
            
    try:
        me = await client.get_me()
        if not me:
            return {"ok": False, "error": "تعذر جلب بيانات المشتري."}
            
        link = gift_link or f"https://t.me/nft/{gift_id}"
        await client.send_resold_gift(
            gift_link=link,
            peer=me.id,
            use_ton=use_ton
        )
        logger.info("✅ حساب الشراء نفذ أمر اقتناص على الهدية رقم: %s بنجاح! (استخدام تون: %s)", gift_id, use_ton)
        return {"ok": True}
    except Exception as e:
        logger.error("❌ فشل حساب الشراء في القنص: %s", e)
        return {"ok": False, "error": str(e)}

