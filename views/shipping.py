# ============================================================
# SHIPPING - Sales & Shipping Dashboard
# ============================================================
# Industry-grade mining operations monitoring
# Version 3.0 - Executive Standard (No S-Curve)

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from utils.data_loader import load_shipping_data, apply_global_filters
from utils.helpers import get_chart_layout

def show_shipping():
    """Sales & Shipping Analysis - Executive View"""
    
    # 1. GET PRELOADED DATA (INSTANT)
    df_shipping = st.session_state.get('df_shipping', pd.DataFrame())
    
    # Fallback if not preloaded
    if df_shipping.empty:
        with st.spinner("Memuat Data Pengiriman..."):
            df_shipping = load_shipping_data()
            if not df_shipping.empty:
                st.session_state['df_shipping'] = df_shipping
    
    # Set source indicator
    if not df_shipping.empty:
        st.session_state['last_update_shipping'] = "Database"
    
    # Timestamp Info
    # Timestamp Info & Data Range
    last_update = st.session_state.get('last_update_shipping', '-')
    max_date = df_shipping['Date'].max().strftime('%d %b %Y') if not df_shipping.empty and 'Date' in df_shipping.columns else "-"
    st.caption(f"🕒 Last Sync: **{last_update}** | 📅 Data Sampai: **{max_date}** | ⚡ Ver: Database Mode")

    df = apply_global_filters(df_shipping, date_col='Date')
    
    if df.empty:
        st.warning("⚠️ Data Pengiriman tidak tersedia.")
        return

    # 2. DATA PROCESSING (Material Focus)
    # Ensure columns exist (loaded by updated loader with DB names)
    # DB Columns: ap_ls, ap_ls_mk3, ap_ss, total_ls, total_ss
    cols_check = ['ap_ls', 'ap_ls_mk3', 'ap_ss', 'total_ls', 'total_ss']
    for c in cols_check:
        if c not in df.columns: df[c] = 0
        
    # Calculate Quantity for internal logic (KPIs/Charts) but DO NOT SHOW in table
    # Quantity = Total LS + Total SS (Based on old logic)
    # or sum of components: ap_ls + ap_ls_mk3 + ap_ss
    # Let's use components sum to be safe and independent of 'total' columns
    df['Quantity'] = df['ap_ls'] + df['ap_ls_mk3'] + df['ap_ss']

    # Metrics
    total_qty = df['Quantity'].sum()
    # Total Transaksi: Hitung hanya baris yang Quantity > 0 (artinya ada pengiriman)
    total_rit = len(df[df['Quantity'] > 0])
    
    # Calculate Material Totals
    total_ls = df['ap_ls'].sum()
    total_mk3 = df['ap_ls_mk3'].sum()
    total_ss = df['ap_ss'].sum()
    
    # Determine Dominant Material
    materials = {'Limestone': total_ls, 'LS MK3': total_mk3, 'Silica Stone': total_ss}
    dominant_mat = max(materials, key=materials.get) if materials else 'None'
    dominant_val = materials[dominant_mat] if materials else 0
    
    avg_daily = total_qty / df['Date'].nunique() if df['Date'].nunique() > 0 else 0

    # 3. EXECUTIVE KPI CARDS
    st.markdown(f"""
    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem;">
        <div class="kpi-card" style="--card-accent: #3b82f6;">
            <div class="kpi-icon">🚢</div>
            <div class="kpi-label">TOTAL PENGIRIMAN (TONASE)</div>
            <div class="kpi-value">{total_qty:,.0f}</div>
            <div class="kpi-subtitle">Ton Material</div>
        </div>
        <div class="kpi-card" style="--card-accent: #10b981;">
            <div class="kpi-icon">📋</div>
            <div class="kpi-label">TOTAL PENGIRIMAN (RITASE)</div>
            <div class="kpi-value">{total_rit:,}</div>
            <div class="kpi-subtitle">Jumlah Pengiriman</div>
        </div>
        <div class="kpi-card" style="--card-accent: #f59e0b;">
            <div class="kpi-icon">📅</div>
            <div class="kpi-label">RATA-RATA KIRIM (HARIAN)</div>
            <div class="kpi-value">{avg_daily:,.0f}</div>
            <div class="kpi-subtitle">Ton / Hari</div>
        </div>
        <div class="kpi-card" style="--card-accent: #8b5cf6;">
            <div class="kpi-icon">💎</div>
            <div class="kpi-label">PRODUK DOMINAN</div>
            <div class="kpi-value" style="font-size: 1.5rem;">{dominant_mat}</div>
            <div class="kpi-subtitle">{dominant_val:,.0f} Ton</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4. CHARTS SECTION
    c1, c2 = st.columns([1.5, 2.5])

    # Chart 1: Material Composition (Donut)
    with c1:
        with st.container(border=True):
            st.markdown("##### 📦 **KOMPOSISI MATERIAL KIRIM** | Jenis Produk")
            st.markdown("---")
            
            mat_df = pd.DataFrame([
                {'Material': 'Limestone (LS)', 'Volume': total_ls},
                {'Material': 'LS MK3', 'Volume': total_mk3},
                {'Material': 'Silica Stone (SS)', 'Volume': total_ss}
            ])
            mat_df = mat_df[mat_df['Volume'] > 0] # Hide zero components
            
            fig_mat = px.pie(mat_df, values='Volume', names='Material', hole=0.6,
                              color='Material',
                              color_discrete_map={
                                  'Limestone (LS)': '#3b82f6', # Blue
                                  'LS MK3': '#8b5cf6',        # Purple (High Contrast)
                                  'Silica Stone (SS)': '#10b981' # Green
                              })
            
            # Fix Layout Merge
            layout_mat = get_chart_layout(height=350)
            layout_mat.update(dict(
                title="Proporsi Material Kirim",
                showlegend=True,
                legend=dict(orientation="h", y=-0.1)
            ))
            fig_mat.update_layout(**layout_mat)
            fig_mat.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_mat, use_container_width=True)

    # Chart 2: Shift Performance (Bar)
    with c2:
        with st.container(border=True):
            st.markdown("##### ⏱️ **KONTRIBUSI SHIFT (PENGIRIMAN)** | Produktivitas Kerja")
            st.markdown("---")
            
            shift_df = df.groupby('Shift')['Quantity'].sum().reset_index()
            # Sort by Quantity Ascending for Plotly (Largest at Top)
            shift_df = shift_df.sort_values('Quantity', ascending=True)
            # Ensure Shift is categorical/string
            shift_df['Shift'] = shift_df['Shift'].astype(str)
            
            fig_shift = px.bar(shift_df, x='Quantity', y='Shift', orientation='h',
                               text='Quantity',
                               color='Shift', color_discrete_sequence=['#f59e0b', '#8b5cf6', '#ec4899'])
            
            fig_shift.update_traces(texttemplate='%{text:,.0f}', textposition='inside')
            
            # Fix Layout Merge
            layout_shift = get_chart_layout(height=350)
            layout_shift.update(dict(
                title="Total Pengiriman per Shift",
                xaxis=dict(showgrid=True, title="Volume (Ton)"),
                yaxis=dict(title="Shift"),
                showlegend=False
            ))
            fig_shift.update_layout(**layout_shift)
            # FORCE sort order: Largest at TOP
            fig_shift.update_yaxes(categoryorder='total ascending')
            st.plotly_chart(fig_shift, use_container_width=True)
    
    # Chart 3: Daily Trend (Stacked)
    with st.container(border=True):
        st.markdown("##### 📈 **TREN PENGIRIMAN HARIAN** | Fluktuasi per Material")
        st.markdown("---")
        
        # Melt for Stacked Bar (Use lowercase columns)
        daily_melt = df.melt(id_vars=['Date'], value_vars=['ap_ls', 'ap_ls_mk3', 'ap_ss'], 
                             var_name='Material', value_name='Volume')
        daily_melt = daily_melt.groupby(['Date', 'Material'])['Volume'].sum().reset_index()
        
        # Rename for nice legend
        material_map = {'ap_ls': 'Limestone', 'ap_ls_mk3': 'LS MK3', 'ap_ss': 'Silica Stone'}
        daily_melt['Material'] = daily_melt['Material'].map(material_map)
        
        fig_trend = px.bar(daily_melt, x='Date', y='Volume', color='Material',
                           color_discrete_map={
                                  'Limestone': '#3b82f6', 
                                  'LS MK3': '#8b5cf6', # Purple (Match Donut Chart)       
                                  'Silica Stone': '#10b981'
                           })
        
        # Add Moving Average Line (Total) - REMOVED per user request
        # total_series = df.groupby('Date')['Quantity'].sum().reset_index()
        # total_series['MA7'] = total_series['Quantity'].rolling(window=7).mean()
        
        # fig_trend.add_trace(go.Scatter(
        #     x=total_series['Date'], y=total_series['MA7'],
        #     name='Rata-rata 7 Hari',
        #     line=dict(color='#d4a84b', width=3)
        # ))

        # Update Layout (Merge dicts to avoid duplicate 'legend' error)
        layout = get_chart_layout(height=400)
        layout.update(dict(
            title="Tren Harian Pengiriman Material",
            xaxis_title="Tanggal",
            yaxis_title="Volume (Ton)",
            legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"), # Move legend to bottom
            hovermode="x unified"
        ))
        fig_trend.update_layout(**layout)
        st.plotly_chart(fig_trend, use_container_width=True)
            
    with st.expander("📄 Lihat Detail Data Textual"):
        # Hide internal calculated columns (Quantity) but keep DB ones per user request
        # AND Rename Date -> tanggal, Shift -> shift to match DB headers exactly
        # RENAME HEADERS (Raw DB -> Title Case)
        # Perbaiki Rename Map agar sesuai dengan output loader/DB
        rename_display = {
            'Date': 'Tanggal', 
            'Shift': 'Shift',
            'tanggal': 'Tanggal',
            'shift': 'Shift',
            'ap_ls': 'AP LS',
            'ap_ls_mk3': 'AP MK3', # Corrected key
            'ap_mk3': 'AP MK3',    # Fallback key
            'ap_ss': 'AP SS',
            'total_ls': 'Total LS',
            'total_ss': 'Total SS',
        }
        
        # Tampilkan semua kolom yang relevan (termasuk komponen 0)
        # Hapus 'Quantity' internal jika membingungkan, tapi user butuh lihat Total
        cols_to_drop = ['Quantity'] if 'total_ls' in df.columns else []
        df_display = df.drop(columns=cols_to_drop, errors='ignore').rename(columns=rename_display)
        
        # Explicitly select columns to ensure no technical columns (id, created_at, updated_at) slip through
        desired_cols = ['Tanggal', 'Shift', 'AP LS', 'AP MK3', 'AP SS', 'Total LS', 'Total SS']
        # Filter matching columns
        final_cols = [c for c in desired_cols if c in df_display.columns]
        df_display = df_display[final_cols]
        
        # Display Sort: Descending (Newest First)
        # User REQ: "Data terbaru di paling atas"
        if 'Tanggal' in df_display.columns:
             sort_cols = ['Tanggal']
             asc_order = [False] # Date Descending (Newest First)
             
             if 'Shift' in df_display.columns:
                 # Ensure Shift is numeric for proper sorting (1, 2, 3)
                 try:
                    df_display['Shift'] = pd.to_numeric(df_display['Shift'])
                    sort_cols.append('Shift')
                    asc_order.append(False) # Shift Descending (3, 2, 1) - User Request "Terakhir Input (Shift 3) Paling Atas"
                 except: pass # If Shift is non-numeric string, standard sort might apply
                 
             df_display = df_display.sort_values(by=sort_cols, ascending=asc_order)
        
        st.dataframe(
            df_display, 
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tanggal": st.column_config.DateColumn("Tanggal", format="YYYY-MM-DD")
            }
        )
        
        # Excel Download (Sort Ascending = OLDEST FIRST)
        # User REQ: "Saat di download data yang paling lama di atas"
        # Use df_display (cleaned & renamed) as source
        # Sort by 'Tanggal' (Title Case)
        if 'Tanggal' in df_display.columns:
            df_download = df_display.sort_values(by='Tanggal', ascending=True)
        else:
            df_download = df_display
        
        # Format Date to String (Remove 00:00:00)
        if 'Tanggal' in df_download.columns:
             try:
                df_download['Tanggal'] = pd.to_datetime(df_download['Tanggal']).dt.strftime('%Y-%m-%d')
             except:
                pass
        
        from utils.helpers import convert_df_to_excel
        excel_data = convert_df_to_excel(df_download)
        
        st.download_button(
             label="📥 Unduh Data (Excel)",
             data=excel_data,
             file_name=f"PTSP_Data_Pengiriman_{datetime.now().strftime('%Y%m%d')}.xlsx",
             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             type="primary"
        )
        
    # --- GHOSTING FIX: Trailing Padding ---
    # Append empty slots to overwrite any trailing DOM remnants from other longer modules
    for _ in range(25):
        st.empty()
