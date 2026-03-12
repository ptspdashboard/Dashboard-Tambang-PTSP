import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import load_stockpile_hopper, apply_global_filters
from utils.helpers import get_chart_layout
from datetime import datetime

def format_number(num):
    if num >= 1_000_000:
        return f"{num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    return f"{num:,.0f}"

def show_process():
    # Page Header
    st.markdown("""
    <div class="page-header">
        <div class="page-header-icon">⚙️</div>
        <div class="page-header-text">
            <h1>Stockpile & Process</h1>
            <p>Monitoring Arus Material & Utilitas Aset Crusher Feeding</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. LOAD DATA
    with st.spinner("Loading Process Data..."):
        df_hopper = load_stockpile_hopper()
        
    if df_hopper.empty:
        st.warning("⚠️ Data Stockpile Hopper tidak tersedia atau format tidak sesuai.")
        st.info("Pastikan sheet 'Stockpile Hopper' memiliki kolom: Date, Time, Shift, Dumping, Ritase, Rit.")
        return

    # Info Timestamp Debug
    last_update = st.session_state.get('last_update_stockpile', '-')
    st.caption(f"🕒 Data Downloaded At: **{last_update}** (Cloud Only Mode)")

    # 2. FILTER DATA (Date & Shift)
    df_filtered = apply_global_filters(df_hopper, date_col='Tanggal')

    if df_filtered.empty:
        st.warning("⚠️ Tidak ada data untuk filter yang dipilih.")
        return

    # Debug: Check columns (New Schema)
    # st.write("DEBUG Columns:", df_filtered.columns.tolist())
    # st.write("DEBUG ID Present:", 'id' in df_filtered.columns)
    # if 'id' in df_filtered.columns:
    #      st.write("DEBUG Top 5 rows:", df_filtered[['Jam', 'Shift', 'id']].head(5))
    
    required_cols = ['Ritase', 'Dumping', 'Unit', 'Jam']
    missing = [c for c in required_cols if c not in df_filtered.columns]
    if missing:
        st.error(f"⚠️ Missing Columns: {missing}")
        st.write("Available Columns:", df_filtered.columns.tolist())
        return

    # 3. ANALYSIS & KPI
    total_rit = df_filtered['Ritase'].sum()
    
    # Calculate Operating Hours (unique Tanggal + Jam combinations)
    # Using nunique() on Jam alone would undercount for multi-day ranges
    op_hours = df_filtered.drop_duplicates(subset=['Tanggal', 'Jam']).shape[0]
    feeding_rate = (total_rit / op_hours) if op_hours > 0 else 0
    
    # Best Shift
    shift_perf = df_filtered.groupby('Shift')['Ritase'].sum().sort_values(ascending=False)
    best_shift = shift_perf.index[0] if not shift_perf.empty else "-"
    best_shift_val = shift_perf.iloc[0] if not shift_perf.empty else 0
    
    # Active Fleet
    active_loaders = df_filtered['Dumping'].nunique()
    active_haulers = df_filtered['Unit'].nunique() # "Unit" is now Hauler

    # KPI CARDS
    kpi_html = f"""
    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem;">
        <div class="kpi-card" style="--card-accent: #3b82f6;">
            <div class="kpi-icon">📉</div>
            <div class="kpi-label">Total Ritase</div>
            <div class="kpi-value">{total_rit:,.0f}</div>
            <div class="kpi-subtitle">Total Trip</div>
        </div>
        <div class="kpi-card" style="--card-accent: #8b5cf6;">
            <div class="kpi-icon">⚡</div>
            <div class="kpi-label">Kecepatan Umpan</div>
            <div class="kpi-value">{feeding_rate:,.0f}</div>
            <div class="kpi-subtitle">Rit/Jam (Rata-rata)</div>
        </div>
        <div class="kpi-card" style="--card-accent: #10b981;">
            <div class="kpi-icon">🏆</div>
            <div class="kpi-label">Shift Terbaik</div>
            <div class="kpi-value">{best_shift}</div>
            <div class="kpi-subtitle">{format_number(best_shift_val)} Rit</div>
        </div>
        <div class="kpi-card" style="--card-accent: #f59e0b;">
            <div class="kpi-icon">🏭</div>
            <div class="kpi-label">Titik Dumping Aktif</div>
            <div class="kpi-value">{active_loaders}</div>
            <div class="kpi-subtitle">Lokasi / {active_haulers} Jenis Unit</div>
        </div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)
    
    # 4. CHARTS
    
    # A. Hourly Rhythm (Area Chart)
    # Extract hour from Jam column (handles both "HH:00-HH:00" format and integer)
    df_for_hourly = df_filtered.copy()
    def extract_hour(jam):
        try:
            s = str(jam)
            if ':' in s:
                return int(s.split(':')[0])
            return int(float(s))
        except:
            return -1
    df_for_hourly['Hour'] = df_for_hourly['Jam'].apply(extract_hour)
    df_for_hourly = df_for_hourly[df_for_hourly['Hour'] >= 0]
    
    hourly_rit = df_for_hourly.groupby('Hour')['Ritase'].sum().reset_index()
    hourly_rit.columns = ['Jam', 'Ritase']
    
    all_hours = pd.DataFrame({'Jam': range(24)})
    hourly_rit = all_hours.merge(hourly_rit, on='Jam', how='left').fillna(0)
    
    fig_hourly = px.area(
        hourly_rit, 
        x='Jam', 
        y='Ritase',
        title="<b>📈 TREN RITASE PER JAM (HOURLY)</b><br><span style='font-size: 12px; color: gray;'>Irama Operasi (Ritase per Jam)</span>",
        labels={'Jam': 'Jam Operasi', 'Ritase': 'Ritase'},
        color_discrete_sequence=['#3b82f6']
    )
    fig_hourly.update_traces(line_shape='spline', fill='tozeroy', fillcolor="rgba(59, 130, 246, 0.2)")
    layout_hourly = get_chart_layout(height=400)
    layout_hourly['xaxis'].update(dict(tickmode='linear', dtick=1, title="Jam Operasi"))
    fig_hourly.update_layout(**layout_hourly)

    # B. Shift Comparison
    chart_shift_perf = df_filtered.groupby('Shift')['Ritase'].sum().reset_index()
    chart_shift_perf['Shift'] = 'Shift ' + chart_shift_perf['Shift'].astype(str)
    
    # Distinct colors per shift (matching reference)
    SHIFT_COLORS = {'Shift 1': '#3b82f6', 'Shift 2': '#8b5cf6', 'Shift 3': '#06b6d4'}
    
    fig_shift = px.bar(
        chart_shift_perf, 
        x='Shift', 
        y='Ritase',
        title="<b>📊 KONTRIBUSI SHIFT (RITASE)</b><br><span style='font-size: 12px; color: gray;'>Perbandingan Produktivitas Regu</span>",
        text='Ritase',
        color='Shift',
        color_discrete_map=SHIFT_COLORS
    )
    fig_shift.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    fig_shift.update_layout(showlegend=False)
    fig_shift.update_layout(**get_chart_layout(height=400))

    # C. Loader Contribution (Was Unit)
    # Using 'Dumping' column
    unit_perf = df_filtered.groupby('Dumping')['Ritase'].sum().sort_values(ascending=True).reset_index()
    fig_unit = px.bar(
        unit_perf,
        y='Dumping',
        x='Ritase',
        title="<b>🏭 Peringkat Titik Dumping (Hopper)</b><br><span style='font-size: 12px; color: gray;'>Kontribusi per Lokasi Dumping</span>",
        orientation='h',
        text='Ritase',
        color_discrete_sequence=['#10b981']
    )
    fig_unit.update_traces(texttemplate='%{text}', textposition='outside')
    fig_unit.update_layout(**get_chart_layout(height=380))
    fig_unit.update_xaxes(showgrid=True, gridcolor='#333')

    # D. Hauler Share (Was Hauler, Now Unit)
    # Using 'Unit' column (Hauler/Vendor)
    # Reverted to Donut Chart because data is categorical (HD, UTSG)
    hauler_share = df_filtered.groupby('Unit')['Ritase'].sum().reset_index()
    fig_hauler = px.pie(
        hauler_share,
        names='Unit',
        values='Ritase',
        title="<b>🚚 KONTRIBUSI VENDOR / UNIT ANGKUT</b><br><span style='font-size: 12px; color: gray;'>Porsi Ritase per Grup Unit</span>",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    fig_hauler.update_traces(textposition='inside', textinfo='percent+label')
    layout_hauler = get_chart_layout(height=380)
    layout_hauler['legend'].update(dict(orientation="h", yanchor="bottom", y=-0.2))
    fig_hauler.update_layout(**layout_hauler)

    # LAYOUT GRID
    col1, col2 = st.columns([1.5, 1])
    with col1:
        with st.container(border=True):
            st.plotly_chart(fig_hourly, use_container_width=True)
    with col2:
        with st.container(border=True):
            st.plotly_chart(fig_shift, use_container_width=True)
    
    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            st.plotly_chart(fig_unit, use_container_width=True)
    with col4:
        with st.container(border=True):
            st.plotly_chart(fig_hauler, use_container_width=True)

    # RAW DATA PREVIEW
    with st.expander("🔍 Lihat Data Detail", expanded=True):
        # Prepare Display Dataframe
        df_display = df_filtered.copy()
        
        # 1. Sort: Latest data (Bottom of Excel) at Top of Dashboard = Shift 3 Top
        # Empirical Data: Shift 1 (High ID), Shift 3 (Low ID) -> We need ID ASC to show Shift 3 at Top
        if 'id' in df_display.columns:
            df_display = df_display.sort_values(by='id', ascending=True) 
        elif 'Row_Order' in df_display.columns:
            df_display = df_display.sort_values(by='Row_Order', ascending=True)
        else:
            # Fallback: Date Desc, Time Desc (Explicit)
            if 'Tanggal' in df_display.columns and 'Jam' in df_display.columns:
                # Custom sort for Time to handle 00:00 as 'End'
                # But ID sort preferred
                 df_display = df_display.sort_values(by=['Tanggal', 'Jam'], ascending=[False, False])
        
        # 2. Format Date
        df_display['Date'] = df_display['Tanggal'].astype(str)
        
        # 3. Rename Columns to Match Excel Headers request:
        # Internal -> External
        # Jam -> Time
        # dumping -> Dumping 
        # Unit -> Unit (Hauler)
        # Ritase -> Ritase (Count)
        df_display = df_display.rename(columns={
            'Jam': 'Time',
            'Jam_Range': 'Time',
            # 'Dumping' already named 'Dumping'
            'Unit': 'Unit',
            'Ritase': 'Ritase'
        })
        
        # 4. Select Columns
        cols_to_show = ['Date', 'Time', 'Shift', 'Dumping', 'Unit', 'Ritase']
        # Filter only existing columns
        cols_to_show = [c for c in cols_to_show if c in df_display.columns]
        
        st.dataframe(df_display[cols_to_show], use_container_width=True, hide_index=True)
        
        # Excel Download (Sort Ascending = Oldest Data First)
        # Empirical: Shift 1 (High ID) -> We need ID DESC to show Shift 1 at Top
        df_download_source = df_display.copy()
        if 'id' in df_download_source.columns:
             df_download_source = df_download_source.sort_values(by='id', ascending=False)
        else:
             # Fallback reverse of dashboard
             df_download_source = df_download_source.iloc[::-1]
             
        df_download = df_download_source[cols_to_show]
        
        from utils.helpers import convert_df_to_excel
        excel_data = convert_df_to_excel(df_download)
        
        st.download_button(
            label="📥 Unduh Data Stockpile (Excel)",
            data=excel_data,
            file_name=f"PTSP_Stockpile_Process_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
        
    # --- GHOSTING FIX: Trailing Padding ---
    # Append empty slots to overwrite any trailing DOM remnants from other longer modules
    for _ in range(25):
        st.empty()
