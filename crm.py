"""
Etsy Shops CRM — plugs into "Patterns by Rish — Etsy Tools" (app.py).

Adds a left sidebar to the app and these pages:
  Work:      Dashboard, Tasks, This week
  Shop data: Listings, Orders & sales, Customers, Sheets
  Setup:     Import data, Shops & schedules, Report for Claude, Settings & updates
Your existing tools (Image Organizer, URL Extractor, ...) stay as they are, under "Tools".

Data lives in your Supabase project (same tables as setup/supabase-setup.sql), so every laptop
sees the same records. Updates: app.py downloads the newest app.py + crm.py from GitHub on every
start, so "Refresh App" is all you need after Claude changes something.
"""
CRM_VERSION = "1.2.2"

import os
import sys
import csv
import json
import re
import time
import uuid
import hashlib
import threading
import traceback
from datetime import date, datetime, timedelta, timezone

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import requests

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "crm_config.json")
PHOTO_LINKS_PATH = os.path.join(HERE, "listing_photo_links.json")  # photo links from the last Listings CSV, kept on this laptop

# ------------------------------------------------------------------ look
C = dict(bg="#0c0c0d", side="#111113", card="#161618", card2="#1d1d20", line="#2a2a2e", hover="#26262b",
         ink="#f3f2ee", muted="#9c9ba3", faint="#6d6c74", yellow="#ffc727", yellow_h="#ffd451", on_y="#121212",
         ok="#46c983", ok_h="#5ad694", warn="#ff9f43", bad="#ff5d55")
FONT = "Segoe UI" if sys.platform.startswith("win") else "DejaVu Sans"
MONO = "Consolas" if sys.platform.startswith("win") else "DejaVu Sans Mono"


def F(size=13, weight="normal", mono=False):
    return ctk.CTkFont(family=MONO if mono else FONT, size=size, weight=weight)


def apply_theme():
    """Black & yellow look for every customtkinter widget. Call before the app window is created."""
    ctk.set_appearance_mode("Dark")
    t = ctk.ThemeManager.theme

    def setk(w, **kv):
        d = t.get(w)
        if not isinstance(d, dict):
            return
        for k, v in kv.items():
            if k in d:
                d[k] = [v, v]
    setk("CTk", fg_color=C["bg"]); setk("CTkToplevel", fg_color=C["bg"])
    setk("CTkFrame", fg_color=C["card"], top_fg_color=C["card2"], border_color=C["line"])
    setk("CTkButton", fg_color=C["hover"], hover_color="#34343a", border_color=C["yellow"], text_color=C["ink"])
    setk("CTkLabel", text_color=C["ink"])
    setk("CTkEntry", fg_color=C["bg"], border_color=C["line"], text_color=C["ink"], placeholder_text_color=C["faint"])
    setk("CTkTextbox", fg_color=C["bg"], border_color=C["line"], text_color=C["ink"], scrollbar_button_color="#2f2f35", scrollbar_button_hover_color=C["yellow"])
    setk("CTkProgressBar", fg_color=C["card2"], progress_color=C["yellow"], border_color=C["line"])
    setk("CTkSegmentedButton", fg_color=C["card2"], selected_color="#7a5f00", selected_hover_color="#8f7000", unselected_color=C["card2"], unselected_hover_color="#2b2b30", text_color=C["ink"])
    setk("CTkOptionMenu", fg_color=C["card2"], button_color="#2b2b30", button_hover_color="#7a5f00", text_color=C["ink"])
    setk("CTkComboBox", fg_color=C["bg"], border_color=C["line"], button_color="#2b2b30", button_hover_color="#7a5f00", text_color=C["ink"])
    setk("CTkCheckBox", fg_color=C["yellow"], hover_color=C["yellow_h"], border_color=C["faint"], checkmark_color=C["on_y"], text_color=C["ink"])
    setk("CTkSwitch", progress_color=C["yellow"], button_color=C["ink"])
    setk("CTkRadioButton", fg_color=C["yellow"], hover_color=C["yellow_h"])
    setk("CTkSlider", button_color=C["yellow"], button_hover_color=C["yellow_h"], progress_color=C["yellow"])
    setk("CTkScrollbar", button_color="#2f2f35", button_hover_color=C["yellow"])
    setk("CTkScrollableFrame", label_fg_color=C["card2"])
    setk("DropdownMenu", fg_color=C["card2"], hover_color="#2f2f35", text_color=C["ink"])


# ------------------------------------------------------------------ small helpers
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
AREAS = {"listing": "Listing update", "new": "New listing", "instagram": "Instagram", "pinterest": "Pinterest", "payhip": "Payhip",
         "review": "Results check", "data": "Etsy data", "ads": "Ads / offers", "customer": "Customer", "other": "Other"}
STATUS = {"todo": "To do", "doing": "In progress", "done": "Done", "skipped": "Skipped"}
LST_LABEL = {"STOPPED": "Stopped selling", "DECLINING": "Declining", "NEVER": "No sales yet", "OK": "Steady", "WINNER": "Winner", "NEW": "No order data", "INACTIVE": "Not active"}
LST_COLOR = {"STOPPED": "#ff8a84", "DECLINING": "#ffb870", "NEVER": "#ff8a84", "OK": C["ink"], "WINNER": C["ok"], "NEW": C["faint"], "INACTIVE": C["faint"]}


def today():
    return date.today().isoformat()


def pdate(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def add_days(s, n):
    return (pdate(s) + timedelta(days=n)).isoformat()


def diff(a, b):
    return (pdate(a) - pdate(b)).days


def nice(s, yr=False):
    d = pdate(s)
    if not d:
        return "-"
    return f"{DAYS[d.weekday()]} {d.day} {MON[d.month - 1]}" + (f" {d.year}" if yr else "")


def short(s):
    d = pdate(s)
    return f"{d.day} {MON[d.month - 1]} {str(d.year)[2:]}" if d else "-"


def valid_date(s):
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s or ""))) and pdate(s) is not None


def slug(s):
    return (re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")[:40]) or "x"


def norm(s):
    return re.sub(r"\s+", " ", str(s or "").lower()).strip()


def money(v):
    try:
        return float(re.sub(r"[^0-9.\-]", "", str(v)) or 0)
    except Exception:
        return 0.0


def fmt_money(n, cur=None):
    return ("$" if not cur or cur == "USD" else cur + " ") + f"{n:,.2f}"


def pct(a, b):
    if not b:
        return "new" if a else "0%"
    p = round((a - b) / b * 100)
    return ("+" if p > 0 else "") + f"{p}%"


def etsy_date(v):
    s = str(v or "").strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        return f"{y:04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def load_cfg():
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(cfg):
    try:
        tmp = CFG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, CFG_PATH)
    except Exception:
        pass


def load_photo_links():
    try:
        with open(PHOTO_LINKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_photo_links(shop, mapped):
    links = load_photo_links()
    links[shop] = {m["key"]: m.get("images") or [] for m in mapped}
    try:
        tmp = PHOTO_LINKS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(links, f)
        os.replace(tmp, PHOTO_LINKS_PATH)
    except Exception:
        pass


class CrmError(Exception):
    pass


# ------------------------------------------------------------------ Supabase (REST, no extra libraries)
COLS = {
    "shops": ["owner", "id", "name", "url", "last_csv", "csv_every_days", "schedules", "sort", "updated_at"],
    "tasks": ["owner", "id", "shop", "title", "area", "sku", "due", "priority", "status", "steps", "copy", "follow_up_days", "notes", "plan", "source", "parent", "started_at", "done_at", "created_at", "updated_at"],
    "listings": ["owner", "shop", "key", "title", "sku", "price", "currency", "quantity", "tags", "image_count", "images", "description", "notes", "active", "imported_at"],
    "orders": ["owner", "shop", "transaction_id", "order_id", "sale_date", "item_name", "listing_id", "sku", "quantity", "price", "discount", "item_total", "currency", "coupon", "buyer", "country"],
    "customer_notes": ["owner", "shop", "buyer", "notes", "tags", "updated_at"],
    "datasets": ["owner", "id", "name", "shop", "source_file", "columns", "row_count", "created_at"],
    "dataset_rows": ["owner", "dataset_id", "row_no", "data"],
    "app_code": ["owner", "name", "version", "content", "updated_at"],
}
PK = {"shops": ["owner", "id"], "tasks": ["owner", "id"], "listings": ["owner", "shop", "key"], "orders": ["owner", "shop", "transaction_id"],
      "customer_notes": ["owner", "shop", "buyer"], "datasets": ["owner", "id"], "dataset_rows": ["owner", "dataset_id", "row_no"], "app_code": ["owner", "name"]}
JSONDEF = {"shops": {"schedules": []}, "tasks": {"copy": []}, "datasets": {"columns": []}, "listings": {"images": []}}


PAUSED_MSG = ("The database is not answering. Your free Supabase project is probably paused or still waking up. "
              "Open supabase.com > your project > Restore project, wait 2-5 minutes, then Sign in again.")


def server_down(r):
    t = (r.text or "").lstrip()[:200].lower()
    return r.status_code in (502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 530, 540, 544) or t.startswith("<!doctype") or t.startswith("<html")


class Supa:
    def __init__(self, url, key):
        self.url = url.strip().rstrip("/")
        self.key = key.strip()
        self.token = None
        self.refresh_token = None
        self.exp = 0
        self.user = {}
        self.no_images_col = False
        self.lock = threading.Lock()
        self.on_token = None

    def _auth(self, grant, payload):
        try:
            r = requests.post(f"{self.url}/auth/v1/token?grant_type={grant}", json=payload,
                              headers={"apikey": self.key, "Content-Type": "application/json"}, timeout=30)
        except requests.RequestException:
            raise CrmError("No connection to the database. Check your internet and the Project URL.")
        if r.status_code >= 400 and server_down(r):
            raise CrmError(PAUSED_MSG)
        if r.status_code >= 400:
            try:
                msg = r.json().get("error_description") or r.json().get("msg") or r.text
            except Exception:
                msg = r.text
            if "Invalid login" in str(msg):
                msg = "Wrong email or password."
            elif "Invalid API key" in str(msg) or r.status_code == 401:
                msg = "The anon / publishable key is not valid for this project."
            raise CrmError(str(msg)[:300])
        d = r.json()
        self.token = d["access_token"]
        self.refresh_token = d.get("refresh_token")
        self.exp = time.time() + int(d.get("expires_in", 3600)) - 120
        self.user = d.get("user") or {}
        if self.on_token:
            self.on_token(self)
        return d

    def sign_in(self, email, password):
        return self._auth("password", {"email": email, "password": password})

    def restore(self, refresh_token):
        return self._auth("refresh_token", {"refresh_token": refresh_token})

    @property
    def uid(self):
        return self.user.get("id")

    def _h(self, extra=None):
        with self.lock:
            if self.token and time.time() > self.exp and self.refresh_token:
                self.restore(self.refresh_token)
        h = {"apikey": self.key, "Authorization": f"Bearer {self.token or self.key}", "Content-Type": "application/json"}
        if extra:
            h.update(extra)
        return h

    def _check(self, r):
        if r.status_code < 400:
            return
        if server_down(r):
            raise CrmError(PAUSED_MSG)
        try:
            j = r.json(); msg = j.get("message") or j.get("hint") or r.text
        except Exception:
            msg = r.text
        if r.status_code == 401:
            msg = "Your login expired. Sign in again under Settings & updates."
        if "does not exist" in str(msg) or "schema cache" in str(msg):
            msg = str(msg) + "  (Run the latest setup/supabase-setup.sql once in Supabase > SQL Editor.)"
        raise CrmError(str(msg)[:400])

    def select(self, table, filters=None):
        out, off = [], 0
        order = ",".join(c + ".asc" for c in PK[table])
        while True:
            params = {"select": "*", "order": order, "limit": 1000, "offset": off}
            for k, v in (filters or {}).items():
                params[k] = f"eq.{v}"
            try:
                r = requests.get(f"{self.url}/rest/v1/{table}", params=params, headers=self._h(), timeout=60)
            except requests.RequestException:
                raise CrmError("No connection to the database. Check your internet.")
            self._check(r)
            rows = r.json()
            out.extend(rows)
            if len(rows) < 1000:
                return out
            off += 1000

    def upsert(self, table, rows, progress=None):
        rows = [self.clean(table, r) for r in rows]
        if table == "listings" and self.no_images_col:
            for r in rows:
                r.pop("images", None)
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            try:
                r = requests.post(f"{self.url}/rest/v1/{table}", params={"on_conflict": ",".join(PK[table])}, data=json.dumps(chunk, default=str),
                                  headers=self._h({"Prefer": "resolution=merge-duplicates,return=minimal"}), timeout=120)
            except requests.RequestException:
                raise CrmError("No connection to the database. Check your internet.")
            if r.status_code >= 400 and table == "listings" and "images" in r.text and not self.no_images_col:
                self.no_images_col = True
                return self.upsert(table, rows, progress)
            self._check(r)
            if progress:
                progress(min(i + 500, len(rows)), len(rows))

    def delete(self, table, match):
        params = {k: f"eq.{v}" for k, v in match.items()}
        params["owner"] = f"eq.{self.uid}"
        r = requests.delete(f"{self.url}/rest/v1/{table}", params=params, headers=self._h(), timeout=60)
        self._check(r)

    def clean(self, table, row):
        o = {}
        for c in COLS[table]:
            if table == "listings" and c == "images" and self.no_images_col:
                continue
            v = row.get(c)
            if v is None and c in JSONDEF.get(table, {}):
                v = JSONDEF[table][c]
            o[c] = v
        o["owner"] = self.uid
        return o


# ------------------------------------------------------------------ data store + analytics
class Store:
    def __init__(self):
        self.shops = []
        self.tasks = {}
        self.listings = []
        self.orders = []
        self.notes = {}
        self.datasets = []
        self.loaded_at = 0
        self.idx = None
        self.build_index()

    def load(self, sb):
        self.shops = sb.select("shops")
        self.tasks = {t["id"]: t for t in sb.select("tasks")}
        self.listings = sb.select("listings")
        links = load_photo_links()  # the database may not have the images column; the laptop copy fills the gap
        for l in self.listings:
            if not l.get("images"):
                imgs = (links.get(l.get("shop")) or {}).get(l.get("key")) or []
                if imgs:
                    l["images"] = imgs; l["image_count"] = len(imgs)
        self.orders = sb.select("orders")
        self.notes = {n["shop"] + "|" + n["buyer"]: n for n in sb.select("customer_notes")}
        self.datasets = sb.select("datasets")
        self.loaded_at = time.time()
        self.build_index()

    def build_index(self):
        idx = {"sku": {}, "title": {}, "last": {}, "lid": {}}
        for o in self.orders:
            if o.get("sku"):
                idx["sku"].setdefault(o["shop"] + "|" + o["sku"], []).append(o)
            idx["title"].setdefault(o["shop"] + "|" + norm(o.get("item_name")), []).append(o)
            d = o.get("sale_date")
            if d and (o["shop"] not in idx["last"] or d > idx["last"][o["shop"]]):
                idx["last"][o["shop"]] = d
            if o.get("listing_id") and o.get("sku"):
                idx["lid"][o["shop"] + "|" + o["sku"]] = o["listing_id"]
        self.idx = idx

    def shop_list(self):
        return sorted(self.shops, key=lambda s: (s.get("sort") or 0, str(s.get("name"))))

    def shop_name(self, sid):
        if not sid:
            return "All shops"
        for s in self.shops:
            if s["id"] == sid:
                return s["name"]
        return sid


def rev(o):
    t = o.get("item_total")
    if t is not None:
        try:
            return float(t)
        except Exception:
            pass
    return float(o.get("price") or 0) * int(o.get("quantity") or 1) - float(o.get("discount") or 0)


def is_open(t):
    return t.get("status") in ("todo", "doing")


def sort_key(t):
    return (t.get("due") or "9999", t.get("priority") or 2, str(t.get("title")))


def listing_stats(st, l, td):
    os_ = (l.get("sku") and st.idx["sku"].get(l["shop"] + "|" + l["sku"])) or st.idx["title"].get(l["shop"] + "|" + norm(l.get("title"))) or []
    r = dict(w0=0, w1=0, w2=0, total=0, revenue=0.0, rev30=0.0, last=None)
    for o in os_:
        q = int(o.get("quantity") or 1)
        d = diff(td, o["sale_date"]) if o.get("sale_date") else 9999
        r["total"] += q; r["revenue"] += rev(o)
        if d < 30:
            r["w0"] += q; r["rev30"] += rev(o)
        elif d < 60:
            r["w1"] += q
        elif d < 90:
            r["w2"] += q
        if o.get("sale_date") and (not r["last"] or o["sale_date"] > r["last"]):
            r["last"] = o["sale_date"]
    if l.get("active") is False:
        s = "INACTIVE"
    elif l["shop"] not in st.idx["last"]:
        s = "NEW"
    elif r["total"] == 0:
        s = "NEVER"
    elif r["w0"] == 0 and (r["w1"] + r["w2"]) > 0:
        s = "STOPPED"
    elif r["w1"] > 0 and r["w0"] < 0.6 * r["w1"]:
        s = "DECLINING"
    elif r["w0"] >= max(r["w1"], 1) and r["total"] >= 20:
        s = "WINNER"
    else:
        s = "OK"
    r["status"] = s
    r["risk"] = {"STOPPED": 0, "DECLINING": 1, "NEVER": 3, "OK": 4, "WINNER": 5, "NEW": 6, "INACTIVE": 7}[s] * 100000 - (r["w1"] + r["w2"]) * 10
    return r


def sales_summary(st, shop, td):
    r = dict(u0=0, u1=0, r0=0.0, r1=0.0, o0=set(), o1=set(), n=0)
    for o in st.orders:
        if shop != "all" and o["shop"] != shop:
            continue
        r["n"] += 1
        if not o.get("sale_date"):
            continue
        d = diff(td, o["sale_date"]); q = int(o.get("quantity") or 1)
        if 0 <= d < 30:
            r["u0"] += q; r["r0"] += rev(o); r["o0"].add(o["shop"] + str(o.get("order_id")))
        elif 30 <= d < 60:
            r["u1"] += q; r["r1"] += rev(o); r["o1"].add(o["shop"] + str(o.get("order_id")))
    return r


def customers(st, shop):
    m = {}
    for o in st.orders:
        if (shop != "all" and o["shop"] != shop) or not o.get("buyer"):
            continue
        k = o["shop"] + "|" + o["buyer"]
        c = m.get(k)
        if not c:
            c = m[k] = dict(key=k, shop=o["shop"], buyer=o["buyer"], orders=set(), units=0, revenue=0.0, first=None, last=None, country=o.get("country") or "", items=[])
        c["orders"].add(o.get("order_id") or o["transaction_id"]); c["units"] += int(o.get("quantity") or 1); c["revenue"] += rev(o); c["items"].append(o)
        d = o.get("sale_date")
        if d:
            if not c["first"] or d < c["first"]:
                c["first"] = d
            if not c["last"] or d > c["last"]:
                c["last"] = d
        if o.get("country"):
            c["country"] = o["country"]
    out = list(m.values())
    for c in out:
        c["order_count"] = len(c["orders"])
    return out


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def analyse_etsy(st, rows, shop, file):
    cols = list(rows[0].keys()) if rows else []
    base = dict(rows=rows, shop=shop, file=file, kind=None)
    if "Transaction ID" in cols and "Sale Date" in cols:
        mapped = []
        for r in rows:
            if not r.get("Transaction ID"):
                continue
            it = r.get("Item Total")
            mapped.append(dict(shop=shop, transaction_id=str(r["Transaction ID"]), order_id=str(r.get("Order ID") or ""), sale_date=etsy_date(r.get("Sale Date")),
                               item_name=str(r.get("Item Name") or "").strip(), listing_id=str(r.get("Listing ID") or ""), sku=str(r.get("SKU") or "").strip(),
                               quantity=int(money(r.get("Quantity")) or 1), price=money(r.get("Price")), discount=money(r.get("Discount Amount")),
                               item_total=money(it) if it not in (None, "") else None, currency=r.get("Currency") or "USD", coupon=str(r.get("Coupon Code") or ""),
                               buyer=str(r.get("Buyer") or "").strip(), country=str(r.get("Ship Country") or "")))
        have = {o["transaction_id"] for o in st.orders if o["shop"] == shop}
        new = sum(1 for m in mapped if m["transaction_id"] not in have)
        ds = sorted(m["sale_date"] for m in mapped if m["sale_date"])
        base.update(kind="orders", mapped=mapped, title=f"Order Items CSV: {len(mapped):,} order items",
                    detail=(f"From {nice(ds[0], True)} to {nice(ds[-1], True)}. " if ds else "") + f"{new:,} new, {len(mapped) - new:,} already imported (will be refreshed).")
        return base
    if "TITLE" in cols and "TAGS" in cols:
        seen, mapped = set(), []
        for r in rows:
            if not r.get("TITLE"):
                continue
            sku = str(r.get("SKU") or "").strip(); title = str(r["TITLE"]).strip()
            key = sku or "t:" + norm(title)[:180]
            if key in seen:
                key += f":{len(mapped)}"
            seen.add(key)
            imgs = [str(r.get(f"IMAGE{i}") or "").strip() for i in range(1, 11)]
            imgs = [u for u in imgs if u]
            mapped.append(dict(shop=shop, key=key, title=title, sku=sku, price=money(r.get("PRICE")), currency=r.get("CURRENCY_CODE") or "USD",
                               quantity=int(money(r.get("QUANTITY")) or 0) or None,
                               tags=", ".join(t.strip().replace("_", " ") for t in str(r.get("TAGS") or "").split(",") if t.strip()),
                               image_count=len(imgs), images=imgs, description=str(r.get("DESCRIPTION") or "")[:20000], active=True))
        have = {l["key"] for l in st.listings if l["shop"] == shop}
        new = sum(1 for m in mapped if m["key"] not in have); gone = len([k for k in have if k not in seen])
        base.update(kind="listings", mapped=mapped, title=f"Listings CSV: {len(mapped):,} active listings",
                    detail=f"{new:,} new, {len(mapped) - new:,} updated" + (f", {gone} no longer in the file (marked not active)" if gone else "") + ".")
        return base
    base.update(title="This is not an Etsy Order Items or Listings CSV",
                detail="Columns found: " + ", ".join(cols[:10]) + (", ..." if len(cols) > 10 else "") + ". You can keep it under Sheets instead.")
    return base


def format_spec(st):
    ids = ", ".join(f'"{s["id"]}" ({s["name"]})' for s in st.shop_list()) or '"your-shop-id"'
    return f"""PLAN FILE FORMAT (JSON) for my Etsy Shops CRM
{{
  "plan": "Plan name, e.g. 'PatternsByRish Instagram 31 Oct - 27 Nov'",
  "settings": {{                                   // optional; shops matched by id, only given fields change
    "shops": [{{"id":"shop-id", "schedules":[{{"name":"Instagram","until":"YYYY-MM-DD","warnDays":2,"planDays":28}}], "lastCsv":"YYYY-MM-DD", "csvEveryDays":14}}]
  }},
  "tasks": [
    {{
      "id": "unique-id (re-using an id updates that task instead of adding a new one)",
      "shop": "one of: {ids}. Empty for tasks that cover all shops",
      "title": "Short, specific action, e.g. 'R122: apply new title and tags'",
      "area": "listing | new | instagram | pinterest | payhip | review | data | ads | customer | other",
      "sku": "R122 (optional)",
      "due": "YYYY-MM-DD",
      "priority": 1,                               // 1 high, 2 normal, 3 low
      "steps": "Numbered steps, use \\n for new lines",
      "copy": [{{"label":"Caption","text":"..."}}],  // optional: exact text to copy-paste
      "followUpDays": 14                           // optional: adds a results-check task this many days after it is done
    }}
  ]
}}
Rules: write everything in English. One task per Instagram post (due = posting date) with caption, 10-12 SEO hashtags and alt text for each image in "copy". The SKU appears only in the DM line of the caption: 💌 Want this pattern? DM us "SKU" for details!"""


def report_text(st, sid):
    td = today()
    allt = sorted([t for t in st.tasks.values() if not sid or t.get("shop") == sid or not t.get("shop")], key=sort_key)
    ss = [s for s in st.shop_list() if not sid or s["id"] == sid]

    def line(t):
        s = f'- [{t.get("status")}] {t.get("due") or "-"} | ' + (st.shop_name(t["shop"]) + " | " if t.get("shop") else "") + (t["sku"] + " | " if t.get("sku") else "") + f'{t.get("title")} (id: {t["id"]})'
        if t.get("status") == "done" and t.get("done_at"):
            s += " | done " + t["done_at"][:10]
        if t.get("notes"):
            s += "\n    note: " + str(t["notes"]).replace("\n", " ")
        return s
    op = [t for t in allt if is_open(t)]
    dn = [t for t in allt if t.get("status") == "done" and t.get("done_at") and diff(td, t["done_at"][:10]) <= 30]
    sk = [t for t in allt if t.get("status") == "skipped" and (not t.get("updated_at") or diff(td, t["updated_at"][:10]) <= 30)]
    blocks = []
    for s in ss:
        x = sales_summary(st, s["id"], td)
        ls = [dict(l=l, **listing_stats(st, l, td)) for l in st.listings if l["shop"] == s["id"] and l.get("active") is not False]
        watch = sorted([r for r in ls if r["status"] in ("STOPPED", "DECLINING")], key=lambda r: r["risk"])[:12]
        win = sorted([r for r in ls if r["status"] == "WINNER"], key=lambda r: -r["w0"])[:5]
        b = f'- {s["name"]} (id: {s["id"]}' + (", " + s["url"] if s.get("url") else "") + ")\n"
        b += "\n".join(f'    {sc.get("name")}: scheduled until {sc.get("until") or "not set"}' for sc in (s.get("schedules") or [])) or "    no schedules"
        b += f'\n    Etsy data last imported: {s.get("last_csv") or "never"}\n'
        b += (f'    Sales last 30 days: {x["u0"]} items, {fmt_money(x["r0"])} ({pct(x["u0"], x["u1"])} items vs previous 30 days: {x["u1"]} items, {fmt_money(x["r1"])})' if x["n"] else "    No orders imported")
        if ls:
            b += f'\n    Listings: {len(ls)} active. Winners: ' + ("; ".join(f'{r["l"].get("sku") or ""} {r["l"]["title"][:50]} [{r["w0"]} in 30d]' for r in win) or "none")
            b += "\n    Needs attention (sales 90-61d / 60-31d / last 30d):\n" + ("\n".join(f'      {r["status"]} {r["l"].get("sku") or "-"} | {r["l"]["title"][:80]} | {r["w2"]}/{r["w1"]}/{r["w0"]}' + (" | note: " + r["l"]["notes"].replace("\n", " ") if r["l"].get("notes") else "") for r in watch) or "      none")
        else:
            b += "\n    No listings imported"
        blocks.append(b)
    return (f"ETSY SHOPS CRM REPORT · {td}\nScope: {st.shop_name(sid) if sid else 'All shops'}\n\nSHOPS\n" + ("\n".join(blocks) or "- none set up")
            + f"\n\nOPEN TASKS ({len(op)})\n" + ("\n".join(map(line, op)) or "- none")
            + f"\n\nDONE IN THE LAST 30 DAYS ({len(dn)})\n" + ("\n".join(map(line, dn)) or "- none")
            + f"\n\nSKIPPED IN THE LAST 30 DAYS ({len(sk)})\n" + ("\n".join(map(line, sk)) or "- none"))


def request_text(st, kind, sid="", i=0, scope=""):
    td = today()
    s = next((x for x in st.shops if x["id"] == sid), None)
    if kind == "sched" and s:
        schs = s.get("schedules") or []
        sc = schs[i] if i < len(schs) else {"name": "Instagram"}
        frm = add_days(sc["until"], 1) if sc.get("until") and diff(sc["until"], td) >= 0 else td
        pdays = int(sc.get("planDays") or 28); to = add_days(frm, pdays - 1)
        ask = (f'My {s["name"]} {sc.get("name")} posts are scheduled until {sc.get("until") or "(not set)"}. Make the {sc.get("name")} plan for {frm} to {to} ({pdays} days): '
               f'one task per post with the listing/SKU it promotes, caption, 10-12 SEO hashtags and alt text for each image. Pick listings using the sales data in the report '
               f'(push winners and listings that need attention, match the season). Add a final task "Schedule {sc.get("name")} posts {frm} to {to}" due {td}. '
               f'In settings, set {s["name"]}\'s {sc.get("name")} "until" to {to}. Use shop id "{s["id"]}" on every task.')
    elif kind == "listing":
        ask = (f'Here is one listing from my {s["name"] if s else ""} Etsy shop with its sales history. Suggest a new title (max 140 characters, keep the strongest keywords first), '
               "which tags to remove and add (13 tags, max 20 characters each) and photo changes. Return it as a plan file with one task, using copy fields for the new title, tags to remove and tags to add.")
    else:
        name = s["name"] if s else "all my shops"
        ask = (f"Make a 14-day plan ({td} to {add_days(td, 13)}) for {name}: listing refreshes (title, tags, photos) for the listings that need attention, new listings that fit the season, "
               "social posts, offers, and any results checks that are due. Use the sales data, open tasks and notes in the report" + (f', and shop id "{s["id"]}" on every task' if s else "") + ".")
    return f"{ask}\n\nGive me the plan as a .json file in the format below so I can import it into my CRM.\n\n{format_spec(st)}\n\n---\n{report_text(st, s['id'] if s else scope)}"


# ------------------------------------------------------------------ listing photos -> one folder per SKU
# Same layout as the old Image Organizer, so folders it made keep working:
#   <folder>/<SKU>/IMAGE1.jpg ... IMAGE10.jpg + manifest.json  (manifest: file -> url)
# Replaced or removed photos are moved to <folder>/_replaced/<date>/<SKU>/ (never deleted).
def photo_folder_name(l):
    sku = re.sub(r'[\\/:*?"<>|]', "-", str(l.get("sku") or "").strip()).strip(". ")
    if sku:
        return sku
    t = re.sub(r'[\\/:*?"<>|]', "-", str(l.get("title") or "listing")).strip()[:50].strip(". ")
    return "NO-SKU " + (t or "listing")


def photo_wanted(l):
    return {f"IMAGE{i}.jpg": u for i, u in enumerate([u for u in (l.get("images") or []) if u][:10], 1)}


def photo_manifest(folder):
    try:
        with open(os.path.join(folder, "manifest.json"), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def photo_check(root, l):
    """Fast local check (no internet). Returns (state, photos_to_download)."""
    folder = os.path.join(root, photo_folder_name(l))
    wanted = photo_wanted(l)
    if not os.path.isdir(folder):
        return "new", len(wanted)
    man = photo_manifest(folder)
    todo = sum(1 for f, u in wanted.items() if not (isinstance(man.get(f), dict) and man[f].get("url") == u and os.path.exists(os.path.join(folder, f))))
    extra = sum(1 for f in man if f not in wanted)
    return ("changed" if (todo or extra) else "same"), todo


class PhotoSync:
    def __init__(self, root, log, progress):
        self.root = root; self.log = log; self.progress = progress
        self.stop = threading.Event()
        self.stats = dict(new=0, changed=0, same=0, downloaded=0, moved=0, renamed=0, failed=0)
        self.session = requests.Session()
        self.verify = True

    def _move_away(self, name, path):
        dest = os.path.join(self.root, "_replaced", date.today().isoformat(), name)
        os.makedirs(dest, exist_ok=True)
        base = os.path.basename(path).replace(".move", ""); target = os.path.join(dest, base); n = 2
        while os.path.exists(target):
            b, e = os.path.splitext(base); target = os.path.join(dest, f"{b}_{n}{e}"); n += 1
        os.replace(path, target) if os.path.splitdrive(path)[0] == os.path.splitdrive(target)[0] else __import__("shutil").move(path, target)
        self.stats["moved"] += 1

    def _get(self, url, **kw):
        try:
            return self.session.get(url, timeout=30, verify=self.verify, **kw)
        except requests.exceptions.SSLError:
            self.verify = False
            try:
                import urllib3; urllib3.disable_warnings()
            except Exception:
                pass
            return self.session.get(url, timeout=30, verify=False, **kw)

    def _same_size(self, url, path):
        try:
            r = self.session.head(url, timeout=10, allow_redirects=True, verify=self.verify)
            n = int(r.headers.get("Content-Length", "-1"))
            return r.status_code == 200 and n > 0 and n == os.path.getsize(path)
        except Exception:
            return False

    def _download(self, url, path):
        tmp = path + ".part"
        for attempt in range(4):
            if self.stop.is_set():
                return False
            try:
                r = self._get(url, stream=True)
                if r.status_code != 200:
                    raise IOError(f"HTTP {r.status_code}")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if chunk:
                            f.write(chunk)
                if os.path.getsize(tmp) == 0:
                    raise IOError("empty file")
                os.replace(tmp, path)
                return True
            except Exception as e:
                err = str(e)
                time.sleep([1, 2, 4, 0][attempt])
        try:
            os.remove(tmp)
        except Exception:
            pass
        self.log(f"   failed: {os.path.basename(path)} ({err})")
        return False

    def sync_listing(self, l):
        from concurrent.futures import ThreadPoolExecutor
        name = photo_folder_name(l); folder = os.path.join(self.root, name); wanted = photo_wanted(l)
        is_new = not os.path.isdir(folder)
        os.makedirs(folder, exist_ok=True)
        for f in os.listdir(folder):
            if f.endswith(".part"):
                try:
                    os.remove(os.path.join(folder, f))
                except Exception:
                    pass
            elif f.endswith(".move"):
                self._move_away(name, os.path.join(folder, f))
        man = photo_manifest(folder)
        urls = set(wanted.values()); kept = set(); parked = {}; changes = 0
        for f in list(man.keys()):
            e = man.get(f) if isinstance(man.get(f), dict) else {}
            u = e.get("url"); p = os.path.join(folder, f)
            if not os.path.exists(p):
                man.pop(f, None); continue
            if wanted.get(f) == u:
                kept.add(f); continue
            if u in urls and u not in parked:
                os.replace(p, p + ".move"); parked[u] = p + ".move"
            else:
                self._move_away(name, p)
            changes += 1; man.pop(f, None)
        for f, u in wanted.items():
            p = os.path.join(folder, f)
            if f in kept or not os.path.exists(p):
                continue
            if u not in parked and self._same_size(u, p):
                man[f] = {"url": u, "downloaded_at": datetime.now().isoformat(timespec="seconds"), "adopted": True}; kept.add(f)
            else:
                self._move_away(name, p); changes += 1
        jobs = []
        for f, u in wanted.items():
            if f in kept:
                continue
            p = os.path.join(folder, f)
            if u in parked and os.path.exists(parked[u]):
                os.replace(parked.pop(u), p); man[f] = {"url": u, "downloaded_at": datetime.now().isoformat(timespec="seconds")}
                self.stats["renamed"] += 1; changes += 1
            else:
                jobs.append((f, u, p))
        for p in parked.values():
            if os.path.exists(p):
                self._move_away(name, p)
        if jobs:
            with ThreadPoolExecutor(max_workers=6) as ex:
                results = list(ex.map(lambda j: (j, self._download(j[1], j[2])), jobs))
            for (f, u, p), ok in results:
                if ok:
                    man[f] = {"url": u, "downloaded_at": datetime.now().isoformat(timespec="seconds")}; self.stats["downloaded"] += 1
                else:
                    self.stats["failed"] += 1
        tmp = os.path.join(folder, "manifest.json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=2)
        os.replace(tmp, os.path.join(folder, "manifest.json"))
        if is_new:
            self.stats["new"] += 1; return "NEW", len(jobs)
        if jobs or changes:
            self.stats["changed"] += 1; return "UPDATED", len(jobs)
        self.stats["same"] += 1; return "SKIP", 0

    def run(self, listings):
        names = set()
        total = len(listings)
        for i, l in enumerate(listings, 1):
            if self.stop.is_set():
                self.log("Stopped. Run again to continue where it left off."); break
            names.add(photo_folder_name(l).lower())
            try:
                state, n = self.sync_listing(l)
                if state != "SKIP":
                    self.log(f"{state:8} {photo_folder_name(l)}  ({n} photo{'s' if n != 1 else ''} downloaded)")
            except Exception as e:
                self.stats["failed"] += 1; self.log(f"ERROR    {photo_folder_name(l)}: {e}")
            self.progress(i, total)
        others = [d for d in os.listdir(self.root) if os.path.isdir(os.path.join(self.root, d)) and d != "_replaced" and d.lower() not in names] if os.path.isdir(self.root) else []
        st = self.stats
        summary = (f"New listings {st['new']} · updated {st['changed']} · unchanged {st['same']} · photos downloaded {st['downloaded']} · "
                   f"reordered {st['renamed']} · moved to _replaced {st['moved']} · failed {st['failed']}")
        try:
            with open(os.path.join(self.root, "_sync-log.txt"), "a", encoding="utf-8") as f:
                f.write(f"\n==== {datetime.now():%Y-%m-%d %H:%M}\n{summary}\n" + (f"Folders not in the current listings (left as they are): {', '.join(sorted(others))}\n" if others else ""))
        except Exception:
            pass
        return summary, others


# ------------------------------------------------------------------ the CRM UI
CRM_PAGES = ["Dashboard", "Tasks", "This week", "Listings", "Photos", "Orders & sales", "Customers", "Sheets", "Import data", "Shops & schedules", "Report for Claude", "Settings & updates"]
NAV = [("WORK", ["Dashboard", "Tasks", "This week"]),
       ("SHOP DATA", ["Listings", "Photos", "Orders & sales", "Customers", "Sheets"]),
       ("SETUP", ["Import data", "Shops & schedules", "Report for Claude", "Settings & updates"])]


class CRM:
    def __init__(self, app):
        self.app = app
        self.cfg = load_cfg()
        self.st = Store()
        self.sb = None
        self.shop = self.cfg.get("shop", "all")
        self.view = None
        self.ui = dict(task_status="open", task_area="", task_q="", lst_status="", lst_q="", cust_f="all", cust_q="", ord_q="", week=0)
        self.pending_plan = None
        self.etsy_import = None
        self.update_note = ""
        self._style()
        self._build_shell()
        self.show("Settings & updates")
        self.app.after(150, self._auto_connect)
        self.app.after(60000, self._tick)

    # ---------------- shell
    def _style(self):
        s = ttk.Style(self.app)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("CRM.Treeview", background=C["card"], fieldbackground=C["card"], foreground=C["ink"], rowheight=30, borderwidth=0, font=(FONT, 10))
        s.configure("CRM.Treeview.Heading", background=C["card2"], foreground=C["muted"], relief="flat", borderwidth=0, font=(FONT, 9, "bold"), padding=(8, 6))
        s.map("CRM.Treeview", background=[("selected", C["yellow"])], foreground=[("selected", C["on_y"])])
        s.map("CRM.Treeview.Heading", background=[("active", C["hover"])], foreground=[("active", C["yellow"])])
        s.layout("CRM.Treeview", [("CRM.Treeview.treearea", {"sticky": "nswe"})])

    def _build_shell(self):
        app = self.app
        try:
            app.title("Etsy Shops CRM")
        except Exception:
            pass
        tv = app.tabview
        tv.pack_forget()
        self.body = ctk.CTkFrame(app, fg_color=C["bg"], corner_radius=0)
        self.body.pack(fill="both", expand=True)
        side = ctk.CTkFrame(self.body, width=236, fg_color=C["side"], corner_radius=0)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.side = side
        tv.pack(in_=self.body, side="left", fill="both", expand=True, padx=(8, 8), pady=(0, 8))
        tv.lift(self.body)  # the tabview was created before body; raise it so body does not cover it
        try:
            tv.configure(fg_color=C["bg"], border_width=0)
            tv._segmented_button.grid_remove()
        except Exception:
            pass
        self.tabs = {}
        for name in CRM_PAGES:
            self.tabs[name] = tv.add(name)
        orig_set = tv.set

        def set_and_mark(name):
            orig_set(name)
            self._mark(name)
        tv.set = set_and_mark
        self._orig_set = orig_set

        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.pack(fill="x", padx=14, pady=(16, 10))
        ctk.CTkLabel(brand, text="E", width=36, height=36, corner_radius=8, fg_color=C["yellow"], text_color=C["on_y"], font=F(19, "bold")).pack(side="left")
        bt = ctk.CTkFrame(brand, fg_color="transparent")
        bt.pack(side="left", padx=10)
        ctk.CTkLabel(bt, text="Etsy Shops CRM", font=F(15, "bold"), anchor="w").pack(anchor="w")
        self.lbl_date = ctk.CTkLabel(bt, text=nice(today(), True), font=F(11, mono=True), text_color=C["muted"], anchor="w")
        self.lbl_date.pack(anchor="w")
        ctk.CTkLabel(side, text="SHOP", font=F(10, "bold"), text_color=C["faint"], anchor="w").pack(fill="x", padx=16, pady=(4, 2))
        self.shop_menu = ctk.CTkOptionMenu(side, values=["All shops"], command=self._shop_changed, height=32, font=F(12), dynamic_resizing=False)
        self.shop_menu.pack(fill="x", padx=14, pady=(0, 6))

        navf = ctk.CTkScrollableFrame(side, fg_color="transparent", scrollbar_button_color=C["side"], scrollbar_button_hover_color=C["line"])
        navf.pack(fill="both", expand=True, padx=4)
        self.nav_btns = {}
        all_names = list(getattr(tv, "_name_list", None) or getattr(tv, "_tab_dict", {}).keys())
        tool_names = [n for n in all_names if n not in CRM_PAGES]
        for sec, items in NAV:
            ctk.CTkLabel(navf, text=sec, font=F(10, "bold"), text_color=C["faint"], anchor="w", height=18).pack(fill="x", padx=12, pady=(10, 2))
            for name in (items if items is not None else tool_names):
                b = ctk.CTkButton(navf, text=name, anchor="w", height=29, corner_radius=7, fg_color="transparent", hover_color=C["hover"],
                                  text_color=C["muted"], font=F(13), command=lambda n=name: self.show(n))
                b.pack(fill="x", padx=6, pady=0)
                self.nav_btns[name] = b
        foot = ctk.CTkFrame(side, fg_color="transparent")
        foot.pack(fill="x", side="bottom", padx=14, pady=(6, 44))
        self.lbl_sync = ctk.CTkLabel(foot, text="Not connected", font=F(11, mono=True), text_color=C["faint"], anchor="w")
        self.lbl_sync.pack(fill="x")
        self.lbl_user = ctk.CTkLabel(foot, text="", font=F(11, mono=True), text_color=C["faint"], anchor="w")
        self.lbl_user.pack(fill="x")
        for w in ("btn_refresh", "lbl_version"):
            if hasattr(app, w):
                getattr(app, w).lift()
        if hasattr(app, "btn_refresh"):
            app.btn_refresh.configure(fg_color=C["card2"], hover_color=C["hover"], text_color=C["ink"], border_width=1, border_color=C["line"])
        self._refresh_shop_menu()

    def _mark(self, name):
        self.view = name
        for n, b in self.nav_btns.items():
            if n == name:
                b.configure(fg_color="#2a2410", text_color=C["yellow"], font=F(13, "bold"))
            else:
                b.configure(fg_color="transparent", text_color=C["muted"], font=F(13))

    def show(self, name):
        if name in CRM_PAGES and name != "Settings & updates" and not self.connected():
            name = "Settings & updates"
        if name == "Shops & schedules" and self.view != name:
            self._draft = None
        self.app.tabview.set(name)
        if name in CRM_PAGES:
            self.render()

    def connected(self):
        return bool(self.sb and self.sb.token)

    def _shop_changed(self, label):
        sid = "all"
        for s in self.st.shops:
            if s["name"] == label:
                sid = s["id"]
        self.shop = sid
        self.cfg["shop"] = sid; save_cfg(self.cfg)
        if self.view in CRM_PAGES:
            self.render()

    def _refresh_shop_menu(self):
        names = ["All shops"] + [s["name"] for s in self.st.shop_list()]
        self.shop_menu.configure(values=names)
        if self.shop != "all" and not any(s["id"] == self.shop for s in self.st.shops):
            self.shop = "all"
        self.shop_menu.set(self.st.shop_name(self.shop) if self.shop != "all" else "All shops")
        open_t = [t for t in self.tasks_in() if is_open(t)]
        td = today()
        due = len([t for t in open_t if t.get("due") and diff(t["due"], td) <= 0])
        over = len([t for t in open_t if t.get("due") and diff(t["due"], td) < 0])
        if "Dashboard" in self.nav_btns:
            self.nav_btns["Dashboard"].configure(text=f"Dashboard   ({due})" if due else "Dashboard", text_color=(C["bad"] if over and self.view != "Dashboard" else None) or (C["yellow"] if self.view == "Dashboard" else C["muted"]))
        if "Tasks" in self.nav_btns:
            self.nav_btns["Tasks"].configure(text=f"Tasks   ({len(open_t)})" if open_t else "Tasks")

    # ---------------- background work
    def bg(self, work, done=None, fail=None, busy=None):
        if busy:
            self.lbl_sync.configure(text=busy)

        def run():
            try:
                r = work()
            except Exception as e:  # noqa
                tb = traceback.format_exc()
                self.app.after(0, lambda e=e, tb=tb: (fail or self.fail)(e, tb))
                return
            if done:
                self.app.after(0, lambda r=r: done(r))
        threading.Thread(target=run, daemon=True).start()

    def fail(self, e, tb=""):
        msg = str(e) if isinstance(e, CrmError) else f"{type(e).__name__}: {e}"
        try:
            self.app.log_error_to_file(tb or msg)
        except Exception:
            pass
        self.lbl_sync.configure(text="Error")
        self.toast(msg, bad=True)

    def toast(self, msg, bad=False, ms=3200):
        try:
            if getattr(self, "_toast", None):
                self._toast.destroy()
        except Exception:
            pass
        t = ctk.CTkLabel(self.app, text="  " + msg + "  ", fg_color=C["bad"] if bad else C["yellow"], text_color="#140806" if bad else C["on_y"],
                         corner_radius=8, font=F(13, "bold"), height=36, wraplength=700)
        t.place(relx=0.5, rely=0.965, anchor="s")
        t.lift()
        self._toast = t
        self.app.after(ms + (2500 if bad else 0), lambda: t.winfo_exists() and t.destroy())

    def copy(self, text, what="Copied"):
        self.app.clipboard_clear()
        self.app.clipboard_append(text)
        self.app.update()
        self.toast(what)

    def synced(self):
        self.lbl_sync.configure(text="● Synced " + datetime.now().strftime("%H:%M"), text_color=C["ok"])

    # ---------------- connect / login
    def _make_sb(self):
        sb = Supa(self.cfg.get("url", ""), self.cfg.get("key", ""))

        def on_tok(s):
            self.cfg["refresh_token"] = s.refresh_token
            self.cfg["email"] = s.user.get("email", self.cfg.get("email", ""))
            save_cfg(self.cfg)
        sb.on_token = on_tok
        return sb

    def _auto_connect(self):
        if not (self.cfg.get("url") and self.cfg.get("key") and self.cfg.get("refresh_token")):
            self.render()
            return
        self.sb = self._make_sb()

        def work():
            self.sb.restore(self.cfg["refresh_token"])
            self.st.load(self.sb)
            return self.check_updates()

        def done(upd):
            self.after_login(upd)

        def failed(e, tb):
            self.sb = None
            self.lbl_sync.configure(text="Sign in needed", text_color=C["warn"])
            self.render()
        self.bg(work, done, failed, busy="Connecting...")

    def after_login(self, upd=None):
        self.synced()
        self.lbl_user.configure(text=self.sb.user.get("email", ""))
        self._refresh_shop_menu()
        if upd:
            self.update_note = upd
            messagebox.showinfo("Update installed", upd + "\n\nClick 'Refresh App' (bottom-left) to start the new version.")
        self.show("Dashboard" if self.st.shops else "Shops & schedules")

    def sync(self, then=None):
        if not self.connected():
            return
        self.bg(lambda: self.st.load(self.sb), lambda r: (self.synced(), self._refresh_shop_menu(), self.render(), then and then()), busy="Syncing...")

    def _tick(self):
        self.lbl_date.configure(text=nice(today(), True))
        if self.connected() and time.time() - self.st.loaded_at > 300 and self.view in ("Dashboard", "Tasks", "This week"):
            def work():
                self.st.shops = self.sb.select("shops")
                self.st.tasks = {t["id"]: t for t in self.sb.select("tasks")}
                self.st.loaded_at = time.time()
            self.bg(work, lambda r: (self.synced(), self._refresh_shop_menu(), self.render()), lambda e, tb: self.lbl_sync.configure(text="Not synced", text_color=C["warn"]))
        self.app.after(60000, self._tick)

    # ---------------- page plumbing
    def tasks_in(self):
        return [t for t in self.st.tasks.values() if self.shop == "all" or t.get("shop") == self.shop or not t.get("shop")]

    def scope(self):
        return "All shops" if self.shop == "all" else self.st.shop_name(self.shop)

    def page(self, scroll=True):
        tab = self.tabs[self.view]
        keep = None
        if getattr(self, "_last_view", None) == self.view:
            for w in tab.winfo_children():
                cv = getattr(w, "_parent_canvas", None)
                if cv is not None:
                    try:
                        keep = cv.yview()[0]
                    except Exception:
                        pass
        self._last_view = self.view
        for w in tab.winfo_children():
            w.destroy()
        if scroll:
            p = ctk.CTkScrollableFrame(tab, fg_color=C["bg"], corner_radius=0)
            if keep:
                self.app.after(30, lambda: p.winfo_exists() and p._parent_canvas.yview_moveto(keep))
        else:
            p = ctk.CTkFrame(tab, fg_color=C["bg"], corner_radius=0)
        p.pack(fill="both", expand=True)
        return p

    def render(self):
        if self.view not in CRM_PAGES:
            return
        try:
            self._refresh_shop_menu()
            getattr(self, "pg_" + slug(self.view).replace("-", "_"))()
        except Exception as e:
            self.fail(e, traceback.format_exc())

    # ---------------- widgets
    def head(self, p, title, sub="", right=None):
        f = ctk.CTkFrame(p, fg_color="transparent")
        f.pack(fill="x", padx=18, pady=(14, 10))
        l = ctk.CTkFrame(f, fg_color="transparent")
        l.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(l, text=title, font=F(24, "bold"), anchor="w").pack(anchor="w")
        if sub:
            ctk.CTkLabel(l, text=sub, font=F(13), text_color=C["muted"], anchor="w", justify="left", wraplength=780).pack(anchor="w")
        if right:
            r = ctk.CTkFrame(f, fg_color="transparent")
            r.pack(side="right", anchor="s")
            for args in right:
                self.btn(r, *args).pack(side="left", padx=(6, 0))
        return f

    def btn(self, parent, text, cmd, kind="default", small=False, width=None):
        kw = dict(text=text, command=cmd, height=28 if small else 34, corner_radius=7, font=F(12 if small else 13, "bold"))
        if width:
            kw["width"] = width
        if kind == "primary":
            kw.update(fg_color=C["yellow"], hover_color=C["yellow_h"], text_color=C["on_y"])
        elif kind == "good":
            kw.update(fg_color=C["ok"], hover_color=C["ok_h"], text_color="#06140c")
        elif kind == "ghost":
            kw.update(fg_color="transparent", hover_color=C["hover"], text_color=C["muted"])
        elif kind == "danger":
            kw.update(fg_color="transparent", hover_color="#2a1414", text_color=C["bad"], border_width=1, border_color="#4a2020")
        else:
            kw.update(fg_color=C["card2"], hover_color=C["hover"], text_color=C["ink"], border_width=1, border_color=C["line"])
        if small and not width:
            kw["width"] = 10
        return ctk.CTkButton(parent, **kw)

    def section(self, p, title, count=None):
        f = ctk.CTkFrame(p, fg_color="transparent")
        f.pack(fill="x", padx=18, pady=(12, 4))
        ctk.CTkLabel(f, text=title, font=F(15, "bold"), anchor="w").pack(side="left")
        if count is not None:
            ctk.CTkLabel(f, text=f" {count} ", font=F(11, mono=True), text_color=C["muted"], fg_color=C["card2"], corner_radius=9).pack(side="left", padx=8)
        return f

    def card(self, p, padx=18, pady=5, accent=None):
        outer = ctk.CTkFrame(p, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["line"])
        outer.pack(fill="x", padx=padx, pady=pady)
        if accent:
            ctk.CTkFrame(outer, width=4, height=10, fg_color=accent, corner_radius=2).pack(side="left", fill="y", padx=(1, 0), pady=1)
        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(side="left", fill="both", expand=True, padx=14, pady=11)
        return inner

    def kpis(self, p, items):
        g = ctk.CTkFrame(p, fg_color="transparent")
        g.pack(fill="x", padx=12, pady=4)
        for i, it in enumerate(items):
            g.grid_columnconfigure(i, weight=1, uniform="k")
            val, label = it[0], it[1]
            tone = it[2] if len(it) > 2 else ""
            sub = it[3] if len(it) > 3 else ""
            subtone = it[4] if len(it) > 4 else C["faint"]
            col = {"warn": C["yellow"], "bad": C["bad"], "ok": C["ok"]}.get(tone, C["ink"])
            bc = {"warn": "#5a4a14", "bad": "#5a2424"}.get(tone, C["line"])
            k = ctk.CTkFrame(g, fg_color=C["card"], corner_radius=10, border_width=1, border_color=bc)
            k.grid(row=0, column=i, sticky="nsew", padx=6, pady=4)
            ctk.CTkLabel(k, text=str(val), font=F(26, "bold"), text_color=col, anchor="w").pack(anchor="w", padx=14, pady=(10, 0))
            ctk.CTkLabel(k, text=label, font=F(12), text_color=C["muted"], anchor="w").pack(anchor="w", padx=14)
            if sub:
                ctk.CTkLabel(k, text=sub, font=F(11, mono=True), text_color=subtone, anchor="w").pack(anchor="w", padx=14, pady=(0, 10))
            else:
                ctk.CTkLabel(k, text="", height=6).pack()

    def empty(self, p, text):
        f = ctk.CTkFrame(p, fg_color="transparent", border_width=1, border_color=C["line"], corner_radius=10)
        f.pack(fill="x", padx=18, pady=5)
        ctk.CTkLabel(f, text=text, font=F(13), text_color=C["muted"], wraplength=820, justify="left", anchor="w").pack(fill="x", padx=14, pady=12)

    def table(self, parent, cols, rows, on_open=None, height=18, tags=None, sortable=True):
        """cols: [(id, label, width, anchor)], rows: [(iid, values, tag)]"""
        wrap = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["line"])
        tv = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings", style="CRM.Treeview", height=height, selectmode="browse")
        for cid, label, w, anchor in cols:
            tv.heading(cid, text=label.upper(), anchor=anchor)
            tv.column(cid, width=w, minwidth=40, anchor=anchor, stretch=(w >= 200))
        for tg, color in (tags or {}).items():
            tv.tag_configure(tg, foreground=color)
        tv.tag_configure("odd", background="#19191c")
        for n, (iid, vals, tg) in enumerate(rows):
            tv.insert("", "end", iid=str(iid), values=vals, tags=tuple(x for x in (tg, "odd" if n % 2 else None) if x))
        sb = ctk.CTkScrollbar(wrap, command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        sb.pack(side="right", fill="y", pady=6)
        if on_open:
            tv.bind("<Double-1>", lambda e: tv.focus() and on_open(tv.focus()))
            tv.bind("<Return>", lambda e: tv.focus() and on_open(tv.focus()))
        if sortable:
            def sort_by(c, rev_=False):
                data = [(tv.set(k, c), k) for k in tv.get_children("")]

                def key(x):
                    v = x[0].replace("$", "").replace(",", "")
                    try:
                        return (0, float(v))
                    except Exception:
                        return (1, x[0].lower())
                data.sort(key=key, reverse=rev_)
                for i, (_, k) in enumerate(data):
                    tv.move(k, "", i)
                tv.heading(c, command=lambda: sort_by(c, not rev_))
            for c in cols:
                tv.heading(c[0], command=lambda c=c[0]: sort_by(c, True))
        return wrap, tv

    def chips(self, parent, options, current, on_pick):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        for val, label in options:
            sel = val == current
            ctk.CTkButton(f, text=label, height=28, corner_radius=14, font=F(12, "bold"), width=10,
                          fg_color=C["yellow"] if sel else C["card2"], hover_color=C["yellow_h"] if sel else C["hover"],
                          text_color=C["on_y"] if sel else C["muted"], border_width=0 if sel else 1, border_color=C["line"],
                          command=lambda v=val: on_pick(v)).pack(side="left", padx=(0, 6))
        return f

    def toolbar(self, p):
        f = ctk.CTkFrame(p, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["line"])
        f.pack(fill="x", padx=18, pady=6)
        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)
        return inner

    def search(self, parent, value, on_change, placeholder="Search"):
        e = ctk.CTkEntry(parent, placeholder_text=placeholder, width=260, height=32)
        if value:
            e.insert(0, value)
        e.bind("<KeyRelease>", lambda ev: on_change(e.get()))
        return e

    # ---------------- task UI
    def task_meta(self, t):
        parts = []
        if self.shop == "all" and t.get("shop"):
            parts.append(self.st.shop_name(t["shop"]))
        if t.get("sku"):
            parts.append(t["sku"])
        parts.append(AREAS.get(t.get("area"), "Other"))
        if t.get("priority") == 1 and is_open(t):
            parts.append("High priority")
        parts.append(STATUS.get(t.get("status"), t.get("status")))
        if t.get("status") == "done" and t.get("done_at"):
            parts.append("done " + nice(t["done_at"][:10]))
        return "  ·  ".join(parts)

    def due_label(self, t, td):
        if not t.get("due"):
            return "No date", C["muted"]
        d = diff(t["due"], td)
        if not is_open(t):
            return nice(t["due"]), C["muted"]
        if d < 0:
            return f"{-d} day{'s' if d < -1 else ''} overdue", C["bad"]
        if d == 0:
            return "Today", C["yellow"]
        if d == 1:
            return "Tomorrow", C["muted"]
        return nice(t["due"]), C["muted"]

    def task_card(self, p, t):
        td = today()
        inner = self.card(p, accent=C["yellow"] if (t.get("priority") == 1 and is_open(t)) else None)
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        dl, dc = self.due_label(t, td)
        ctk.CTkLabel(top, text=dl, font=F(12, "bold", mono=True), text_color=dc).pack(side="right", anchor="n")
        ctk.CTkLabel(top, text=t.get("title", ""), font=F(14, "bold"), anchor="w", justify="left", wraplength=760,
                     text_color=C["faint"] if not is_open(t) else C["ink"]).pack(side="left", fill="x", expand=True, anchor="w")
        ctk.CTkLabel(inner, text=self.task_meta(t), font=F(11, mono=True), text_color=C["muted"], anchor="w").pack(fill="x", pady=(2, 6))
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        if is_open(t):
            if t.get("status") == "todo":
                self.btn(row, "Start", lambda: self.task_act(t, "start"), small=True).pack(side="left", padx=(0, 6))
            self.btn(row, "Mark done", lambda: self.task_act(t, "done"), "good", small=True).pack(side="left", padx=(0, 6))
            self.btn(row, "Tomorrow", lambda: self.task_act(t, "later"), small=True).pack(side="left", padx=(0, 6))
            self.btn(row, "Skip", lambda: self.task_act(t, "skip"), "ghost", small=True).pack(side="left", padx=(0, 6))
        else:
            self.btn(row, "Reopen", lambda: self.task_act(t, "undo"), small=True).pack(side="left", padx=(0, 6))
        self.btn(row, "Steps & copy text", lambda: self.task_dialog(t["id"]), small=True).pack(side="left", padx=(0, 6))

    def save_task(self, t, then=None):
        t["updated_at"] = now_iso()
        self.st.tasks[t["id"]] = t
        self.bg(lambda: self.sb.upsert("tasks", [t]), lambda r: (self.synced(), self._refresh_shop_menu(), self.render(), then and then()))

    def task_act(self, t, act, extra=None):
        t = dict(t)
        td = today()
        if act == "start":
            t.update(status="doing", started_at=now_iso())
        elif act == "done":
            t.update(status="done", done_at=now_iso())
        elif act == "skip":
            t.update(status="skipped")
        elif act == "undo":
            t.update(status="todo", done_at=None)
        elif act == "later":
            t.update(due=add_days(td, 1))
        elif act == "pull":
            t.update(due=td)
        elif act == "move":
            t.update(due=extra)
        followups = self.follow_ups(t, td) if act == "done" else []
        rows = [t] + followups
        for r in rows:
            r["updated_at"] = now_iso()
            self.st.tasks[r["id"]] = r

        def done(_):
            self.synced(); self._refresh_shop_menu(); self.render()
            if followups:
                self.toast(f"Done. {len(followups)} follow-up task{'s' if len(followups) > 1 else ''} added.")
        self.bg(lambda: self.sb.upsert("tasks", rows), done)

    def follow_ups(self, t, done_date):
        make = []
        base = dict(shop=t.get("shop") or "", status="todo", source="auto", parent=t["id"], copy=[], created_at=now_iso())
        fud = int(t.get("follow_up_days") or 0)
        if t.get("area") in ("listing", "new") and fud > 0:
            make.append(dict(id="fu-" + t["id"], title="Results check: " + re.sub(r":?\s*apply new title and tags$", "", str(t.get("title")), flags=re.I) + f" ({fud} days after the change)",
                             area="review", sku=t.get("sku") or "", due=add_days(done_date, fud), priority=2,
                             steps=f"1. Import fresh Etsy CSVs (Import data), then open Listings, or check Etsy Stats for the last {fud} days.\n2. Note views, favourites and orders, and whether they went up or down.\n3. Write it in the note and mark done. Claude sees it in your next report."))
        if t.get("area") == "new":
            nm = re.sub(r"^New listing:\s*", "", str(t.get("title")), flags=re.I)
            make.append(dict(id="xp-payhip-" + t["id"], title="Upload to Payhip: " + nm, area="payhip", due=add_days(done_date, 1), priority=1, steps="Upload the same files and photos to Payhip and check the price."))
            make.append(dict(id="xp-pin-" + t["id"], title="Pinterest pins: " + nm, area="pinterest", due=add_days(done_date, 1), priority=1, steps="Create 2-3 pins with different photos, each linking to the Etsy listing."))
            make.append(dict(id="xp-ig-" + t["id"], title="Add to Instagram plan: " + nm, area="instagram", due=add_days(done_date, 2), priority=2,
                             steps='Ask Claude for the caption, 10-12 hashtags and alt text. Put the SKU only in the DM line: 💌 Want this pattern? DM us "SKU" for details!'))
        return [dict(base, **m) for m in make if m["id"] not in self.st.tasks]

    def task_dialog(self, tid):
        t = self.st.tasks.get(tid)
        if not t:
            return
        d = ctk.CTkToplevel(self.app)
        d.title(t.get("title", "Task"))
        d.geometry("760x640")
        d.transient(self.app)
        d.after(50, d.lift)
        d.configure(fg_color=C["bg"])
        sf = ctk.CTkScrollableFrame(d, fg_color=C["bg"])
        sf.pack(fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(sf, text=t.get("title", ""), font=F(18, "bold"), wraplength=680, justify="left", anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        dl, dc = self.due_label(t, today())
        ctk.CTkLabel(sf, text=f"{dl}   ·   {self.task_meta(t)}", font=F(11, mono=True), text_color=C["muted"], anchor="w").pack(fill="x", padx=12)
        if t.get("steps"):
            ctk.CTkLabel(sf, text="STEPS", font=F(10, "bold"), text_color=C["faint"], anchor="w").pack(fill="x", padx=12, pady=(12, 2))
            tb = ctk.CTkTextbox(sf, height=150, font=F(13), wrap="word")
            tb.insert("1.0", t["steps"]); tb.configure(state="disabled")
            tb.pack(fill="x", padx=12)
        for c in (t.get("copy") or []):
            box = ctk.CTkFrame(sf, fg_color=C["card"], corner_radius=8, border_width=1, border_color=C["line"])
            box.pack(fill="x", padx=12, pady=(8, 0))
            hd = ctk.CTkFrame(box, fg_color="transparent")
            hd.pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(hd, text=str(c.get("label", "")).upper(), font=F(10, "bold"), text_color=C["faint"]).pack(side="left")
            self.btn(hd, "Copy", lambda txt=c.get("text", ""): self.copy(txt), "primary", small=True, width=64).pack(side="right")
            ctk.CTkLabel(box, text=c.get("text", ""), font=F(12, mono=True), wraplength=640, justify="left", anchor="w").pack(fill="x", padx=10, pady=(4, 10))
        ctk.CTkLabel(sf, text="YOUR NOTE (goes into the report for Claude)", font=F(10, "bold"), text_color=C["faint"], anchor="w").pack(fill="x", padx=12, pady=(14, 2))
        note = ctk.CTkTextbox(sf, height=80, font=F(13), wrap="word")
        note.insert("1.0", t.get("notes") or "")
        note.pack(fill="x", padx=12)
        row = ctk.CTkFrame(sf, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=10)

        def save_note():
            nt = dict(self.st.tasks[tid]); nt["notes"] = note.get("1.0", "end").strip()
            self.save_task(nt, lambda: self.toast("Note saved"))
        self.btn(row, "Save note", save_note, "primary").pack(side="left")
        ctk.CTkLabel(row, text="   Due date (YYYY-MM-DD)", text_color=C["muted"], font=F(12)).pack(side="left")
        due = ctk.CTkEntry(row, width=120)
        due.insert(0, t.get("due") or "")
        due.pack(side="left", padx=6)

        def move():
            v = due.get().strip()
            if not valid_date(v):
                messagebox.showwarning("Date", "Use the format YYYY-MM-DD, e.g. " + today(), parent=d); return
            self.task_act(self.st.tasks[tid], "move", v); d.destroy()
        self.btn(row, "Move", move).pack(side="left")
        row2 = ctk.CTkFrame(sf, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 12))
        cur = self.st.tasks[tid]
        if is_open(cur):
            if cur.get("status") == "todo":
                self.btn(row2, "Start", lambda: (self.task_act(cur, "start"), d.destroy())).pack(side="left", padx=(0, 6))
            self.btn(row2, "Mark done", lambda: (self.task_act(cur, "done"), d.destroy()), "good").pack(side="left", padx=(0, 6))
            self.btn(row2, "Skip", lambda: (self.task_act(cur, "skip"), d.destroy()), "ghost").pack(side="left", padx=(0, 6))
        else:
            self.btn(row2, "Reopen", lambda: (self.task_act(cur, "undo"), d.destroy())).pack(side="left", padx=(0, 6))

        def delete():
            if not messagebox.askyesno("Delete task", "Delete this task for good?", parent=d):
                return
            self.st.tasks.pop(tid, None)
            self.bg(lambda: self.sb.delete("tasks", {"id": tid}), lambda r: (self.toast("Task deleted"), self.render()))
            d.destroy()
        self.btn(row2, "Delete task", delete, "danger").pack(side="right")

    def new_task_dialog(self, preset=None):
        preset = preset or {}
        d = ctk.CTkToplevel(self.app)
        d.title("New task"); d.geometry("620x560"); d.transient(self.app); d.after(50, d.lift); d.configure(fg_color=C["bg"])
        f = ctk.CTkFrame(d, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=18, pady=14)
        ctk.CTkLabel(f, text="New task", font=F(20, "bold"), anchor="w").pack(fill="x")
        ent = {}

        def field(label, widget):
            ctk.CTkLabel(f, text=label, font=F(12), text_color=C["muted"], anchor="w").pack(fill="x", pady=(8, 2))
            widget.pack(fill="x")
            return widget
        ent["title"] = field("Task", ctk.CTkEntry(f, placeholder_text="e.g. R190: replace thumbnail"))
        shops = ["All shops / general"] + [s["name"] for s in self.st.shop_list()]
        ent["shop"] = field("Shop", ctk.CTkOptionMenu(f, values=shops))
        ent["shop"].set(self.st.shop_name(self.shop) if self.shop != "all" else shops[0])
        ent["due"] = field("Due date (YYYY-MM-DD)", ctk.CTkEntry(f)); ent["due"].insert(0, preset.get("due", today()))
        ent["area"] = field("Type", ctk.CTkOptionMenu(f, values=list(AREAS.values()))); ent["area"].set(AREAS.get(preset.get("area", "other")))
        ent["pri"] = field("Priority", ctk.CTkOptionMenu(f, values=["High", "Normal", "Low"])); ent["pri"].set("Normal")
        ent["sku"] = field("SKU (optional)", ctk.CTkEntry(f)); ent["sku"].insert(0, preset.get("sku", ""))
        ent["steps"] = field("Steps (optional)", ctk.CTkTextbox(f, height=90, wrap="word"))

        def create():
            title = ent["title"].get().strip(); due = ent["due"].get().strip()
            if not title:
                messagebox.showwarning("Task", "Write what needs to be done.", parent=d); return
            if due and not valid_date(due):
                messagebox.showwarning("Date", "Use the format YYYY-MM-DD.", parent=d); return
            sid = next((s["id"] for s in self.st.shops if s["name"] == ent["shop"].get()), "")
            area = next((k for k, v in AREAS.items() if v == ent["area"].get()), "other")
            t = dict(id="m-" + uuid.uuid4().hex[:10], shop=sid, title=title, due=due or None, area=area, sku=ent["sku"].get().strip(),
                     priority={"High": 1, "Normal": 2, "Low": 3}[ent["pri"].get()], status="todo", steps=ent["steps"].get("1.0", "end").strip(),
                     copy=[], source="manual", created_at=now_iso())
            self.save_task(t, lambda: self.toast("Task added"))
            d.destroy()
        self.btn(f, "Add task", create, "primary").pack(anchor="w", pady=14)

    # ---------------- alerts
    def alerts(self):
        td = today(); out = []
        allt = self.tasks_in(); op = [t for t in allt if is_open(t)]
        if not self.st.shops:
            out.append(("warn", "No shops set up yet", "Add your Etsy shops in Shops & schedules.", [("Open Shops & schedules", lambda: self.show("Shops & schedules"))]))
        over = [t for t in op if t.get("due") and diff(t["due"], td) < 0]
        if over:
            out.append(("bad", f"{len(over)} task{'s are' if len(over) > 1 else ' is'} overdue", ", ".join(x.get("sku") or x["title"] for x in over[:5]) + (", ..." if len(over) > 5 else "") + ". Do them today, move the date, or skip them.", []))
        for s in self.st.shop_list():
            if self.shop != "all" and s["id"] != self.shop:
                continue
            for i, sc in enumerate(s.get("schedules") or []):
                who = f'{s["name"]} · {sc.get("name")}'
                if not sc.get("until"):
                    out.append(("warn", who + ": no scheduled-until date", "Add the date your posts are scheduled until.", [("Open Shops & schedules", lambda: self.show("Shops & schedules"))]))
                    continue
                left = diff(sc["until"], td); warn = int(sc.get("warnDays") or 2); pdays = int(sc.get("planDays") or 28)
                acts = [("Copy request for Claude", lambda sid=s["id"], i=i: self.copy(request_text(self.st, "sched", sid, i), "Request copied. Paste it into a Claude chat.")),
                        ("Update date", lambda: self.show("Shops & schedules"))]
                if left < 0:
                    out.append(("bad", f"{who}: schedule ran out {-left} day{'s' if left < -1 else ''} ago", f"Nothing is scheduled. Ask Claude for the next {pdays} days, schedule the posts, then update the date.", acts))
                elif left <= warn:
                    out.append(("warn", f"{who}: scheduled only until {nice(sc['until'])}" + (" (last day today)" if left == 0 else f" ({left} day{'s' if left > 1 else ''} left)"),
                                f"Get the plan for {nice(add_days(sc['until'], 1))} to {nice(add_days(sc['until'], pdays))} from Claude, schedule it, then update the date.", acts))
            if s.get("last_csv"):
                ago = diff(td, s["last_csv"])
                if ago >= int(s.get("csv_every_days") or 14):
                    out.append(("info", f'{s["name"]}: Etsy data is {ago} days old', "Download Order Items CSV (this year) and Listings CSV from Etsy (Shop Manager › Settings › Options › Download Data) and import them.", [("Open Import data", lambda: self.show("Import data"))]))
            else:
                out.append(("info", f'{s["name"]}: no Etsy data imported yet', "Import this shop's Order Items CSV and Listings CSV to see sales, listing health and customers.", [("Open Import data", lambda: self.show("Import data"))]))
            ls = [l for l in self.st.listings if l["shop"] == s["id"] and l.get("active") is not False]
            if ls and s["id"] in self.st.idx["last"]:
                stt = [listing_stats(self.st, l, td)["status"] for l in ls]
                a, b = stt.count("STOPPED"), stt.count("DECLINING")
                if a + b:
                    out.append(("info", f'{s["name"]}: {a} listings stopped selling, {b} declining', "Open Listings to see which ones, then create tasks or ask Claude for a refresh plan.",
                                [("Open Listings", lambda sid=s["id"]: (self._set_shop(sid), self.ui.update(lst_status=""), self.show("Listings")))]))
        stuck = [t for t in allt if t.get("status") == "doing" and t.get("started_at") and diff(td, t["started_at"][:10]) >= 3]
        if stuck:
            out.append(("warn", f"{len(stuck)} task{'s have' if len(stuck) > 1 else ' has'} been in progress for 3+ days", ", ".join(x.get("sku") or x["title"] for x in stuck[:5]) + ". Finish them or add a note on what is blocking.", []))
        if self.st.shops and not over and not any(t.get("due") and 0 <= diff(t["due"], td) <= 3 for t in op):
            out.append(("info", "Nothing planned for the next 3 days", "Copy your report for Claude and ask for a two-week plan.",
                        [("Copy plan request", lambda: self.copy(request_text(self.st, "plan", "" if self.shop == "all" else self.shop, scope="" if self.shop == "all" else self.shop), "Request copied. Paste it into a Claude chat."))]))
        order = {"bad": 0, "warn": 1, "info": 2}
        return sorted(out, key=lambda a: order[a[0]])

    def _set_shop(self, sid):
        self.shop = sid; self.cfg["shop"] = sid; save_cfg(self.cfg); self._refresh_shop_menu()

    # =============================================================== pages
    def pg_dashboard(self):
        p = self.page()
        td = today(); allt = self.tasks_in(); op = [t for t in allt if is_open(t)]
        due = sorted([t for t in allt if t.get("status") == "todo" and t.get("due") and diff(t["due"], td) <= 0], key=sort_key)
        doing = sorted([t for t in allt if t.get("status") == "doing"], key=sort_key)
        up = sorted([t for t in allt if t.get("status") == "todo" and t.get("due") and 0 < diff(t["due"], td) <= 7], key=sort_key)
        over = len([t for t in op if t.get("due") and diff(t["due"], td) < 0])
        wk = len([t for t in allt if t.get("status") == "done" and t.get("done_at") and diff(td, t["done_at"][:10]) < 7])
        self.head(p, "Dashboard", f"{nice(td, True)} · {self.scope()}", [("Sync now", self.sync)])
        self.kpis(p, [(len(due), "Due today", "warn" if due else ""), (over, "Overdue", "bad" if over else ""), (len(doing), "In progress"), (wk, "Done in last 7 days", "ok")])
        ss = sales_summary(self.st, self.shop, td)
        if ss["n"]:
            cs = customers(self.st, self.shop); rep_ = len([c for c in cs if c["order_count"] >= 2])
            self.kpis(p, [(f'{ss["u0"]:,}', "Items sold, last 30 days", "", f'{pct(ss["u0"], ss["u1"])} vs previous 30', C["ok"] if ss["u0"] >= ss["u1"] else C["bad"]),
                          (fmt_money(ss["r0"]), "Sales, last 30 days", "", f'{pct(ss["r0"], ss["r1"])} vs previous 30', C["ok"] if ss["r0"] >= ss["r1"] else C["bad"]),
                          (f'{len(ss["o0"]):,}', "Orders, last 30 days", "", pct(len(ss["o0"]), len(ss["o1"])), C["ok"] if len(ss["o0"]) >= len(ss["o1"]) else C["bad"]),
                          (f"{rep_:,}", "Repeat customers", "", f"of {len(cs):,} buyers")])
        al = self.alerts()
        self.section(p, "Alerts", len(al))
        if not al:
            i = self.card(p, accent=C["ok"]); ctk.CTkLabel(i, text="All clear — no overdue tasks and no schedules running out.", font=F(13), anchor="w").pack(fill="x")
        for sev, title, desc, acts in al:
            i = self.card(p, accent={"bad": C["bad"], "warn": C["warn"], "info": C["yellow"]}[sev])
            ctk.CTkLabel(i, text=title, font=F(14, "bold"), anchor="w", wraplength=820, justify="left").pack(fill="x")
            ctk.CTkLabel(i, text=desc, font=F(12), text_color=C["muted"], anchor="w", wraplength=820, justify="left").pack(fill="x", pady=(2, 0))
            if acts:
                r = ctk.CTkFrame(i, fg_color="transparent"); r.pack(fill="x", pady=(8, 0))
                for n, (label, fn) in enumerate(acts):
                    self.btn(r, label, fn, "primary" if n == 0 else "default", small=True).pack(side="left", padx=(0, 6))
        self.section(p, "Due today", len(due))
        if due:
            for t in due:
                self.task_card(p, t)
        else:
            self.empty(p, "Nothing left for today. Check the alerts, or pull a task forward from the next 7 days." if self.st.tasks else "No tasks yet. Import a plan from Claude under Import data, or add one under Tasks.")
        self.section(p, "In progress", len(doing))
        if doing:
            for t in doing:
                self.task_card(p, t)
        else:
            self.empty(p, "Nothing half-done. Press Start when you begin a task so it stays here until it is finished.")
        self.section(p, "Next 7 days", len(up))
        if not up:
            self.empty(p, "Nothing planned for the next 7 days.")
        for t in up:
            i = self.card(p, pady=2)
            r = ctk.CTkFrame(i, fg_color="transparent"); r.pack(fill="x")
            ctk.CTkLabel(r, text=self.due_label(t, td)[0], width=110, anchor="w", font=F(12, mono=True), text_color=C["muted"]).pack(side="left")
            ctk.CTkLabel(r, text=((t.get("sku") + "  ") if t.get("sku") else "") + t["title"], anchor="w", font=F(13), wraplength=600, justify="left").pack(side="left", fill="x", expand=True)
            self.btn(r, "Do today", lambda t=t: self.task_act(t, "pull"), small=True).pack(side="right")
            self.btn(r, "Open", lambda t=t: self.task_dialog(t["id"]), "ghost", small=True).pack(side="right", padx=4)
        ctk.CTkFrame(p, height=30, fg_color="transparent").pack()

    def pg_tasks(self):
        p = self.page(scroll=False)
        u = self.ui; td = today(); q = u["task_q"].strip().lower()
        lst = sorted([t for t in self.tasks_in() if (u["task_status"] == "all" or (is_open(t) if u["task_status"] == "open" else t.get("status") == u["task_status"]))
                      and (not u["task_area"] or t.get("area") == u["task_area"]) and (not q or q in (t.get("title", "") + " " + (t.get("sku") or "")).lower())], key=sort_key)
        self.head(p, "Tasks", f"{len(lst)} task{'s' if len(lst) != 1 else ''} · {self.scope()} · double-click a task to open it", [("+ New task", self.new_task_dialog, "primary")])
        tb = self.toolbar(p)
        st_opts = [("open", "Open"), ("all", "All"), ("todo", "To do"), ("doing", "In progress"), ("done", "Done"), ("skipped", "Skipped")]
        self.chips(tb, st_opts, u["task_status"], lambda v: (u.update(task_status=v), self.render())).pack(side="left")
        am = ctk.CTkOptionMenu(tb, values=["All types"] + list(AREAS.values()), width=160, command=lambda v: (u.update(task_area=next((k for k, x in AREAS.items() if x == v), "")), self.render()))
        am.set(AREAS.get(u["task_area"], "All types")); am.pack(side="left", padx=10)
        s = self.search(tb, u["task_q"], lambda v: (u.update(task_q=v), self._debounce(self.render)), "Search title or SKU"); s.pack(side="right")
        rows = []
        for t in lst[:2000]:
            dl, _ = self.due_label(t, td)
            tag = "over" if dl.endswith("overdue") else ("today" if dl == "Today" else ("closed" if not is_open(t) else ""))
            rows.append((t["id"], (t.get("due") or "-", dl, self.st.shop_name(t["shop"]) if t.get("shop") else "-", t.get("sku") or "", t.get("title", ""), AREAS.get(t.get("area"), "Other"),
                                   {1: "High", 2: "Normal", 3: "Low"}.get(t.get("priority"), "Normal"), STATUS.get(t.get("status"), "")), tag))
        wrap, tv = self.table(p, [("due", "Due", 92, "w"), ("when", "When", 120, "w"), ("shop", "Shop", 130, "w"), ("sku", "SKU", 80, "w"), ("title", "Task", 420, "w"),
                                  ("type", "Type", 120, "w"), ("pri", "Priority", 80, "w"), ("status", "Status", 100, "w")], rows, on_open=self.task_dialog, height=22,
                              tags={"over": C["bad"], "today": C["yellow"], "closed": C["faint"]})
        wrap.pack(fill="both", expand=True, padx=18, pady=(4, 40))
        if q:
            self.app.after(10, lambda: (s.focus_set(), s.icursor("end")))

    def _debounce(self, fn, ms=350):
        if getattr(self, "_deb", None):
            self.app.after_cancel(self._deb)
        self._deb = self.app.after(ms, fn)

    def pg_this_week(self):
        p = self.page()
        td = today(); start = add_days(td, self.ui["week"] * 7); allt = self.tasks_in()
        self.head(p, "This week", f"{nice(start)} to {nice(add_days(start, 6))} · {self.scope()} · click a task to open it",
                  [("Previous", lambda: (self.ui.update(week=self.ui["week"] - 1), self.render())), ("This week", lambda: (self.ui.update(week=0), self.render())),
                   ("Next", lambda: (self.ui.update(week=self.ui["week"] + 1), self.render()))])
        g = ctk.CTkFrame(p, fg_color="transparent"); g.pack(fill="both", expand=True, padx=12)
        for i in range(7):
            dd = add_days(start, i); g.grid_columnconfigure(i, weight=1, uniform="d")
            items = [t for t in allt if t.get("due") == dd and t.get("status") != "skipped"]
            if dd == td:
                items += [t for t in allt if is_open(t) and t.get("due") and diff(t["due"], td) < 0]
            items.sort(key=sort_key)
            col = ctk.CTkFrame(g, fg_color=C["card"], corner_radius=10, border_width=2 if dd == td else 1, border_color=C["yellow"] if dd == td else C["line"])
            col.grid(row=0, column=i, sticky="nsew", padx=4, pady=4)
            hd = ctk.CTkFrame(col, fg_color="transparent"); hd.pack(fill="x", padx=8, pady=(8, 4))
            dobj = pdate(dd)
            ctk.CTkLabel(hd, text=DAYS[dobj.weekday()], font=F(15, "bold"), text_color=C["yellow"] if dd == td else C["ink"]).pack(side="left")
            ctk.CTkLabel(hd, text=f"{dobj.day} {MON[dobj.month - 1]}", font=F(11), text_color=C["muted"]).pack(side="right")
            if not items:
                ctk.CTkLabel(col, text="Free", font=F(12), text_color=C["faint"]).pack(anchor="w", padx=10, pady=(0, 10))
            for t in items:
                late = t.get("due") and diff(t["due"], dd) < 0
                txt = ("OVERDUE · " if late else "") + ((self.st.shop_name(t["shop"]) + " · ") if self.shop == "all" and t.get("shop") else "") + t["title"]
                mini = ctk.CTkLabel(col, text=txt, anchor="w", justify="left", font=F(11), fg_color=C["card2"], corner_radius=6, wraplength=132, cursor="hand2",
                                    text_color=C["faint"] if t.get("status") == "done" else (C["bad"] if late else C["ink"]))
                mini.pack(fill="x", padx=6, pady=2, ipady=4)
                mini.bind("<Button-1>", lambda e, t=t: self.task_dialog(t["id"]))
                mini.bind("<Enter>", lambda e, m=mini: m.configure(fg_color=C["hover"]))
                mini.bind("<Leave>", lambda e, m=mini: m.configure(fg_color=C["card2"]))
            ctk.CTkFrame(col, height=6, fg_color="transparent").pack()

    def pg_listings(self):
        p = self.page(scroll=False)
        td = today(); u = self.ui
        mine = [l for l in self.st.listings if self.shop == "all" or l["shop"] == self.shop]
        if not mine:
            self.head(p, "Listings", self.scope())
            self.empty(p, "No listings yet. Import the Listings CSV from Etsy under Import data, and the Order Items CSV too, so each listing shows its sales.")
            return
        rows_all = [dict(l=l, **listing_stats(self.st, l, td)) for l in mine]
        cnt = {}
        for r in rows_all:
            cnt[r["status"]] = cnt.get(r["status"], 0) + 1
        self.head(p, "Listings", "Sales per listing from your imported orders, sorted by what needs attention first. Double-click a listing to open it.", [("Export CSV", lambda: self.export_listings(rows_all))])
        self.kpis(p, [(cnt.get("WINNER", 0), "Winners", "ok"), (cnt.get("DECLINING", 0), "Declining", "warn"), (cnt.get("STOPPED", 0), "Stopped selling", "bad"), (cnt.get("NEVER", 0), "No sales yet")])
        tb = self.toolbar(p)
        opts = [("", "All")] + [(k, f"{LST_LABEL[k]} · {cnt[k]}") for k in ("STOPPED", "DECLINING", "NEVER", "WINNER", "OK", "INACTIVE", "NEW") if cnt.get(k)]
        self.chips(tb, opts, u["lst_status"], lambda v: (u.update(lst_status=v), self.render())).pack(side="left")
        s = self.search(tb, u["lst_q"], lambda v: (u.update(lst_q=v), self._debounce(self.render)), "Search title or SKU"); s.pack(side="right")
        q = u["lst_q"].strip().lower()
        rows = [r for r in rows_all if (not u["lst_status"] or r["status"] == u["lst_status"]) and (not q or q in (r["l"]["title"] + " " + (r["l"].get("sku") or "")).lower())]
        rows.sort(key=lambda r: (r["risk"], -r["total"]))
        self._lst_rows = {r["l"]["shop"] + "|" + r["l"]["key"]: r for r in rows}
        cols = [("sku", "SKU", 70, "w"), ("title", "Listing", 340, "w")] + ([("shop", "Shop", 120, "w")] if self.shop == "all" else []) + [
            ("price", "Price", 70, "e"), ("w2", "90-61d", 64, "e"), ("w1", "60-31d", 64, "e"), ("w0", "Last 30d", 74, "e"), ("tot", "Total", 60, "e"), ("last", "Last sale", 90, "w"), ("st", "Status", 140, "w")]
        data = []
        for r in rows:
            l = r["l"]
            vals = [l.get("sku") or "", l["title"]] + ([self.st.shop_name(l["shop"])] if self.shop == "all" else []) + [
                fmt_money(float(l["price"]), l.get("currency")) if l.get("price") is not None else "-", r["w2"], r["w1"], r["w0"], r["total"], short(r["last"]), LST_LABEL[r["status"]]]
            data.append((l["shop"] + "|" + l["key"], vals, r["status"]))
        wrap, tv = self.table(p, cols, data, on_open=self.listing_dialog, height=20, tags=LST_COLOR)
        wrap.pack(fill="both", expand=True, padx=18, pady=(4, 40))
        if q:
            self.app.after(10, lambda: (s.focus_set(), s.icursor("end")))

    def export_listings(self, rows):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"listings-{today()}.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["shop", "sku", "title", "price", "sales_90_61", "sales_60_31", "sales_last_30", "total", "last_sale", "status", "tags", "notes"])
            for r in rows:
                l = r["l"]
                w.writerow([self.st.shop_name(l["shop"]), l.get("sku"), l["title"], l.get("price"), r["w2"], r["w1"], r["w0"], r["total"], r["last"], LST_LABEL[r["status"]], l.get("tags"), l.get("notes")])
        self.toast("Exported")

    def listing_dialog(self, key):
        r = getattr(self, "_lst_rows", {}).get(key)
        if not r:
            return
        l = r["l"]
        d = ctk.CTkToplevel(self.app); d.title(l["title"][:80]); d.geometry("780x640"); d.transient(self.app); d.after(50, d.lift); d.configure(fg_color=C["bg"])
        sf = ctk.CTkScrollableFrame(d, fg_color=C["bg"]); sf.pack(fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(sf, text=l["title"], font=F(17, "bold"), wraplength=700, justify="left", anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(sf, text=f'{l.get("sku") or "no SKU"}  ·  {self.st.shop_name(l["shop"])}  ·  {fmt_money(float(l.get("price") or 0), l.get("currency"))}  ·  {l.get("image_count") or 0} photos',
                     font=F(11, mono=True), text_color=C["muted"], anchor="w").pack(fill="x", padx=12)
        ctk.CTkLabel(sf, text=LST_LABEL[r["status"]], font=F(13, "bold"), text_color=LST_COLOR[r["status"]], anchor="w").pack(fill="x", padx=12, pady=(8, 0))
        self.kpis(sf, [(r["w2"], "Sold 90-61 days ago"), (r["w1"], "Sold 60-31 days ago"), (r["w0"], "Sold last 30 days", "warn"), (r["total"], f'Total · last sale {short(r["last"])}')])
        ctk.CTkLabel(sf, text=f'Revenue (imported orders): {fmt_money(r["revenue"])}   ·   last 30 days: {fmt_money(r["rev30"])}', font=F(12), text_color=C["muted"], anchor="w").pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(sf, text="TAGS", font=F(10, "bold"), text_color=C["faint"], anchor="w").pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(sf, text=l.get("tags") or "-", font=F(12), wraplength=700, justify="left", anchor="w").pack(fill="x", padx=12)
        ctk.CTkLabel(sf, text="YOUR NOTES ON THIS LISTING", font=F(10, "bold"), text_color=C["faint"], anchor="w").pack(fill="x", padx=12, pady=(12, 2))
        note = ctk.CTkTextbox(sf, height=80, wrap="word"); note.insert("1.0", l.get("notes") or ""); note.pack(fill="x", padx=12)
        row = ctk.CTkFrame(sf, fg_color="transparent"); row.pack(fill="x", padx=12, pady=10)

        def save_note():
            l["notes"] = note.get("1.0", "end").strip()
            self.bg(lambda: self.sb.upsert("listings", [l]), lambda x: self.toast("Note saved"))
        self.btn(row, "Save note", save_note).pack(side="left", padx=(0, 6))

        def make_task():
            tid = f'm-lst-{slug(l["shop"])}-{slug(l.get("sku") or l["title"])}-{today()}'
            t = dict(id=tid, shop=l["shop"], title=(l["sku"] + ": " if l.get("sku") else "") + f'refresh listing ({LST_LABEL[r["status"]].lower()})', area="listing", sku=l.get("sku") or "",
                     due=today(), priority=1 if r["status"] == "STOPPED" else 2, status="todo",
                     steps=f'Sales 90-61d / 60-31d / last 30d: {r["w2"]} / {r["w1"]} / {r["w0"]}.\n1. Click "Copy for Claude" on this listing and ask for a new title and tags.\n2. Update the thumbnail and first 2 photos.\n3. Apply the changes in Etsy and mark done.',
                     copy=[{"label": "Current title", "text": l["title"]}, {"label": "Current tags", "text": l.get("tags") or ""}], follow_up_days=14, source="manual", created_at=now_iso())
            self.save_task(t, lambda: self.toast("Task created for today"))
        self.btn(row, "Create refresh task", make_task, "primary").pack(side="left", padx=(0, 6))
        self.btn(row, "Copy for Claude", lambda: self.copy(request_text(self.st, "listing", l["shop"]) + f'\n\nLISTING\nShop: {self.st.shop_name(l["shop"])}\nSKU: {l.get("sku") or "-"}\nTitle: {l["title"]}\nTags: {l.get("tags")}\nPrice: {l.get("price")}\nPhotos: {l.get("image_count")}\nSales 90-61d / 60-31d / last 30d: {r["w2"]} / {r["w1"]} / {r["w0"]} (total {r["total"]}, last sale {r["last"] or "never"})\nMy notes: {l.get("notes") or "-"}\nDescription (start): {str(l.get("description") or "")[:600]}', "Copied. Paste it into a Claude chat.")).pack(side="left", padx=(0, 6))
        lid = self.st.idx["lid"].get(l["shop"] + "|" + (l.get("sku") or ""))
        if lid:
            self.btn(row, "Open on Etsy", lambda: __import__("webbrowser").open(f"https://www.etsy.com/listing/{lid}")).pack(side="left", padx=(0, 6))
        folder = None
        root = self.photo_root(l["shop"])
        if root and os.path.isdir(os.path.join(root, photo_folder_name(l))):
            folder = os.path.join(root, photo_folder_name(l))
        if folder:
            self.btn(row, "Open photos folder", lambda: self._open_path(folder)).pack(side="left", padx=(0, 6))
        imgs = l.get("images") or []
        if imgs:
            ctk.CTkLabel(sf, text="PHOTO LINKS", font=F(10, "bold"), text_color=C["faint"], anchor="w").pack(fill="x", padx=12, pady=(8, 2))
            for n, url in enumerate(imgs, 1):
                ctk.CTkButton(sf, text=f"Photo {n}", anchor="w", height=26, font=F(12), fg_color="transparent", hover_color=C["hover"], text_color=C["yellow"],
                              command=lambda url=url: __import__("webbrowser").open(url)).pack(fill="x", padx=12)

    def _open_path(self, path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa
            else:
                import subprocess; subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.toast(str(e), bad=True)

    def pg_orders_sales(self):
        p = self.page()
        td = today(); os_ = [o for o in self.st.orders if self.shop == "all" or o["shop"] == self.shop]
        if not os_:
            self.head(p, "Orders & sales", self.scope()); self.empty(p, "No orders yet. Import the Order Items CSV from Etsy under Import data."); return
        ss = sales_summary(self.st, self.shop, td)
        self.head(p, "Orders & sales", f"{self.scope()} · {len(os_):,} order items imported", [("Export CSV", lambda: self.export_orders(os_))])
        self.kpis(p, [(f'{ss["u0"]:,}', "Items, last 30 days", "", f'{pct(ss["u0"], ss["u1"])} vs previous 30', C["ok"] if ss["u0"] >= ss["u1"] else C["bad"]),
                      (fmt_money(ss["r0"]), "Sales, last 30 days", "", pct(ss["r0"], ss["r1"]), C["ok"] if ss["r0"] >= ss["r1"] else C["bad"]),
                      (f'{len(ss["o0"]):,}', "Orders, last 30 days"), (fmt_money(ss["r0"] / len(ss["o0"])) if ss["o0"] else "-", "Average order, last 30 days")])
        months, weeks, items = {}, {}, {}
        for o in os_:
            dd = o.get("sale_date")
            if not dd:
                continue
            m = months.setdefault(dd[:7], dict(u=0, o=set(), r=0.0, disc=0.0))
            q = int(o.get("quantity") or 1); m["u"] += q; m["o"].add(o["shop"] + str(o.get("order_id"))); m["r"] += rev(o); m["disc"] += float(o.get("discount") or 0)
            dobj = pdate(dd); wend = (dobj + timedelta(days=6 - dobj.weekday())).isoformat(); weeks[wend] = weeks.get(wend, 0) + q
            if diff(td, dd) < 30:
                items[o.get("item_name")] = items.get(o.get("item_name"), 0) + q
        tdo = pdate(td); cur_end = (tdo + timedelta(days=6 - tdo.weekday())).isoformat()
        wk = [(add_days(cur_end, -7 * i), weeks.get(add_days(cur_end, -7 * i), 0)) for i in range(19, -1, -1)]
        self.section(p, "Items sold per week (last 20 weeks)")
        cf = ctk.CTkFrame(p, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["line"]); cf.pack(fill="x", padx=18, pady=4)
        cv = tk.Canvas(cf, height=190, bg=C["card"], highlightthickness=0); cv.pack(fill="x", padx=14, pady=12)

        def draw(ev=None):
            cv.delete("all"); w = max(cv.winfo_width(), 400); h = 190; mx = max(1, max(v for _, v in wk)); bw = (w - 10) / len(wk)
            cv.create_line(0, h - 22, w, h - 22, fill=C["line"])
            for i, (e, v) in enumerate(wk):
                x0 = 5 + i * bw + 3; x1 = 5 + (i + 1) * bw - 3; y = h - 22 - (v / mx) * (h - 50)
                cv.create_rectangle(x0, y, x1, h - 22, fill=C["yellow"] if e != cur_end else C["card2"], outline=C["yellow"] if e == cur_end else "", dash=(3, 2) if e == cur_end else None)
                if i % 4 == 0 or i == len(wk) - 1:
                    cv.create_text((x0 + x1) / 2, h - 10, text=short(add_days(e, -6))[:6], fill=C["muted"], font=(MONO, 8))
                if v == mx:
                    cv.create_text((x0 + x1) / 2, y - 9, text=str(v), fill=C["ink"], font=(MONO, 9, "bold"))
        cv.bind("<Configure>", draw)
        two = ctk.CTkFrame(p, fg_color="transparent"); two.pack(fill="x", padx=12, pady=6)
        two.grid_columnconfigure(0, weight=1, uniform="t"); two.grid_columnconfigure(1, weight=1, uniform="t")
        a = ctk.CTkFrame(two, fg_color="transparent"); a.grid(row=0, column=0, sticky="nsew", padx=6)
        ctk.CTkLabel(a, text="By month", font=F(15, "bold"), anchor="w").pack(fill="x", pady=(0, 4))
        mrows = [(m, (f"{MON[int(m[5:]) - 1]} {m[:4]}", f'{x["u"]:,}', f'{len(x["o"]):,}', fmt_money(x["r"]), fmt_money(x["disc"])), None) for m, x in sorted(months.items(), reverse=True)]
        w1, _ = self.table(a, [("m", "Month", 100, "w"), ("u", "Items", 70, "e"), ("o", "Orders", 70, "e"), ("r", "Sales", 100, "e"), ("d", "Discounts", 100, "e")], mrows, height=min(12, max(3, len(mrows))), sortable=False)
        w1.pack(fill="x")
        b = ctk.CTkFrame(two, fg_color="transparent"); b.grid(row=0, column=1, sticky="nsew", padx=6)
        ctk.CTkLabel(b, text="Top items, last 30 days", font=F(15, "bold"), anchor="w").pack(fill="x", pady=(0, 4))
        trows = [(i, (n, v), None) for i, (n, v) in enumerate(sorted(items.items(), key=lambda x: -x[1])[:12])]
        w2, _ = self.table(b, [("n", "Item", 360, "w"), ("v", "Sold", 60, "e")], trows, height=min(12, max(3, len(trows))), sortable=False)
        w2.pack(fill="x")
        self.section(p, "Recent order items (newest 300)")
        tb = self.toolbar(p)
        holder = ctk.CTkFrame(p, fg_color="transparent"); holder.pack(fill="x", padx=18, pady=(0, 40))

        def fill(qv=""):
            for w in holder.winfo_children():
                w.destroy()
            q = qv.strip().lower()
            lst = [o for o in os_ if not q or q in " ".join(str(o.get(k) or "") for k in ("item_name", "buyer", "sku", "coupon", "order_id")).lower()]
            lst = sorted(lst, key=lambda o: str(o.get("sale_date")), reverse=True)[:300]
            rows = [(f'{o["shop"]}|{o["transaction_id"]}', [short(o.get("sale_date"))] + ([self.st.shop_name(o["shop"])] if self.shop == "all" else []) + [o.get("item_name"), o.get("buyer"), o.get("quantity") or 1, fmt_money(rev(o), o.get("currency")), o.get("coupon") or ""], None) for o in lst]
            cols = [("d", "Date", 90, "w")] + ([("s", "Shop", 120, "w")] if self.shop == "all" else []) + [("i", "Item", 420, "w"), ("b", "Buyer", 200, "w"), ("q", "Qty", 50, "e"), ("t", "Total", 90, "e"), ("c", "Coupon", 100, "w")]
            w3, _ = self.table(holder, cols, rows, height=14); w3.pack(fill="x")
        se = self.search(tb, self.ui["ord_q"], lambda v: (self.ui.update(ord_q=v), self._debounce(lambda: fill(v))), "Search item, buyer, SKU, coupon"); se.pack(side="left")
        fill(self.ui["ord_q"])

    def export_orders(self, os_):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"orders-{today()}.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["shop", "date", "order_id", "transaction_id", "item", "sku", "quantity", "total", "currency", "coupon", "buyer", "country"])
            for o in os_:
                w.writerow([self.st.shop_name(o["shop"]), o.get("sale_date"), o.get("order_id"), o.get("transaction_id"), o.get("item_name"), o.get("sku"), o.get("quantity"), round(rev(o), 2), o.get("currency"), o.get("coupon"), o.get("buyer"), o.get("country")])
        self.toast("Exported")

    def pg_customers(self):
        p = self.page(scroll=False)
        cs = customers(self.st, self.shop); td = today(); u = self.ui
        if not cs:
            self.head(p, "Customers", self.scope()); self.empty(p, "Customers are built from your imported Etsy orders. Import the Order Items CSV under Import data."); return
        rep_ = [c for c in cs if c["order_count"] >= 2]; act = [c for c in cs if c["last"] and diff(td, c["last"]) < 30]
        self.head(p, "Customers", f"Everyone who bought from {self.scope()}, with their history and your notes. Double-click a customer to open them.", [("Export CSV", lambda: self.export_customers(cs))])
        self.kpis(p, [(f"{len(cs):,}", "Buyers"), (f"{len(rep_):,}", "Repeat buyers (2+ orders)", "ok"), (f"{round(len(rep_) / len(cs) * 100) if cs else 0}%", "Repeat rate"), (f"{len(act):,}", "Bought in last 30 days")])
        tb = self.toolbar(p)
        self.chips(tb, [("all", "All"), ("repeat", "Repeat buyers"), ("recent", "Last 30 days"), ("noted", "With notes")], u["cust_f"], lambda v: (u.update(cust_f=v), self.render())).pack(side="left")
        s = self.search(tb, u["cust_q"], lambda v: (u.update(cust_q=v), self._debounce(self.render)), "Search name or username"); s.pack(side="right")
        q = u["cust_q"].strip().lower()
        if u["cust_f"] == "repeat":
            cs = rep_
        elif u["cust_f"] == "recent":
            cs = act
        elif u["cust_f"] == "noted":
            cs = [c for c in cs if (self.st.notes.get(c["key"]) or {}).get("notes") or (self.st.notes.get(c["key"]) or {}).get("tags")]
        if q:
            cs = [c for c in cs if q in c["buyer"].lower()]
        cs = sorted(cs, key=lambda c: -c["revenue"])
        self._cust = {c["key"]: c for c in cs}
        rows = [(c["key"], [c["buyer"]] + ([self.st.shop_name(c["shop"])] if self.shop == "all" else []) + [c["order_count"], c["units"], fmt_money(c["revenue"]), short(c["first"]), short(c["last"]), c["country"],
                                                                                                    (self.st.notes.get(c["key"]) or {}).get("tags") or ""], "rep" if c["order_count"] >= 2 else None) for c in cs[:3000]]
        cols = [("b", "Buyer", 260, "w")] + ([("s", "Shop", 120, "w")] if self.shop == "all" else []) + [("o", "Orders", 70, "e"), ("i", "Items", 60, "e"), ("sp", "Spent", 90, "e"), ("f", "First", 90, "w"), ("l", "Last", 90, "w"), ("c", "Country", 130, "w"), ("t", "Tags", 120, "w")]
        wrap, _ = self.table(p, cols, rows, on_open=self.customer_dialog, height=20, tags={"rep": C["ok"]})
        wrap.pack(fill="both", expand=True, padx=18, pady=(4, 40))
        if q:
            self.app.after(10, lambda: (s.focus_set(), s.icursor("end")))

    def export_customers(self, cs):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"customers-{today()}.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["shop", "buyer", "orders", "items", "spent", "first", "last", "country", "tags", "notes"])
            for c in cs:
                n = self.st.notes.get(c["key"]) or {}
                w.writerow([self.st.shop_name(c["shop"]), c["buyer"], c["order_count"], c["units"], round(c["revenue"], 2), c["first"], c["last"], c["country"], n.get("tags", ""), n.get("notes", "")])
        self.toast("Exported")

    def customer_dialog(self, key):
        c = getattr(self, "_cust", {}).get(key)
        if not c:
            return
        n = self.st.notes.get(key) or {}
        d = ctk.CTkToplevel(self.app); d.title(c["buyer"]); d.geometry("760x600"); d.transient(self.app); d.after(50, d.lift); d.configure(fg_color=C["bg"])
        f = ctk.CTkFrame(d, fg_color="transparent"); f.pack(fill="both", expand=True, padx=16, pady=12)
        ctk.CTkLabel(f, text=c["buyer"], font=F(18, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(f, text=f'{self.st.shop_name(c["shop"])}  ·  {c["order_count"]} orders  ·  {c["units"]} items  ·  {fmt_money(c["revenue"])}  ·  {c["country"]}  ·  first {short(c["first"])}, last {short(c["last"])}',
                     font=F(11, mono=True), text_color=C["muted"], anchor="w").pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(f, text="Tags (comma separated, e.g. VIP, wholesale)", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x")
        tags = ctk.CTkEntry(f); tags.insert(0, n.get("tags") or ""); tags.pack(fill="x")
        ctk.CTkLabel(f, text="Notes", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x", pady=(8, 0))
        notes = ctk.CTkTextbox(f, height=70, wrap="word"); notes.insert("1.0", n.get("notes") or ""); notes.pack(fill="x")
        row = ctk.CTkFrame(f, fg_color="transparent"); row.pack(fill="x", pady=8)

        def save():
            nn = dict(shop=c["shop"], buyer=c["buyer"], notes=notes.get("1.0", "end").strip(), tags=tags.get().strip(), updated_at=now_iso())
            self.st.notes[key] = nn
            self.bg(lambda: self.sb.upsert("customer_notes", [nn]), lambda r: (self.toast("Saved"), self.render()))
        self.btn(row, "Save", save, "primary").pack(side="left", padx=(0, 6))

        def follow():
            t = dict(id="m-cust-" + uuid.uuid4().hex[:8], shop=c["shop"], title="Follow up with customer: " + c["buyer"], area="customer", due=add_days(today(), 1), priority=2, status="todo",
                     steps="Message this buyer on Etsy (thank-you, review request, or a repeat-buyer coupon).", copy=[], source="manual", created_at=now_iso())
            self.save_task(t, lambda: self.toast("Follow-up task added for tomorrow"))
        self.btn(row, "Create follow-up task", follow).pack(side="left")
        rows = [(i, (short(o.get("sale_date")), o.get("item_name"), fmt_money(rev(o), o.get("currency")), o.get("coupon") or ""), None) for i, o in enumerate(sorted(c["items"], key=lambda o: str(o.get("sale_date")), reverse=True))]
        w, _ = self.table(f, [("d", "Date", 90, "w"), ("i", "Item", 420, "w"), ("t", "Total", 90, "e"), ("c", "Coupon", 100, "w")], rows, height=10)
        w.pack(fill="both", expand=True, pady=6)

    # ---------- photos
    def photo_root(self, sid):
        return (self.cfg.get("photo_folders") or {}).get(sid) or ""

    def pg_photos(self):
        p = self.page()
        self.head(p, "Photos", "Saves every listing photo into one folder per SKU on this laptop. It uses the latest Listings CSV you imported. "
                               "Only new or changed photos are downloaded; replaced ones go to _replaced, nothing is deleted.")
        shops = [s for s in self.st.shop_list() if self.shop == "all" or s["id"] == self.shop]
        if not shops:
            self.empty(p, "Add your shops first in Shops & schedules."); return
        running = getattr(self, "_photo_job", None)
        for s in shops:
            ls = [l for l in self.st.listings if l["shop"] == s["id"] and l.get("active") is not False]
            with_img = [l for l in ls if l.get("images")]
            root = self.photo_root(s["id"])
            self.section(p, s["name"])
            i = self.card(p, accent=C["yellow"])
            top = ctk.CTkFrame(i, fg_color="transparent"); top.pack(fill="x")
            ctk.CTkLabel(top, text="Save photos in", font=F(11), text_color=C["muted"], anchor="w").pack(anchor="w")
            row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", pady=(2, 0))
            ctk.CTkLabel(row, text=root or "No folder chosen yet", font=F(13, mono=True), text_color=C["ink"] if root else C["warn"], anchor="w").pack(side="left", fill="x", expand=True)
            self.btn(row, "Choose folder...", lambda sid=s["id"]: self.choose_photo_folder(sid), small=True).pack(side="right")
            if root and os.path.isdir(root):
                self.btn(row, "Open folder", lambda r=root: self._open_path(r), "ghost", small=True).pack(side="right", padx=6)
            if not ls:
                ctk.CTkLabel(i, text="No listings imported for this shop yet. Import its Listings CSV under Import data.", font=F(12), text_color=C["warn"], anchor="w").pack(fill="x", pady=(10, 0))
                self.btn(i, "Open Import data", lambda: self.show("Import data"), small=True).pack(anchor="w", pady=(6, 0))
                continue
            if not with_img:
                ctk.CTkLabel(i, text="No photo links on this laptop yet. Go to Import data and import the newest Listings CSV of this shop once, then come back here and click Sync photos now.",
                             font=F(12), text_color=C["warn"], anchor="w", wraplength=820, justify="left").pack(fill="x", pady=(10, 0))
                continue
            imp = max((str(l.get("imported_at") or "") for l in ls), default="")
            info = f"{len(with_img)} listings with {sum(len(l.get('images') or []) for l in with_img):,} photos · from the Listings CSV imported {short(imp[:10]) if imp else '-'}"
            ctk.CTkLabel(i, text=info, font=F(12), text_color=C["muted"], anchor="w").pack(fill="x", pady=(10, 0))
            if root:
                cnt = {"new": 0, "changed": 0, "same": 0}; todo = 0
                for l in with_img:
                    stt, n = photo_check(root, l); cnt[stt] += 1; todo += n
                self.kpis(i, [(cnt["new"], "New listings (no folder yet)", "warn" if cnt["new"] else ""), (cnt["changed"], "Listings with changed photos", "warn" if cnt["changed"] else ""),
                              (cnt["same"], "Up to date (skipped)", "ok"), (f"{todo:,}", "Photos to download")])
            last = (self.cfg.get("photo_last") or {}).get(s["id"])
            if last:
                ctk.CTkLabel(i, text="Last sync: " + last, font=F(11, mono=True), text_color=C["faint"], anchor="w", wraplength=820, justify="left").pack(fill="x", pady=(4, 0))
            act = ctk.CTkFrame(i, fg_color="transparent"); act.pack(fill="x", pady=(10, 0))
            if running and running["shop"] == s["id"]:
                self.btn(act, "Stop", lambda: running["sync"].stop.set(), "danger").pack(side="left")
                running["bar_parent"] = i
            elif running:
                ctk.CTkLabel(act, text="Another shop is syncing...", text_color=C["muted"]).pack(side="left")
            else:
                self.btn(act, "Sync photos now", lambda sid=s["id"]: self.start_photo_sync(sid), "primary").pack(side="left")
                self.btn(act, "Re-check", self.render, small=True).pack(side="left", padx=8)
        if running:
            box = self.card(p)
            ctk.CTkLabel(box, text=f'Syncing {self.st.shop_name(running["shop"])}...', font=F(14, "bold"), anchor="w").pack(fill="x")
            bar = ctk.CTkProgressBar(box); bar.pack(fill="x", pady=6); bar.set(running["done"] / max(1, running["total"]))
            lab = ctk.CTkLabel(box, text=f'{running["done"]} of {running["total"]} listings', font=F(12, mono=True), text_color=C["muted"], anchor="w"); lab.pack(fill="x")
            logb = ctk.CTkTextbox(box, height=220, font=F(11, mono=True)); logb.pack(fill="x", pady=(6, 0))
            logb.insert("1.0", "\n".join(running["lines"][-400:])); logb.see("end")
            running["widgets"] = (bar, lab, logb)
        elif getattr(self, "_photo_result", None):
            box = self.card(p, accent=C["ok"])
            ctk.CTkLabel(box, text="Last run", font=F(14, "bold"), anchor="w").pack(fill="x")
            logb = ctk.CTkTextbox(box, height=200, font=F(11, mono=True)); logb.pack(fill="x", pady=(6, 0))
            logb.insert("1.0", self._photo_result); logb.configure(state="disabled")
        ctk.CTkFrame(p, height=40, fg_color="transparent").pack()

    def choose_photo_folder(self, sid):
        cur = self.photo_root(sid)
        path = filedialog.askdirectory(title=f"Folder for {self.st.shop_name(sid)} photos", initialdir=cur or os.path.expanduser("~"))
        if not path:
            return
        self.cfg.setdefault("photo_folders", {})[sid] = os.path.normpath(path); save_cfg(self.cfg)
        self.render()

    def start_photo_sync(self, sid):
        root = self.photo_root(sid)
        if not root:
            self.choose_photo_folder(sid); root = self.photo_root(sid)
            if not root:
                return
        try:
            os.makedirs(root, exist_ok=True)
            test = os.path.join(root, ".write_test"); open(test, "w").close(); os.remove(test)
        except Exception as e:
            messagebox.showerror("Photos", f"Cannot write to this folder:\n{root}\n\n{e}"); return
        ls = [l for l in self.st.listings if l["shop"] == sid and l.get("active") is not False and l.get("images")]
        job = dict(shop=sid, done=0, total=len(ls), lines=[f"Folder: {root}", f"Listings: {len(ls)}", ""], widgets=None)

        def ui_update():
            w = job.get("widgets")
            if w and all(x.winfo_exists() for x in w):
                bar, lab, logb = w
                bar.set(job["done"] / max(1, job["total"])); lab.configure(text=f'{job["done"]} of {job["total"]} listings')
                logb.delete("1.0", "end"); logb.insert("1.0", "\n".join(job["lines"][-400:])); logb.see("end")

        def log(msg):
            job["lines"].append(msg); self.app.after(0, ui_update)

        def progress(a, b):
            job["done"] = a
            if a % 5 == 0 or a == b:
                self.app.after(0, ui_update)
        sync = PhotoSync(root, log, progress); job["sync"] = sync
        self._photo_job = job; self._photo_result = None
        self.render()

        def done(res):
            summary, others = res
            stamp = datetime.now().strftime("%d %b %Y %H:%M")
            self.cfg.setdefault("photo_last", {})[sid] = f"{stamp} · {summary}"; save_cfg(self.cfg)
            self._photo_job = None
            self._photo_result = "\n".join(job["lines"][-300:]) + "\n\n" + summary + (f"\nFolders not in the current listings (left as they are): {', '.join(sorted(others))}" if others else "")
            self.lbl_sync.configure(text="● Photos synced " + datetime.now().strftime("%H:%M"), text_color=C["ok"])
            self.toast("Photos: " + summary[:120])
            if self.view == "Photos":
                self.render()

        def failed(e, tb):
            self._photo_job = None; self.fail(e, tb)
            if self.view == "Photos":
                self.render()
        self.bg(lambda: sync.run(ls), done, failed, busy="Syncing photos...")

    # ---------- sheets
    def pg_sheets(self):
        p = self.page(scroll=False)
        ds = sorted([x for x in self.st.datasets if self.shop == "all" or not x.get("shop") or x.get("shop") == self.shop], key=lambda x: str(x.get("created_at")), reverse=True)
        self.head(p, "Sheets", "Keep any spreadsheet here (Google Sheets export, Excel, CSV): trackers, supplier lists, pricing, anything. Every row is saved online. Double-click a sheet to open it.",
                  [("+ Add sheet", self.add_sheet, "primary")])
        if not ds:
            self.empty(p, "No sheets saved yet. Click Add sheet and choose an .xlsx or .csv file. (Etsy's Order Items and Listings CSVs go under Import data instead.)"); return
        self._ds = {x["id"]: x for x in ds}
        rows = [(x["id"], (x["name"], self.st.shop_name(x["shop"]) if x.get("shop") else "All shops", f'{x.get("row_count") or 0:,}', ", ".join((x.get("columns") or [])[:8]), short(str(x.get("created_at"))[:10]), x.get("source_file") or ""), None) for x in ds]
        wrap, _ = self.table(p, [("n", "Name", 260, "w"), ("s", "Shop", 130, "w"), ("r", "Rows", 70, "e"), ("c", "Columns", 360, "w"), ("a", "Added", 90, "w"), ("f", "File", 200, "w")], rows, on_open=self.open_sheet, height=18)
        wrap.pack(fill="both", expand=True, padx=18, pady=(4, 40))

    def add_sheet(self):
        path = filedialog.askopenfilename(filetypes=[("Spreadsheets", "*.xlsx *.xls *.csv *.tsv *.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            if path.lower().endswith((".csv", ".tsv", ".txt")):
                sheets = {"": read_csv_rows(path)}
            else:
                if pd is None:
                    raise CrmError("pandas is needed to read Excel files.")
                try:
                    xl = pd.read_excel(path, sheet_name=None, dtype=str)
                except ImportError:
                    raise CrmError("To read Excel files run once:  pip install openpyxl")
                sheets = {k: v.fillna("").to_dict("records") for k, v in xl.items()}
        except Exception as e:
            self.fail(e); return
        d = ctk.CTkToplevel(self.app); d.title("Add sheet"); d.geometry("560x380"); d.transient(self.app); d.after(50, d.lift); d.configure(fg_color=C["bg"])
        f = ctk.CTkFrame(d, fg_color="transparent"); f.pack(fill="both", expand=True, padx=18, pady=14)
        base = os.path.splitext(os.path.basename(path))[0]
        ctk.CTkLabel(f, text=os.path.basename(path), font=F(16, "bold"), anchor="w").pack(fill="x")
        tabs = list(sheets.keys())
        ctk.CTkLabel(f, text="Tab", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x", pady=(10, 2))
        tab = ctk.CTkOptionMenu(f, values=[t or "(file)" for t in tabs]); tab.pack(fill="x")
        ctk.CTkLabel(f, text="Name", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x", pady=(10, 2))
        name = ctk.CTkEntry(f); name.insert(0, base + (f" · {tabs[0]}" if len(tabs) > 1 else "")); name.pack(fill="x")
        tab.configure(command=lambda v: (name.delete(0, "end"), name.insert(0, base + (f" · {v}" if len(tabs) > 1 else ""))))
        ctk.CTkLabel(f, text="Shop", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x", pady=(10, 2))
        shops = ["All shops / general"] + [s["name"] for s in self.st.shop_list()]
        sh = ctk.CTkOptionMenu(f, values=shops); sh.set(self.st.shop_name(self.shop) if self.shop != "all" else shops[0]); sh.pack(fill="x")
        prog = ctk.CTkLabel(f, text="", text_color=C["muted"], anchor="w"); prog.pack(fill="x", pady=6)

        def go():
            key = tab.get(); key = "" if key == "(file)" else key
            rows = [{str(k): ("" if v is None else str(v)) for k, v in r.items() if not str(k).startswith("Unnamed")} for r in sheets[key]]
            rows = [r for r in rows if any(v.strip() for v in r.values())]
            cols = []
            for r in rows[:300]:
                for k in r:
                    if k not in cols:
                        cols.append(k)
            did = str(uuid.uuid4()); sid = next((s["id"] for s in self.st.shops if s["name"] == sh.get()), "")
            meta = dict(id=did, name=name.get().strip() or base, shop=sid, source_file=os.path.basename(path) + (f" · {key}" if key else ""), columns=cols, row_count=len(rows), created_at=now_iso())

            def work():
                self.sb.upsert("datasets", [meta])
                try:
                    self.sb.upsert("dataset_rows", [dict(dataset_id=did, row_no=i, data=r) for i, r in enumerate(rows)],
                                   progress=lambda a, b: self.app.after(0, lambda: prog.winfo_exists() and prog.configure(text=f"Saving {a:,} of {b:,}...")))
                except Exception:
                    self.sb.delete("datasets", {"id": did}); raise
                return meta

            def done(m):
                self.st.datasets.append(m); d.destroy(); self.toast(f'Saved {m["row_count"]:,} rows'); self.render()
            self.bg(work, done)
        self.btn(f, "Save sheet", go, "primary").pack(anchor="w", pady=8)

    def open_sheet(self, did):
        meta = self._ds.get(did)
        if not meta:
            return
        d = ctk.CTkToplevel(self.app); d.title(meta["name"]); d.geometry("1100x700"); d.transient(self.app); d.after(50, d.lift); d.configure(fg_color=C["bg"])
        top = ctk.CTkFrame(d, fg_color="transparent"); top.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(top, text=meta["name"], font=F(18, "bold")).pack(side="left")
        info = ctk.CTkLabel(top, text="Loading rows...", text_color=C["muted"]); info.pack(side="left", padx=12)
        holder = ctk.CTkFrame(d, fg_color="transparent"); holder.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        state = {"rows": []}
        cols = meta.get("columns") or []

        def fill(q=""):
            for w in holder.winfo_children():
                w.destroy()
            ql = q.strip().lower()
            rows = [r for r in state["rows"] if not ql or ql in " ".join(str(v) for v in (r.get("data") or {}).values()).lower()]
            info.configure(text=f'{len(rows):,} of {len(state["rows"]):,} rows' + (" (first 3,000 shown)" if len(rows) > 3000 else ""))
            data = [(r["row_no"], [r["row_no"] + 1] + [str((r.get("data") or {}).get(c, ""))[:200] for c in cols], None) for r in rows[:3000]]
            w, _ = self.table(holder, [("_n", "#", 50, "e")] + [(f"c{i}", c[:30], 160, "w") for i, c in enumerate(cols)], data, height=24)
            w.pack(fill="both", expand=True)
        se = ctk.CTkEntry(top, placeholder_text="Search all columns", width=260); se.pack(side="right")
        se.bind("<KeyRelease>", lambda e: self._debounce(lambda: fill(se.get())))

        def export():
            path = filedialog.asksaveasfilename(parent=d, defaultextension=".csv", initialfile=slug(meta["name"]) + ".csv", filetypes=[("CSV", "*.csv")])
            if not path:
                return
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f); w.writerow(cols)
                for r in state["rows"]:
                    w.writerow([(r.get("data") or {}).get(c, "") for c in cols])
            self.toast("Exported")

        def delete():
            if not messagebox.askyesno("Delete sheet", f'Delete "{meta["name"]}" and all its rows?', parent=d):
                return
            self.bg(lambda: self.sb.delete("datasets", {"id": did}), lambda r: (self.st.datasets.__setitem__(slice(None), [x for x in self.st.datasets if x["id"] != did]), d.destroy(), self.toast("Sheet deleted"), self.render()))
        self.btn(top, "Delete sheet", delete, "danger", small=True).pack(side="right", padx=6)
        self.btn(top, "Export CSV", export, small=True).pack(side="right", padx=6)
        self.bg(lambda: self.sb.select("dataset_rows", {"dataset_id": did}), lambda rows: (state.update(rows=sorted(rows, key=lambda r: r["row_no"])), d.winfo_exists() and fill()))

    # ---------- import
    def pg_import_data(self):
        p = self.page()
        self.head(p, "Import data", "Bring in Etsy exports and Claude's plans. Re-importing the same file is safe: existing rows are updated, not duplicated.")
        self.section(p, "Etsy CSV")
        i = self.card(p)
        ctk.CTkLabel(i, text="In Etsy: Shop Manager › Settings › Options › Download Data. Use Order Items (pick the year, leave the month empty) and Listings. Do this for each shop.",
                     font=F(12), text_color=C["muted"], wraplength=820, justify="left", anchor="w").pack(fill="x")
        if not self.st.shops:
            ctk.CTkLabel(i, text="Add your shops first in Shops & schedules.", text_color=C["warn"], anchor="w").pack(fill="x", pady=6)
        else:
            r = ctk.CTkFrame(i, fg_color="transparent"); r.pack(fill="x", pady=8)
            names = [s["name"] for s in self.st.shop_list()]
            cur = self.etsy_import["shop"] if self.etsy_import else (self.shop if self.shop != "all" else self.st.shop_list()[0]["id"])
            sm = ctk.CTkOptionMenu(r, values=names, width=220); sm.set(self.st.shop_name(cur)); sm.pack(side="left")

            def choose():
                path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
                if not path:
                    return
                sid = next(s["id"] for s in self.st.shops if s["name"] == sm.get())
                try:
                    self.etsy_import = analyse_etsy(self.st, read_csv_rows(path), sid, path)
                except Exception as e:
                    self.fail(e); return
                self.render()
            self.btn(r, "Choose CSV file...", choose, "primary").pack(side="left", padx=8)
            ei = self.etsy_import
            if ei:
                box = self.card(i, padx=0, accent=C["ok"] if ei["kind"] else C["warn"])
                ctk.CTkLabel(box, text=ei["title"] + f'  →  {self.st.shop_name(ei["shop"])}', font=F(14, "bold"), anchor="w").pack(fill="x")
                ctk.CTkLabel(box, text=ei["detail"], font=F(12), text_color=C["muted"], anchor="w", wraplength=760, justify="left").pack(fill="x")
                rr = ctk.CTkFrame(box, fg_color="transparent"); rr.pack(fill="x", pady=(8, 0))
                prog = ctk.CTkLabel(rr, text="", text_color=C["muted"])
                if ei["kind"]:
                    self.btn(rr, f'Import into {self.st.shop_name(ei["shop"])}', lambda: self.run_etsy_import(prog), "primary").pack(side="left")
                else:
                    self.btn(rr, "Save it under Sheets instead", lambda: self.show("Sheets"), small=True).pack(side="left")
                self.btn(rr, "Cancel", lambda: (setattr(self, "etsy_import", None), self.render()), "ghost").pack(side="left", padx=6)
                prog.pack(side="left", padx=8)
        if getattr(self, "last_listings_csv", None):
            i2 = self.card(p, accent=C["yellow"])
            ctk.CTkLabel(i2, text="Update listing photos too?", font=F(14, "bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(i2, text="Photos uses the listings you just imported and only downloads new or changed photos.", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x")
            self.btn(i2, "Open Photos", lambda: self.show("Photos"), "primary").pack(anchor="w", pady=(8, 0))
        self.section(p, "Plan from Claude (.json)")
        i = self.card(p)
        ctk.CTkLabel(i, text="Choose the .json plan file Claude gives you, or paste its text below. Tasks you already finished keep their status.", font=F(12), text_color=C["muted"], anchor="w", wraplength=820, justify="left").pack(fill="x")
        txt = ctk.CTkTextbox(i, height=150, font=F(12, mono=True)); txt.pack(fill="x", pady=8)
        r = ctk.CTkFrame(i, fg_color="transparent"); r.pack(fill="x")

        def choose_plan():
            path = filedialog.askopenfilename(filetypes=[("Plan file", "*.json *.txt"), ("All files", "*.*")])
            if path:
                with open(path, "r", encoding="utf-8") as f:
                    txt.delete("1.0", "end"); txt.insert("1.0", f.read())
                self.check_plan(txt.get("1.0", "end"))
        self.btn(r, "Choose plan file...", choose_plan, "primary").pack(side="left")
        self.btn(r, "Check pasted plan", lambda: self.check_plan(txt.get("1.0", "end"))).pack(side="left", padx=6)
        self.btn(r, "Copy plan format for Claude", lambda: self.copy(format_spec(self.st))).pack(side="left", padx=6)
        if self.pending_plan:
            pp = self.pending_plan
            box = self.card(i, padx=0, accent=C["warn"] if pp["warn"] else C["ok"])
            ctk.CTkLabel(box, text=pp["title"], font=F(14, "bold"), anchor="w", wraplength=760, justify="left").pack(fill="x")
            ctk.CTkLabel(box, text=pp["detail"], font=F(12), text_color=C["muted"], anchor="w", wraplength=760, justify="left").pack(fill="x")
            rr = ctk.CTkFrame(box, fg_color="transparent"); rr.pack(fill="x", pady=(8, 0))
            if pp["tasks"] or pp["settings"]:
                self.btn(rr, "Import plan", self.run_plan_import, "primary").pack(side="left")
            self.btn(rr, "Cancel", lambda: (setattr(self, "pending_plan", None), self.render()), "ghost").pack(side="left", padx=6)
        ctk.CTkFrame(p, height=30, fg_color="transparent").pack()

    def open_organizer(self):
        try:
            self.app.org_csv_path.set(self.last_listings_csv)
            self.app.lbl_org_csv.configure(text=os.path.basename(self.last_listings_csv))
        except Exception:
            pass
        self.show("Image Organizer")

    def run_etsy_import(self, prog):
        ei = self.etsy_import
        if not ei or not ei["kind"]:
            return

        def progress(a, b):
            self.app.after(0, lambda: prog.winfo_exists() and prog.configure(text=f"Saving {a:,} of {b:,}..."))

        def work():
            if ei["kind"] == "orders":
                self.sb.upsert("orders", ei["mapped"], progress)
                s = next((x for x in self.st.shops if x["id"] == ei["shop"]), None)
                if s:
                    s = dict(s, last_csv=today(), updated_at=now_iso()); self.sb.upsert("shops", [s])
            else:
                existing = [l for l in self.st.listings if l["shop"] == ei["shop"]]
                keep = {l["key"]: l for l in existing}; keys = {m["key"] for m in ei["mapped"]}
                rows = [dict(m, notes=(keep.get(m["key"]) or {}).get("notes") or "", imported_at=now_iso()) for m in ei["mapped"]]
                gone = [dict(l, active=False) for l in existing if l["key"] not in keys]
                save_photo_links(ei["shop"], ei["mapped"])
                self.sb.upsert("listings", rows + gone, progress)
            self.st.load(self.sb)
            return len(ei["mapped"])

        def done(n):
            if ei["kind"] == "listings":
                self.last_listings_csv = ei["file"]
            self.etsy_import = None
            self.synced(); self.toast(f"Imported {n:,} rows into {self.st.shop_name(ei['shop'])}")
            self.render()
        self.bg(work, done, busy="Importing...")

    def check_plan(self, text):
        t = text.strip()
        t = re.sub(r"^```(?:json)?", "", t).strip(); t = re.sub(r"```\s*$", "", t).strip()
        a, z = t.find("{"), t.rfind("}")
        try:
            if a < 0 or z < a:
                raise ValueError("No JSON found. Ask Claude for the plan as a .json file.")
            data = json.loads(t[a:z + 1])
        except Exception as e:
            self.pending_plan = dict(title="Could not read this plan", detail=str(e), tasks=[], settings=None, warn=True); self.render(); return
        arr = data if isinstance(data, list) else (data.get("tasks") or [])
        errs, ok, unk = [], [], set(); new = upd = keep = 0
        ids = {s["id"] for s in self.st.shops}
        for n, x in enumerate(arr, 1):
            if not isinstance(x, dict):
                errs.append(f"#{n}: not a task"); continue
            if not x.get("title"):
                errs.append(f"#{n}: missing title"); continue
            if x.get("due") and not valid_date(x["due"]):
                errs.append(f"#{n}: bad date '{x['due']}' (use YYYY-MM-DD)"); continue
            if not x.get("id"):
                x["id"] = f't-{x.get("due") or "nodate"}-{slug(x.get("shop"))}-{slug((x.get("sku") or "") + " " + x["title"])}'
            x["id"] = re.sub(r"[^A-Za-z0-9_.~:@+-]", "-", str(x["id"]))[:150]
            if x.get("area") and x["area"] not in AREAS:
                x["area"] = "other"
            if x.get("shop") and x["shop"] not in ids:
                unk.add(x["shop"])
            cur = self.st.tasks.get(x["id"])
            if not cur:
                new += 1
            elif not is_open(cur):
                keep += 1
            else:
                upd += 1
            ok.append(x)
        sett = data.get("settings") if isinstance(data, dict) and isinstance(data.get("settings"), dict) and isinstance(data["settings"].get("shops"), list) else None
        detail = f"{new} new, {upd} updated, {keep} already finished (status kept)." + (" Shop settings will be updated too." if sett else "")
        if unk:
            detail += f"\nUnknown shop ids: {', '.join(sorted(unk))}. Add these shops (same id) or the tasks only show under All shops."
        if errs:
            detail += "\nSkipped: " + "; ".join(errs)
        self.pending_plan = dict(plan=str(data.get("plan") if isinstance(data, dict) else "Imported plan") or "Imported plan", tasks=ok, settings=sett,
                                 title=f'{(data.get("plan") if isinstance(data, dict) else None) or "Plan"}: {len(ok)} valid task{"s" if len(ok) != 1 else ""}', detail=detail, warn=bool(errs or unk))
        self.render()

    def run_plan_import(self):
        pp = self.pending_plan
        if not pp:
            return
        now = now_iso(); rows = []
        for x in pp["tasks"]:
            cur = self.st.tasks.get(x["id"]) or {}
            fud = x.get("followUpDays", x.get("follow_up_days"))
            r = dict(dict(status=x.get("status") if x.get("status") in STATUS else "todo", created_at=now), **cur)
            r.update(id=x["id"], shop=str(x.get("shop") or ""), title=str(x["title"]), area=x.get("area") or "other", sku=str(x.get("sku") or ""), due=x.get("due") or None,
                     priority=int(x.get("priority") or 2), steps=str(x.get("steps") or ""), copy=[{"label": str(c.get("label", "")), "text": str(c.get("text", ""))} for c in (x.get("copy") or []) if isinstance(c, dict)],
                     follow_up_days=None if fud is None else int(fud), plan=pp["plan"], source="plan", updated_at=now)
            if not cur:
                r.update(notes=x.get("notes") or "", done_at=x.get("doneAt") or x.get("done_at"), started_at=x.get("startedAt") or x.get("started_at"))
            rows.append(r)

        def work():
            if rows:
                self.sb.upsert("tasks", rows)
            if pp["settings"]:
                shops = {s["id"]: dict(s) for s in self.st.shops}
                for ps in pp["settings"]["shops"]:
                    if not isinstance(ps, dict) or not ps.get("id"):
                        continue
                    x = shops.get(ps["id"]) or dict(id=str(ps["id"]), name=str(ps.get("name") or ps["id"]), url="", schedules=[], csv_every_days=14, last_csv=None, sort=len(shops))
                    for a, b in (("name", "name"), ("url", "url"), ("lastCsv", "last_csv"), ("last_csv", "last_csv"), ("csvEveryDays", "csv_every_days"), ("csv_every_days", "csv_every_days")):
                        if a in ps:
                            x[b] = ps[a]
                    if isinstance(ps.get("schedules"), list):
                        sch = [dict(s) for s in (x.get("schedules") or [])]
                        for sc in ps["schedules"]:
                            ex = next((s for s in sch if s.get("name") == sc.get("name")), None)
                            if ex:
                                ex.update(sc)
                            else:
                                sch.append(sc)
                        x["schedules"] = sch
                    x["updated_at"] = now; shops[x["id"]] = x
                    self.sb.upsert("shops", [x])
            self.st.load(self.sb)
            return len(rows)

        def done(n):
            self.pending_plan = None; self.synced(); self.toast(f"Imported {n} task{'s' if n != 1 else ''}"); self.show("Dashboard")
        self.bg(work, done, busy="Importing...")

    # ---------- shops
    def pg_shops_schedules(self):
        p = self.page()
        td = today()
        self.head(p, "Shops & schedules", "Your Etsy shops, what content is scheduled until when, and how often to refresh Etsy data.")
        if self.st.shops:
            g = ctk.CTkFrame(p, fg_color="transparent"); g.pack(fill="x", padx=12)
            for n, s in enumerate(self.st.shop_list()):
                g.grid_columnconfigure(n % 3, weight=1, uniform="s")
                c = ctk.CTkFrame(g, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["line"]); c.grid(row=n // 3, column=n % 3, sticky="nsew", padx=6, pady=6)
                ctk.CTkFrame(c, height=3, fg_color=C["yellow"], corner_radius=2).pack(fill="x", padx=1, pady=(1, 0))
                ctk.CTkLabel(c, text=s["name"], font=F(17, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
                ctk.CTkLabel(c, text=s.get("url") or "No shop link", font=F(11, mono=True), text_color=C["muted"], anchor="w").pack(fill="x", padx=14)
                mine = [t for t in self.st.tasks.values() if t.get("shop") == s["id"]]; op = [t for t in mine if is_open(t)]
                over = len([t for t in op if t.get("due") and diff(t["due"], td) < 0]); x = sales_summary(self.st, s["id"], td)
                stl = f'{len(op)} open · {over} overdue · {x["u0"]} sold in 30d' + (f' ({pct(x["u0"], x["u1"])})' if x["n"] else "")
                ctk.CTkLabel(c, text=stl, font=F(12), text_color=C["bad"] if over else C["ink"], anchor="w").pack(fill="x", padx=14, pady=(8, 2))
                for sc in (s.get("schedules") or []):
                    left = diff(sc["until"], td) if sc.get("until") else None
                    col = C["warn"] if left is None else (C["bad"] if left < 0 else (C["yellow"] if left <= int(sc.get("warnDays") or 2) else C["ok"]))
                    ctk.CTkLabel(c, text=f'{sc.get("name")}: ' + (f'until {nice(sc["until"])}' if sc.get("until") else "not set"), font=F(12, mono=True), text_color=col, anchor="w").pack(fill="x", padx=14)
                ago = diff(td, s["last_csv"]) if s.get("last_csv") else None
                ctk.CTkLabel(c, text="Etsy data: " + (f'{nice(s["last_csv"])} ({ago}d ago)' if ago is not None else "never imported"), font=F(12, mono=True),
                             text_color=C["warn"] if ago is None else (C["bad"] if ago >= int(s.get("csv_every_days") or 14) else C["ok"]), anchor="w").pack(fill="x", padx=14)
                r = ctk.CTkFrame(c, fg_color="transparent"); r.pack(fill="x", padx=14, pady=10)
                self.btn(r, "Open this shop", lambda sid=s["id"]: (self._set_shop(sid), self.show("Dashboard")), small=True).pack(side="left", padx=(0, 6))
                self.btn(r, "Copy plan request", lambda sid=s["id"]: self.copy(request_text(self.st, "plan", sid), "Request copied. Paste it into a Claude chat."), small=True).pack(side="left")
        self.section(p, "Edit shops")
        self._shop_rows = []
        draft = getattr(self, "_draft", None) or [json.loads(json.dumps(s, default=str)) for s in self.st.shop_list()]
        self._draft = draft
        for si, s in enumerate(draft):
            i = self.card(p)
            grid = ctk.CTkFrame(i, fg_color="transparent"); grid.pack(fill="x")
            w = {}
            for col, (k, label, width) in enumerate((("name", "Shop name", 200), ("url", "Etsy shop link", 230), ("last_csv", "Etsy data last imported (YYYY-MM-DD)", 230), ("csv_every_days", "Remind me every (days)", 150))):
                cf = ctk.CTkFrame(grid, fg_color="transparent"); cf.grid(row=0, column=col, sticky="w", padx=(0, 10))
                ctk.CTkLabel(cf, text=label, font=F(11), text_color=C["muted"], anchor="w").pack(fill="x")
                e = ctk.CTkEntry(cf, width=width); e.insert(0, str(s.get(k) if s.get(k) is not None else (14 if k == "csv_every_days" else ""))); e.pack()
                w[k] = e
            ctk.CTkLabel(i, text="SCHEDULED CONTENT", font=F(10, "bold"), text_color=C["faint"], anchor="w").pack(fill="x", pady=(10, 2))
            scw = []
            for sci, sc in enumerate(s.get("schedules") or []):
                rr = ctk.CTkFrame(i, fg_color="transparent"); rr.pack(fill="x", pady=2)
                ents = {}
                for k, label, width in (("name", "Channel", 160), ("until", "Scheduled until (YYYY-MM-DD)", 200), ("warnDays", "Alert days before", 130), ("planDays", "Next plan (days)", 120)):
                    cf = ctk.CTkFrame(rr, fg_color="transparent"); cf.pack(side="left", padx=(0, 10))
                    ctk.CTkLabel(cf, text=label, font=F(11), text_color=C["muted"], anchor="w").pack(fill="x")
                    e = ctk.CTkEntry(cf, width=width); e.insert(0, str(sc.get(k) if sc.get(k) is not None else {"warnDays": 2, "planDays": 28}.get(k, ""))); e.pack()
                    ents[k] = e
                self.btn(rr, "Remove", lambda si=si, sci=sci: self._draft_edit(lambda dr: dr[si]["schedules"].pop(sci)), "ghost", small=True).pack(side="left", pady=(14, 0))
                scw.append(ents)
            if not (s.get("schedules") or []):
                ctk.CTkLabel(i, text="No schedules for this shop.", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x")
            br = ctk.CTkFrame(i, fg_color="transparent"); br.pack(fill="x", pady=(8, 0))
            self.btn(br, "+ Add schedule", lambda si=si: self._draft_edit(lambda dr: dr[si].setdefault("schedules", []).append({"name": "Instagram", "until": None, "warnDays": 2, "planDays": 28})), small=True).pack(side="left")
            ctk.CTkLabel(br, text=f'Shop id: {s["id"]}', font=F(11, mono=True), text_color=C["yellow"]).pack(side="right")
            if s.get("_new"):
                self.btn(br, "Remove", lambda si=si: self._draft_edit(lambda dr: dr.pop(si)), "ghost", small=True).pack(side="right", padx=8)
            self._shop_rows.append((w, scw))
        if not draft:
            self.empty(p, "No shops yet. Click Add shop.")
        r = ctk.CTkFrame(p, fg_color="transparent"); r.pack(fill="x", padx=18, pady=10)
        self.btn(r, "+ Add shop", self._add_shop).pack(side="left")
        self.btn(r, "Save changes", self._save_shops, "primary").pack(side="left", padx=8)
        ctk.CTkLabel(p, text="The shop id is used in Claude's plan files. It is set from the name when a shop is first saved and does not change after that.", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x", padx=18)
        ctk.CTkFrame(p, height=40, fg_color="transparent").pack()

    def _read_draft(self):
        dr = self._draft
        for si, (w, scw) in enumerate(getattr(self, "_shop_rows", [])):
            if si >= len(dr):
                break
            s = dr[si]
            s["name"] = w["name"].get().strip() or s.get("name") or "Shop"; s["url"] = w["url"].get().strip()
            lc = w["last_csv"].get().strip(); s["last_csv"] = lc if valid_date(lc) else None
            try:
                s["csv_every_days"] = max(3, int(w["csv_every_days"].get()))
            except Exception:
                s["csv_every_days"] = 14
            sch = []
            for ents in scw:
                u = ents["until"].get().strip()
                try:
                    wd = int(ents["warnDays"].get())
                except Exception:
                    wd = 2
                try:
                    pdays = int(ents["planDays"].get())
                except Exception:
                    pdays = 28
                sch.append({"name": ents["name"].get().strip() or "Schedule", "until": u if valid_date(u) else None, "warnDays": wd, "planDays": pdays})
            s["schedules"] = sch
        return dr

    def _draft_edit(self, fn):
        dr = self._read_draft(); fn(dr); self._draft = dr; self.render()

    def _add_shop(self):
        dr = self._read_draft()
        n = len(dr) + 1
        while any(s["id"] == f"shop-{n}" for s in dr):
            n += 1
        dr.append({"id": f"shop-{n}", "name": "New shop", "url": "", "last_csv": None, "csv_every_days": 14, "schedules": [], "sort": len(dr), "_new": True})
        self._draft = dr; self.render()

    def _save_shops(self):
        dr = self._read_draft(); now = now_iso(); rows = []
        for i, s in enumerate(dr):
            r = {k: v for k, v in s.items() if k != "_new"}
            r["sort"] = i; r["updated_at"] = now
            if s.get("_new") and r["name"] != "New shop":
                nid = slug(r["name"])
                if not any(o is not s and o["id"] == nid for o in dr) and not any(x["id"] == nid for x in self.st.shops):
                    r["id"] = nid
            rows.append(r)

        def done(_):
            self.st.shops = rows; self._draft = None; self.toast("Shops saved"); self._refresh_shop_menu(); self.render()
        self.bg(lambda: self.sb.upsert("shops", rows), done)

    # ---------- report
    def pg_report_for_claude(self):
        p = self.page()
        sid = "" if self.shop == "all" else self.shop
        self.head(p, "Report for Claude", f"Copy this into a Claude chat. It covers {self.scope()}: sales, listings that need attention, open and finished tasks, and your notes.")
        self.section(p, "Ask Claude for the next plan")
        i = self.card(p)
        ctk.CTkLabel(i, text="Each button copies a ready request with your report and the plan file format. Paste it into a new Claude chat, then import the .json Claude gives you under Import data.",
                     font=F(12), text_color=C["muted"], wraplength=820, justify="left", anchor="w").pack(fill="x")
        r = ctk.CTkFrame(i, fg_color="transparent"); r.pack(fill="x", pady=(8, 0))
        for s in self.st.shop_list():
            if sid and s["id"] != sid:
                continue
            for n, sc in enumerate(s.get("schedules") or []):
                self.btn(r, f'{s["name"]} · next {sc.get("planDays") or 28} days of {sc.get("name")}', lambda s_=s["id"], n=n: self.copy(request_text(self.st, "sched", s_, n), "Request copied. Paste it into a Claude chat."), small=True).pack(side="left", padx=(0, 6), pady=2)
        self.btn(r, f"14-day plan · {self.scope()}", lambda: self.copy(request_text(self.st, "plan", sid, scope=sid), "Request copied. Paste it into a Claude chat."), "primary", small=True).pack(side="left", padx=(0, 6))
        self.section(p, "Full report")
        rep_ = report_text(self.st, sid)
        i = self.card(p)
        rr = ctk.CTkFrame(i, fg_color="transparent"); rr.pack(fill="x")
        self.btn(rr, "Copy report", lambda: self.copy(rep_), "primary", small=True).pack(side="left")

        def save():
            path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=f"crm-report-{today()}.txt", filetypes=[("Text", "*.txt")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(rep_)
                self.toast("Saved")
        self.btn(rr, "Save as .txt", save, small=True).pack(side="left", padx=6)
        tb = ctk.CTkTextbox(i, height=420, font=F(11, mono=True), wrap="word"); tb.insert("1.0", rep_); tb.configure(state="disabled"); tb.pack(fill="x", pady=(8, 0))
        ctk.CTkFrame(p, height=40, fg_color="transparent").pack()

    # ---------- settings & updates
    def pg_settings_updates(self):
        p = self.page()
        self.head(p, "Settings & updates", "Database connection, your login, backup, and software updates.")
        self.section(p, "Database connection")
        i = self.card(p)
        ctk.CTkLabel(i, text="From Supabase: Project Settings › API Keys. Paste the Project URL and the Publishable key (never the secret key).", font=F(12), text_color=C["muted"], anchor="w", wraplength=820, justify="left").pack(fill="x")
        url = ctk.CTkEntry(i, placeholder_text="https://xxxx.supabase.co"); url.pack(fill="x", pady=(8, 4))
        key = ctk.CTkEntry(i, placeholder_text="sb_publishable_... or eyJ..."); key.pack(fill="x", pady=4)
        if self.cfg.get("url"):
            url.insert(0, self.cfg["url"])
        if self.cfg.get("key"):
            key.insert(0, self.cfg["key"])
        self.section(p, "Sign in")
        i2 = self.card(p)
        if self.connected():
            ctk.CTkLabel(i2, text=f'Signed in as {self.sb.user.get("email", "")}', font=F(14, "bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(i2, text=f'Last sync: {datetime.fromtimestamp(self.st.loaded_at).strftime("%d %b %Y %H:%M") if self.st.loaded_at else "-"}', font=F(12), text_color=C["muted"], anchor="w").pack(fill="x")
            r = ctk.CTkFrame(i2, fg_color="transparent"); r.pack(fill="x", pady=(8, 0))
            self.btn(r, "Sync now", self.sync).pack(side="left")
            self.btn(r, "Sign out", self.sign_out, "ghost").pack(side="left", padx=6)
        else:
            ctk.CTkLabel(i2, text="Use the user you created in Supabase (Authentication › Users). Same login on every laptop.", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x")
            em = ctk.CTkEntry(i2, placeholder_text="Email"); em.pack(fill="x", pady=(8, 4))
            if self.cfg.get("email"):
                em.insert(0, self.cfg["email"])
            pw = ctk.CTkEntry(i2, placeholder_text="Password", show="•"); pw.pack(fill="x", pady=4)
            msg = ctk.CTkLabel(i2, text="", text_color=C["bad"], anchor="w"); msg.pack(fill="x")

            def go():
                u, k = url.get().strip().rstrip("/"), key.get().strip()
                if not u.startswith("https://") or not k:
                    msg.configure(text="Paste the Project URL (starts with https://) and the publishable key first."); return
                self.cfg.update(url=u, key=k); save_cfg(self.cfg)
                self.sb = self._make_sb()

                def work():
                    self.sb.sign_in(em.get().strip(), pw.get())
                    self.st.load(self.sb)
                    return self.check_updates()

                def failed(e, tb):
                    self.sb = None; self.lbl_sync.configure(text="Not connected", text_color=C["faint"])
                    if msg.winfo_exists():
                        msg.configure(text=str(e))
                self.bg(work, self.after_login, failed, busy="Signing in...")
            self.btn(i2, "Sign in", go, "primary").pack(anchor="w", pady=(6, 0))
            pw.bind("<Return>", lambda e: go())
            return
        self.section(p, "What is stored")
        i3 = self.card(p)
        ctk.CTkLabel(i3, text=f'Shops {len(self.st.shops)}  ·  Tasks {len(self.st.tasks):,}  ·  Listings {len(self.st.listings):,}  ·  Order items {len(self.st.orders):,}  ·  Customer notes {len(self.st.notes):,}  ·  Sheets {len(self.st.datasets):,} ({sum(int(x.get("row_count") or 0) for x in self.st.datasets):,} rows)',
                     font=F(12, mono=True), anchor="w", wraplength=820, justify="left").pack(fill="x")
        self.section(p, "Backup")
        i4 = self.card(p)
        ctk.CTkLabel(i4, text="Saves everything (including all sheet rows) as one JSON file. Keep a copy somewhere safe once a month.", font=F(12), text_color=C["muted"], anchor="w").pack(fill="x")
        self.btn(i4, "Download full backup...", self.backup, "primary").pack(anchor="w", pady=(8, 0))
        self.section(p, "Software updates")
        i5 = self.card(p)
        info = self.update_info()
        ctk.CTkLabel(i5, text=f"CRM version {CRM_VERSION}" + (f"   ·   build {info.get('commit')}" if info.get("commit") else ""), font=F(14, "bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(i5, text="Updates install by themselves: every time the app starts or you press 'Refresh App', it downloads the newest version Claude has published. "
                              f"Last check: {info.get('status', 'not checked')}.", font=F(12), text_color=C["muted"], anchor="w", wraplength=820, justify="left").pack(fill="x")
        self.btn(i5, "Check for updates now", self.check_github_now, "primary").pack(anchor="w", pady=(8, 0))
        ctk.CTkFrame(p, height=40, fg_color="transparent").pack()

    def sign_out(self):
        self.cfg.pop("refresh_token", None); save_cfg(self.cfg)
        self.sb = None; self.st = Store(); self.st.build_index()
        self.lbl_sync.configure(text="Not connected", text_color=C["faint"]); self.lbl_user.configure(text="")
        self._refresh_shop_menu(); self.show("Settings & updates")

    def backup(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile=f"etsy-crm-backup-{today()}.json", filetypes=[("JSON", "*.json")])
        if not path:
            return

        def work():
            out = {"app": "Etsy Shops CRM", "exported_at": now_iso()}
            for tb in ("shops", "tasks", "listings", "orders", "customer_notes", "datasets", "dataset_rows"):
                out[tb] = self.sb.select(tb)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=1, default=str)
        self.bg(work, lambda r: (self.synced(), self.toast("Backup saved")), busy="Backing up...")

    # ---------- updates via database
    @staticmethod
    def _sha(text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def check_updates(self):
        """Updates now come from GitHub (see app.py). Kept for compatibility; returns ''."""
        return ""

    def update_info(self):
        main = sys.modules.get("__main__")
        return getattr(main, "_UPDATE_INFO", None) or {}

    def check_github_now(self):
        main = sys.modules.get("__main__")
        fn = getattr(main, "_crm_self_update", None)
        if not fn:
            messagebox.showinfo("Updates", "Start the app with Start-Etsy-CRM.bat to use automatic updates."); return

        def done(info):
            if info.get("updated"):
                messagebox.showinfo("Updates", "Downloaded: " + ", ".join(info["updated"]) + "\n\nClick 'Refresh App' (bottom-left) to start the new version.")
            else:
                messagebox.showinfo("Updates", "You have the latest version (" + str(info.get("status")) + ").")
            self.render()
        self.bg(lambda: fn(restart_if_app_changed=False), lambda info: (self.synced() if self.connected() else None, done(info)), busy="Checking for updates...")


def install(app):
    """Called from app.py after all tabs are set up."""
    app.crm = CRM(app)
    return app.crm
