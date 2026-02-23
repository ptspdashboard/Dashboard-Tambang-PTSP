# ============================================================
# SETTINGS - Centralized Configuration
# ============================================================
import os
import hashlib
from pathlib import Path

# ============================================================
# 1. PATHS & ENVIRONMENT
# ============================================================
BASE_DIR = Path(__file__).parent.parent.absolute()
ASSETS_DIR = BASE_DIR / "assets"

# User Data Paths
USER_HOME = Path.home()
ONEDRIVE_PATH = USER_HOME / "OneDrive" / "Dashboard_Tambang"

DEFAULT_EXCEL_PATH = str(ONEDRIVE_PATH / "Monitoring.xlsx")
PRODUKSI_EXCEL_PATH = str(ONEDRIVE_PATH / "Produksi_UTSG_Harian.xlsx")
GANGGUAN_EXCEL_PATH = str(ONEDRIVE_PATH / "Gangguan_Produksi.xlsx")

MONITORING_EXCEL_PATH = os.getenv("MONITORING_FILE", DEFAULT_EXCEL_PATH)
PRODUKSI_FILE = os.getenv("PRODUKSI_FILE", PRODUKSI_EXCEL_PATH)
GANGGUAN_FILE = os.getenv("GANGGUAN_FILE", GANGGUAN_EXCEL_PATH)

# ============================================================
# ONEDRIVE CONFIGURATION (PUBLIC LINKS)
# ============================================================
# Paste your OneDrive Share Links here.
# Format: "https://1drv.ms/x/s!Am..."
# NOTE: Ensure the link permission is set to "Anyone with the link" (Public)
ONEDRIVE_LINKS = {
    "produksi": "https://1drv.ms/x/c/2C5FE08062FE9C86/IQB60Xmi1U3zSbKLtsoA6iCTAUSikpgSdjhXfNU5ESJJHos?e=dHmrpS",        # Produksi
    "gangguan": "https://1drv.ms/x/c/2C5FE08062FE9C86/IQDGAgAhw_g8T60j5r-48RCNAdkJqJvzTjzFiFysqVPH7Rw?e=SU3P09",        # Gangguan
    "monitoring": "https://1drv.ms/x/c/2C5FE08062FE9C86/IQCocd2EUJivQrPMCiYODE3iAZFdVY8U2kChWNr_2gMZWSI?e=omI2nK",      # Monitoring (Shipping & Stockpile)
    "daily_plan": "https://1drv.ms/x/c/2C5FE08062FE9C86/IQDjcJHcAkDsR6ZUoHVHSTVcAewqMFGMH5iSKbQCf5vD7V0?e=BFxDWH",      # Daily Plan
    "shipping": "",   # (Integrated in Monitoring)
    "stockpile": ""   # (Integrated in Monitoring)
}

# Try to load from Streamlit Secrets if available (prioritized for Cloud)
try:
    import streamlit as st
    if hasattr(st, "secrets") and "onedrive" in st.secrets:
        for key in ONEDRIVE_LINKS.keys():
            if key in st.secrets["onedrive"]:
                ONEDRIVE_LINKS[key] = st.secrets["onedrive"][key]
except:
    pass

CACHE_TTL = 3600  # 1 hour (was 300 seconds / 5 minutes)

def get_monitoring_path():
    if os.path.exists(MONITORING_EXCEL_PATH):
        return MONITORING_EXCEL_PATH
    return None

def get_assets_path(filename):
    return str(ASSETS_DIR / filename)

# ============================================================
# 2. AUTHENTICATION & USERS
# ============================================================
def hash_password(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def _load_users():
    """
    Load users from Streamlit Secrets (Cloud) or use hardcoded defaults (Local Dev).
    
    In Streamlit Secrets, define users like this:
    [users.admin_produksi]
    name = "Admin Produksi"
    role = "admin"
    password_hash = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
    
    [users.guest]
    name = "Tamu"
    role = "viewer"
    password_hash = "..."
    """
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "users" in st.secrets:
            users = {}
            for username, user_data in st.secrets["users"].items():
                users[username] = {
                    "name": user_data.get("name", username),
                    "role": user_data.get("role", "viewer"),
                    "password_hash": user_data.get("password_hash", ""),
                }
            if users:
                return users
    except Exception:
        pass

    # Fallback for local development only
    return {
        "admin_produksi": {
            "name": "Admin Produksi",
            "role": "admin",
            "password_hash": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
        },
        "guest": {
            "name": "Tamu",
            "role": "viewer",
            "password_hash": hash_password("guest")
        }
    }

USERS = _load_users()

# ============================================================
# 3. VISUAL STYLING (COLORS)
# ============================================================
MINING_COLORS = {
    'gold': '#d4a84b', 
    'blue': '#3b82f6', 
    'green': '#10b981', 
    'red': '#ef4444',
    'dark': '#0a1628',
    'light': '#f1f5f9'
}

COLORS = MINING_COLORS  # Alias

CHART_COLORS = [
    '#d4a84b', '#3b82f6', '#10b981', '#ef4444', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899'
]

CHART_SEQUENCE = CHART_COLORS

# ============================================================
# 4. OPERATIONAL CONSTANTS
# ============================================================
APP_TITLE = "Mining Dashboard | Semen Padang"
APP_ICON = str(ASSETS_DIR / "logo_semen_padang.jpg")

# Production Targets (Default Placeholders)
DAILY_PRODUCTION_TARGET = 18000  # Ton (Plan)
DAILY_INTERNAL_TARGET = 25000    # Ton (Internal)

# Shift Configuration
SHIFT_HOURS = 8
SHIFTS_PER_DAY = 3