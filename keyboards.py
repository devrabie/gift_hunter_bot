from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_kb(hunting: bool, has_session: bool, targets: list[dict], demo_mode: bool) -> InlineKeyboardMarkup:
    hunt_btn = (
        InlineKeyboardButton("⏹ إيقاف الصيد", callback_data="stop_hunt") if hunting
        else InlineKeyboardButton("▶️ بدء الصيد", callback_data="start_hunt")
    )
    demo_btn = (
        InlineKeyboardButton("🧪 التجربة: 🟢", callback_data="toggle_demo") if demo_mode
        else InlineKeyboardButton("🧪 التجربة: 🔴", callback_data="toggle_demo")
    )
    t_count = len(targets)
    targets_label = f"🎯 الأهداف والفلاتر ({t_count})" if t_count > 0 else "🎯 إضافة هدف شراء ⚠️"
    account_label = "👤 إدارة الحسابات المتعددة ⚙️"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(account_label, callback_data="menu_account")],
        [InlineKeyboardButton(targets_label, callback_data="menu_targets")],
        [InlineKeyboardButton("📢 إعدادات الإشعارات", callback_data="menu_notifications")],
        [demo_btn, hunt_btn],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="menu_stats"), InlineKeyboardButton("👥 المطورون", callback_data="menu_admins")]
    ])

def targets_menu_kb(targets: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for t in targets:
        name = "أي هدية" if t["type"] == "any" else t.get("name", "")
        conds = []
        if t.get("max_stars"): conds.append(f"{t['max_stars']}⭐")
        if t.get("max_ton"): conds.append(f"{t['max_ton']}💎")
        if t.get("max_mint"): conds.append(f"#{t['max_mint']}")
        
        label = f"❌ {name} | " + (" - ".join(conds) if conds else "بدون شروط")
        t_id = t.get("id", name)
        rows.append([InlineKeyboardButton(label, callback_data=f"del_target_{t_id}")])

    rows.append([
        InlineKeyboardButton("➕ أي هدية مميزة", callback_data="add_target_any"),
        InlineKeyboardButton("🔍 هدية بالاسم", callback_data="add_target_named"),
    ])
    rows.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def target_builder_kb(draft: dict) -> InlineKeyboardMarkup:
    stars = f"{draft.get('max_stars')} ⭐" if draft.get('max_stars') else "لم يحدد ❌"
    ton = f"{draft.get('max_ton')} 💎" if draft.get('max_ton') else "لم يحدد ❌"
    mint = f"أقل من {draft.get('max_mint')}" if draft.get('max_mint') else "لم يحدد ❌"
    rarity = f"أندر من {draft.get('max_rarity')}‰" if draft.get('max_rarity') else "لم يحدد ❌"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐ أقصى سعر نجوم: {stars}", callback_data="tb_set_stars")],
        [InlineKeyboardButton(f"💎 أقصى سعر TON: {ton}", callback_data="tb_set_ton")],
        [InlineKeyboardButton(f"🔢 أقصى رقم للنسخة: {mint}", callback_data="tb_set_mint")],
        [InlineKeyboardButton(f"✨ أقصى نسبة ندرة: {rarity}", callback_data="tb_set_rarity")],
        [InlineKeyboardButton("✅ حفظ الهدف والفلتر", callback_data="tb_save_target")],
        [InlineKeyboardButton("🗑 إلغاء", callback_data="menu_targets")]
    ])

def account_kb(has_session: bool, pool_count: int) -> InlineKeyboardMarkup:
    rows = []
    rows.append([InlineKeyboardButton("➕ إضافة حساب برقم هاتف", callback_data="add_account_phone")])
    rows.append([InlineKeyboardButton("➕ إضافة حساب بـ Session", callback_data="add_account_session")])
    if pool_count > 0:
        rows.append([InlineKeyboardButton("🛒 تعيين حساب الشراء الأساسي", callback_data="set_buyer_menu")])
        rows.append([InlineKeyboardButton("🔍 اختيار حسابات الفحص (تزامن)", callback_data="set_checker_menu")])
        rows.append([InlineKeyboardButton("🗑 إزالة حساب", callback_data="remove_account_menu")])

    rows.append([InlineKeyboardButton("🚪 مسح كافة الحسابات", callback_data="logout_account")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def pool_select_kb(pool: list[dict], action_prefix: str, selected_ids: list[int] = None) -> InlineKeyboardMarkup:
    selected_ids = selected_ids or []
    rows = []
    for acc in pool:
        mark = "✅ " if acc["id"] in selected_ids else ""
        label = f"{mark}{acc.get('name', 'بدون اسم')} ({acc.get('id')})"
        rows.append([InlineKeyboardButton(label, callback_data=f"{action_prefix}_{acc['id']}")])
    rows.append([InlineKeyboardButton("🔙 رجوع للحسابات", callback_data="menu_account")])
    return InlineKeyboardMarkup(rows)

def notifications_kb(settings: dict) -> InlineKeyboardMarkup:
    dev = "🟢 مُفعّل" if settings.get("notify_developer", True) else "🔴 مُعطّل"
    chan = "🟢 مُفعّل" if settings.get("notify_channel", False) else "🔴 مُعطّل"
    chan_id = settings.get("channel_id") or "لم يحدد ❌"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👤 إشعارات المطور: {dev}", callback_data="toggle_notif_dev")],
        [InlineKeyboardButton(f"📢 إشعارات القناة: {chan}", callback_data="toggle_notif_chan")],
        [InlineKeyboardButton(f"🔗 قناة الإشعارات: {chan_id}", callback_data="set_notif_chan")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ])

def admins_kb(admins: list[int]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"❌ إزالة {uid}", callback_data=f"rm_admin_{uid}")] for uid in admins]
    rows.append([InlineKeyboardButton("➕ إضافة مطور", callback_data="add_admin")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def login_cancel_kb() -> InlineKeyboardMarkup: return InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_account")]])
def back_main_kb() -> InlineKeyboardMarkup: return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")]])
def back_targets_kb() -> InlineKeyboardMarkup: return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للأهداف", callback_data="menu_targets")]])
def back_builder_kb() -> InlineKeyboardMarkup: return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للإعدادات", callback_data="tb_show_builder")]])

