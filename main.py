import logging
import sys
import time
import uuid
import telegram

from telegram import Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters)
from telegram.request import HTTPXRequest

import hunter
import storage
import user_client
from config import BOT_TOKEN, DEVELOPER_ID
from keyboards import (account_kb, admins_kb, back_main_kb, back_targets_kb, back_builder_kb, login_cancel_kb, main_menu_kb, targets_menu_kb, target_builder_kb)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

_session: dict[int, dict] = {}

if not hasattr(storage, "is_demo_mode"):
    storage._demo_mode_active = False
    storage.is_demo_mode = lambda: storage._demo_mode_active
    storage.set_demo_mode = lambda val: setattr(storage, "_demo_mode_active", val)


def _guard(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not storage.is_authorized(user.id):
            if update.callback_query: await update.callback_query.answer("⛔ غير مصرح لك.", show_alert=True)
            return
        await handler(update, context)
    wrapper.__name__ = handler.__name__
    return wrapper


async def _send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    hunting = storage.is_hunting()
    targets = storage.get_targets()
    demo_mode = storage.is_demo_mode()
    checker_info = await user_client.get_account_status("checker")
    buyer_info = await user_client.get_account_status("buyer")
    has_both = bool(checker_info and buyer_info)
    
    status_icon = "🟢" if hunting else "🔴"
    status_txt = "يعمل المستكشف الذكي" if hunting else "متوقف"
    if hunting and demo_mode:
        status_txt = "يعمل (وضع تجربة وهمي 🧪)"

    account_txt = "✅ معزولة ومربوطة بالكامل" if has_both else "❌ غير مكتملة (يرجى ربط الحسابين)"

    text = f"🤖 *بوت صيد الـ P2P المتقدم*\n\n{status_icon} الحالة: {status_txt}\n👤 الحسابات: {account_txt}\n🎯 الأهداف المضافة: `{len(targets)}`"
    kb = main_menu_kb(hunting, has_both, targets, demo_mode)
    
    if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    elif update.effective_message: await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not storage.is_authorized(update.effective_user.id): return
    await _send_main_menu(update, context)


async def cb_back_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    uid = update.effective_user.id
    await user_client.cancel_login(uid)
    _session.pop(uid, None)
    await _send_main_menu(update, context)


@_guard
async def cb_toggle_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    current = storage.is_demo_mode()
    storage.set_demo_mode(not current)
    await q.answer(f"🧪 تم {'تفعيل' if not current else 'تعطيل'} وضع التجربة الوهمي!", show_alert=True)
    await _send_main_menu(update, context)


@_guard
async def cb_menu_targets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    targets = storage.get_targets()
    await update.callback_query.edit_message_text("🎯 *إدارة فلاتر الصيد المتقدمة*\n\n_اختر هدفاً لحذفه أو أضف شروطاً جديدة:_", reply_markup=targets_menu_kb(targets), parse_mode="Markdown")


@_guard
async def cb_add_target_any(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    uid = update.effective_user.id
    _session[uid] = {"draft": {"id": str(uuid.uuid4())[:8], "type": "any", "name": "أي هدية مميزة"}}
    await cb_tb_show_builder(update, context)


@_guard
async def cb_add_target_named(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    uid = update.effective_user.id
    _session[uid] = {"awaiting_draft_name": True}
    await update.callback_query.edit_message_text("🔍 *أرسل اسم الهدية بالضبط (مثال: PoolFloat):*", reply_markup=back_targets_kb(), parse_mode="Markdown")


@_guard
async def cb_del_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    t_id = update.callback_query.data.replace("del_target_", "")
    storage.remove_target_by_id(t_id)
    targets = storage.get_targets()
    try:
        await update.callback_query.edit_message_text("🎯 *إدارة فلاتر الصيد المتقدمة*\n\n_اختر هدفاً لحذفه أو أضف شروطاً جديدة:_", reply_markup=targets_menu_kb(targets), parse_mode="Markdown")
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        else:
            raise e


# ─── باني الأهداف (Target Builder) ───
@_guard
async def cb_tb_show_builder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query: await update.callback_query.answer()
    uid = update.effective_user.id
    draft = _session.get(uid, {}).get("draft")
    if not draft: return await cb_menu_targets(update, context)
    
    text = f"🛠 *إعدادات الفلتر لـ: {draft['name']}*\n\n_اختر الشروط الاختيارية (يمكنك ترك بعضها فارغاً):_"
    kb = target_builder_kb(draft)
    if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    else: await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


@_guard
async def cb_tb_set_stars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    _session[update.effective_user.id]["awaiting_tb"] = "max_stars"
    await update.callback_query.edit_message_text("⭐ أرسل الحد الأقصى للسعر بالنجوم (أرقام فقط):", reply_markup=back_builder_kb())


@_guard
async def cb_tb_set_ton(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    _session[update.effective_user.id]["awaiting_tb"] = "max_ton"
    await update.callback_query.edit_message_text("💎 أرسل الحد الأقصى للسعر بعُملة TON (مثال: `4.5`):", reply_markup=back_builder_kb())


@_guard
async def cb_tb_set_mint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    _session[update.effective_user.id]["awaiting_tb"] = "max_mint"
    await update.callback_query.edit_message_text("🔢 أرسل أقصى رقم للنسخة (مثال: `1000` لقنص الأرقام الثلاثية والثنائية):", reply_markup=back_builder_kb())


@_guard
async def cb_tb_set_rarity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    _session[update.effective_user.id]["awaiting_tb"] = "max_rarity"
    await update.callback_query.edit_message_text("✨ أرسل أقصى نسبة ندرة بالألف (مثال: `15` يعني يشتري ندرة 15‰ أو أندر):", reply_markup=back_builder_kb())


@_guard
async def cb_tb_save_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    uid = update.effective_user.id
    draft = _session.get(uid, {}).get("draft")
    
    if draft:
        t_type = draft.get("type", "any")
        t_name = draft.get("name", "any")
        max_stars = draft.get("max_stars", 999999)

        try:
            storage.add_target(
                t_type, 
                max_stars, 
                t_name, 
                max_ton=draft.get("max_ton"), 
                max_mint=draft.get("max_mint"), 
                max_rarity=draft.get("max_rarity"),
                t_id=draft.get("id")
            )
        except TypeError:
            storage.add_target(t_type, max_stars, t_name)
            targets = storage.get_targets()
            if targets:
                last_target = targets[-1]
                last_target["id"] = draft.get("id")
                last_target["max_ton"] = draft.get("max_ton")
                last_target["max_mint"] = draft.get("max_mint")
                last_target["max_rarity"] = draft.get("max_rarity")

    _session.pop(uid, None)
    await cb_menu_targets(update, context)


@_guard
async def cb_start_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    hunter.start_hunting(context.bot, DEVELOPER_ID)
    await _send_main_menu(update, context)


@_guard
async def cb_stop_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    hunter.stop_hunting()
    await _send_main_menu(update, context)


@_guard
async def cb_menu_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    s = hunter.get_stats()
    await q.edit_message_text(
        f"📊 *الإحصائيات سوق إعادة البيع*\n\n"
        f"🎁 هدايا تم فحصها: {s['found']}\n"
        f"✅ صفقات تم اقتناصها: {s['bought']}\n"
        f"❌ أخطاء المعالجة: {s['errors']}\n"
        f"🕐 تاريخ البدء: {s.get('started_at') or '—'}",
        reply_markup=back_main_kb(),
        parse_mode="Markdown"
    )

# ─── Account Login Handlers ───
@_guard
async def cb_menu_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    uid = update.effective_user.id
    _session.pop(uid, None)

    checker_info = await user_client.get_account_status("checker")
    buyer_info = await user_client.get_account_status("buyer")

    has_any = bool(checker_info or buyer_info)
    has_both = bool(checker_info and buyer_info)

    def format_acc(info, title):
        if info:
            uname = f" (@{info['username']})" if info.get("username") else ""
            return f"✅ {title}: *{info['name']}*{uname}"
        return f"❌ {title}: غير مربوط"

    c_str = format_acc(checker_info, "حساب الفحص (Checker)")
    b_str = format_acc(buyer_info, "حساب الشراء الأساسي (Buyer)")

    guide = "\n_يرجى ربط كلا الحسابين ليعمل البوت بشكل صحيح._" if not has_both else ""

    await update.callback_query.edit_message_text(
        f"👤 *إدارة الحسابات المعزولة*\n\n{c_str}\n{b_str}\n{guide}",
        reply_markup=account_kb(has_any, True), parse_mode="Markdown"
    )

@_guard
async def cb_login_phone_checker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    _session[update.effective_user.id] = {"awaiting_phone": True, "type": "checker"}
    await update.callback_query.edit_message_text("📱 *ربط حساب الفحص (Checker)*\n\nأرسل رقم الهاتف (مثال: `+967771234567`):", reply_markup=login_cancel_kb(), parse_mode="Markdown")

@_guard
async def cb_login_phone_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    _session[update.effective_user.id] = {"awaiting_phone": True, "type": "buyer"}
    await update.callback_query.edit_message_text("📱 *ربط حساب الشراء (Buyer)*\n\nأرسل رقم الهاتف (مثال: `+967777654321`):", reply_markup=login_cancel_kb(), parse_mode="Markdown")

@_guard
async def cb_paste_session_checker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    _session[update.effective_user.id] = {"awaiting_session_string": True, "type": "checker"}
    await update.callback_query.edit_message_text("📋 *لصق الجلسة لحساب الفحص (Checker)*\n\nأرسل الـ Pyrogram session string:", reply_markup=login_cancel_kb(), parse_mode="Markdown")

@_guard
async def cb_paste_session_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    _session[update.effective_user.id] = {"awaiting_session_string": True, "type": "buyer"}
    await update.callback_query.edit_message_text("📋 *لصق الجلسة لحساب الشراء (Buyer)*\n\nأرسل الـ Pyrogram session string:", reply_markup=login_cancel_kb(), parse_mode="Markdown")

@_guard
async def cb_logout_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await user_client.logout()
    await update.callback_query.edit_message_text("🚪 *تم تسجيل الخروج وتصفير الجلسات بنجاح.*", reply_markup=back_main_kb(), parse_mode="Markdown")


# ─── Admins Handlers ───
@_guard
async def cb_menu_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not storage.is_developer(update.effective_user.id):
        await q.answer("⛔ للمطور الرئيسي فقط.", show_alert=True)
        return
    admins = storage.get_admins()
    text = f"👥 *إدارة المطورين*\n\nالمطور الرئيسي: `{DEVELOPER_ID}`\n" + (f"إضافيون: {len(admins)}" if admins else "_لا يوجد مطورون إضافيون_")
    await q.edit_message_text(text, reply_markup=admins_kb(admins), parse_mode="Markdown")

@_guard
async def cb_add_admin_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    _session[update.effective_user.id] = {"awaiting_new_admin": True}
    await update.callback_query.edit_message_text("➕ *إضافة مطور*\n\nأرسل User ID الخاص به:", reply_markup=back_main_kb(), parse_mode="Markdown")

@_guard
async def cb_rm_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    storage.remove_admin(int(q.data[len("rm_admin_"):]))
    await cb_menu_admins(update, context)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else None
    if not uid or not storage.is_authorized(uid): return
    text = update.effective_message.text.strip()
    sess = _session.get(uid, {})

    if sess.get("awaiting_draft_name"):
        _session[uid] = {"draft": {"id": str(uuid.uuid4())[:8], "type": "named", "name": text}}
        await cb_tb_show_builder(update, context)
        return

    if sess.get("awaiting_tb"):
        prop = sess.pop("awaiting_tb")
        try:
            val = float(text) if prop == "max_ton" else int(text)
            _session[uid]["draft"][prop] = val
        except ValueError:
            await update.effective_message.reply_text("⚠️ قيمة غير صحيحة، يرجى إرسال أرقام فقط.")
            return
        await cb_tb_show_builder(update, context)
        return
        
    if sess.get("awaiting_phone"):
        client_type = sess.get("type", "checker")
        clean_phone = text.strip().replace(" ", "")
        msg = await update.effective_message.reply_text("📲 جاري الاتصال وتوليد الرمز...")
        result = await user_client.start_phone_login(uid, clean_phone, client_type=client_type)
        if result["ok"]:
            _session[uid] = {"awaiting_code": True, "type": client_type}
            await msg.edit_text(f"📲 *تم الإرسال لحساب {client_type.upper()}!*\n\nأرسل رمز التحقق (5 أرقام):", reply_markup=login_cancel_kb(), parse_mode="Markdown")
        else:
            _session.pop(uid, None)
            await msg.edit_text(f"❌ *فشل:* `{result['error']}`", reply_markup=back_main_kb(), parse_mode="Markdown")
        return

    if sess.get("awaiting_code"):
        client_type = sess.get("type", "checker")
        msg_code = text.strip().replace(" ", "").replace("-", "")
        msg = await update.effective_message.reply_text("⏳ جاري فحص الرمز...")
        result = await user_client.complete_phone_login(uid, msg_code)
        if result["ok"]:
            _session.pop(uid, None)
            await msg.edit_text(f"✅ *تم تأمين حساب {client_type.upper()}!*\n👤 `{result.get('name')}`", reply_markup=back_main_kb(), parse_mode="Markdown")
        elif result.get("need_password"):
            _session[uid] = {"awaiting_2fa": True, "type": client_type}
            await msg.edit_text("🔐 *الحساب محمي (2FA)*\n\nأرسل كلمة المرور:", reply_markup=login_cancel_kb(), parse_mode="Markdown")
        else:
            _session.pop(uid, None)
            await msg.edit_text(f"❌ *خطأ:* `{result.get('error', 'خطأ')}`", reply_markup=back_main_kb(), parse_mode="Markdown")
        return

    if sess.get("awaiting_2fa"):
        client_type = sess.get("type", "checker")
        msg = await update.effective_message.reply_text("🔐 جاري التحقق...")
        _session.pop(uid, None)
        result = await user_client.complete_2fa(uid, text.strip())
        if result["ok"]:
            await msg.edit_text(f"✅ *تم ربط حساب {client_type.upper()} بنجاح!*", reply_markup=back_main_kb(), parse_mode="Markdown")
        else:
            await msg.edit_text(f"❌ *فشل التحقق:* `{result.get('error', 'خطأ')}`", reply_markup=back_main_kb(), parse_mode="Markdown")
        return

    if sess.get("awaiting_session_string"):
        client_type = sess.get("type", "checker")
        _session.pop(uid, None)
        msg = await update.effective_message.reply_text("🔄 جاري تثبيت الجلسة المعزولة...")
        result = await user_client.set_session_directly(uid, text.strip(), client_type=client_type)
        if result["ok"]:
            await msg.edit_text(f"✅ *تم ربط الجلسة بنجاح!*\n👤 الحساب: `{result.get('name')}`", reply_markup=back_main_kb(), parse_mode="Markdown")
        else:
            await msg.edit_text(f"❌ *فشل:* `{result['error']}`", reply_markup=back_main_kb(), parse_mode="Markdown")
        return

    if sess.get("awaiting_new_admin"):
        _session.pop(uid, None)
        if not text.strip().lstrip("-").isdigit():
            await update.effective_message.reply_text("⚠️ User ID رقم فقط.")
            return
        new_id = int(text.strip())
        added = storage.add_admin(new_id)
        await update.effective_message.reply_text(f"✅ تمت إضافة `{new_id}`." if added else f"⚠️ موجود مسبقاً.", reply_markup=back_main_kb(), parse_mode="Markdown")
        return


def main() -> None:
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0, pool_timeout=30.0)
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(cb_back_main, pattern="^back_main$"))
    
    app.add_handler(CallbackQueryHandler(cb_toggle_demo, pattern="^toggle_demo$"))
    
    app.add_handler(CallbackQueryHandler(cb_menu_targets, pattern="^menu_targets$"))
    app.add_handler(CallbackQueryHandler(cb_add_target_any, pattern="^add_target_any$"))
    app.add_handler(CallbackQueryHandler(cb_add_target_named, pattern="^add_target_named$"))
    app.add_handler(CallbackQueryHandler(cb_del_target, pattern="^del_target_"))
    
    app.add_handler(CallbackQueryHandler(cb_tb_show_builder, pattern="^tb_show_builder$"))
    app.add_handler(CallbackQueryHandler(cb_tb_set_stars, pattern="^tb_set_stars$"))
    app.add_handler(CallbackQueryHandler(cb_tb_set_ton, pattern="^tb_set_ton$"))
    app.add_handler(CallbackQueryHandler(cb_tb_set_mint, pattern="^tb_set_mint$"))
    app.add_handler(CallbackQueryHandler(cb_tb_set_rarity, pattern="^tb_set_rarity$"))
    app.add_handler(CallbackQueryHandler(cb_tb_save_target, pattern="^tb_save_target$"))
    
    app.add_handler(CallbackQueryHandler(cb_start_hunt, pattern="^start_hunt$"))
    app.add_handler(CallbackQueryHandler(cb_stop_hunt, pattern="^stop_hunt$"))
    
    app.add_handler(CallbackQueryHandler(cb_menu_stats, pattern="^menu_stats$"))
    app.add_handler(CallbackQueryHandler(cb_menu_account, pattern="^menu_account$"))
    app.add_handler(CallbackQueryHandler(cb_login_phone_checker, pattern="^login_phone_checker$"))
    app.add_handler(CallbackQueryHandler(cb_login_phone_buyer, pattern="^login_phone_buyer$"))
    app.add_handler(CallbackQueryHandler(cb_paste_session_checker, pattern="^paste_session_checker$"))
    app.add_handler(CallbackQueryHandler(cb_paste_session_buyer, pattern="^paste_session_buyer$"))
    app.add_handler(CallbackQueryHandler(cb_logout_account, pattern="^logout_account$"))
    
    app.add_handler(CallbackQueryHandler(cb_menu_admins, pattern="^menu_admins$"))
    app.add_handler(CallbackQueryHandler(cb_add_admin_btn, pattern="^add_admin$"))
    app.add_handler(CallbackQueryHandler(cb_rm_admin, pattern="^rm_admin_"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🤖 بوت الهدايا الرقمية المعزول — جاهز للعمل")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

