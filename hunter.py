import asyncio
import logging
from datetime import datetime
import storage
import user_client
from config import DEVELOPER_ID, HUNT_INTERVAL

logger = logging.getLogger(__name__)
_hunt_task, _stats, _bot_ref, _bought_ids, _cycle = None, {"found": 0, "bought": 0, "errors": 0}, None, set(), 0

def get_stats() -> dict: return _stats.copy()
def set_bot(bot) -> None: global _bot_ref; _bot_ref = bot

async def _send_notify(chat_id: int, text: str) -> None:
    if not _bot_ref:
        return

    settings = storage.get_notification_settings()

    # Notify Developer
    if settings.get("notify_developer", True):
        try:
            await _bot_ref.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to notify developer: {e}")

    # Notify Channel
    channel_id = settings.get("channel_id")
    if channel_id and settings.get("notify_channel", False):
        try:
            # channel_id string to int if needed, but python-telegram-bot handles both "@channel" and int
            await _bot_ref.send_message(chat_id=channel_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to notify channel {channel_id}: {e}")

def _is_match(gift: dict, target: dict) -> bool:
    """المطابقة الذكية والعميقة بين شروط الهدف والمواصفات الحية للهدية"""
    if target.get("type") == "named":
        search = target.get("name", "").strip().lower()
        if search not in gift.get("base_name", "").lower() and search not in gift.get("name", "").lower():
            return False

    # فحص رقم الإصدار (Mint Number)
    max_mint = target.get("max_mint")
    if max_mint:
        if gift["mint_number"] == 0 or gift["mint_number"] > max_mint:
            return False

    # فحص ندرة الموديل
    max_rarity = target.get("max_rarity")
    if max_rarity:
        if gift["rarity"] > max_rarity:
            return False

    # فحص الأسعار (يجب أن يحقق شرط واحد على الأقل من الأسعار ليتم قبول المطابقة)
    max_stars = target.get("max_stars") or target.get("max_price")
    max_ton = target.get("max_ton")

    stars_match = False
    if max_stars and max_stars > 0:
        if gift["stars"] is not None and gift["stars"] <= max_stars:
            stars_match = True

    ton_match = False
    if max_ton and max_ton > 0:
        if gift["ton"] is not None and gift["ton"] <= max_ton:
            ton_match = True

    # إذا لم يحدد المستخدم أي حدود للسعر (نادر الحدوث)، نقبلها.
    # إذا حدد أحدهما أو كلاهما، نقبلها إذا طابقت أي منهما.
    if not max_stars and not max_ton:
        return True

    if stars_match or ton_match:
        return True

    return False

async def _check_and_buy(notify_chat_id: int) -> None:
    global _cycle; _cycle += 1
    targets = storage.get_targets()
    if not targets: return

    async def process_gift(gift: dict) -> None:
        if gift["id"] in _bought_ids:
            return

        for target in targets:
            if _is_match(gift, target):
                # قفل لمنع تكرار الشراء إذا تم فحص نفس الهدية من خيوط متعددة
                if gift["id"] in _bought_ids:
                    break
                _bought_ids.add(gift["id"])

                _stats["found"] += 1
                name_display = gift["name"]
                
                prices = []
                if gift["stars"]: prices.append(f"`{gift['stars']:,}` ⭐")
                if gift["ton"]: prices.append(f"`{gift['ton']}` 💎")
                price_txt = " أو ".join(prices)

                await _send_notify(notify_chat_id, f"🎯 *لقطة لقطة مطابقة للفلاتر!*\n\n🏷 الاسم: `{name_display}`\n🔢 النسخة: `#{gift['mint_number']}`\n✨ الندرة: `{gift['rarity']}‰`\n💰 السعر: {price_txt}\n\n⚡ _جاري القنص الصاعق..._")

                if storage.is_demo_mode():
                    _stats["bought"] += 1
                    await _send_notify(notify_chat_id, f"🧪 *تم القنص الوهمي بنجاح!* (وضع التجربة)\n📥 `{name_display}` لم يتم خصم أي رصيد حقيقي.")
                    break

                max_stars = target.get("max_stars") or target.get("max_price")
                max_ton = target.get("max_ton")

                # شراء الهدية بالعملة التي طابقت الشرط الفعلي (الأولوية للنجوم إذا طابقت كليهما)
                if max_stars and max_stars > 0 and gift["stars"] is not None and gift["stars"] <= max_stars:
                    result = await user_client.buy_gift_to_self(gift["id"], stars=gift["stars"])
                elif max_ton and max_ton > 0 and gift["ton"] is not None and gift["ton"] <= max_ton:
                    result = await user_client.buy_gift_to_self(gift["id"], ton=gift["ton"])
                else:
                    # كاحتياط، إذا كانت بدون شروط أو لسبب آخر
                    if gift["stars"]:
                        result = await user_client.buy_gift_to_self(gift["id"], stars=gift["stars"])
                    elif gift["ton"]:
                         result = await user_client.buy_gift_to_self(gift["id"], ton=gift["ton"])
                    else:
                        result = {"ok": False, "error": "لم يتم العثور على سعر مناسب للهدية"}
                
                if result["ok"]:
                    _stats["bought"] += 1
                    await _send_notify(notify_chat_id, f"✅ *تم الشراء والاقتاص الفوري بنجاح!*\n📥 `{name_display}` تم حفظها في حساب الشراء.")
                else:
                    _stats["errors"] += 1
                    # إذا فشل الشراء نحذفها من _bought_ids لنعطي فرصة لشرائها مرة أخرى إذا ظهرت
                    _bought_ids.discard(gift["id"])
                    await _send_notify(notify_chat_id, f"❌ *فشل القنص الفوري*\n⚠️ السبب: `{result.get('error')}`")
                break 

    # تمرير دالة الاقتناص الفوري ليتم استدعاؤها بمجرد العثور على أي هدية
    await user_client.get_available_gifts(on_gift_found=process_gift)


async def _hunt_loop(notify_chat_id: int) -> None:
    _stats["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await user_client.initialize_all_clients()

    if not storage.get_checker_accounts() or not storage.get_buyer_account():
        await _send_notify(notify_chat_id, "⚠️ *تنبيه:* لا توجد حسابات فحص أو حساب شراء محدد. تم إيقاف المستكشف الذكي.")
        storage.set_hunting(False)
        return

    while storage.is_hunting():
        try:
            await _check_and_buy(notify_chat_id)
        except Exception as e:
            _stats["errors"] += 1
        await asyncio.sleep(HUNT_INTERVAL)

def start_hunting(bot, notify_chat_id: int) -> None:
    global _hunt_task
    set_bot(bot); storage.set_hunting(True)
    if not _hunt_task or _hunt_task.done(): _hunt_task = asyncio.create_task(_hunt_loop(notify_chat_id))

def stop_hunting() -> None:
    global _hunt_task
    storage.set_hunting(False)
    if _hunt_task: _hunt_task.cancel(); _hunt_task = None

