"""قراءة المحتوى المُدار من لوحة التحكم (Firebase Realtime Database عبر REST).

/public/config   إعدادات: affiliate_tag, show_prices, search_mode, announcement, channel_url, contact, privacy_url
/public/timer    مؤقت الكوبون القادم: text, delay_ms, created (وقت الخادم)
/public/coupons  كوبونات: name, code, ts, ttl_ms (مدة الصلاحية، اختياري)
/public/offers   عروض: title, url, ts
/public/hot      منتجات مميزة (عروض قوية) على الصفحة الرئيسية: title, url, note, image, ts
تُحفظ نسخة محلية من آخر محتوى ليظهر عند انقطاع الإنترنت (لا علاقة لها بأسعار المنتجات).
"""
import json
import os
import time
from email.utils import parsedate_to_datetime

import requests

import app_config

DATA_DIR = os.getenv("FLET_APP_STORAGE_DATA", ".")
os.makedirs(DATA_DIR, exist_ok=True)
CACHE = os.path.join(DATA_DIR, "remote_cache.json")
_state = {"offset": 0.0}


def server_now():
    """الوقت الحالي بتوقيت الخادم (يُصحَّح فرق ساعة الجوال)."""
    return time.time() + _state["offset"]


def _rows(d, need):
    out = []
    for key, v in (d or {}).items() if isinstance(d, dict) else []:
        if isinstance(v, dict) and all(str(v.get(n, "")).strip() for n in need):
            row = {"id": key, **v}
            ttl, ts = v.get("ttl_ms"), v.get("ts")
            # وقت انتهاء الكوبون (بتوقيت الخادم). None = بلا وقت محدد ← يظهر «سينتهي قريباً»
            row["expires_ts"] = (ts + ttl) / 1000.0 if isinstance(ttl, (int, float)) and ttl > 0 and isinstance(ts, (int, float)) else None
            out.append(row)
    out.sort(key=lambda x: x.get("ts") or 0, reverse=True)
    return out


def normalize(data):
    data = data if isinstance(data, dict) else {}
    cfg = data.get("config") if isinstance(data.get("config"), dict) else {}
    t = data.get("timer")
    timer = None
    if isinstance(t, dict) and isinstance(t.get("created"), (int, float)) and isinstance(t.get("delay_ms"), (int, float)):
        timer = {"text": str(t.get("text") or "كوبون قادم في"), "end_ts": (t["created"] + t["delay_ms"]) / 1000.0}
    return {"config": cfg, "timer": timer, "coupons": _rows(data.get("coupons"), ("code",)),
            "offers": _rows(data.get("offers"), ("title", "url")),
            "hot": _rows(data.get("hot"), ("title", "url"))}


def fetch():
    """يرجع (محتوى مُطبَّع، حالة) حيث الحالة: ok | cache | none | not_configured."""
    base = (app_config.FIREBASE_DB_URL or "").rstrip("/")
    if not base:
        return normalize({}), "not_configured"
    try:
        r = requests.get(f"{base}/public.json", timeout=12)
        r.raise_for_status()
        date = r.headers.get("Date")
        if date:
            _state["offset"] = parsedate_to_datetime(date).timestamp() - time.time()
        data = r.json() or {}
        try:
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass
        return normalize(data), "ok"
    except Exception:
        try:
            with open(CACHE, encoding="utf-8") as f:
                return normalize(json.load(f)), "cache"
        except Exception:
            return normalize({}), "none"


# ---------------------------------------------------------------- حالة محلية (تفضيلات المستخدم فقط)
LOCAL = os.path.join(DATA_DIR, "local.json")


def load_local():
    base = {"notify": False, "seen": []}
    try:
        with open(LOCAL, encoding="utf-8") as f:
            base.update(json.load(f))
    except Exception:
        pass
    return base


def save_local(d):
    try:
        with open(LOCAL, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass
