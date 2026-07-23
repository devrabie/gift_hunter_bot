import json
import os
from typing import Any

from config import DATA_FILE, DEVELOPER_ID


def _default() -> dict:
    return {
        "admins": [],
        "settings": {
            "hunting": False,
        },
        "targets": [],   # قائمة الأهداف المتقدمة المعززة بالفلاتر
        "account": {
            "session_string": None,
            "api_id": None,
            "api_hash": None,
        },
        "pool": [],
        "buyer_id": None,
        "checker_ids": [],
        "notifications": {
            "channel_id": None,
            "notify_developer": True,
            "notify_channel": False
        },
    }


def _load() -> dict:
    if not os.path.exists(DATA_FILE):
        return _default()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("admins", [])
    data.setdefault("settings", {"hunting": False})
    data.setdefault("targets", [])
    data.setdefault("account", {"session_string": None, "api_id": None, "api_hash": None})
    data.setdefault("pool", [])
    data.setdefault("buyer_id", None)
    data.setdefault("checker_ids", [])
    data.setdefault("notifications", {"channel_id": None, "notify_developer": True, "notify_channel": False})
    return data


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_authorized(user_id: int) -> bool:
    return user_id == DEVELOPER_ID or user_id in _load()["admins"]


def is_developer(user_id: int) -> bool:
    return user_id == DEVELOPER_ID


def get_admins() -> list[int]:
    return _load()["admins"]


def add_admin(user_id: int) -> bool:
    if user_id == DEVELOPER_ID:
        return False
    data = _load()
    if user_id in data["admins"]:
        return False
    data["admins"].append(user_id)
    _save(data)
    return True


def remove_admin(user_id: int) -> bool:
    data = _load()
    if user_id not in data["admins"]:
        return False
    data["admins"].remove(user_id)
    _save(data)
    return True


def get_settings() -> dict:
    return _load().get("settings", {})


def update_setting(key: str, value: Any) -> None:
    data = _load()
    data.setdefault("settings", {})
    data["settings"][key] = value
    _save(data)


def is_hunting() -> bool:
    return _load().get("settings", {}).get("hunting", False)


def set_hunting(active: bool) -> None:
    update_setting("hunting", active)


# ─── targets المتقدمة ──────────────────────────────────────────────────────────

def get_targets() -> list[dict]:
    return _load().get("targets", [])


def add_target(target_type: str, max_price: int, name: str | None = None, **kwargs) -> None:
    """إضافة هدف صيد متقدم أو تحديثه بكامل فلاتره الذكية"""
    data = _load()
    targets = data.setdefault("targets", [])
    
    t_id = kwargs.get("t_id") or kwargs.get("id")
    
    # فلترة الاستبدال: إزالة الهدف القديم إن وجد بالـ ID أو المفتاح القديم
    if t_id:
        data["targets"] = [t for t in targets if t.get("id") != t_id]
    else:
        key = _target_key(target_type, name)
        data["targets"] = [t for t in targets if _target_key(t["type"], t.get("name")) != key]
        
    # بناء هيكل الهدف المعزز بالخيارات الاختيارية
    target_item = {
        "id": t_id,
        "type": target_type,
        "name": name,
        "max_stars": max_price,  # التوافق مع الكود القديم والمستقبل
        "max_ton": kwargs.get("max_ton"),
        "max_mint": kwargs.get("max_mint"),
        "max_rarity": kwargs.get("max_rarity"),
        "excluded": kwargs.get("excluded", [])
    }
    
    data["targets"].append(target_item)
    _save(data)


def remove_target_by_id(t_id: str) -> bool:
    """حذف مرن وعميق للهدف باستخدام معرفه الفريد، مع التراجع الذكي للأهداف الافتراضية القديمة"""
    data = _load()
    before = len(data["targets"])
    
    # 1. محاولة الحذف بالمعرف الفريد
    data["targets"] = [t for t in data["targets"] if t.get("id") != t_id]
    
    # 2. خطة بديلة (Fallback): إذا لم يتغير العدد وكان المعرف الممرر هو "any" أو اسم هدف قديم
    if len(data["targets"]) == before:
        if t_id == "any" or t_id == "أي هدية مميزة":
            data["targets"] = [t for t in data["targets"] if t.get("type") != "any"]
        else:
            data["targets"] = [t for t in data["targets"] if t.get("name") != t_id]
            
    _save(data)
    return len(data["targets"]) < before


def remove_target(target_type: str, name: str | None = None) -> bool:
    data = _load()
    key = _target_key(target_type, name)
    before = len(data["targets"])
    data["targets"] = [t for t in data["targets"] if _target_key(t["type"], t.get("name")) != key]
    _save(data)
    return len(data["targets"]) < before


def _target_key(target_type: str, name: str | None) -> str:
    if target_type == "any":
        return "any"
    return f"named:{(name or '').strip().lower()}"


# ─── account ──────────────────────────────────────────────────────────────────

def get_account_credentials() -> dict:
    return _load().get("account", {})


def set_account_credentials(api_id: int, api_hash: str) -> None:
    data = _load()
    data.setdefault("account", {})
    data["account"]["api_id"] = api_id
    data["account"]["api_hash"] = api_hash
    _save(data)


def get_session_string() -> str | None:
    return _load().get("account", {}).get("session_string")


def set_session_string(session: str) -> None:
    data = _load()
    data.setdefault("account", {})
    data["account"]["session_string"] = session
    _save(data)


def clear_session() -> None:
    data = _load()
    data.setdefault("account", {})
    data["account"]["session_string"] = None
    _save(data)


# ─── Account Pool ─────────────────────────────────────────────────────────────

def get_account_pool() -> list[dict]:
    return _load().get("pool", [])

def add_account_to_pool(session_string: str, acc_id: int, name: str, username: str | None = None, phone: str | None = None) -> None:
    data = _load()
    pool = data.setdefault("pool", [])

    # Remove existing if any with same id
    pool = [acc for acc in pool if acc.get("id") != acc_id]

    pool.append({
        "id": acc_id,
        "session_string": session_string,
        "name": name,
        "username": username,
        "phone": phone
    })
    data["pool"] = pool
    _save(data)

def remove_account_from_pool(acc_id: int) -> bool:
    data = _load()
    pool = data.get("pool", [])
    before = len(pool)
    data["pool"] = [acc for acc in pool if acc.get("id") != acc_id]

    if data.get("buyer_id") == acc_id:
        data["buyer_id"] = None

    if "checker_ids" in data and acc_id in data["checker_ids"]:
        data["checker_ids"].remove(acc_id)

    _save(data)
    return len(data["pool"]) < before

def clear_all_accounts() -> None:
    data = _load()
    data["pool"] = []
    data["buyer_id"] = None
    data["checker_ids"] = []
    _save(data)

def get_load() -> dict:
    return _load()

def get_buyer_account() -> dict | None:
    data = _load()
    buyer_id = data.get("buyer_id")
    if not buyer_id:
        return None
    for acc in data.get("pool", []):
        if acc.get("id") == buyer_id:
            return acc
    return None

def set_buyer_account(acc_id: int | None) -> None:
    data = _load()
    data["buyer_id"] = acc_id
    _save(data)

def get_checker_accounts() -> list[dict]:
    data = _load()
    checker_ids = data.get("checker_ids", [])
    checkers = []
    for acc in data.get("pool", []):
        if acc.get("id") in checker_ids:
            checkers.append(acc)
    return checkers

def toggle_checker_account(acc_id: int) -> None:
    data = _load()
    checker_ids = data.setdefault("checker_ids", [])
    if acc_id in checker_ids:
        checker_ids.remove(acc_id)
    else:
        checker_ids.append(acc_id)
    data["checker_ids"] = checker_ids
    _save(data)

# ─── Notifications ────────────────────────────────────────────────────────────

def get_notification_settings() -> dict:
    return _load().get("notifications", {"channel_id": None, "notify_developer": True, "notify_channel": False})

def set_notification_channel(channel_id: int | str | None) -> None:
    data = _load()
    notif = data.setdefault("notifications", {"channel_id": None, "notify_developer": True, "notify_channel": False})
    notif["channel_id"] = channel_id
    data["notifications"] = notif
    _save(data)

def toggle_notify_developer() -> None:
    data = _load()
    notif = data.setdefault("notifications", {"channel_id": None, "notify_developer": True, "notify_channel": False})
    notif["notify_developer"] = not notif.get("notify_developer", True)
    data["notifications"] = notif
    _save(data)

def toggle_notify_channel() -> None:
    data = _load()
    notif = data.setdefault("notifications", {"channel_id": None, "notify_developer": True, "notify_channel": False})
    notif["notify_channel"] = not notif.get("notify_channel", False)
    data["notifications"] = notif
    _save(data)
