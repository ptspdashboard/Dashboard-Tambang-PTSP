"""
Solar Module 3: Efisiensi BBM (Fuel Efficiency)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from views.solar_common import (
    COLORS, fmt, header, kpi_card, section, spacer, is_lkm_unit, load_and_filter,
    content_end_marker
)
from utils.helpers import convert_df_to_excel


def _is_lkm(row):
    name = str(row.get('Tipe_Unit', '')).upper()
    return any(kw in name for kw in ['LV ', 'LV)', 'SCANIA', 'STRADA', 'PICK UP', 'PICKUP'])


def show_solar_efisiensi():
    df_full, df = load_and_filter()
    header("Efisiensi BBM", "Analisis Efisiensi L/Jam (Alat Berat) & L/Km (LV/Scania)", "⚡")

    # Filter to rows with valid efficiency data
    df_eff = df[(df['L_per_Jam'].notna()) & (df['L_per_Jam'] > 0)].copy()

    if df_eff.empty:
        st.warning("Data efisiensi belum tersedia. Klik **Sync & Refresh Data**.")
        return

    # Always use name-based detection (most reliable)
    mask_lkm = df_eff.apply(_is_lkm, axis=1)
    df_ljam = df_eff[~mask_lkm].copy()
    df_lkm = df_eff[mask_lkm].copy()

    # ==================== SECTION 1: L/Jam (Alat Berat) ====================
    st.markdown("---")
    section("🔧 Efisiensi Alat Berat (L/Jam)")

    if not df_ljam.empty:
        avg_lph = df_ljam['L_per_Jam'].mean()
        unit_avg_ljam = df_ljam.groupby('Tipe_Unit')['L_per_Jam'].mean()
        best_u = unit_avg_ljam.idxmin() if len(unit_avg_ljam) > 0 else 'N/A'
        best_v = unit_avg_ljam.min() if len(unit_avg_ljam) > 0 else 0
        worst_u = unit_avg_ljam.idxmax() if len(unit_avg_ljam) > 0 else 'N/A'
        worst_v = unit_avg_ljam.max() if len(unit_avg_ljam) > 0 else 0
        total_jam = df_ljam[df_ljam['Jam_Operasi'].notna() & (df_ljam['Jam_Operasi'] > 0)]['Jam_Operasi'].sum()

        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi_card("Avg L/Jam", f"{avg_lph:.1f}", icon="⚡", help_text="Rata-rata alat berat")
        with c2: kpi_card("Paling Efisien", f"{best_u[:20]}", icon="✅", help_text=f"{best_v:.1f} L/Jam")
        with c3: kpi_card("Paling Boros", f"{worst_u[:20]}", icon="🔴", help_text=f"{worst_v:.1f} L/Jam")
        with c4: kpi_card("Total Jam Operasi", fmt(total_jam, " Jam"), icon="⏱️")
        spacer()

        # Mengelompokkan berdasarkan Tipe_Unit, Perusahaan, dan Jenis_Alat agar informasi tidak hilang
        unit_rank = df_ljam.groupby(['Tipe_Unit', 'Perusahaan', 'Jenis_Alat'])['L_per_Jam'].mean().reset_index()
        unit_rank.columns = ['Tipe_Unit', 'Perusahaan', 'Jenis_Alat', 'Avg_Val']
        unit_rank = unit_rank.nlargest(15, 'Avg_Val').sort_values('Avg_Val', ascending=True)
        
        # Membuat label gabungan untuk ditampilkan di sumbu Y chart
        unit_rank['Label'] = unit_rank['Tipe_Unit'].str[:18] + ' (' + unit_rank['Perusahaan'].str[:8] + ' | ' + unit_rank['Jenis_Alat'].str[:8] + ')'

        fig = go.Figure()
        bar_colors = ['#22c55e' if v <= avg_lph else '#ef4444' for v in unit_rank['Avg_Val']]
        fig.add_trace(go.Bar(x=unit_rank['Avg_Val'], y=unit_rank['Label'],
                            orientation='h', marker_color=bar_colors,
                            text=unit_rank['Avg_Val'].round(1), textposition='inside',
                            textfont=dict(color='white', size=11)))
        fig.add_vline(x=avg_lph, line_dash="dash", line_color="#FFB627", annotation_text=f"Avg: {avg_lph:.1f}")
        fig.update_layout(template='plotly_dark', height=500,
                         margin=dict(t=30, b=30, l=20, r=60), yaxis_title="", xaxis_title="L/Jam")
        st.plotly_chart(fig, use_container_width=True, key="efisiensi_chart_unitrank")

        col1, col2 = st.columns(2)
        with col1:
            section("📈 Tren L/Jam Harian")
            daily = df_ljam.groupby('Tanggal')['L_per_Jam'].mean().reset_index().sort_values('Tanggal')
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=daily['Tanggal'], y=daily['L_per_Jam'],
                                     mode='lines+markers+text', fill='tozeroy',
                                     line=dict(color='#06D6A0', width=2), marker=dict(size=4),
                                     text=daily['L_per_Jam'].round(1),
                                     textposition='middle center', textfont=dict(color='white', size=10)))
            fig2.add_hline(y=avg_lph, line_dash="dash", line_color="#FFB627", annotation_text=f"Avg: {avg_lph:.1f}")
            fig2.update_layout(template='plotly_dark', height=350,
                              margin=dict(t=40, b=30, l=40, r=20), yaxis_title="L/Jam")
            st.plotly_chart(fig2, use_container_width=True, key="efisiensi_chart_trendlph")
        with col2:
            section("📊 Rata-rata L/Jam per Jenis Alat")
            jenis_avg = df_ljam.groupby('Jenis_Alat')['L_per_Jam'].mean().reset_index()
            jenis_avg.columns = ['Jenis_Alat', 'Avg_LJam']
            jenis_avg = jenis_avg.sort_values('Avg_LJam', ascending=True)
            max_val = jenis_avg['Avg_LJam'].max()
            min_val = jenis_avg['Avg_LJam'].min()
            def _consumption_color(v):
                if max_val == min_val:
                    return '#22c55e'
                ratio = (v - min_val) / (max_val - min_val)
                if ratio < 0.33:
                    return '#22c55e'
                elif ratio < 0.66:
                    return '#f59e0b'
                else:
                    return '#ef4444'
            bar_colors3 = [_consumption_color(v) for v in jenis_avg['Avg_LJam']]
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(
                x=jenis_avg['Avg_LJam'], y=jenis_avg['Jenis_Alat'],
                orientation='h', marker_color=bar_colors3,
                text=jenis_avg['Avg_LJam'].round(1), textposition='inside',
                textfont=dict(color='white', size=12, family='Arial Black')
            ))
            fig3.update_layout(template='plotly_dark', height=350,
                              margin=dict(t=30, b=30, l=20, r=20),
                              xaxis_title="L/Jam", yaxis_title="")
            st.plotly_chart(fig3, use_container_width=True, key="efisiensi_chart_jenisavg")
    else:
        st.info("Belum ada data L/Jam untuk alat berat.")

    # ==================== SECTION 2: L/Km (LV & Scania) ====================
    st.markdown("---")
    section("🚛 Efisiensi LV & Scania (L/Km)")

    if not df_lkm.empty:
        avg_lpk = df_lkm['L_per_Jam'].mean()  # Value stored as L/Km
        unit_avg_lkm = df_lkm.groupby('Tipe_Unit')['L_per_Jam'].mean()
        best_k = unit_avg_lkm.idxmin() if len(unit_avg_lkm) > 0 else 'N/A'
        best_kv = unit_avg_lkm.min() if len(unit_avg_lkm) > 0 else 0
        worst_k = unit_avg_lkm.idxmax() if len(unit_avg_lkm) > 0 else 'N/A'
        worst_kv = unit_avg_lkm.max() if len(unit_avg_lkm) > 0 else 0
        total_km = df_lkm[df_lkm['Jam_Operasi'].notna() & (df_lkm['Jam_Operasi'] > 0)]['Jam_Operasi'].sum()

        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi_card("Avg L/Km", f"{avg_lpk:.2f}", icon="🚛", help_text="Rata-rata LV & Scania")
        with c2: kpi_card("Paling Efisien", f"{best_k[:20]}", icon="✅", help_text=f"{best_kv:.2f} L/Km")
        with c3: kpi_card("Paling Boros", f"{worst_k[:20]}", icon="🔴", help_text=f"{worst_kv:.2f} L/Km")
        with c4: kpi_card("Total Kilometer", fmt(total_km, " Km"), icon="📏")
        spacer()

        # Mengelompokkan berdasarkan Tipe_Unit, Perusahaan, dan Jenis_Alat agar informasi tidak hilang
        lkm_rank = df_lkm.groupby(['Tipe_Unit', 'Perusahaan', 'Jenis_Alat'])['L_per_Jam'].mean().reset_index()
        lkm_rank.columns = ['Tipe_Unit', 'Perusahaan', 'Jenis_Alat', 'Avg_Val']
        lkm_rank = lkm_rank.sort_values('Avg_Val', ascending=True)
        
        # Membuat label gabungan untuk ditampilkan di sumbu Y chart
        lkm_rank['Label'] = lkm_rank['Tipe_Unit'].str[:18] + ' (' + lkm_rank['Perusahaan'].str[:8] + ' | ' + lkm_rank['Jenis_Alat'].str[:8] + ')'

        fig5 = go.Figure()
        bar_colors5 = ['#22c55e' if v <= avg_lpk else '#ef4444' for v in lkm_rank['Avg_Val']]
        fig5.add_trace(go.Bar(x=lkm_rank['Avg_Val'], y=lkm_rank['Label'],
                            orientation='h', marker_color=bar_colors5,
                            text=lkm_rank['Avg_Val'].round(2), textposition='inside',
                            textfont=dict(color='white', size=11)))
        fig5.add_vline(x=avg_lpk, line_dash="dash", line_color="#FFB627", annotation_text=f"Avg: {avg_lpk:.2f}")
        fig5.update_layout(template='plotly_dark', height=max(300, len(lkm_rank) * 30 + 100),
                         margin=dict(t=30, b=30, l=20, r=60), yaxis_title="", xaxis_title="L/Km")
        st.plotly_chart(fig5, use_container_width=True, key="efisiensi_chart_lkmrank")

        section("📈 Tren L/Km Harian")
        daily_k = df_lkm.groupby('Tanggal')['L_per_Jam'].mean().reset_index().sort_values('Tanggal')
        fig6 = go.Figure()
        fig6.add_trace(go.Scatter(x=daily_k['Tanggal'], y=daily_k['L_per_Jam'],
                                 mode='lines+markers+text', fill='tozeroy',
                                 line=dict(color='#118AB2', width=2), marker=dict(size=5),
                                 text=daily_k['L_per_Jam'].round(2),
                                 textposition='middle center', textfont=dict(color='white', size=10)))
        fig6.add_hline(y=avg_lpk, line_dash="dash", line_color="#FFB627", annotation_text=f"Avg: {avg_lpk:.2f}")
        fig6.update_layout(template='plotly_dark', height=350,
                          margin=dict(t=40, b=30, l=40, r=20), yaxis_title="L/Km")
        st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("Belum ada data L/Km untuk LV & Scania.")

    # Table + Download
    with st.expander("📋 Data Detail Efisiensi", expanded=False):
        disp = df_eff.copy()
        disp['Satuan'] = disp.apply(lambda r: 'L/Km' if _is_lkm(r) else 'L/Jam', axis=1)
        disp['Efisiensi'] = disp.apply(lambda r: f"{r['L_per_Jam']:.2f} {r['Satuan']}", axis=1)
        disp['Operasi'] = disp.apply(
            lambda r: f"{r['Jam_Operasi']:,.0f} {'Km' if r['Satuan'] == 'L/Km' else 'Jam'}"
            if pd.notna(r['Jam_Operasi']) else '-', axis=1)
        cols = [c for c in ['Perusahaan', 'Jenis_Alat', 'Tipe_Unit', 'Tanggal',
                            'Efisiensi', 'Operasi', 'Satuan', 'Bulan'] if c in disp.columns]
        disp = disp[cols].copy()
        if 'Tanggal' in disp.columns:
            disp['Tanggal'] = disp['Tanggal'].dt.strftime('%Y-%m-%d')
        disp = disp.sort_values(['Tanggal', 'Tipe_Unit'], ascending=[False, True])
        st.dataframe(disp, use_container_width=True, height=400)
        excel_data = convert_df_to_excel(disp)
        st.download_button("📥 Download Excel", data=excel_data, file_name="efisiensi_bbm.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Anti-ghosting: pad the end of the page with empty slots to wipe out previous charts
    content_end_marker(count=25)
