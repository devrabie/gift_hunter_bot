from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_kb(hunting: bool, has_session: bool, targets: list[dict], demo_mode: bool) -> InlineKeyboardMarkup:
    hunt_btn = (
        InlineKeyboardButton("⏹ إيقاف الصيد", callback_data="stop_hunt") if hunting
        else InlineKeyboardButton("▶️ بدء الصيد", callback_data="start_hunt")
    )
    demo_btn = (
        InlineKeyboardButton("🧪 وضع التجربة: 🟢 مُفعّل", callback_data="toggle_demo") if demo_mode
        else InlineKeyboardButton("🧪 وضع التجربة: 🔴 مُعطّل", callback_data="toggle_demo")
    )
    t_count = len(targets)
    targets_label = f"🎯 الأهداف والفلاتر ({t_count})" if t_count > 0 else "🎯 إضافة هدف شراء ⚠️"
    account_label = "👤 ربط الحسابات المعزولة ⚙️"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(account_label, callback_data="menu_account")],
        [InlineKeyboardButton(targets_label, callback_data="menu_targets")],
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

def account_kb(has_session: bool, has_creds: bool) -> InlineKeyboardMarkup:
    rows = []
    rows.append([InlineKeyboardButton("📱 ربط الفحص بهاتف", callback_data="login_phone_checker"), InlineKeyboardButton("📋 فحص بـ Session", callback_data="paste_session_checker")])
    rows.append([InlineKeyboardButton("📱 ربط الشراء بهاتف", callback_data="login_phone_buyer"), InlineKeyboardButton("📋 شراء بـ Session", callback_data="paste_session_buyer")])
    if has_session:
        rows.append([InlineKeyboardButton("🚪 تسجيل الخروج وتصفير الجلسات", callback_data="logout_account")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def admins_kb(admins: list[int]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"❌ إزالة {uid}", callback_data=f"rm_admin_{uid}")] for uid in admins]
    rows.append([InlineKeyboardButton("➕ إضافة مطور", callback_data="add_admin")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def login_cancel_kb() -> InlineKeyboardMarkup: return InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_account")]])
def back_main_kb() -> InlineKeyboardMarkup: return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")]])
def back_targets_kb() -> InlineKeyboardMarkup: return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للأهداف", callback_data="menu_targets")]])
def back_builder_kb() -> InlineKeyboardMarkup: return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للإعدادات", callback_data="tb_show_builder")]])

