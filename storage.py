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
        "max_rarity": kwargs.get("max_rarity")
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

