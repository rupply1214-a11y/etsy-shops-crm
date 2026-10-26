import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
import pandas as pd
import requests
import os
import threading
import time
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import hashlib
import pdfplumber
from PIL import Image, ImageStat
import google.generativeai as genai

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- Auto-update from GitHub: every start / "Refresh App" fetches the latest app.py + crm.py ---
UPDATE_REPO = "rupply1214-a11y/etsy-shops-crm"
UPDATE_FILES = ("crm.py", "app.py")
_UPDATE_INFO = {"status": "not checked", "commit": "", "updated": []}


def _crm_self_update(restart_if_app_changed=True):
    """Download newer files from the GitHub repo. Never raises; works offline (just skips)."""
    here = os.path.dirname(os.path.abspath(__file__))
    state_path = os.path.join(here, "update_state.json")
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}
    try:
        r = requests.get(f"https://api.github.com/repos/{UPDATE_REPO}/commits/main",
                         headers={"Accept": "application/vnd.github.sha"}, timeout=6)
        if r.status_code != 200:
            _UPDATE_INFO["status"] = f"update check skipped (GitHub {r.status_code})"
            return _UPDATE_INFO
        sha = r.text.strip()
    except Exception:
        _UPDATE_INFO["status"] = "offline - update check skipped"
        return _UPDATE_INFO
    _UPDATE_INFO["commit"] = sha[:7]
    if state.get("commit") == sha:
        _UPDATE_INFO["status"] = "up to date"
        return _UPDATE_INFO
    updated = []
    for name in UPDATE_FILES:
        try:
            rr = requests.get(f"https://raw.githubusercontent.com/{UPDATE_REPO}/{sha}/{name}", timeout=30)
            if rr.status_code != 200:
                continue
            new_code = rr.content.decode("utf-8")
            compile(new_code, name, "exec")
            path = os.path.join(here, name)
            old_code = ""
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    old_code = f.read()
            if old_code.replace("\r\n", "\n") == new_code.replace("\r\n", "\n"):
                continue
            if old_code:
                with open(os.path.join(here, name.replace(".py", "_backup.py")), "w", encoding="utf-8") as f:
                    f.write(old_code)
            tmp = path + ".new"
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(new_code)
            os.replace(tmp, path)
            updated.append(name)
        except Exception:
            continue
    state["commit"] = sha
    state["checked"] = datetime.now().isoformat(timespec="seconds")
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass
    _UPDATE_INFO["updated"] = updated
    _UPDATE_INFO["status"] = ("updated: " + ", ".join(updated)) if updated else "up to date"
    if "app.py" in updated and restart_if_app_changed:
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)
    return _UPDATE_INFO


if __name__ == "__main__" and os.environ.get("ETSY_CRM_NO_UPDATE") != "1":
    _crm_self_update()

# --- Etsy Shops CRM (crm.py, same folder). If it fails to load, the old tools still work. ---
_crm = None
_crm_error = ""
try:
    import crm as _crm
except Exception:
    _crm_error = traceback.format_exc()
    try:
        import crm_backup as _crm
    except Exception:
        _crm = None
if _crm:
    try:
        _crm.apply_theme()
    except Exception:
        _crm_error = traceback.format_exc()

CONFIG_FILE = "config.json"
LISTING_HISTORY_FILE = "listing_history.json"
GEMINI_MODEL_FALLBACK_CHAIN = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]

# Default config structure including social_accounts placeholder
DEFAULT_CONFIG = {
    "master_csv_path": "",
    "social_accounts": {
        "instagram": {"connected": False},
        "facebook": {"connected": False},
        "pinterest": {"connected": False}
    },
    "gemini_api_key": ""
}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Patterns by Rish — Etsy Tools")
        self.geometry("1100x700")
        self.resizable(True, True)
        self.after(0, lambda: self.state('zoomed'))

        # Tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_home = self.tabview.add("Home")
        self.tab_org = self.tabview.add("Image Organizer")
        self.tab_ext = self.tabview.add("Listing URL Extractor")
        self.tab_perf = self.tabview.add("Performance Report")
        self.tab_video = self.tabview.add("Sewing Tip Prompts")
        self.tab_listing = self.tabview.add("Listing Content")
        self.tab_social = self.tabview.add("Social Poster (Coming Soon)")

        # Set Home as default
        self.tabview.set("Home")

        # Load config
        self.config = self.load_config()

        # Setup all tabs
        self.setup_home_ui()
        self.setup_org_ui()
        self.setup_ext_ui()
        self.setup_perf_ui()
        self.setup_video_ui()
        self.setup_listing_ui()
        self.setup_social_ui()

        # Version label
        self.lbl_version = ctk.CTkLabel(self, text="v1.2.0 · 2026-08-22", text_color="gray", font=("Arial", 10))
        self.lbl_version.place(relx=0.99, rely=0.99, anchor="se")

        # Refresh App button (bottom-left) — restarts the app to pick up code changes
        self.btn_refresh = ctk.CTkButton(
            self, text="\U0001f504 Refresh App", width=120, height=28,
            font=("Arial", 11), fg_color="#334155", hover_color="#475569",
            command=self.restart_app
        )
        self.btn_refresh.place(relx=0.01, rely=0.99, anchor="sw")

        # Etsy Shops CRM: sidebar + Dashboard, Tasks, Listings, Customers, ... (crm.py)
        if _crm_error:
            self.log_error_to_file("CRM load problem:\n" + _crm_error)
        if _crm:
            try:
                _crm.install(self)
            except Exception:
                self.log_error_to_file("CRM install failed:\n" + traceback.format_exc())
                messagebox.showerror("CRM", "The CRM part could not start. Your other tools still work.\nDetails are in error_log.txt.")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                # Merge with defaults so new keys are always present
                for key, val in DEFAULT_CONFIG.items():
                    if key not in data:
                        data[key] = val
                return data
            except:
                return dict(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def create_stat_card(self, parent, title, value, row, col, color="gray"):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        
        lbl_title = ctk.CTkLabel(card, text=title, font=("Arial", 12))
        lbl_title.pack(pady=(10, 0))
        
        lbl_val = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=24, weight="bold"), text_color=color)
        lbl_val.pack(pady=(5, 10))
        return lbl_val

    def log(self, box, message):
        box.configure(state="normal")
        box.insert("end", message + "\n")
        box.see("end")
        box.configure(state="disabled")

    def add_caption(self, parent, text, row, col=0):
        """Helper to add a small gray caption label below a button."""
        lbl = ctk.CTkLabel(parent, text=text, text_color="#888888", font=("Arial", 9), wraplength=200, justify="center")
        lbl.grid(row=row, column=col, padx=20, pady=(0, 8))
        return lbl

    def log_error_to_file(self, error_msg):
        """Appends an error message with timestamp to error_log.txt."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_log.txt")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {error_msg}\n{'-'*50}\n")
        except Exception:
            pass

    # =======================================================
    # SHARED HTML PARSING LOGIC
    # =======================================================
    def parse_listing_card(self, a_tag):
        """Extracts all data from a listing card. Returns a dict or None if invalid."""
        href = a_tag.get('href', '')
        match = re.search(r'listing-editor/edit/(\d+)', href)
        if not match:
            return None
            
        listing_id = match.group(1)
        listing_url = f"https://www.etsy.com/listing/{listing_id}"
        
        # Extract SKU
        sku = None
        sku_elem = a_tag.find(class_='card-meta-row-sku')
        if sku_elem:
            span = sku_elem.find('span')
            if span:
                sku = span.get('title') or span.text.strip()
        
        # Regex helpers
        v_match = re.search(r'(\d+)\s*visits', container_text)
        if v_match: visits_30d = int(v_match.group(1))
            
        f_match = re.search(r'(\d+)\s*favourites', container_text)
        if f_match: fav_30d = int(f_match.group(1))
            
        s_match = re.search(r'(\d+)\s*sales', container_text)
        if s_match: sales_all = int(s_match.group(1))
            
        r_match = re.search(r'\$?([\d,]+\.?\d*)\s*revenue', container_text)
        if r_match:
            try: rev_all = float(r_match.group(1).replace(',', ''))
            except: pass
            
        ren_match = re.search(r'(\d+)\s*renewals', container_text)
        if ren_match: renewals_all = int(ren_match.group(1))

        # We will not return None if SKU is missing anymore. We'll return it so the caller can decide.
        # But wait, the prompt said: "Current parse_listing_card() returns None if no SKU is found - this is correct for URL Extractor... but change the perf_process handler"
        # So I'll modify parse_listing_card to NOT return None for missing SKU, and instead let the callers handle it.
        # Let's fix parse_listing_card to return the dict even if sku is None.

        return {
            'LISTING_ID': listing_id,
            'SKU': sku,
            'TITLE': title,
            'LISTING_URL': listing_url,
            'PRICE': price,
            'VISITS_30D': visits_30d,
            'FAVOURITES_30D': fav_30d,
            'SALES_ALLTIME': sales_all,
            'REVENUE_ALLTIME': rev_all,
            'RENEWALS_ALLTIME': renewals_all
        }


    # =======================================================
    # UI SETUP: HOME TAB
    # =======================================================
    def setup_home_ui(self):
        # Scrollable container for nice padding
        home = ctk.CTkScrollableFrame(self.tab_home, fg_color="transparent")
        home.pack(fill="both", expand=True, padx=40, pady=20)

        # Welcome heading
        ctk.CTkLabel(home, text="Patterns by Rish — Etsy Tools", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", pady=(10, 5))
        ctk.CTkLabel(home, text="Apni Etsy shop ko manage karna ab bahut easy hai!", font=("Arial", 14), text_color="#aaaaaa").pack(anchor="w", pady=(0, 25))

        # Step cards
        steps = [
            ("Step 1:  Image Organizer", 
             "Apni Etsy listing CSV se saari product images ko SKU-wise folders mein automatically download karo.\nJo images pehle se hain, wo duplicate nahi hongi — zarurat padne par replace ho jayengi.",
             "#3b82f6"),
            ("Step 2:  Listing URL Extractor",
             "Apne saved Etsy listing pages (HTML files) se har product ka asli Etsy link nikalo.\nYe links baad mein Pinterest/Social media posting ke kaam aayengi.",
             "#8b5cf6"),
            ("Step 3:  Performance Report",
             "Dekho kaunsi listings kam visits/favourites le rahi hain, taaki pata chale kis product par dhyaan dena hai.\nEk Excel file milegi jismein sab data hoga aur ek alag 'weak listings' sheet bhi.",
             "#eab308"),
            ("Coming Soon:  Social Media Poster",
             "Apne products ko Instagram, Facebook aur Pinterest par automatically post karo.\nYe feature jaldi aa raha hai!",
             "#555555"),
        ]

        for title, desc, color in steps:
            card = ctk.CTkFrame(home, corner_radius=12)
            card.pack(fill="x", pady=8)
            
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=16, weight="bold"), text_color=color).pack(anchor="w", padx=20, pady=(15, 5))
            ctk.CTkLabel(card, text=desc, font=("Arial", 12), text_color="#bbbbbb", wraplength=700, justify="left").pack(anchor="w", padx=20, pady=(0, 15))

        # Get Started button
        ctk.CTkButton(home, text="Shuru Karein →  Image Organizer", font=ctk.CTkFont(size=15, weight="bold"),
                      height=45, fg_color="#3b82f6", hover_color="#2563eb",
                      command=lambda: self.tabview.set("Image Organizer")).pack(pady=(25, 10))

    # =======================================================
    # UI SETUP: IMAGE ORGANIZER
    # =======================================================
    def setup_org_ui(self):
        self.org_csv_path = ctk.StringVar()
        self.org_output_dir = ctk.StringVar()
        self.org_pause_event = threading.Event()
        self.org_pause_event.set()
        self.org_stop_event = threading.Event()
        self.org_stat_total = 0
        self.org_stat_new = 0
        self.org_stat_replaced = 0
        self.org_stat_failed = 0
        self.org_report_data = []
        self.org_lock = threading.Lock()

        self.tab_org.grid_columnconfigure(1, weight=1)
        self.tab_org.grid_rowconfigure(0, weight=1)

        # Sidebar (using rows: 0=title, 1=btn, 2=caption, 3=file_lbl, 4=btn, 5=caption, 6=folder_lbl, 7=start, 8=start_cap, 9=pause, 10=pause_cap, 11=stop, 12=stop_cap, 13=spacer)
        self.org_sidebar = ctk.CTkFrame(self.tab_org, width=260, corner_radius=0)
        self.org_sidebar.grid(row=0, column=0, sticky="nsew")
        self.org_sidebar.grid_rowconfigure(13, weight=1)

        ctk.CTkLabel(self.org_sidebar, text="Image Organizer", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 20))

        self.btn_org_csv = ctk.CTkButton(self.org_sidebar, text="CSV File Chunein", command=self.org_browse_csv)
        self.btn_org_csv.grid(row=1, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.org_sidebar, "Apni Etsy listing CSV file jismein SKU aur image links hon.", 2)
        self.lbl_org_csv = ctk.CTkLabel(self.org_sidebar, textvariable=self.org_csv_path, text_color="gray", font=("Arial", 10))
        self.lbl_org_csv.grid(row=3, column=0, padx=20, pady=(0, 10))

        self.btn_org_out = ctk.CTkButton(self.org_sidebar, text="Output Folder Chunein", command=self.org_browse_output)
        self.btn_org_out.grid(row=4, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.org_sidebar, "Wo folder jaha images SKU ke naam se save hongi.", 5)
        self.lbl_org_out = ctk.CTkLabel(self.org_sidebar, textvariable=self.org_output_dir, text_color="gray", font=("Arial", 10))
        self.lbl_org_out.grid(row=6, column=0, padx=20, pady=(0, 20))

        self.btn_org_start = ctk.CTkButton(self.org_sidebar, text="Download Shuru Karein", fg_color="green", hover_color="darkgreen", command=self.org_start)
        self.btn_org_start.grid(row=7, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.org_sidebar, "Images download hona shuru ho jayengi. Jo pehle se hain unhe update karega.", 8)

        self.btn_org_pause = ctk.CTkButton(self.org_sidebar, text="Pause", fg_color="orange", hover_color="darkorange", state="disabled", command=self.org_pause)
        self.btn_org_pause.grid(row=9, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.org_sidebar, "Beech mein rokne ke liye. Dobara dabayein to Resume ho jayega.", 10)
        
        self.btn_org_stop = ctk.CTkButton(self.org_sidebar, text="Band Karein", fg_color="red", hover_color="darkred", state="disabled", command=self.org_stop)
        self.btn_org_stop.grid(row=11, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.org_sidebar, "Poora process yahi rok dega. Report save ho jayegi.", 12)

        # Main View
        self.org_main = ctk.CTkFrame(self.tab_org, fg_color="transparent")
        self.org_main.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.org_main.grid_rowconfigure(2, weight=1)
        self.org_main.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.lbl_org_total = self.create_stat_card(self.org_main, "Total Found", "0", 0, 0)
        self.lbl_org_new = self.create_stat_card(self.org_main, "New Images", "0", 0, 1, color="#3b82f6")
        self.lbl_org_replaced = self.create_stat_card(self.org_main, "Replaced", "0", 0, 2, color="#eab308")
        self.lbl_org_failed = self.create_stat_card(self.org_main, "Failed", "0", 0, 3, color="#ef4444")

        ctk.CTkLabel(self.org_main, text="Live Progress", font=ctk.CTkFont(size=16, weight="bold")).grid(row=1, column=0, columnspan=4, sticky="w", pady=(20, 5))
        self.org_log_box = ctk.CTkTextbox(self.org_main, font=("Consolas", 12))
        self.org_log_box.grid(row=2, column=0, columnspan=4, sticky="nsew")
        self.org_log_box.insert("0.0", "Yaha par live updates dikhenge jab aap process start karenge.\n")
        self.org_log_box.configure(state="disabled")

        self.org_progress = ctk.CTkProgressBar(self.org_main)
        self.org_progress.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(20, 0))
        self.org_progress.set(0)

    # =======================================================
    # UI SETUP: LISTING URL EXTRACTOR
    # =======================================================
    def setup_ext_ui(self):
        self.ext_html_files = []
        self.ext_master_csv = ctk.StringVar(value=self.config.get("master_csv_path", ""))
        self.ext_pause_event = threading.Event()
        self.ext_pause_event.set()
        self.ext_stop_event = threading.Event()
        self.ext_stat_files = 0
        self.ext_stat_new = 0
        self.ext_stat_dupes = 0
        self.ext_stat_nosku = 0

        self.tab_ext.grid_columnconfigure(1, weight=1)
        self.tab_ext.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.ext_sidebar = ctk.CTkFrame(self.tab_ext, width=260, corner_radius=0)
        self.ext_sidebar.grid(row=0, column=0, sticky="nsew")
        self.ext_sidebar.grid_rowconfigure(15, weight=1)

        ctk.CTkLabel(self.ext_sidebar, text="URL Extractor", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 20))

        self.btn_ext_html = ctk.CTkButton(self.ext_sidebar, text="HTML Files Chunein", command=self.ext_browse_html)
        self.btn_ext_html.grid(row=1, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.ext_sidebar, "Apne saved Etsy Listings pages chunein (browser se Save As karke rakhi thi).", 2)
        self.lbl_ext_html = ctk.CTkLabel(self.ext_sidebar, text="No files selected", text_color="gray", font=("Arial", 10))
        self.lbl_ext_html.grid(row=3, column=0, padx=20, pady=(0, 10))

        self.btn_ext_master = ctk.CTkButton(self.ext_sidebar, text="Master CSV Chunein / Banayein", command=self.ext_browse_master)
        self.btn_ext_master.grid(row=4, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.ext_sidebar, "Ye file saari extract hui URLs yaad rakhti hai. Ek baar set karein, phir yaad rahega.", 5)
        self.lbl_ext_master = ctk.CTkLabel(self.ext_sidebar, textvariable=self.ext_master_csv, text_color="gray", font=("Arial", 10))
        self.lbl_ext_master.grid(row=6, column=0, padx=20, pady=(0, 15))

        self.btn_ext_start = ctk.CTkButton(self.ext_sidebar, text="URLs Nikaalein", fg_color="green", hover_color="darkgreen", command=self.ext_start)
        self.btn_ext_start.grid(row=7, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.ext_sidebar, "HTML files se SKU + Listing URL nikaal kar Master CSV mein save karega.", 8)

        self.btn_ext_pause = ctk.CTkButton(self.ext_sidebar, text="Pause", fg_color="orange", hover_color="darkorange", state="disabled", command=self.ext_pause)
        self.btn_ext_pause.grid(row=9, column=0, padx=20, pady=(5, 0))
        
        self.btn_ext_stop = ctk.CTkButton(self.ext_sidebar, text="Band Karein", fg_color="red", hover_color="darkred", state="disabled", command=self.ext_stop)
        self.btn_ext_stop.grid(row=10, column=0, padx=20, pady=(5, 0))
        
        ctk.CTkLabel(self.ext_sidebar, text="─── Alag Feature ───", text_color="#666666", font=("Arial", 10)).grid(row=11, column=0, pady=(15, 5))
        
        self.btn_ext_merge = ctk.CTkButton(self.ext_sidebar, text="Links Jodo Meri Listing CSV Mein", fg_color="#6366f1", hover_color="#4f46e5", command=self.ext_merge)
        self.btn_ext_merge.grid(row=12, column=0, padx=20, pady=(5, 0))
        self.add_caption(self.ext_sidebar, "Master CSV ki URLs ko aapki original listing CSV mein SKU se match karke jod dega.", 13)

        # Main View
        self.ext_main = ctk.CTkFrame(self.tab_ext, fg_color="transparent")
        self.ext_main.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.ext_main.grid_rowconfigure(2, weight=1)
        self.ext_main.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.lbl_ext_files = self.create_stat_card(self.ext_main, "Files Processed", "0", 0, 0)
        self.lbl_ext_new = self.create_stat_card(self.ext_main, "New Listings", "0", 0, 1, color="#3b82f6")
        self.lbl_ext_dupes = self.create_stat_card(self.ext_main, "Dupes Skipped", "0", 0, 2, color="#eab308")
        self.lbl_ext_nosku = self.create_stat_card(self.ext_main, "No-SKU Skipped", "0", 0, 3, color="#ef4444")

        ctk.CTkLabel(self.ext_main, text="Live Progress", font=ctk.CTkFont(size=16, weight="bold")).grid(row=1, column=0, columnspan=4, sticky="w", pady=(20, 5))
        self.ext_log_box = ctk.CTkTextbox(self.ext_main, font=("Consolas", 12))
        self.ext_log_box.grid(row=2, column=0, columnspan=4, sticky="nsew")
        self.ext_log_box.insert("0.0", "HTML files aur Master CSV select karein, phir 'URLs Nikaalein' dabayein.\n")
        self.ext_log_box.configure(state="disabled")

        self.ext_progress = ctk.CTkProgressBar(self.ext_main)
        self.ext_progress.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(20, 0))
        self.ext_progress.set(0)

    # =======================================================
    # UI SETUP: PERFORMANCE REPORT
    # =======================================================
    def setup_perf_ui(self):
        self.perf_html_files = []
        self.perf_pause_event = threading.Event()
        self.perf_pause_event.set()
        self.perf_stop_event = threading.Event()
        
        self.perf_stat_parsed = 0
        self.perf_stat_low_vis = 0
        self.perf_stat_low_fav = 0
        self.perf_stat_failed = 0

        self.tab_perf.grid_columnconfigure(1, weight=1)
        self.tab_perf.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.perf_sidebar = ctk.CTkFrame(self.tab_perf, width=260, corner_radius=0)
        self.perf_sidebar.grid(row=0, column=0, sticky="nsew")
        self.perf_sidebar.grid_rowconfigure(9, weight=1)

        ctk.CTkLabel(self.perf_sidebar, text="Performance Report", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 20))

        self.btn_perf_html = ctk.CTkButton(self.perf_sidebar, text="HTML Files Chunein", command=self.perf_browse_html)
        self.btn_perf_html.grid(row=1, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.perf_sidebar, "Wahi saved Etsy pages chunein (URL Extractor wali bhi chal jayengi).", 2)
        self.lbl_perf_html = ctk.CTkLabel(self.perf_sidebar, text="No files selected", text_color="gray", font=("Arial", 10))
        self.lbl_perf_html.grid(row=3, column=0, padx=20, pady=(0, 20))

        self.btn_perf_start = ctk.CTkButton(self.perf_sidebar, text="Excel Report Banayein", fg_color="green", hover_color="darkgreen", command=self.perf_start)
        self.btn_perf_start.grid(row=4, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.perf_sidebar, "Ek Excel file banegi jismein har listing ke visits, favourites, sales honge + weak listings ki sheet.", 5)

        self.btn_perf_pause = ctk.CTkButton(self.perf_sidebar, text="Pause", fg_color="orange", hover_color="darkorange", state="disabled", command=self.perf_pause)
        self.btn_perf_pause.grid(row=6, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.perf_sidebar, "Beech mein rokne ke liye.", 7)
        
        self.btn_perf_stop = ctk.CTkButton(self.perf_sidebar, text="Band Karein", fg_color="red", hover_color="darkred", state="disabled", command=self.perf_stop)
        self.btn_perf_stop.grid(row=8, column=0, padx=20, pady=(5, 0))

        # Main View
        self.perf_main = ctk.CTkFrame(self.tab_perf, fg_color="transparent")
        self.perf_main.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.perf_main.grid_rowconfigure(2, weight=1)
        self.perf_main.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.lbl_perf_parsed = self.create_stat_card(self.perf_main, "Listings Parsed", "0", 0, 0)
        self.lbl_perf_low_vis = self.create_stat_card(self.perf_main, "Low Visits", "0", 0, 1, color="#eab308")
        self.lbl_perf_low_fav = self.create_stat_card(self.perf_main, "Low Favourites", "0", 0, 2, color="#f97316")
        self.lbl_perf_failed = self.create_stat_card(self.perf_main, "Failed to Parse", "0", 0, 3, color="#ef4444")

        ctk.CTkLabel(self.perf_main, text="Live Progress", font=ctk.CTkFont(size=16, weight="bold")).grid(row=1, column=0, columnspan=4, sticky="w", pady=(20, 5))
        self.perf_log_box = ctk.CTkTextbox(self.perf_main, font=("Consolas", 12))
        self.perf_log_box.grid(row=2, column=0, columnspan=4, sticky="nsew")
        self.perf_log_box.insert("0.0", "HTML files select karein aur 'Excel Report Banayein' dabayein.\n")
        self.perf_log_box.configure(state="disabled")

        self.perf_progress = ctk.CTkProgressBar(self.perf_main)
        self.perf_progress.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(20, 0))
        self.perf_progress.set(0)

    # =======================================================
    # UI SETUP: SEWING TIP VIDEO PROMPTS
    # =======================================================
    def setup_video_ui(self):
        self.video_folder_path = ctk.StringVar()
        self.video_tech_sketch_path = ctk.StringVar()
        self.video_sewing_instr_path = ctk.StringVar()
        self.video_pattern_path = ctk.StringVar()

        self.tab_video.grid_columnconfigure(1, weight=1)
        self.tab_video.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.video_sidebar = ctk.CTkFrame(self.tab_video, width=260, corner_radius=0)
        self.video_sidebar.grid(row=0, column=0, sticky="nsew")
        self.video_sidebar.grid_rowconfigure(15, weight=1)

        ctk.CTkLabel(self.video_sidebar, text="Sewing Tip Prompts", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 20))

        self.btn_video_folder = ctk.CTkButton(self.video_sidebar, text="Listing Folder Chunein", command=self.video_browse_folder)
        self.btn_video_folder.grid(row=1, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.video_sidebar, "SKU folder jismein Technical Sketch, Sewing Instructions aur Pattern PDF hon.", 2)
        self.lbl_video_folder = ctk.CTkLabel(self.video_sidebar, text="No folder selected", text_color="gray", font=("Arial", 10))
        self.lbl_video_folder.grid(row=3, column=0, padx=20, pady=(0, 5))

        # Status labels for the 3 files
        self.lbl_video_tech = ctk.CTkLabel(self.video_sidebar, text="Technical Sketch: ❓", text_color="gray", font=("Arial", 10))
        self.lbl_video_tech.grid(row=4, column=0, padx=20, pady=(2, 0))
        self.lbl_video_sewing = ctk.CTkLabel(self.video_sidebar, text="Sewing Instructions: ❓", text_color="gray", font=("Arial", 10))
        self.lbl_video_sewing.grid(row=5, column=0, padx=20, pady=(2, 0))
        self.lbl_video_pattern = ctk.CTkLabel(self.video_sidebar, text="Pattern PDF: ❓", text_color="gray", font=("Arial", 10))
        self.lbl_video_pattern.grid(row=6, column=0, padx=20, pady=(2, 5))

        # Manual file browse buttons (for missing files)
        self.btn_video_tech_browse = ctk.CTkButton(self.video_sidebar, text="Technical Sketch Chunein", width=180, height=28, font=("Arial", 11), fg_color="#555555", command=self.video_browse_tech)
        self.btn_video_tech_browse.grid(row=7, column=0, padx=20, pady=(5, 0))
        self.btn_video_sewing_browse = ctk.CTkButton(self.video_sidebar, text="Sewing Instructions Chunein", width=180, height=28, font=("Arial", 11), fg_color="#555555", command=self.video_browse_sewing)
        self.btn_video_sewing_browse.grid(row=8, column=0, padx=20, pady=(5, 0))
        self.btn_video_pattern_browse = ctk.CTkButton(self.video_sidebar, text="Pattern PDF Chunein", width=180, height=28, font=("Arial", 11), fg_color="#555555", command=self.video_browse_pattern)
        self.btn_video_pattern_browse.grid(row=9, column=0, padx=20, pady=(5, 0))
        self.add_caption(self.video_sidebar, "Jo file auto-detect na ho, usse manually select karein.", 10)

        self.btn_video_generate = ctk.CTkButton(self.video_sidebar, text="Video Prompts Banayein", fg_color="green", hover_color="darkgreen", command=self.video_start)
        self.btn_video_generate.grid(row=11, column=0, padx=20, pady=(15, 0))
        self.add_caption(self.video_sidebar, "Har sewing step ke liye ek ready-to-copy Gemini video prompt banega.", 12)

        self.btn_video_reset = ctk.CTkButton(self.video_sidebar, text="\U0001f5d1 Reset / Naya Listing", fg_color="#dc2626", hover_color="#b91c1c", command=self.video_reset)
        self.btn_video_reset.grid(row=13, column=0, padx=20, pady=(10, 0))
        self.add_caption(self.video_sidebar, "Sab clear karke naye listing ke liye taiyaar.", 14)

        # Main View
        self.video_main = ctk.CTkFrame(self.tab_video, fg_color="transparent")
        self.video_main.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.video_main.grid_rowconfigure(1, weight=1)
        self.video_main.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.video_main, text="Generated Video Prompts", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))

        # Scrollable frame for prompt blocks
        self.video_scroll = ctk.CTkScrollableFrame(self.video_main, fg_color="transparent")
        self.video_scroll.grid(row=1, column=0, sticky="nsew")
        self.video_scroll.grid_columnconfigure(0, weight=1)

        # Log box at the bottom
        self.video_log_box = ctk.CTkTextbox(self.video_main, font=("Consolas", 11), height=100)
        self.video_log_box.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.video_log_box.insert("0.0", "Listing folder select karein aur 'Video Prompts Banayein' dabayein.\n")
        self.video_log_box.configure(state="disabled")

    # =======================================================
    # APP-LEVEL: REFRESH / RESTART
    # =======================================================
    def restart_app(self):
        """Restart the entire app process to pick up code changes."""
        import subprocess
        self.destroy()
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)

    # =======================================================
    # LOGIC: SEWING TIP VIDEO PROMPTS — RESET
    # =======================================================
    def video_reset(self):
        """Clear all selected files, prompts, and log for a fresh start."""
        # Clear file paths
        self.video_folder_path.set("")
        self.video_tech_sketch_path.set("")
        self.video_sewing_instr_path.set("")
        self.video_pattern_path.set("")

        # Reset labels
        self.lbl_video_folder.configure(text="No folder selected", text_color="gray")
        self.lbl_video_tech.configure(text="Technical Sketch: \u2753", text_color="gray")
        self.lbl_video_sewing.configure(text="Sewing Instructions: \u2753", text_color="gray")
        self.lbl_video_pattern.configure(text="Pattern PDF: \u2753", text_color="gray")

        # Clear all generated prompt blocks
        for widget in self.video_scroll.winfo_children():
            widget.destroy()

        # Clear log
        self.video_log_box.configure(state="normal")
        self.video_log_box.delete("0.0", "end")
        self.video_log_box.insert("0.0", "Reset ho gaya! Naya listing folder select karein aur 'Video Prompts Banayein' dabayein.\n")
        self.video_log_box.configure(state="disabled")

        # Re-enable generate button
        self.btn_video_generate.configure(state="normal")

    # =======================================================
    # LOGIC: SEWING TIP VIDEO PROMPTS
    # =======================================================
    def video_browse_folder(self):
        folderpath = filedialog.askdirectory()
        if folderpath:
            self.video_folder_path.set(folderpath)
            display_path = os.path.basename(folderpath) or folderpath
            self.lbl_video_folder.configure(text=display_path)
            # Auto-detect files
            self.video_auto_detect_files(folderpath)

    def video_auto_detect_files(self, folder):
        """Scan folder for the 3 required files and update status labels."""
        self.video_tech_sketch_path.set("")
        self.video_sewing_instr_path.set("")
        self.video_pattern_path.set("")

        files = os.listdir(folder)
        for fname in files:
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath):
                continue
            fname_lower = fname.lower()

            # Technical Sketch (PNG or PDF with "technical" and "sketch" in name)
            if ("technical" in fname_lower and "sketch" in fname_lower) or ("technical-sketch" in fname_lower):
                if fname_lower.endswith(('.png', '.pdf')):
                    self.video_tech_sketch_path.set(fpath)

            # Sewing Instructions (PDF with "sewing" and "instruction" in name)
            if "sewing" in fname_lower and "instruction" in fname_lower and fname_lower.endswith('.pdf'):
                self.video_sewing_instr_path.set(fpath)

            # Pattern PDF — any PDF that isn't the other two, try to match
            if fname_lower.endswith('.pdf') and "technical" not in fname_lower and "sewing" not in fname_lower:
                # Check if it contains "Pattern Name:" line
                try:
                    with pdfplumber.open(fpath) as pdf:
                        for page in pdf.pages[:3]:
                            text = page.extract_text() or ""
                            if "pattern name" in text.lower():
                                self.video_pattern_path.set(fpath)
                                break
                    if self.video_pattern_path.get():
                        break
                except Exception:
                    pass

        # Update status labels
        if self.video_tech_sketch_path.get():
            self.lbl_video_tech.configure(text=f"Technical Sketch: ✅ {os.path.basename(self.video_tech_sketch_path.get())}", text_color="#22c55e")
        else:
            self.lbl_video_tech.configure(text="Technical Sketch: ❌ Not found", text_color="#ef4444")

        if self.video_sewing_instr_path.get():
            self.lbl_video_sewing.configure(text=f"Sewing Instructions: ✅ {os.path.basename(self.video_sewing_instr_path.get())}", text_color="#22c55e")
        else:
            self.lbl_video_sewing.configure(text="Sewing Instructions: ❌ Not found", text_color="#ef4444")

        if self.video_pattern_path.get():
            self.lbl_video_pattern.configure(text=f"Pattern PDF: ✅ {os.path.basename(self.video_pattern_path.get())}", text_color="#22c55e")
        else:
            self.lbl_video_pattern.configure(text="Pattern PDF: ❌ Not found", text_color="#ef4444")

    def video_browse_tech(self):
        filepath = filedialog.askopenfilename(filetypes=[("Technical Sketch", "*.png;*.pdf")])
        if filepath:
            self.video_tech_sketch_path.set(filepath)
            self.lbl_video_tech.configure(text=f"Technical Sketch: ✅ {os.path.basename(filepath)}", text_color="#22c55e")

    def video_browse_sewing(self):
        filepath = filedialog.askopenfilename(filetypes=[("Sewing Instructions PDF", "*.pdf")])
        if filepath:
            self.video_sewing_instr_path.set(filepath)
            self.lbl_video_sewing.configure(text=f"Sewing Instructions: ✅ {os.path.basename(filepath)}", text_color="#22c55e")

    def video_browse_pattern(self):
        filepath = filedialog.askopenfilename(filetypes=[("Pattern PDF", "*.pdf")])
        if filepath:
            self.video_pattern_path.set(filepath)
            self.lbl_video_pattern.configure(text=f"Pattern PDF: ✅ {os.path.basename(filepath)}", text_color="#22c55e")

    def video_start(self):
        sewing_path = self.video_sewing_instr_path.get()
        if not sewing_path:
            messagebox.showwarning("Missing File", "Sewing Instructions PDF is required.\nPlease select the listing folder or manually browse for the file.")
            return

        # Clear log
        self.video_log_box.configure(state="normal")
        self.video_log_box.delete("0.0", "end")
        self.video_log_box.configure(state="disabled")

        # Clear previous prompt blocks
        for widget in self.video_scroll.winfo_children():
            widget.destroy()

        self.btn_video_generate.configure(state="disabled")
        threading.Thread(target=self.video_process, daemon=True).start()

    def video_extract_pattern_info(self, pdf_path):
        """Extract garment name and size info from Pattern PDF."""
        garment_name = ""
        size_info = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    for line in text.split('\n'):
                        line_stripped = line.strip()
                        # Pattern Name
                        if line_stripped.lower().startswith("pattern name"):
                            # Extract value after colon or after "Pattern Name"
                            parts = line_stripped.split(':', 1)
                            if len(parts) > 1:
                                raw_name = parts[1].strip()
                            else:
                                raw_name = line_stripped.replace("Pattern Name", "").strip()
                            # Parse garment name: text before " - Patterns" or " - PatternsByRish"
                            name_match = re.split(r'\s*-\s*Pattern', raw_name, maxsplit=1, flags=re.IGNORECASE)
                            garment_name = name_match[0].strip() if name_match else raw_name.strip()
                        # Size
                        if line_stripped.lower().startswith("size") or (line_stripped.lower().startswith("height") and "bust" in line_stripped.lower()):
                            size_info = line_stripped
        except Exception as e:
            self.log(self.video_log_box, f"⚠ Pattern PDF parse issue: {e}")
        return garment_name, size_info

    # -------------------------------------------------------
    # WATERMARK STRIPPING (applied before ANY text parsing)
    # -------------------------------------------------------
    # Matches the spaced-out diagonal watermark "P A T T E R N S B Y R I S H"
    # that pdfplumber extracts from the PDF.  Each letter can be separated by
    # arbitrary whitespace (spaces, tabs, even newlines in the raw dump).
    _WATERMARK_SPACED_RE = re.compile(
        r'\s*'.join(list('PATTERNSBYRISH')),
        re.IGNORECASE,
    )
    # Also catch compact forms and simple branding lines
    _WATERMARK_LINE_RE = re.compile(
        r'^\s*(patterns?\s*by\s*rish|patternsbyrish|pbr|©|copyright|all\s*rights\s*reserved)\s*$',
        re.IGNORECASE,
    )

    @classmethod
    def _strip_watermark_from_text(cls, text):
        """Remove all occurrences of the diagonal PATTERNSBYRISH watermark
        (in any spacing variant) from raw extracted PDF text, BEFORE line
        splitting or any other parsing."""
        # Pass 1 — remove spaced-out watermark fragments across the text
        text = cls._WATERMARK_SPACED_RE.sub('', text)
        # Pass 2 — remove any remaining full-line branding/watermark lines
        cleaned_lines = []
        for line in text.split('\n'):
            if cls._WATERMARK_LINE_RE.match(line.strip()):
                continue  # drop the entire line
            cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)

    def video_extract_tech_details(self, file_path):
        """Extract garment construction details from Technical Sketch file."""
        if not file_path:
            return ""
        if file_path.lower().endswith('.png'):
            self.log(self.video_log_box, "ℹ Technical Sketch is PNG — cannot extract text, skipping garment details.")
            return ""
        try:
            details = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    raw_text = page.extract_text() or ""
                    # Strip watermarks before parsing
                    text = self._strip_watermark_from_text(raw_text)
                    lines = text.split('\n')
                    found_heading = False
                    for i, line in enumerate(lines):
                        if "technical sketch" in line.lower():
                            found_heading = True
                            continue
                        if found_heading:
                            stripped = line.strip()
                            if stripped:
                                details = stripped
                                break
            return details
        except Exception as e:
            self.log(self.video_log_box, f"⚠ Technical Sketch PDF parse issue: {e}")
            return ""

    # -------------------------------------------------------
    # SEWING-STEP EXTRACTION — CONSTANTS & HELPERS
    # -------------------------------------------------------

    # Sewing action verbs — at least one must appear in a step's full
    # grouped content for the step to be kept.
    SEWING_ACTION_VERBS = {
        'stitch', 'sew', 'pin', 'press', 'trim', 'clip', 'understitch',
        'tack', 'fold', 'hem', 'baste', 'knot', 'grade', 'finish',
        'turn', 'apply', 'staystitch', 'topstitch', 'edgestitch',
        'serge', 'overlock', 'gather', 'pleat', 'interface', 'fuse',
        'slash', 'notch', 'ease', 'miter', 'bias', 'attach', 'join',
        'iron', 'cut', 'mark', 'transfer', 'secure', 'close', 'open',
        'insert', 'pull', 'align', 'match', 'place', 'layer', 'wrap',
        'roll', 'slide', 'zip', 'prepare',
    }

    # STEP N – TITLE heading keywords to exclude (case-insensitive
    # substring match on the TITLE portion after the dash).
    EXCLUDED_STEP_TITLE_KEYWORDS = [
        'fit check',
    ]

    # Format B heading regex: "STEP 1 – PREPARE THE PIECES"
    _STEP_HEADING_RE = re.compile(
        r'^STEP\s+\d+\s*[-\u2013\u2014:]\s*(.+)$',
        re.IGNORECASE,
    )

    # Closing-section markers (case-insensitive).  When any line contains
    # one of these, stop collecting content for the current step and do
    # NOT create a step for the marker itself.
    _CLOSING_MARKERS = [
        'you did it',
        'congratulations on finishing',
        'beginner troubleshooting tips',
        'helpful sewing terms',
    ]

    def _is_closing_marker(self, line):
        """Return True if this line is a closing-section marker."""
        low = line.lower()
        return any(m in low for m in self._CLOSING_MARKERS)

    def _is_excluded_step_title(self, heading):
        """Return True if a STEP N heading's title contains an excluded keyword."""
        m = self._STEP_HEADING_RE.match(heading)
        if m:
            title = m.group(1).strip().lower()
        else:
            title = heading.lower()
        for kw in self.EXCLUDED_STEP_TITLE_KEYWORDS:
            if kw in title:
                return True
        return False

    def _content_contains_sewing_verb(self, content_lines):
        """Return True if at least one sewing action verb appears in the
        combined content lines."""
        combined = ' '.join(content_lines).lower()
        for verb in self.SEWING_ACTION_VERBS:
            if re.search(r'\b' + re.escape(verb) + r'\w*\b', combined):
                return True
        return False

    # -------------------------------------------------------
    # MAIN EXTRACTION — FORMAT DETECTION + GROUPING
    # -------------------------------------------------------

    def video_extract_sewing_steps(self, pdf_path):
        """Extract sewing steps as [(heading, [content_lines]), ...].

        Algorithm:
        1. Strip watermarks from raw PDF text.
        2. Detect document format ONCE:
           - Format B if any STEP N lines found (ONLY those are headings).
           - Format A otherwise (short title lines followed by bullets).
        3. Group content under each heading.
        4. Filter: excluded heading keywords, then sewing-verb check.
        """
        try:
            full_text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    full_text += text + "\n"

            # Strip watermarks BEFORE any parsing
            full_text = self._strip_watermark_from_text(full_text)
            lines = full_text.split('\n')

            # --- Step 1: Detect format ---
            step_heading_indices = []
            for i, line in enumerate(lines):
                if self._STEP_HEADING_RE.match(line.strip()):
                    step_heading_indices.append(i)

            if step_heading_indices:
                self.log(self.video_log_box,
                         f"  Format B detected ({len(step_heading_indices)} STEP headings found)")
                raw_steps = self._extract_format_b(lines, step_heading_indices)
            else:
                self.log(self.video_log_box, "  Format A detected (plain headings)")
                raw_steps = self._extract_format_a(lines)

        except Exception as e:
            self.log(self.video_log_box, f"\u26a0 Sewing Instructions PDF parse issue: {e}")
            return []

        # --- Step 3 & 4: Filter ---
        valid_steps = []
        for heading, content in raw_steps:
            if self._is_excluded_step_title(heading):
                self.log(self.video_log_box,
                         f"  \u23ed Skipped excluded heading: \"{heading}\"")
                continue
            if not self._content_contains_sewing_verb(content):
                self.log(self.video_log_box,
                         f"  \u23ed Skipped (no sewing verbs): \"{heading}\"")
                continue
            valid_steps.append((heading, content))

        return valid_steps

    def _extract_format_b(self, lines, heading_indices):
        """Format B: STEP N headings ONLY.  Content for each step is
        everything between this heading and the next (or a closing marker
        / end of document)."""
        steps = []
        for pos, idx in enumerate(heading_indices):
            heading = lines[idx].strip()

            # Content runs from the line AFTER this heading to just before
            # the next STEP heading (or end of lines).
            start = idx + 1
            end = heading_indices[pos + 1] if pos + 1 < len(heading_indices) else len(lines)

            content = []
            for j in range(start, end):
                line = lines[j].strip()
                if not line:
                    continue
                # Stop if we hit a closing-section marker
                if self._is_closing_marker(line):
                    break
                content.append(line)

            if content:
                steps.append((heading, content))
        return steps

    def _extract_format_a(self, lines):
        """Format A: a candidate heading is a short line (< 60 chars) that
        is NOT a bullet and is immediately followed by at least one bullet
        line.  Nothing else counts as a heading."""
        steps = []
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            i += 1
            if not stripped:
                continue
            # Skip bullets / long lines — not candidate headings
            if (stripped.startswith('-') or stripped.startswith('\u2022')
                    or stripped.startswith('\u2013') or len(stripped) >= 60):
                continue
            # Must contain at least one 3+ letter word
            if not re.search(r'[a-zA-Z]{3,}', stripped):
                continue
            # Must start with uppercase
            if not stripped[0].isupper():
                continue
            # Now look ahead: must be followed by at least one bullet line
            bullets = []
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                if next_line.startswith('-') or next_line.startswith('\u2022') or next_line.startswith('\u2013'):
                    clean = re.sub(r'^[-\u2022\u2013]\s*', '', next_line)
                    if clean:
                        bullets.append(clean)
                    i += 1
                else:
                    # Non-bullet, non-empty line — stop collecting
                    break
            if bullets:
                steps.append((stripped, bullets))
        return steps

    # -------------------------------------------------------
    # ACTION TEXT BUILDER
    # -------------------------------------------------------

    def _build_action_description(self, step_heading, content_lines):
        """Condense a step's full grouped content into a 1-3 sentence
        natural-language action description in present-continuous tense,
        focusing on the most visually distinctive sewing actions."""
        # Extract the step title (without "STEP N –" prefix if present)
        m = self._STEP_HEADING_RE.match(step_heading)
        title = m.group(1).strip() if m else step_heading

        # Identify lines containing core sewing verbs (visually interesting)
        priority_verbs = {
            'stitch', 'sew', 'pin', 'understitch', 'topstitch',
            'edgestitch', 'staystitch', 'baste', 'gather', 'pleat',
            'serge', 'overlock', 'hem', 'insert', 'attach', 'zip',
        }
        secondary_verbs = {
            'press', 'trim', 'clip', 'fold', 'turn', 'finish',
            'knot', 'grade', 'tack', 'apply', 'fuse', 'interface',
            'cut', 'mark', 'transfer', 'secure', 'align', 'match',
            'place', 'layer', 'wrap', 'roll', 'prepare',
        }

        priority_lines = []
        secondary_lines = []
        for line in content_lines:
            low = line.lower()
            if any(re.search(r'\b' + v + r'\w*\b', low) for v in priority_verbs):
                priority_lines.append(line)
            elif any(re.search(r'\b' + v + r'\w*\b', low) for v in secondary_verbs):
                secondary_lines.append(line)

        # Pick the best 2-3 lines to summarise
        best = priority_lines[:3] if priority_lines else secondary_lines[:3]
        if not best:
            best = content_lines[:3]

        # Build a condensed present-continuous description
        action_parts = []
        for line in best[:3]:
            # Clean bullet prefixes
            clean = re.sub(r'^[-\u2022\u2013]\s*', '', line)
            clean = re.sub(r'^\d+[\.\\)]\s*', '', clean)
            if clean:
                action_parts.append(clean)

        if action_parts:
            action_desc = ' '.join(action_parts)
        else:
            action_desc = title

        return action_desc

    def video_build_prompt(self, step_heading, bullet_lines, garment_name, garment_details):
        """Build a single video prompt from a sewing step."""
        action_desc = self._build_action_description(step_heading, bullet_lines)

        garment_context = ""
        if garment_name:
            garment_context = f"This is for a {garment_name}"
            if garment_details:
                garment_context += f", described as: {garment_details}"
            garment_context += "."

        prompt = f"""Create a short, realistic, documentary-style video clip of someone sewing at a home sewing studio. The video must look like genuine handheld or tripod footage from a real sewing content creator \u2014 NOT like a polished AI-generated animation.

Subject & framing: Show only hands, forearms, the sewing machine or work surface, and the fabric/garment piece being worked on \u2014 no face, no head, no full body, no identifying features.

Action: {action_desc}

Garment context: {garment_context}

Setting: A cozy, lived-in home sewing studio \u2014 wooden table, natural daylight from a window, a few sewing supplies visible in the background slightly out of focus.

Camera realism cues: slight natural handheld camera shake, realistic depth of field (background soft, hands/fabric sharp), natural imperfect lighting, fabric moving and folding naturally with real texture and weight, no unnatural finger movements or fabric morphing. Hand movements must look genuinely human and unscripted \u2014 natural small pauses, slight hesitation, tiny adjustments and re-grips, uneven pacing \u2014 exactly like real unrehearsed footage, not a simulated animation.

Audio: natural ambient sewing machine or hand-sewing sound, no music, no voiceover.

Duration: 4-5 seconds.

End Card (last 1-2 seconds only): a brief, clean text overlay reading exactly: "Shop digital sewing patterns on Etsy: Patterns By Rish" \u2014 simple, centered, legible sans-serif font, no distortion. If this text doesn't render cleanly, the user will replace it manually in a video editor \u2014 that's expected and fine.

Style reference: authentic small-business sewist filming their own process for Instagram Reels on a phone \u2014 warm, cozy, real, unpolished-but-charming."""

        return prompt

    def video_add_prompt_block(self, step_heading, prompt_text, index):
        """Add a prompt block to the scrollable results area (must be called from main thread)."""
        block = ctk.CTkFrame(self.video_scroll, corner_radius=10)
        block.grid(row=index, column=0, sticky="ew", padx=5, pady=8)
        block.grid_columnconfigure(0, weight=1)

        # Header row
        header_frame = ctk.CTkFrame(block, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text=f'— Prompt for: "{step_heading}" —',
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#8b5cf6").grid(row=0, column=0, sticky="w")

        def copy_prompt():
            self.clipboard_clear()
            self.clipboard_append(prompt_text)
            copy_btn.configure(text="✓ Copied!", fg_color="#22c55e")
            self.after(1500, lambda: copy_btn.configure(text="Copy", fg_color="#6366f1"))

        copy_btn = ctk.CTkButton(header_frame, text="Copy", width=70, height=28, font=("Arial", 11),
                                  fg_color="#6366f1", hover_color="#4f46e5", command=copy_prompt)
        copy_btn.grid(row=0, column=1, padx=(10, 0))

        # Prompt text
        prompt_box = ctk.CTkTextbox(block, font=("Consolas", 11), height=180, wrap="word")
        prompt_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 10))
        prompt_box.insert("0.0", prompt_text)
        prompt_box.configure(state="disabled")

    def video_process(self):
        """Background thread: extract data and generate prompts."""
        try:
            self.log(self.video_log_box, "[SYSTEM] Starting prompt generation...")

            # --- Extract Pattern Info ---
            garment_name = ""
            size_info = ""
            pattern_path = self.video_pattern_path.get()
            if pattern_path:
                self.log(self.video_log_box, f"[FILE] Pattern: {os.path.basename(pattern_path)}")
                garment_name, size_info = self.video_extract_pattern_info(pattern_path)
                if garment_name:
                    self.log(self.video_log_box, f"  → Garment Name: {garment_name}")
                else:
                    self.log(self.video_log_box, "  ⚠ Could not extract garment name from Pattern PDF.")
                if size_info:
                    self.log(self.video_log_box, f"  → Size Info: {size_info}")
            else:
                self.log(self.video_log_box, "ℹ No Pattern PDF — garment name will be omitted from prompts.")

            # --- Extract Technical Sketch Details ---
            garment_details = ""
            tech_path = self.video_tech_sketch_path.get()
            if tech_path:
                self.log(self.video_log_box, f"[FILE] Technical Sketch: {os.path.basename(tech_path)}")
                garment_details = self.video_extract_tech_details(tech_path)
                if garment_details:
                    self.log(self.video_log_box, f"  → Details: {garment_details}")
                else:
                    self.log(self.video_log_box, "  ⚠ Could not extract construction details.")
            else:
                self.log(self.video_log_box, "ℹ No Technical Sketch — garment details will be omitted from prompts.")

            # --- Extract Sewing Steps ---
            sewing_path = self.video_sewing_instr_path.get()
            self.log(self.video_log_box, f"[FILE] Sewing Instructions: {os.path.basename(sewing_path)}")
            steps = self.video_extract_sewing_steps(sewing_path)

            if not steps:
                self.log(self.video_log_box, "\n[ERROR] No valid sewing steps could be extracted from the PDF.")
                self.log(self.video_log_box, "  Possible causes:")
                self.log(self.video_log_box, "  • The PDF doesn't contain recognizable section headings with sewing instructions.")
                self.log(self.video_log_box, "  • All detected sections were filtered out (non-instructional content only).")
                self.log(self.video_log_box, "  → Please manually check the PDF structure and ensure it has")
                self.log(self.video_log_box, "    sewing step headings (e.g. 'Sewing Darts on the Front')")
                self.log(self.video_log_box, "    followed by bullet-point instructions with sewing verbs.")
                messagebox.showwarning("No Steps Found",
                    "Could not extract any valid sewing steps from the PDF.\n\n"
                    "All detected sections were either non-instructional (fabric lists, metadata)\n"
                    "or did not contain sewing action verbs.\n\n"
                    "Please check the PDF structure manually.")
                return

            # --- Sanity-check preview ---
            step_names = [h for h, _ in steps]
            self.log(self.video_log_box, f"\n[SYSTEM] Detected {len(steps)} valid sewing steps: {step_names}")
            self.log(self.video_log_box, f"  ↑ Please visually confirm these are real construction steps before using the prompts.")
            self.log(self.video_log_box, f"\n[SYSTEM] Generating prompts...")

            # --- Generate Prompts ---
            for i, (heading, bullets) in enumerate(steps):
                prompt = self.video_build_prompt(heading, bullets, garment_name, garment_details)
                # Add block on main thread
                self.after(0, lambda h=heading, p=prompt, idx=i: self.video_add_prompt_block(h, p, idx))
                self.log(self.video_log_box, f"  ✅ Prompt generated: \"{heading}\"")
                time.sleep(0.05)

            self.log(self.video_log_box, f"\n[SYSTEM] Done! {len(steps)} video prompts ready to copy.")
            messagebox.showinfo("Prompts Ready", f"{len(steps)} video prompt(s) generated successfully!\n\nScroll through the results and click 'Copy' next to each prompt to paste into Gemini.")

        except Exception as e:
            err_msg = traceback.format_exc()
            self.log_error_to_file(err_msg)
            self.log(self.video_log_box, f"\n[CRITICAL ERROR] {str(e)}")
            messagebox.showerror("Critical Error", f"An unexpected error occurred:\n{str(e)}\n\nSee error_log.txt for details.")
        finally:
            self.btn_video_generate.configure(state="normal")

    # =======================================================
    # UI SETUP: SOCIAL MEDIA POSTER (COMING SOON)
    # =======================================================
    def setup_social_ui(self):
        placeholder = ctk.CTkFrame(self.tab_social, fg_color="transparent")
        placeholder.pack(fill="both", expand=True, padx=40, pady=40)

        ctk.CTkLabel(placeholder, text="Social Media Poster", font=ctk.CTkFont(size=28, weight="bold"), text_color="#555555").pack(pady=(80, 10))
        ctk.CTkLabel(placeholder, text="Coming Soon!", font=ctk.CTkFont(size=20, weight="bold"), text_color="#eab308").pack(pady=(0, 20))
        ctk.CTkLabel(placeholder, text="Ye feature jaldi aa raha hai!\n\nApne products ko Instagram, Facebook aur Pinterest par\nautomatically post kar payenge — seedha isi dashboard se.",
                     font=("Arial", 14), text_color="#888888", justify="center").pack(pady=10)

    # =======================================================
    # LOGIC: IMAGE ORGANIZER
    # =======================================================
    def org_browse_csv(self):
        filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if filepath:
            self.org_csv_path.set(filepath)
            self.lbl_org_csv.configure(text=os.path.basename(filepath))

    def org_browse_output(self):
        folderpath = filedialog.askdirectory()
        if folderpath:
            self.org_output_dir.set(folderpath)
            display_path = folderpath if len(folderpath) < 30 else "..." + folderpath[-27:]
            self.lbl_org_out.configure(text=display_path)

    def org_pause(self):
        if self.org_pause_event.is_set():
            self.org_pause_event.clear()
            self.btn_org_pause.configure(text="Resume", fg_color="green", hover_color="darkgreen")
            self.log(self.org_log_box, "[PAUSED] Waiting to resume...")
        else:
            self.org_pause_event.set()
            self.btn_org_pause.configure(text="Pause", fg_color="orange", hover_color="darkorange")
            self.log(self.org_log_box, "[RESUMED] Continuing process...")

    def org_stop(self):
        if not self.org_stop_event.is_set():
            self.org_stop_event.set()
            self.org_pause_event.set()
            self.log(self.org_log_box, "\n[SYSTEM] Stopping process... Please wait.")
            self.btn_org_stop.configure(state="disabled")

    def org_update_stats(self):
        self.lbl_org_total.configure(text=str(self.org_stat_total))
        self.lbl_org_new.configure(text=str(self.org_stat_new))
        self.lbl_org_replaced.configure(text=str(self.org_stat_replaced))
        self.lbl_org_failed.configure(text=str(self.org_stat_failed))

    def org_start(self):
        csv_file = self.org_csv_path.get()
        out_folder = self.org_output_dir.get()
        if not csv_file or not out_folder:
            messagebox.showwarning("Missing Input", "Please select both the CSV file and the Output Folder.")
            return

        # Pre-flight validation: CSV
        try:
            df = pd.read_csv(csv_file, nrows=0) # Just read headers
            sku_col = next((col for col in df.columns if 'sku' in col.lower()), None)
            if not sku_col:
                messagebox.showerror("Invalid CSV", "Could not find a 'sku' column in the selected CSV.")
                return
            image_cols = [col for col in df.columns if 'image' in col.lower()]
            if not image_cols:
                messagebox.showerror("Invalid CSV", "Could not find any 'image' columns in the selected CSV.")
                return
        except Exception as e:
            messagebox.showerror("Invalid CSV", f"Failed to read CSV file:\n{str(e)}")
            return

        # Pre-flight validation: Output folder
        try:
            test_file = os.path.join(out_folder, ".write_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            messagebox.showerror("Folder Error", f"Output folder is not writable or doesn't exist.\n{str(e)}")
            return

        self.org_stat_total = 0; self.org_stat_new = 0; self.org_stat_replaced = 0; self.org_stat_failed = 0
        self.org_report_data = []
        self.org_update_stats()
        
        self.org_log_box.configure(state="normal")
        self.org_log_box.delete("0.0", "end")
        self.org_log_box.configure(state="disabled")
        self.log(self.org_log_box, "[SYSTEM] Starting Organization Process...")

        self.btn_org_start.configure(state="disabled")
        self.btn_org_csv.configure(state="disabled")
        self.btn_org_out.configure(state="disabled")
        
        self.org_pause_event.set()
        self.btn_org_pause.configure(state="normal", text="Pause", fg_color="orange")
        self.btn_org_stop.configure(state="normal")
        self.org_stop_event.clear()
        
        threading.Thread(target=self.org_process, args=(csv_file, out_folder), daemon=True).start()

    # -------------------------------------------------------
    # IMAGE ORGANIZER — incremental sync
    # Rules:
    #  * New listing (no folder yet)      -> folder banta hai, saari images download
    #  * Same URL already in manifest     -> SKIP (kuch download nahi)
    #  * Image badli (same slot, new URL) -> purani _replaced/<date>/<SKU>/ me, nayi download
    #  * Image order badla (URL same)     -> sirf rename, download nahi
    #  * Image hata di                    -> purani _replaced/<date>/<SKU>/ me
    # manifest.json ab sirf main thread likhta hai (pehle 6 threads ek saath likhte the,
    # entries overwrite ho jaati thi, isliye har baar sab dobara download hota tha).
    # -------------------------------------------------------
    def org_load_manifest(self, sku_folder):
        path = os.path.join(sku_folder, "manifest.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def org_save_manifest(self, sku_folder, manifest):
        path = os.path.join(sku_folder, "manifest.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        os.replace(tmp, path)

    def org_move_to_replaced(self, out_folder, sku, filepath):
        import shutil
        dest_dir = os.path.join(out_folder, "_replaced", datetime.now().strftime("%Y-%m-%d"), sku)
        os.makedirs(dest_dir, exist_ok=True)
        base = os.path.basename(filepath)
        dest = os.path.join(dest_dir, base)
        n = 2
        while os.path.exists(dest):
            name, ext = os.path.splitext(base)
            dest = os.path.join(dest_dir, f"{name}_{n}{ext}")
            n += 1
        shutil.move(filepath, dest)

    def org_same_remote_size(self, url, filepath):
        """Old folders (made by the buggy version) may have a file but no manifest entry.
        A cheap HEAD request tells us if the file on disk is the same image, so we don't
        download it again."""
        try:
            res = requests.head(url, verify=False, timeout=10, allow_redirects=True)
            size = int(res.headers.get("Content-Length", "-1"))
            return res.status_code == 200 and size > 0 and size == os.path.getsize(filepath)
        except Exception:
            return False

    def org_download_worker(self, sku, filepath, url):
        """Downloads one image to a .part file, then renames. Does NOT touch the manifest.
        Returns (ok, error_message)."""
        self.org_pause_event.wait()
        if self.org_stop_event.is_set():
            return False, "stopped"
        time.sleep(0.15)
        tmp = filepath + ".part"
        delays = [1, 2, 4]
        last_err = ""
        for attempt in range(len(delays) + 1):
            if self.org_stop_event.is_set():
                break
            try:
                res = requests.get(url, stream=True, verify=False, timeout=20)
                if res.status_code != 200:
                    raise Exception(f"HTTP {res.status_code}")
                with open(tmp, "wb") as f:
                    for chunk in res.iter_content(65536):
                        if chunk:
                            f.write(chunk)
                if os.path.getsize(tmp) == 0:
                    raise Exception("empty file")
                os.replace(tmp, filepath)
                return True, ""
            except Exception as e:
                last_err = str(e)
                if attempt < len(delays):
                    with self.org_lock:
                        self.log(self.org_log_box, f"  -> [RETRY {attempt+1}/3] {sku}/{os.path.basename(filepath)} — {last_err}")
                    time.sleep(delays[attempt])
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass
        return False, last_err or "stopped"

    def org_process(self, csv_file, out_folder):
        try:
            df = pd.read_csv(csv_file)
            sku_col = next((col for col in df.columns if 'sku' in col.lower()), None)
            # Etsy columns are IMAGE1..IMAGE10; keep them in slot order
            image_cols = [col for col in df.columns if re.fullmatch(r'image\s*\d+', col.strip().lower())]
            if not image_cols:
                image_cols = [col for col in df.columns if 'image' in col.lower()]
            image_cols.sort(key=lambda c: int(re.sub(r'\D', '', c) or 0))

            total_rows = len(df)
            new_listings = changed_listings = skipped_listings = moved = renamed = 0
            seen_folders = set()

            for index, row in df.iterrows():
                if self.org_stop_event.is_set():
                    with self.org_lock:
                        self.log(self.org_log_box, "[SYSTEM] Process Stopped.")
                    break

                if pd.isna(row[sku_col]) or not str(row[sku_col]).strip():
                    continue
                sku = re.sub(r'[\\/:*?"<>|]', '-', str(row[sku_col]).strip())
                seen_folders.add(sku.lower())
                sku_folder = os.path.join(out_folder, sku)
                is_new = not os.path.isdir(sku_folder)
                os.makedirs(sku_folder, exist_ok=True)
                for leftover in os.listdir(sku_folder):
                    if leftover.endswith(".part") or leftover.endswith(".move"):
                        try: os.remove(os.path.join(sku_folder, leftover))
                        except Exception: pass

                manifest = self.org_load_manifest(sku_folder)
                wanted = {}  # filename -> url
                for col in image_cols:
                    url = row[col]
                    if pd.isna(url) or not str(url).strip():
                        continue
                    wanted[f"{col.strip().upper()}.jpg"] = str(url).strip()

                downloads = []   # (filename, url, action)
                changes = 0
                kept = set()
                parked = {}      # url -> parked file path (image moved to another slot)
                wanted_urls = set(wanted.values())

                # A) existing images from the manifest: keep, park (reordered) or move away
                for fname in list(manifest.keys()):
                    entry = manifest.get(fname) if isinstance(manifest.get(fname), dict) else {}
                    old_url = entry.get("url")
                    fpath = os.path.join(sku_folder, fname)
                    if not os.path.exists(fpath):
                        manifest.pop(fname, None)
                        continue
                    if wanted.get(fname) == old_url:
                        kept.add(fname)
                        continue
                    if old_url in wanted_urls and old_url not in parked:
                        os.replace(fpath, fpath + ".move")
                        parked[old_url] = fpath + ".move"
                    else:
                        self.org_move_to_replaced(out_folder, sku, fpath)
                        moved += 1
                    changes += 1
                    manifest.pop(fname, None)

                # A2) files from the old buggy version (file exists, no manifest entry)
                for fname, url in wanted.items():
                    fpath = os.path.join(sku_folder, fname)
                    if fname in kept or not os.path.exists(fpath):
                        continue
                    if url not in parked and self.org_same_remote_size(url, fpath):
                        manifest[fname] = {"url": url, "downloaded_at": datetime.now().isoformat(), "adopted": True}
                        kept.add(fname)
                    else:
                        self.org_move_to_replaced(out_folder, sku, fpath)
                        moved += 1; changes += 1

                # B) fill every remaining slot: rename a parked image, else download
                for fname, url in wanted.items():
                    if fname in kept:
                        continue
                    fpath = os.path.join(sku_folder, fname)
                    if url in parked and os.path.exists(parked[url]):
                        os.replace(parked.pop(url), fpath)
                        manifest[fname] = {"url": url, "downloaded_at": datetime.now().isoformat()}
                        renamed += 1; changes += 1
                    else:
                        downloads.append((fname, url, "NEW" if is_new else "REPLACED"))

                # C) anything still parked is no longer needed
                for p in parked.values():
                    if os.path.exists(p):
                        self.org_move_to_replaced(out_folder, sku, p)
                        moved += 1

                with self.org_lock:
                    self.org_stat_total += len(wanted)
                    if not downloads and not changes:
                        skipped_listings += 1
                        self.log(self.org_log_box, f"[SKIP] {sku} — no change")
                    else:
                        if is_new: new_listings += 1
                        else: changed_listings += 1
                        self.log(self.org_log_box, f"[{'NEW' if is_new else 'UPDATE'}] {sku} — {len(downloads)} image(s) to download")
                    self.org_update_stats()

                if downloads:
                    with ThreadPoolExecutor(max_workers=6) as executor:
                        futures = {executor.submit(self.org_download_worker, sku, os.path.join(sku_folder, f), u): (f, u, a) for f, u, a in downloads}
                        for future in as_completed(futures):
                            f, u, a = futures[future]
                            ok, err = future.result()
                            with self.org_lock:
                                if ok:
                                    manifest[f] = {"url": u, "downloaded_at": datetime.now().isoformat()}
                                    if a == "NEW": self.org_stat_new += 1
                                    else: self.org_stat_replaced += 1
                                    self.log(self.org_log_box, f"  -> [{a}] {f}")
                                    self.org_report_data.append(f"SUCCESS | SKU: {sku} | {f} | {a} | URL: {u}")
                                elif err != "stopped":
                                    self.org_stat_failed += 1
                                    self.log(self.org_log_box, f"  -> [FAILED] {f} ({err})")
                                    self.org_report_data.append(f"FAILED  | SKU: {sku} | {f} | ERROR: {err}")
                                self.org_update_stats()

                # only the main thread writes the manifest, once per SKU
                self.org_save_manifest(sku_folder, manifest)
                self.org_progress.set((index + 1) / total_rows)

            not_in_csv = [d for d in os.listdir(out_folder) if os.path.isdir(os.path.join(out_folder, d)) and d != "_replaced" and d.lower() not in seen_folders]
            summary = (f"New listings: {new_listings} | Updated listings: {changed_listings} | Skipped (no change): {skipped_listings} | "
                       f"Reordered: {renamed} | Old images moved to _replaced: {moved}")
            self.org_report_data.insert(0, summary)
            if not_in_csv:
                self.org_report_data.append("Folders not in this CSV (left untouched): " + ", ".join(sorted(not_in_csv)))
            if not self.org_stop_event.is_set():
                with self.org_lock:
                    self.log(self.org_log_box, "\n[SYSTEM] Finished! " + summary)
            self.org_generate_report(out_folder)

        except Exception as e:
            err_msg = traceback.format_exc()
            self.log_error_to_file(err_msg)
            with self.org_lock:
                self.log(self.org_log_box, f"\n[CRITICAL ERROR] {str(e)}")
            messagebox.showerror("Critical Error", f"An unexpected error occurred:\n{str(e)}\n\nSee error_log.txt for details.")
        finally:
            self.org_reset_ui()

    def org_generate_report(self, out_folder):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rpath = os.path.join(out_folder, f"Organizer_Report_{timestamp}.txt")
        with open(rpath, "w", encoding="utf-8") as f:
            f.write("="*50 + "\n ETSY IMAGE ORGANIZER - FINAL REPORT\n" + "="*50 + "\n\n")
            f.write(f" Total: {self.org_stat_total}\n New: {self.org_stat_new}\n Replaced: {self.org_stat_replaced}\n Failed: {self.org_stat_failed}\n\n")
            for line in self.org_report_data: f.write(line + "\n")
                
        with self.org_lock:
            self.log(self.org_log_box, f"[SYSTEM] Report saved: {rpath}")
        if not self.org_stop_event.is_set():
            msg = f"{self.org_report_data[0] if self.org_report_data else ''}\n\n{self.org_stat_new} new images, {self.org_stat_replaced} replaced, {self.org_stat_failed} failed.\nReport saved to {rpath}"
            messagebox.showinfo("Success", msg)

    def org_reset_ui(self):
        self.btn_org_start.configure(state="normal")
        self.btn_org_csv.configure(state="normal")
        self.btn_org_out.configure(state="normal")
        self.btn_org_pause.configure(state="disabled", text="Pause", fg_color="orange")
        self.btn_org_stop.configure(state="disabled")

    # =======================================================
    # LOGIC: URL EXTRACTOR
    # =======================================================
    def ext_browse_html(self):
        files = filedialog.askopenfilenames(filetypes=[("HTML Files", "*.html;*.htm")])
        if files:
            self.ext_html_files = files
            self.lbl_ext_html.configure(text=f"{len(files)} file(s) selected")

    def ext_browse_master(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if filepath:
            self.ext_master_csv.set(filepath)
            self.config["master_csv_path"] = filepath
            self.save_config()

    def ext_pause(self):
        if self.ext_pause_event.is_set():
            self.ext_pause_event.clear()
            self.btn_ext_pause.configure(text="Resume", fg_color="green")
            self.log(self.ext_log_box, "[PAUSED]")
        else:
            self.ext_pause_event.set()
            self.btn_ext_pause.configure(text="Pause", fg_color="orange")
            self.log(self.ext_log_box, "[RESUMED]")

    def ext_stop(self):
        if not self.ext_stop_event.is_set():
            self.ext_stop_event.set(); self.ext_pause_event.set()
            self.log(self.ext_log_box, "\n[SYSTEM] Stopping...")
            self.btn_ext_stop.configure(state="disabled")

    def ext_update_stats(self):
        self.lbl_ext_files.configure(text=str(self.ext_stat_files))
        self.lbl_ext_new.configure(text=str(self.ext_stat_new))
        self.lbl_ext_dupes.configure(text=str(self.ext_stat_dupes))
        self.lbl_ext_nosku.configure(text=str(self.ext_stat_nosku))

    def ext_start(self):
        if not self.ext_html_files or not self.ext_master_csv.get():
            messagebox.showwarning("Missing Input", "Select HTML files and Master CSV.")
            return

        self.ext_stat_files = 0; self.ext_stat_new = 0; self.ext_stat_dupes = 0; self.ext_stat_nosku = 0
        self.ext_update_stats()
        self.ext_log_box.configure(state="normal"); self.ext_log_box.delete("0.0", "end"); self.ext_log_box.configure(state="disabled")
        
        self.btn_ext_start.configure(state="disabled"); self.btn_ext_html.configure(state="disabled")
        self.btn_ext_master.configure(state="disabled"); self.btn_ext_merge.configure(state="disabled")
        self.btn_ext_pause.configure(state="normal", text="Pause", fg_color="orange")
        self.btn_ext_stop.configure(state="normal")
        self.ext_pause_event.set(); self.ext_stop_event.clear()
        
        threading.Thread(target=self.ext_process, daemon=True).start()

    def ext_process(self):
        master_csv = self.ext_master_csv.get()
        existing_ids = set()
        
        if os.path.exists(master_csv):
            try:
                df = pd.read_csv(master_csv)
                if 'LISTING_ID' in df.columns:
                    existing_ids = set(df['LISTING_ID'].astype(str))
            except: pass
        
        total = len(self.ext_html_files)
        master_f = open(master_csv, 'a', encoding='utf-8')
        if not os.path.exists(master_csv) or os.path.getsize(master_csv) == 0:
            master_f.write("SKU,LISTING_ID,TITLE,LISTING_URL\n")
            
        total_raw_cards = 0
        total_unique_listings = 0

        try:
            for idx, filepath in enumerate(self.ext_html_files):
                if self.ext_stop_event.is_set(): break
                self.ext_pause_event.wait()
                
                self.log(self.ext_log_box, f"\n[FILE] {os.path.basename(filepath)}")
                
                # Pre-flight check
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if "listing-editor/edit/" not in content:
                            self.log(self.ext_log_box, f"⚠ SKIPPED {os.path.basename(filepath)} — no listing cards found. Did you scroll to the bottom before saving this page?")
                            continue
                        soup = BeautifulSoup(content, 'html.parser')
                except Exception as e:
                    self.log(self.ext_log_box, f"  -> [ERROR] {e}"); continue
                    
                anchors = soup.find_all('a', href=re.compile(r'listing-editor/edit/\d+'))
                self.log(self.ext_log_box, f"  -> Found {len(anchors)} raw anchor links")
                total_raw_cards += len(anchors)
                
                # Dedupe anchors by listing ID, as Etsy may use multiple <a> tags per card
                cards_by_lid = {}
                for a in anchors:
                    match = re.search(r'listing-editor/edit/(\d+)', a.get('href', ''))
                    if match:
                        lid = match.group(1)
                        if lid not in cards_by_lid: cards_by_lid[lid] = []
                        cards_by_lid[lid].append(a)
                
                self.log(self.ext_log_box, f"  -> Processing {len(cards_by_lid)} unique cards")
                total_unique_listings += len(cards_by_lid)
                
                for lid, a_tags in cards_by_lid.items():
                    if self.ext_stop_event.is_set(): break
                    self.ext_pause_event.wait()
                    
                    data = None
                    for a in a_tags:
                        data = self.parse_listing_card(a)
                        if data: break
                        
                    if not data or not data['SKU']:
                        self.ext_stat_nosku += 1
                        continue
                        
                    lid = data['LISTING_ID']
                    if lid in existing_ids:
                        self.ext_stat_dupes += 1
                        self.log(self.ext_log_box, f"  -> [DUPE] {data['SKU']}")
                    else:
                        existing_ids.add(lid)
                        self.ext_stat_new += 1
                        self.log(self.ext_log_box, f"  -> [NEW] {data['SKU']}")
                        clean_title = data['TITLE'].replace('"', '""')
                        master_f.write(f'{data["SKU"]},{lid},"{clean_title}",{data["LISTING_URL"]}\n')
                        master_f.flush()
                        
                self.ext_stat_files += 1
                self.ext_update_stats()
                self.ext_progress.set((idx + 1) / total)
                time.sleep(0.1)

            if not self.ext_stop_event.is_set():
                self.log(self.ext_log_box, "\n[SYSTEM] Finished!")
                self.log(self.ext_log_box, f"Total raw cards found across all files: {total_raw_cards} | Unique listings after dedupe: {total_unique_listings} | Skipped (no SKU): {self.ext_stat_nosku}")
                messagebox.showinfo("Success", f"Extraction complete!\nSaved to:\n{master_csv}")

        except Exception as e:
            err_msg = traceback.format_exc()
            self.log_error_to_file(err_msg)
            self.log(self.ext_log_box, f"\n[CRITICAL ERROR] {str(e)}")
            messagebox.showerror("Critical Error", f"An unexpected error occurred:\n{str(e)}\n\nSee error_log.txt for details.")
        finally:
            master_f.close()
            self.ext_reset_ui()

    def ext_reset_ui(self):
        self.btn_ext_start.configure(state="normal")
        self.btn_ext_html.configure(state="normal")
        self.btn_ext_master.configure(state="normal")
        self.btn_ext_merge.configure(state="normal")
        self.btn_ext_pause.configure(state="disabled", text="Pause", fg_color="orange")
        self.btn_ext_stop.configure(state="disabled")

    def ext_merge(self):
        master_csv = self.ext_master_csv.get()
        if not master_csv or not os.path.exists(master_csv):
            messagebox.showerror("Error", "Extract URLs first.")
            return
            
        listings_csv = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not listings_csv: return
            
        out_csv = os.path.splitext(listings_csv)[0] + "_with_urls.csv"
        try:
            m_df = pd.read_csv(master_csv).drop_duplicates(subset=['SKU'])
            l_df = pd.read_csv(listings_csv)
            sku_col = next((c for c in l_df.columns if 'sku' in c.lower()), None)
            if not sku_col:
                messagebox.showerror("Error", "No SKU col found in Listings CSV.")
                return
                
            merged_df = pd.merge(l_df, m_df[['SKU', 'LISTING_ID', 'LISTING_URL']], left_on=sku_col, right_on='SKU', how='left')
            if 'SKU' in merged_df.columns and sku_col != 'SKU': merged_df.drop(columns=['SKU'], inplace=True)
                
            merged_df.to_csv(out_csv, index=False)
            miss = merged_df['LISTING_URL'].isna().sum()
            messagebox.showinfo("Complete", f"Merged CSV created!\n{miss} SKUs missing URLs.\nSaved: {out_csv}")
        except Exception as e:
            messagebox.showerror("Merge Error", str(e))

    # =======================================================
    # LOGIC: PERFORMANCE REPORT
    # =======================================================
    def perf_browse_html(self):
        files = filedialog.askopenfilenames(filetypes=[("HTML Files", "*.html;*.htm")])
        if files:
            self.perf_html_files = files
            self.lbl_perf_html.configure(text=f"{len(files)} file(s) selected")

    def perf_pause(self):
        if self.perf_pause_event.is_set():
            self.perf_pause_event.clear()
            self.btn_perf_pause.configure(text="Resume", fg_color="green")
            self.log(self.perf_log_box, "[PAUSED]")
        else:
            self.perf_pause_event.set()
            self.btn_perf_pause.configure(text="Pause", fg_color="orange")
            self.log(self.perf_log_box, "[RESUMED]")

    def perf_stop(self):
        if not self.perf_stop_event.is_set():
            self.perf_stop_event.set(); self.perf_pause_event.set()
            self.log(self.perf_log_box, "\n[SYSTEM] Stopping...")
            self.btn_perf_stop.configure(state="disabled")

    def perf_update_stats(self):
        self.lbl_perf_parsed.configure(text=str(self.perf_stat_parsed))
        self.lbl_perf_low_vis.configure(text=str(self.perf_stat_low_vis))
        self.lbl_perf_low_fav.configure(text=str(self.perf_stat_low_fav))
        self.lbl_perf_failed.configure(text=str(self.perf_stat_failed))

    def perf_start(self):
        if not self.perf_html_files:
            messagebox.showwarning("Missing Input", "Select HTML files.")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="Performance_Report.xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if not save_path: return

        self.perf_stat_parsed = 0; self.perf_stat_low_vis = 0; self.perf_stat_low_fav = 0; self.perf_stat_failed = 0
        self.perf_update_stats()
        self.perf_log_box.configure(state="normal"); self.perf_log_box.delete("0.0", "end"); self.perf_log_box.configure(state="disabled")
        
        self.btn_perf_start.configure(state="disabled"); self.btn_perf_html.configure(state="disabled")
        self.btn_perf_pause.configure(state="normal", text="Pause", fg_color="orange")
        self.btn_perf_stop.configure(state="normal")
        self.perf_pause_event.set(); self.perf_stop_event.clear()
        
        threading.Thread(target=self.perf_process, args=(save_path,), daemon=True).start()

    def perf_process(self, save_path):
        all_listings_map = {} # Dict to dedupe by LISTING_ID (keeps latest)
        
        total = len(self.perf_html_files)
        total_raw_cards = 0
        total_unique_listings = 0
        skipped_nosku = 0

        try:
            for idx, filepath in enumerate(self.perf_html_files):
                if self.perf_stop_event.is_set(): break
                self.perf_pause_event.wait()
                
                self.log(self.perf_log_box, f"\n[FILE] {os.path.basename(filepath)}")
                
                # Pre-flight check
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if "listing-editor/edit/" not in content:
                            self.log(self.perf_log_box, f"⚠ SKIPPED {os.path.basename(filepath)} — no listing cards found. Did you scroll to the bottom before saving this page?")
                            continue
                        soup = BeautifulSoup(content, 'html.parser')
                except Exception as e:
                    self.log(self.perf_log_box, f"  -> [ERROR] {e}"); continue
                    
                anchors = soup.find_all('a', href=re.compile(r'listing-editor/edit/\d+'))
                self.log(self.perf_log_box, f"  -> Found {len(anchors)} raw anchor links")
                total_raw_cards += len(anchors)
                
                # Dedupe anchors by listing ID
                cards_by_lid = {}
                for a in anchors:
                    match = re.search(r'listing-editor/edit/(\d+)', a.get('href', ''))
                    if match:
                        lid = match.group(1)
                        if lid not in cards_by_lid: cards_by_lid[lid] = []
                        cards_by_lid[lid].append(a)
                
                self.log(self.perf_log_box, f"  -> Processing {len(cards_by_lid)} unique cards")
                total_unique_listings += len(cards_by_lid)
                
                for lid, a_tags in cards_by_lid.items():
                    if self.perf_stop_event.is_set(): break
                    self.perf_pause_event.wait()
                    
                    try:
                        data = None
                        for a in a_tags:
                            data = self.parse_listing_card(a)
                            if data: break
                            
                        if not data or not data['SKU']:
                            self.log(self.perf_log_box, "  -> [SKIP] No SKU found")
                            skipped_nosku += 1
                            continue
                            
                        # Add DATA_COMPLETE boolean
                        data['DATA_COMPLETE'] = any(data[k] > 0 for k in ['VISITS_30D', 'FAVOURITES_30D', 'SALES_ALLTIME', 'REVENUE_ALLTIME'])
                        
                        # Overwrite if exists (smart refresh)
                        all_listings_map[data['LISTING_ID']] = data
                        self.perf_stat_parsed = len(all_listings_map)
                        self.log(self.perf_log_box, f"  -> [PARSED] SKU: {data['SKU']} | Vis: {data['VISITS_30D']} | Fav: {data['FAVOURITES_30D']}")
                    except Exception as e:
                        self.perf_stat_failed += 1
                        self.log(self.perf_log_box, f"  -> [FAILED] Card parse error: {e}")
                        
                self.perf_update_stats()
                self.perf_progress.set((idx + 1) / total)
                time.sleep(0.1)

            if not self.perf_stop_event.is_set():
                self.log(self.perf_log_box, "\n[SYSTEM] Generating Excel Report...")
                self.log(self.perf_log_box, f"Total raw cards found across all files: {total_raw_cards} | Unique listings after dedupe: {total_unique_listings} | Skipped (no SKU): {skipped_nosku}")
                self.perf_generate_excel(all_listings_map, save_path)

        except Exception as e:
            err_msg = traceback.format_exc()
            self.log_error_to_file(err_msg)
            self.log(self.perf_log_box, f"\n[CRITICAL ERROR] {str(e)}")
            messagebox.showerror("Critical Error", f"An unexpected error occurred:\n{str(e)}\n\nSee error_log.txt for details.")
        finally:
            self.perf_reset_ui()

    def perf_generate_excel(self, data_map, save_path):
        if not data_map:
            self.log(self.perf_log_box, "[SYSTEM] No valid listings parsed. Aborting Excel generation.")
            return

        df = pd.DataFrame(list(data_map.values()))
        
        # Sort by 30D visits ascending
        df = df.sort_values(by=['VISITS_30D'], ascending=True)

        # Calculate Low Performers (bottom 25% visits OR 0 favourites)
        # Using quantile for bottom 25%
        q25 = df['VISITS_30D'].quantile(0.25) if not df.empty else 0
        low_df = df[(df['VISITS_30D'] <= q25) | (df['FAVOURITES_30D'] == 0)]
        
        # Update UI stats
        self.perf_stat_low_vis = len(df[df['VISITS_30D'] <= q25])
        self.perf_stat_low_fav = len(df[df['FAVOURITES_30D'] == 0])
        self.perf_update_stats()

        cols_order = ['SKU', 'TITLE', 'PRICE', 'VISITS_30D', 'FAVOURITES_30D', 'SALES_ALLTIME', 'REVENUE_ALLTIME', 'RENEWALS_ALLTIME', 'LISTING_URL', 'DATA_COMPLETE']
        
        # Write to excel
        try:
            with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='All Listings', columns=cols_order, index=False)
                low_df.to_excel(writer, sheet_name='Low Performers', columns=cols_order, index=False)
                
            self.log(self.perf_log_box, f"[SUCCESS] Saved to {save_path}")
            messagebox.showinfo("Report Ready", f"Performance Report generated successfully!\n\nLow Performers found: {len(low_df)}\nSaved to:\n{save_path}")
        except Exception as e:
            self.log(self.perf_log_box, f"[EXCEL ERROR] {e}")
            messagebox.showerror("Excel Error", f"Failed to save Excel file:\n{e}\nMake sure the file is not open in another program.")

    def perf_reset_ui(self):
        self.btn_perf_start.configure(state="normal")
        self.btn_perf_html.configure(state="normal")
        self.btn_perf_pause.configure(state="disabled", text="Pause", fg_color="orange")
        self.btn_perf_stop.configure(state="disabled")


    # --- LISTING CONTENT GENERATOR LOGIC ---

    def setup_listing_ui(self):
        self.listing_folder_path = ctk.StringVar()
        self.listing_sku = ctk.StringVar()
        self.listing_cover_path = ctk.StringVar()
        self.listing_front_path = ctk.StringVar()
        self.listing_back_path = ctk.StringVar()
        self.listing_tech_path = ctk.StringVar()
        self.listing_sewing_path = ctk.StringVar()
        self.listing_pattern_path = ctk.StringVar()

        self.tab_listing.grid_columnconfigure(1, weight=1)
        self.tab_listing.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.listing_sidebar = ctk.CTkFrame(self.tab_listing, width=280, corner_radius=0)
        self.listing_sidebar.grid(row=0, column=0, sticky="nsew")
        self.listing_sidebar.grid_rowconfigure(15, weight=1)

        ctk.CTkLabel(self.listing_sidebar, text="Listing Content Generator", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 20))

        self.btn_listing_folder = ctk.CTkButton(self.listing_sidebar, text="📁 SKU Folder Chunein", command=self.listing_browse_folder)
        self.btn_listing_folder.grid(row=1, column=0, padx=20, pady=(10, 0))

        self.lbl_listing_sku = ctk.CTkLabel(self.listing_sidebar, text="SKU: No folder selected", font=ctk.CTkFont(weight="bold"))
        self.lbl_listing_sku.grid(row=2, column=0, padx=20, pady=(10, 5))

        # File status & Manual overrides
        status_font = ("Arial", 11)
        self.btn_lst_cover = ctk.CTkButton(self.listing_sidebar, text="Cover Image Chunein", width=180, height=28, fg_color="#555555", command=lambda: self.listing_browse_image('cover'))
        self.btn_lst_cover.grid(row=3, column=0, padx=20, pady=(10, 0))
        self.lbl_lst_cover = ctk.CTkLabel(self.listing_sidebar, text="Cover Image: ❓", text_color="gray", font=status_font)
        self.lbl_lst_cover.grid(row=4, column=0, padx=20, pady=(2, 5))

        self.btn_lst_front = ctk.CTkButton(self.listing_sidebar, text="Front Sketch Chunein", width=180, height=28, fg_color="#555555", command=lambda: self.listing_browse_image('front'))
        self.btn_lst_front.grid(row=5, column=0, padx=20, pady=(5, 0))
        self.lbl_lst_front = ctk.CTkLabel(self.listing_sidebar, text="Front Sketch: ❓", text_color="gray", font=status_font)
        self.lbl_lst_front.grid(row=6, column=0, padx=20, pady=(2, 5))

        self.btn_lst_back = ctk.CTkButton(self.listing_sidebar, text="Back Sketch Chunein", width=180, height=28, fg_color="#555555", command=lambda: self.listing_browse_image('back'))
        self.btn_lst_back.grid(row=7, column=0, padx=20, pady=(5, 0))
        self.lbl_lst_back = ctk.CTkLabel(self.listing_sidebar, text="Back Sketch: ❓", text_color="gray", font=status_font)
        self.lbl_lst_back.grid(row=8, column=0, padx=20, pady=(2, 10))

        # Garment Name Input
        self.ent_garment_name = ctk.CTkEntry(self.listing_sidebar, placeholder_text="Garment Name (e.g. Maxi Dress)", width=240)
        self.ent_garment_name.grid(row=9, column=0, padx=20, pady=(5, 10))

        self.btn_listing_generate = ctk.CTkButton(self.listing_sidebar, text="✨ Content Generate Karein", fg_color="green", hover_color="darkgreen", command=self.listing_start)
        self.btn_listing_generate.grid(row=10, column=0, padx=20, pady=(10, 0))

        self.btn_listing_reset = ctk.CTkButton(self.listing_sidebar, text="🗑 Reset", fg_color="#dc2626", hover_color="#b91c1c", command=self.listing_reset)
        self.btn_listing_reset.grid(row=11, column=0, padx=20, pady=(10, 20))

        ctk.CTkLabel(self.listing_sidebar, text="SKU History", font=ctk.CTkFont(weight="bold")).grid(row=12, column=0, padx=20, pady=(10, 0))
        self.listing_history_box = ctk.CTkTextbox(self.listing_sidebar, height=120, font=("Arial", 11))
        self.listing_history_box.grid(row=13, column=0, padx=20, pady=(5, 10), sticky="nsew")
        self.listing_history_box.configure(state="disabled")

        # Main Area
        self.listing_main = ctk.CTkFrame(self.tab_listing, fg_color="transparent")
        self.listing_main.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.listing_main.grid_rowconfigure(1, weight=1)
        self.listing_main.grid_columnconfigure(0, weight=1)

        self.listing_tabs = ctk.CTkTabview(self.listing_main)
        self.listing_tabs.grid(row=1, column=0, sticky="nsew")

        self.tab_etsy = self.listing_tabs.add("🟠 Etsy")
        self.tab_meta = self.listing_tabs.add("🔵 Meta")
        self.tab_pin = self.listing_tabs.add("🔴 Pinterest")

        # Setup Etsy Tab
        self.tab_etsy.grid_columnconfigure(1, weight=1)
        self.setup_copy_field(self.tab_etsy, 0, "Title (≤140 chars):", "etsy_title", height=50)
        self.setup_copy_field(self.tab_etsy, 1, "Description:", "etsy_desc", height=200)
        self.setup_copy_field(self.tab_etsy, 2, "Tags (13 tags):", "etsy_tags", height=50)
        self.setup_copy_field(self.tab_etsy, 3, "Alt Text - Cover:", "etsy_alt_cover", height=50)
        self.setup_copy_field(self.tab_etsy, 4, "Alt Text - Front:", "etsy_alt_front", height=50)
        self.setup_copy_field(self.tab_etsy, 5, "Alt Text - Back:", "etsy_alt_back", height=50)

        # Setup Meta Tab
        self.tab_meta.grid_columnconfigure(1, weight=1)
        self.setup_copy_field(self.tab_meta, 0, "Caption:", "meta_caption", height=150)
        self.setup_copy_field(self.tab_meta, 1, "Hashtags:", "meta_tags", height=100)
        self.setup_copy_field(self.tab_meta, 2, "Alt Text:", "meta_alt", height=50)

        # Setup Pinterest Tab
        self.tab_pin.grid_columnconfigure(1, weight=1)
        self.setup_copy_field(self.tab_pin, 0, "Title (≤100 chars):", "pin_title", height=50)
        self.setup_copy_field(self.tab_pin, 1, "Description (≤500 chars):", "pin_desc", height=150)
        self.setup_copy_field(self.tab_pin, 2, "Alt Text:", "pin_alt", height=50)

        # Log Box
        self.listing_log_box = ctk.CTkTextbox(self.listing_main, height=100, font=("Consolas", 11))
        self.listing_log_box.grid(row=2, column=0, sticky="ew", pady=(10,0))
        self.listing_log_box.insert("0.0", "Listing content generator ready.\n")
        self.listing_log_box.configure(state="disabled")

        self.listing_load_history()

    def setup_copy_field(self, parent, row, label_text, attr_name, height=50):
        ctk.CTkLabel(parent, text=label_text, font=ctk.CTkFont(weight="bold")).grid(row=row, column=0, padx=10, pady=(10,2), sticky="ne")
        textbox = ctk.CTkTextbox(parent, height=height, wrap="word")
        textbox.grid(row=row, column=1, padx=10, pady=(10,2), sticky="ew")
        btn_copy = ctk.CTkButton(parent, text="Copy", width=60, command=lambda t=textbox: self.copy_to_clipboard(t.get("0.0", "end-1c")))
        btn_copy.grid(row=row, column=2, padx=10, pady=(10,2), sticky="nw")
        setattr(self, f"txt_{attr_name}", textbox)

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def listing_browse_image(self, img_type):
        filepath = filedialog.askopenfilename(filetypes=[("Images", "*.jpg;*.jpeg;*.png")])
        if filepath:
            if img_type == 'cover':
                self.listing_cover_path.set(filepath)
                self._update_lst_label(self.lbl_lst_cover, "Cover Image", filepath)
            elif img_type == 'front':
                self.listing_front_path.set(filepath)
                self._update_lst_label(self.lbl_lst_front, "Front Sketch", filepath)
            elif img_type == 'back':
                self.listing_back_path.set(filepath)
                self._update_lst_label(self.lbl_lst_back, "Back Sketch", filepath)

    def listing_browse_folder(self):
        folderpath = filedialog.askdirectory()
        if folderpath:
            self.listing_folder_path.set(folderpath)
            sku = os.path.basename(folderpath)
            self.listing_sku.set(sku)
            self.lbl_listing_sku.configure(text=f"SKU: {sku}")
            self.listing_auto_detect_files(folderpath)

    def listing_auto_detect_files(self, folder):
        self.listing_cover_path.set("")
        self.listing_front_path.set("")
        self.listing_back_path.set("")
        self.listing_tech_path.set("")
        self.listing_sewing_path.set("")
        self.listing_pattern_path.set("")

        images = []

        files = os.listdir(folder)
        for fname in files:
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath): continue
            fname_lower = fname.lower()

            # PDFs
            if fname_lower.endswith('.pdf'):
                if "technical" in fname_lower and "sketch" in fname_lower:
                    self.listing_tech_path.set(fpath)
                elif "sewing" in fname_lower and "instruction" in fname_lower:
                    self.listing_sewing_path.set(fpath)
                else:
                    self.listing_pattern_path.set(fpath)

            # Images
            elif fname_lower.endswith(('.jpg', '.jpeg', '.png')):
                images.append(fpath)

        # Image Auto-Detection using PIL Color Entropy/Variance
        if images:
            img_stats = []
            for img_path in images:
                try:
                    with Image.open(img_path) as img:
                        img = img.convert('RGB')
                        stat = ImageStat.Stat(img)
                        # Sum of standard deviations of R, G, B channels
                        variance = sum(stat.stddev)
                        img_stats.append((variance, img_path))
                except Exception as e:
                    pass

            if img_stats:
                # Sort by variance descending
                img_stats.sort(key=lambda x: x[0], reverse=True)
                # Highest variance is likely the cover (model photo)
                self.listing_cover_path.set(img_stats[0][1])

                # Lowest variances are likely the line drawings (Front/Back)
                # Usually front is earlier in sequence than back, so sort the rest by filename
                line_drawings = [x[1] for x in img_stats[1:]]
                line_drawings.sort()
                if len(line_drawings) >= 1:
                    self.listing_front_path.set(line_drawings[0])
                if len(line_drawings) >= 2:
                    self.listing_back_path.set(line_drawings[1])

        # Update Labels
        self._update_lst_label(self.lbl_lst_cover, "Cover Image", self.listing_cover_path.get())
        self._update_lst_label(self.lbl_lst_front, "Front Sketch", self.listing_front_path.get())
        self._update_lst_label(self.lbl_lst_back, "Back Sketch", self.listing_back_path.get())

    def _update_lst_label(self, label, prefix, path):
        if path:
            label.configure(text=f"{prefix}: ✅ {os.path.basename(path)}", text_color="#22c55e")
        else:
            label.configure(text=f"{prefix}: ❌ Not found", text_color="#ef4444")

    def listing_reset(self):
        self.listing_folder_path.set("")
        self.listing_sku.set("")
        self.lbl_listing_sku.configure(text="SKU: No folder selected")
        self.ent_garment_name.delete(0, "end")
        self.listing_auto_detect_files("") # clears paths and labels

        fields = [
            "etsy_title", "etsy_desc", "etsy_tags", "etsy_alt_cover", "etsy_alt_front", "etsy_alt_back",
            "meta_caption", "meta_tags", "meta_alt",
            "pin_title", "pin_desc", "pin_alt"
        ]
        for field in fields:
            getattr(self, f"txt_{field}").delete("0.0", "end")

        self.listing_log_box.configure(state="normal")
        self.listing_log_box.delete("0.0", "end")
        self.listing_log_box.insert("0.0", "Reset complete.\n")
        self.listing_log_box.configure(state="disabled")

    def listing_save_history(self, sku, title, tags):
        history = {}
        if os.path.exists(LISTING_HISTORY_FILE):
            try:
                with open(LISTING_HISTORY_FILE, "r") as f:
                    history = json.load(f)
            except Exception:
                pass

        history[sku] = {
            "listing_date": time.strftime("%Y-%m-%d"),
            "title": title,
            "tags": tags
        }

        with open(LISTING_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)

        self.listing_load_history()

    def listing_load_history(self):
        if not os.path.exists(LISTING_HISTORY_FILE): return
        try:
            with open(LISTING_HISTORY_FILE, "r") as f:
                history = json.load(f)

            self.listing_history_box.configure(state="normal")
            self.listing_history_box.delete("0.0", "end")

            now = time.time()
            for sku, data in history.items():
                date_str = data.get("listing_date", "")
                if not date_str: continue

                try:
                    date_obj = time.strptime(date_str, "%Y-%m-%d")
                    age_days = (now - time.mktime(date_obj)) / (60*60*24)

                    if age_days < 30:
                        indicator = "🟢"
                    elif age_days < 90:
                        indicator = "🟡 (Refresh soon)"
                    else:
                        indicator = "🔴 (Refresh needed)"

                    self.listing_history_box.insert("end", f"{indicator} {sku} - {date_str}\n")
                except Exception:
                    pass

            self.listing_history_box.configure(state="disabled")
        except Exception:
            pass

    def listing_start(self):
        if not self.listing_folder_path.get():
            messagebox.showwarning("Missing Folder", "Please select a SKU folder first.")
            return
            
        if not self.ent_garment_name.get().strip():
            messagebox.showwarning("Missing Garment Name", "Please enter the Garment Name (e.g. Maxi Dress) so we can do accurate market research.")
            return

        self.btn_listing_generate.configure(state="disabled")
        self.listing_log_box.configure(state="normal")
        self.listing_log_box.delete("0.0", "end")
        self.listing_log_box.insert("0.0", "Starting content generation...\n")
        self.listing_log_box.configure(state="disabled")

        threading.Thread(target=self.listing_process, daemon=True).start()

    def listing_process(self):
        try:
            garment_name = self.ent_garment_name.get().strip()
            size_info = "Multiple Sizes"
            
            self.log(self.listing_log_box, f"Garment: {garment_name}")
            self.log(self.listing_log_box, "Performing deep market research...")

            research = self.listing_market_research(garment_name)

            api_key = self.config.get("gemini_api_key", "").strip()
            if api_key:
                self.log(self.listing_log_box, "Using Gemini AI Vision for generation...")
                self.listing_generate_gemini(api_key, garment_name, size_info, research)
            else:
                self.log(self.listing_log_box, "No Gemini API key found. Using Template Mode...")
                self.listing_generate_template(garment_name, size_info, research)

            self.listing_save_history(self.listing_sku.get(), self.txt_etsy_title.get("0.0", "end-1c"), self.txt_etsy_tags.get("0.0", "end-1c"))
            self.log(self.listing_log_box, "✨ Generation Complete!")
        except Exception as e:
            self.log(self.listing_log_box, f"❌ Error: {e}")
        finally:
            self.btn_listing_generate.configure(state="normal")

    def listing_market_research(self, garment_name):
        """Deep Etsy market research. Returns a dict with ranked keyword phrases, 
        competitor titles, competitor tags, and popularity-weighted phrase scores."""
        from collections import Counter
        
        research = {
            "competitor_titles": [],
            "competitor_tags": [],
            "ranked_phrases": [],       # frequency-ranked multi-word phrases
            "top_single_keywords": [],   # single high-frequency words (for fallback)
            "num_listings_analyzed": 0,
        }
        
        etsy_key = self.config.get("etsy_api_key", "").strip()
        etsy_secret = self.config.get("etsy_shared_secret", "").strip()
        query = garment_name.replace(" ", "+") + "+sewing+pattern"

        raw_listings = []

        if etsy_key and etsy_secret:
            self.log(self.listing_log_box, "Using Etsy API for deep research...")
            url = f"https://openapi.etsy.com/v3/application/listings/active?keywords={query}&limit=15&sort_on=score"
            headers = {
                "x-api-key": f"{etsy_key}:{etsy_secret}",
                "Accept": "application/json"
            }
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    for listing in data.get("results", []):
                        raw_listings.append({
                            "title": listing.get("title", ""),
                            "tags": listing.get("tags", []),
                            "views": listing.get("views", 0),
                            "num_favorers": listing.get("num_favorers", 0),
                        })
                else:
                    self.log(self.listing_log_box, f"Etsy API Error {response.status_code}. Falling back to scraper...")
            except Exception as e:
                self.log(self.listing_log_box, f"Etsy API Error: {e}. Falling back to scraper...")

        # Fallback to web scraper if API returned nothing
        if not raw_listings:
            self.log(self.listing_log_box, "Using web scraper for research...")
            url = f"https://www.etsy.com/search?q={query}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    for t in soup.find_all("h3")[:15]:
                        raw_listings.append({
                            "title": t.get_text().strip(),
                            "tags": [],
                            "views": 0,
                            "num_favorers": 0,
                        })
            except Exception as e:
                self.log(self.listing_log_box, f"Web scraper error: {e}")

        if not raw_listings:
            self.log(self.listing_log_box, "No competitor data found. Using generic defaults.")
            research["ranked_phrases"] = [("sewing pattern", 1), ("pdf pattern", 1), ("digital download", 1)]
            research["top_single_keywords"] = ["sewing", "pattern", "pdf", "digital", "download"]
            return research

        research["num_listings_analyzed"] = len(raw_listings)
        self.log(self.listing_log_box, f"Analyzing {len(raw_listings)} competing listings...")

        # Sort by popularity signal (favorites + views) so we can weight phrases
        raw_listings.sort(key=lambda x: x.get("num_favorers", 0) + x.get("views", 0), reverse=True)

        # --- Extract PHRASE-level data ---
        # We care about multi-word phrases (2-3 word combos), not single words
        phrase_counter = Counter()
        single_word_counter = Counter()
        
        stopwords = {"the", "and", "for", "with", "this", "that", "from", "your", "our", 
                      "you", "are", "was", "has", "have", "not", "but", "all", "can",
                      "will", "one", "two", "new", "its", "also", "each", "how",
                      "pdf", "svg", "a4", "a0", "instant", "download", "digital"}

        for idx, listing in enumerate(raw_listings):
            title = listing["title"]
            research["competitor_titles"].append(title)
            
            # Popularity weight: top-5 listings get 3x weight, next 5 get 2x, rest get 1x
            weight = 3 if idx < 5 else (2 if idx < 10 else 1)
            
            # Clean and tokenize title
            clean = re.sub(r'[^a-zA-Z\s]', ' ', title.lower())
            words = [w for w in clean.split() if len(w) > 2 and w not in stopwords]
            
            # Count single keywords
            for w in words:
                single_word_counter[w] += weight

            # Extract 2-word and 3-word phrases from title
            for n in [2, 3]:
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i:i+n])
                    phrase_counter[phrase] += weight

            # Process tags (these are the GOLD — actual tag phrases used by competitors)
            for tag in listing.get("tags", []):
                tag_clean = tag.strip().lower()
                if len(tag_clean) > 3:
                    research["competitor_tags"].append(tag_clean)
                    phrase_counter[tag_clean] += weight * 2  # Tags get double weight — they're curated SEO choices

        # Deduplicate competitor tags for logging
        tag_counter = Counter(research["competitor_tags"])
        
        # Build ranked phrases (filter out very low frequency noise)
        ranked = [(phrase, count) for phrase, count in phrase_counter.most_common(40) if count >= 2]
        research["ranked_phrases"] = ranked
        research["top_single_keywords"] = [w for w, c in single_word_counter.most_common(15)]

        # --- Log research summary for transparency ---
        self.log(self.listing_log_box, f"")
        self.log(self.listing_log_box, f"[RESEARCH] Analyzed {len(raw_listings)} competing listings.")
        self.log(self.listing_log_box, f"Top recurring keyword phrases (by weighted frequency):")
        for i, (phrase, count) in enumerate(ranked[:10]):
            self.log(self.listing_log_box, f"  {i+1}. \"{phrase}\" (score: {count})")
        
        if tag_counter:
            self.log(self.listing_log_box, f"Most common competitor tags:")
            for tag, cnt in tag_counter.most_common(8):
                self.log(self.listing_log_box, f"  - \"{tag}\" ({cnt}/{len(raw_listings)} listings)")
        self.log(self.listing_log_box, f"")

        return research

    def listing_generate_template(self, garment_name, size_info, research):
        """Generate listing content using templates grounded in research data."""
        # Extract top phrases for use in template
        phrases = [p for p, c in research.get("ranked_phrases", [])]
        top_phrase = phrases[0] if phrases else garment_name.lower()
        
        # Build title: front-load the best keyword phrase
        title = f"{top_phrase.title()} Sewing Pattern PDF | {garment_name} | {size_info} | Digital Download"
        title = title[:140]
        self._set_text(self.txt_etsy_title, title)

        # Build description with keyword phrases woven in
        feature_phrases = phrases[1:6] if len(phrases) > 1 else []
        features_text = "\n".join([f"- {p.title()}" for p in feature_phrases]) if feature_phrases else f"- {garment_name} sewing pattern"
        
        desc = f"""{title}

Sew your own beautiful {garment_name} with this professionally designed digital sewing pattern. Perfect for {', '.join(phrases[:3]) if phrases else 'all skill levels'}.

✨ Pattern Features:
{features_text}

📐 Sizes: {size_info}
🖨 Print Formats: A4, A0, US Letter
📥 Instant Digital Download

© Patterns By Rish — For personal use only."""
        self._set_text(self.txt_etsy_desc, desc)

        # Build 13 tags from research phrases (prefer multi-word, deduplicated)
        tag_candidates = []
        seen = set()
        for p in phrases:
            p_clean = p.strip()[:20]  # Etsy max 20 chars per tag
            if p_clean and p_clean not in seen:
                seen.add(p_clean)
                tag_candidates.append(p_clean)
            if len(tag_candidates) >= 13:
                break
        # Pad with defaults if needed
        defaults = ["sewing pattern", "pdf pattern", "digital download", "diy sewing", "handmade fashion"]
        for d in defaults:
            if len(tag_candidates) >= 13:
                break
            if d not in seen:
                tag_candidates.append(d)
                seen.add(d)
        
        tags = ", ".join(tag_candidates[:13])
        self._set_text(self.txt_etsy_tags, tags)

        self._set_text(self.txt_etsy_alt_cover, f"{garment_name} on model, {top_phrase} sewing pattern digital download."[:250])
        self._set_text(self.txt_etsy_alt_front, f"Front view technical sketch of {garment_name} {top_phrase} pattern."[:250])
        self._set_text(self.txt_etsy_alt_back, f"Back view technical sketch of {garment_name} {top_phrase} pattern."[:250])

        # Meta
        self._set_text(self.txt_meta_caption, f"New pattern alert! 🧵✨ Sew your own {garment_name}.\n{top_phrase.title()} — now available!\nLink in bio to shop!\n\n#patternsbyrish")
        meta_tags = " ".join([f"#{p.replace(' ', '')}" for p in phrases[:15]]) + " #sewing #sewingpattern #diyfashion #seamstress"
        self._set_text(self.txt_meta_tags, meta_tags)
        self._set_text(self.txt_meta_alt, f"{garment_name} on model, {top_phrase} sewing pattern."[:250])

        # Pinterest
        self._set_text(self.txt_pin_title, f"{top_phrase.title()} | {garment_name} Sewing Pattern"[:100])
        self._set_text(self.txt_pin_desc, f"Create your dream {garment_name} with this {top_phrase} digital PDF sewing pattern. Includes {size_info}. Click to shop!"[:500])
        self._set_text(self.txt_pin_alt, f"{garment_name} on model, {top_phrase} sewing pattern digital download."[:250])

    def listing_generate_gemini(self, api_key, garment_name, size_info, research):
        genai.configure(api_key=api_key)
        
        # Format research data for the prompt
        phrases_block = ""
        for i, (phrase, score) in enumerate(research.get("ranked_phrases", [])[:15]):
            phrases_block += f"  {i+1}. \"{phrase}\" (frequency score: {score})\n"
        
        sample_titles = ""
        for t in research.get("competitor_titles", [])[:8]:
            sample_titles += f"  - {t}\n"

        competitor_tags_block = ""
        tag_counter = {}
        for tag in research.get("competitor_tags", []):
            tag_counter[tag] = tag_counter.get(tag, 0) + 1
        sorted_tags = sorted(tag_counter.items(), key=lambda x: -x[1])[:20]
        for tag, cnt in sorted_tags:
            competitor_tags_block += f"  - \"{tag}\" (used by {cnt} listings)\n"

        prompt = f"""You are a world-class Etsy SEO specialist who has helped hundreds of sewing pattern shops reach Page 1 of Etsy search results. Your job is to create listing content that MAXIMIZES organic (non-paid) Etsy search ranking.

PRODUCT DETAILS:
- Garment: {garment_name}
- Sizes: {size_info}
- Brand: Patterns By Rish

REAL COMPETITOR RESEARCH (from {research.get('num_listings_analyzed', 0)} actual competing Etsy listings):

Top-ranking competitor titles:
{sample_titles}
Most frequently used keyword PHRASES across competitor titles and tags (ranked by frequency):
{phrases_block}
Most common competitor TAGS (these are the exact tag phrases real sellers chose):
{competitor_tags_block}

IMPORTANT: I am attaching images (Cover Image, Front Technical Sketch, Back Technical Sketch).
Read ALL text visible on the Front and Back Sketch images carefully — these contain the pattern's technical features (e.g., neckline type, sleeve style, hem details, dart placements, closures). List these features in the description.

=== STRICT ETSY SEO RULES (you MUST follow these) ===

TITLE (max 140 chars):
- Front-load the single highest-value 2-3 word keyword phrase from the research above in the FIRST 40 characters. Etsy search weighs the beginning of the title most heavily.
- Use natural, readable phrasing. Do NOT stuff with commas or pipe-separate random words.
- Every phrase in the title should be a phrase that ACTUALLY appeared in the competitor research above. Do NOT invent keyword phrases.
- Include the garment name + "sewing pattern" + "PDF" within the title.

TAGS (exactly 13 tags, comma-separated, each tag max 20 chars):
- Each tag should be a DISTINCT multi-word phrase (2-3 words). Single-word tags waste Etsy's tag slots.
- Prioritize tag phrases that appeared in MULTIPLE competitor listings (proven search demand).
- NO duplicate or near-duplicate tags (e.g., don't have both "maxi dress pattern" and "maxi dress sewing pattern" — pick the one with higher research frequency).
- Do NOT repeat words that are already in the title (Etsy already indexes the title).

DESCRIPTION:
- Open with the SAME front-loaded keyword phrase used at the start of the title (Etsy's algorithm weights the opening line of the description).
- Work in 5-8 of the researched keyword phrases naturally across the description (readable, benefit-focused sentences — NOT keyword stuffing).
- Include a "✨ Pattern Features:" section listing the technical features you extracted from the sketch images.
- End with standard footer: sizes, print formats (A4, A0, US Letter), instant digital download, © Patterns By Rish.

ALT TEXT (max 250 chars each):
- Describe what is LITERALLY visible in the image.
- Where natural, include ONE relevant keyword phrase from the research per alt text.

Provide the response in raw JSON format (no markdown code blocks, no backticks, just raw JSON) with these exact keys:
{{
    "etsy_title": "...",
    "etsy_desc": "...",
    "etsy_tags": "tag1, tag2, tag3, tag4, tag5, tag6, tag7, tag8, tag9, tag10, tag11, tag12, tag13",
    "etsy_alt_cover": "...",
    "etsy_alt_front": "...",
    "etsy_alt_back": "...",
    "meta_caption": "3-5 lines, engaging, emojis, call to action, include #patternsbyrish",
    "meta_tags": "20-30 relevant hashtags including #sewing #sewingpattern",
    "pin_title": "Max 100 chars.",
    "pin_desc": "Max 500 chars."
}}"""

        inputs = [prompt]
        if self.listing_cover_path.get() and os.path.exists(self.listing_cover_path.get()):
            inputs.append(Image.open(self.listing_cover_path.get()))
        if self.listing_front_path.get() and os.path.exists(self.listing_front_path.get()):
            inputs.append(Image.open(self.listing_front_path.get()))
        if self.listing_back_path.get() and os.path.exists(self.listing_back_path.get()):
            inputs.append(Image.open(self.listing_back_path.get()))

        response = None
        last_error = None

        for model_name in GEMINI_MODEL_FALLBACK_CHAIN:
            try:
                self.log(self.listing_log_box, f"Attempting generation with {model_name}...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(inputs)
                self.log(self.listing_log_box, f"Successfully generated content with {model_name}")
                break
            except Exception as e:
                error_msg = str(e)
                last_error = error_msg
                if "404" in error_msg or "not found" in error_msg.lower():
                    self.log(self.listing_log_box, f"Model {model_name} unavailable, trying next...")
                    continue
                else:
                    break

        if not response:
            self.log(self.listing_log_box, f"Gemini API Error: {last_error}. Falling back to Template Mode.")
            messagebox.showerror("Gemini AI Error", f"AI content generate nahi kar paya.\nError: {last_error}\n\nKya aapki Gemini API Key sahi hai? (Gemini keys 'AIza' se shuru hoti hain).\n\nApp basic template use kar raha hai.")
            self.listing_generate_template(garment_name, size_info, research)
            return

        try:
            text = response.text.strip()
            
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(text)

            self._set_text(self.txt_etsy_title, data.get("etsy_title", ""))
            self._set_text(self.txt_etsy_desc, data.get("etsy_desc", ""))
            self._set_text(self.txt_etsy_tags, data.get("etsy_tags", ""))
            self._set_text(self.txt_etsy_alt_cover, data.get("etsy_alt_cover", ""))
            self._set_text(self.txt_etsy_alt_front, data.get("etsy_alt_front", ""))
            self._set_text(self.txt_etsy_alt_back, data.get("etsy_alt_back", ""))

            self._set_text(self.txt_meta_caption, data.get("meta_caption", ""))
            self._set_text(self.txt_meta_tags, data.get("meta_tags", ""))
            self._set_text(self.txt_meta_alt, data.get("etsy_alt_cover", ""))

            self._set_text(self.txt_pin_title, data.get("pin_title", ""))
            self._set_text(self.txt_pin_desc, data.get("pin_desc", ""))
            self._set_text(self.txt_pin_alt, data.get("etsy_alt_cover", ""))

        except Exception as e:
            error_msg = str(e)
            self.log(self.listing_log_box, f"Response Parsing Error: {error_msg}. Falling back to Template Mode.")
            self.listing_generate_template(garment_name, size_info, research)

    def _set_text(self, widget, text):
        widget.delete("0.0", "end")
        widget.insert("0.0", text)


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    app = App()
    app.mainloop()
