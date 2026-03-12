# ============================================================
# MINING DASHBOARD - Semen Padang
# ============================================================
import streamlit as st

# Page Config (must be first Streamlit command)
st.set_page_config(
    page_title="Mining Dashboard | Semen Padang",
    page_icon="assets/logo_semen_padang.jpg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import components
from components import inject_css, show_login, render_sidebar
from views import (
    show_dashboard, 
    show_produksi,
    show_ritase,
    show_gangguan,
    show_daily_plan,
)

try:
    from views.process import show_process
except ImportError:
    def show_process(): st.title("⚙️ Stockpile & Process (Under Construction)")

try:
    from views.shipping import show_shipping
except ImportError:
    def show_shipping(): st.title("🚢 Sales & Shipping (Under Construction)")

from views.solar_ringkasan import show_solar_ringkasan
from views.solar_pemakaian import show_solar_pemakaian
from views.solar_efisiensi import show_solar_efisiensi
from views.solar_perusahaan import show_solar_perusahaan
from views.solar_hourmeter import show_solar_hourmeter
from views.solar_trend import show_solar_trend

# ============================================================
# SESSION STATE
# ============================================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.name = None

if 'current_menu' not in st.session_state:
    st.session_state.current_menu = "Ringkasan Eksekutif"

# Route map
ROUTE_MAP = {
    "Ringkasan Eksekutif": show_dashboard,
    "Executive Summary": show_dashboard,
    "Kinerja Produksi": show_produksi,
    "Produksi": show_produksi,
    "Aktivitas Ritase": show_ritase,
    "Ritase": show_ritase,
    "Stockpile & Pengolahan": show_process,
    "Stockpile & Proses": show_process,
    "Analisa Kendala": show_gangguan,
    "Gangguan Unit": show_gangguan,
    "Pengiriman & Logistik": show_shipping,
    "Rencana Harian": show_daily_plan,
    "Daily Plan": show_daily_plan,
    "Ringkasan BBM": show_solar_ringkasan,
    "Pemakaian Solar": show_solar_pemakaian,
    "Efisiensi BBM": show_solar_efisiensi,
    "Analisis Perusahaan": show_solar_perusahaan,
    "Hour Meter & Operasi": show_solar_hourmeter,
    "Trend & Perbandingan": show_solar_trend,
}


def main():
    inject_css()
    
    if not st.session_state.logged_in:
        show_login()
    else:
        if st.session_state.get('_menu_initialized') != st.session_state.username:
            if st.session_state.role == 'admin_solar':
                st.session_state.current_menu = "Ringkasan BBM"
            else:
                st.session_state.current_menu = "Ringkasan Eksekutif"
            st.session_state['_menu_initialized'] = st.session_state.username
        
        render_sidebar()
        
        menu = st.session_state.current_menu
        
        # --- POSITIONAL STRATAGEM (GHOSTING FIX) ---
        # Streamlit's Delta Generator reuses identically structured DOM slots 
        # (e.g., st.columns) across different module renders if they share the same tree index.
        # To break this and force a hard frontend unmount of all previous components,
        # we shift the starting index of the main block based on the menu sequence.
        menu_keys = list(ROUTE_MAP.keys())
        menu_idx = menu_keys.index(menu) if menu in menu_keys else 0
        
        for _ in range(menu_idx):
            st.empty()
            
        render_fn = ROUTE_MAP.get(menu)
        if render_fn is None:
            render_fn = show_solar_ringkasan if st.session_state.role == 'admin_solar' else show_dashboard
        
        # Render the target module normally
        render_fn()


if __name__ == "__main__":
    main()
