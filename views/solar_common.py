"""
Solar/BBM Dashboard — Shared Helpers & Data Loading
Used by all 6 solar module files.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io
from utils.data_loader import load_solar_refueling
from utils.helpers import convert_df_to_excel

# ============================================================
# DESIGN SYSTEM
# ============================================================
COLORS = ['#FF6B35', '#F7931E', '#FFB627', '#06D6A0', '#118AB2',
          '#073B4C', '#EF476F', '#7209B7', '#3A0CA3', '#4CC9F0']
GRADIENT_BG = "linear-gradient(135deg,#1a1a2e 0%,#16213e 100%)"
CARD_BG = "linear-gradient(135deg,#0f172a,#1e293b)"
ACCENT = "#FF6B35"

BULAN_ORDER = {
    'Januari': 1, 'Februari': 2, 'Maret': 3, 'April': 4,
    'Mei': 5, 'Juni': 6, 'Juli': 7, 'Agustus': 8,
    'September': 9, 'Oktober': 10, 'November': 11, 'Desember': 12
}


def fmt(val, suffix=''):
    """Format large numbers: 1234 -> 1,234"""
    if val is None or pd.isna(val):
        return 'N/A'
    if abs(val) >= 1_000_000:
        return f"{val/1_000_000:,.1f}M{suffix}"
    if abs(val) >= 1_000:
        return f"{val:,.0f}{suffix}"
    return f"{val:,.1f}{suffix}"


def header(title, subtitle, icon="🛢️"):
    """Professional module header with gradient bar"""
    st.markdown(f"""
    <div style="background:{GRADIENT_BG};
         padding:1.5rem 2rem;border-radius:12px;margin-bottom:1.5rem;
         border-left:4px solid {ACCENT};">
        <h2 style="color:#fff;margin:0;font-size:1.6rem;">{icon} {title}</h2>
        <p style="color:#94a3b8;margin:0.3rem 0 0 0;font-size:0.9rem;">{subtitle}</p>
    </div>""", unsafe_allow_html=True)


def kpi_card(label, value, delta=None, icon="📊", help_text=None):
    """Render a single KPI card with optional delta indicator"""
    delta_html = ""
    if delta is not None:
        color = "#ef4444" if delta > 0 else "#22c55e"
        arrow = "↑" if delta > 0 else "↓"
        delta_html = f'<span style="color:{color};font-size:0.8rem;">{arrow} {abs(delta):.1f}%</span>'

    help_html = ""
    if help_text:
        help_html = f'<p style="color:#64748b;font-size:0.65rem;margin:0.2rem 0 0 0;">{help_text}</p>'

    st.markdown(f"""
    <div style="background:{CARD_BG};padding:1rem 1.2rem;
         border-radius:10px;border-left:3px solid {ACCENT};height:100%;">
        <p style="color:#94a3b8;font-size:0.75rem;margin:0;text-transform:uppercase;">{icon} {label}</p>
        <p style="color:#fff;font-size:1.5rem;font-weight:700;margin:0.3rem 0 0 0;">{value}</p>
        {delta_html}{help_html}
    </div>""", unsafe_allow_html=True)


def section(title):
    """Section subheader"""
    st.markdown(f"#### {title}")


def spacer():
    st.markdown("<br>", unsafe_allow_html=True)


def is_lkm_unit(name):
    """Check if unit uses L/Km metric (LV, Scania, Strada, Pickup)"""
    n = str(name).upper()
    return any(kw in n for kw in ['LV ', 'LV)', 'SCANIA', 'STRADA', 'PICK UP', 'PICKUP'])


# ============================================================
# DATA LOADING & FILTER APPLICATION
# ============================================================
def load_and_filter():
    """
    Load solar_refueling data and apply filters from sidebar (st.session_state.solar_filters).
    Filters are rendered in sidebar.py — this function only READS and APPLIES them.
    Returns: (df_full, df_filtered)
    """
    # Load from cache/DB
    df = st.session_state.get('df_solar_ref', pd.DataFrame())
    if df.empty:
        df = load_solar_refueling()
        if not df.empty:
            st.session_state['df_solar_ref'] = df

    if df.empty:
        return df, df

    # Ensure datetime
    if 'Tanggal' in df.columns:
        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')

    # Read filters from session_state (set by sidebar.py)
    filters = st.session_state.get('solar_filters', {})
    date_range = filters.get('date_range', None)
    sel_co = filters.get('perusahaan', [])
    sel_jenis = filters.get('jenis_alat', [])
    sel_units = filters.get('unit', [])

    # Apply filters
    mask = pd.Series([True] * len(df), index=df.index)

    if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        if 'Tanggal' in df.columns:
            mask &= df['Tanggal'] >= pd.Timestamp(date_range[0])
            mask &= df['Tanggal'] <= pd.Timestamp(date_range[1])

    if sel_co:
        mask &= df['Perusahaan'].isin(sel_co)
    if sel_jenis:
        mask &= df['Jenis_Alat'].isin(sel_jenis)
    if sel_units:
        mask &= df['Tipe_Unit'].isin(sel_units)

    return df, df[mask].copy()


def content_end_marker(count=25):
    """
    Clears out any 'ghost' elements (charts/tables from previously visited, 
    longer modules) by forcing Streamlit's Delta Generator to overwrite 
    the trailing positional slots with empty nodes.
    """
    for _ in range(count):
        st.empty()
