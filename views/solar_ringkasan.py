"""
Solar Module 1: Ringkasan BBM (Executive Summary)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
from views.solar_common import (
    COLORS, GRADIENT_BG, CARD_BG, ACCENT, BULAN_ORDER,
    fmt, header, kpi_card, section, spacer, is_lkm_unit, load_and_filter,
    content_end_marker
)


def show_solar_ringkasan():
    df_full, df = load_and_filter()
    header("Ringkasan BBM", "Overview Konsumsi Bahan Bakar Seluruh Unit Operasi", "🏠")

    if df.empty:
        st.warning("Belum ada data. Klik **Sync & Refresh Data** di sidebar.")
        return

    df_active = df[df['Liter'] > 0]
    total = df_active['Liter'].sum()
    days = df_active['Tanggal'].nunique()
    avg_daily = total / days if days > 0 else 0
    units = df_active['Tipe_Unit'].nunique()
    companies = df_active['Perusahaan'].nunique()

    # Top consumer unit
    unit_totals = df_active.groupby('Tipe_Unit')['Liter'].sum()
    top_unit = unit_totals.idxmax() if len(unit_totals) > 0 else 'N/A'
    top_unit_val = unit_totals.max() if len(unit_totals) > 0 else 0

    # Company totals
    co_totals = df_active.groupby('Perusahaan')['Liter'].sum()

    # Avg L/Jam & L/Km
    df_eff = df_active[(df_active['L_per_Jam'].notna()) & (df_active['L_per_Jam'] > 0)]
    df_ljam_r = df_eff[~df_eff['Tipe_Unit'].apply(is_lkm_unit)]
    df_lkm_r = df_eff[df_eff['Tipe_Unit'].apply(is_lkm_unit)]
    avg_ljam = df_ljam_r['L_per_Jam'].mean() if not df_ljam_r.empty else 0
    avg_lkm = df_lkm_r['L_per_Jam'].mean() if not df_lkm_r.empty else 0

    # MoM calculation (avg daily based)
    mom_label = "N/A"
    mom_val = None
    if 'Bulan' in df_full.columns and df_full['Bulan'].nunique() >= 2:
        bulan_sorted = sorted(df_full['Bulan'].dropna().unique(),
                             key=lambda x: BULAN_ORDER.get(x, 99))
        cur_m_data = df_full[(df_full['Bulan'] == bulan_sorted[-1]) & (df_full['Liter'] > 0)]
        prev_m_data = df_full[(df_full['Bulan'] == bulan_sorted[-2]) & (df_full['Liter'] > 0)]
        cur_m_days = cur_m_data['Tanggal'].nunique()
        prev_m_days = prev_m_data['Tanggal'].nunique()
        cur_m_avg = cur_m_data['Liter'].sum() / cur_m_days if cur_m_days > 0 else 0
        prev_m_avg = prev_m_data['Liter'].sum() / prev_m_days if prev_m_days > 0 else 0
        if prev_m_avg > 0:
            mom_val = ((cur_m_avg - prev_m_avg) / prev_m_avg) * 100
            mom_label = f"{'↑ Naik' if mom_val > 0 else '↓ Turun'} {abs(mom_val):.1f}%"

    # ─── HERO KPI ROW ─────────────────────────────────────────
    hero_col, side_col = st.columns([3, 2])

    with hero_col:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #FF6B35 0%, #D4380D 100%);
                    border-radius: 16px; padding: 28px 32px; margin-bottom: 12px;">
            <div style="color: rgba(255,255,255,0.75); font-size: 13px; font-weight: 600;
                        letter-spacing: 1px; text-transform: uppercase;">⛽ TOTAL KONSUMSI BBM</div>
            <div style="color: white; font-size: 42px; font-weight: 800; margin: 4px 0;">
                {total:,.0f} <span style="font-size: 22px; opacity: 0.8;">Liter</span>
            </div>
            <div style="color: rgba(255,255,255,0.7); font-size: 13px;">
                {days} hari operasi · {companies} perusahaan
            </div>
        </div>
        """, unsafe_allow_html=True)

    with side_col:
        mom_color = '#22c55e' if mom_val is not None and mom_val < 0 else '#ef4444' if mom_val is not None else '#94a3b8'
        mom_bg = f"rgba({34},{197},{94},0.15)" if mom_val is not None and mom_val < 0 else f"rgba({239},{68},{68},0.15)"
        mom_border = f"rgba({34},{197},{94},0.3)" if mom_val is not None and mom_val < 0 else f"rgba({239},{68},{68},0.3)"
        st.markdown(f"""
        <div style="display:flex; gap:8px; flex-direction:column;">
            <div style="background: rgba(6,214,160,0.15); border: 1px solid rgba(6,214,160,0.3);
                        border-radius: 12px; padding: 16px 20px;">
                <div style="color: #06D6A0; font-size: 11px; font-weight: 600; text-transform: uppercase;">
                    📊 Rata-rata Harian</div>
                <div style="color: white; font-size: 26px; font-weight: 700;">{avg_daily:,.0f} L/Hari</div>
            </div>
            <div style="background: {mom_bg}; border: 1px solid {mom_border};
                        border-radius: 12px; padding: 16px 20px;">
                <div style="color: {mom_color}; font-size: 11px; font-weight: 600; text-transform: uppercase;">
                    📈 vs Bulan Lalu (Avg Harian)</div>
                <div style="color: {mom_color}; font-size: 26px; font-weight: 700;">{mom_label}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ─── SECONDARY KPI ROW ────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Unit Aktif", f"{units}", icon="🚜")
    with c2: kpi_card("Top Consumer", f"{top_unit[:20]}", icon="🔥",
                       help_text=f"{fmt(top_unit_val)} L total")
    with c3: kpi_card("Avg L/Jam", f"{avg_ljam:.1f}", icon="⚡",
                       help_text="Efisiensi alat berat")
    with c4: kpi_card("Avg L/Km", f"{avg_lkm:.2f}", icon="🛣️",
                       help_text="Efisiensi LV & Scania")

    spacer()

    # ─── CHART ROW 1: Tren + Distribusi ───────────────────────
    col1, col2 = st.columns([2, 1])

    with col1:
        section("📊 Tren Konsumsi Harian")
        daily = df_active.groupby('Tanggal')['Liter'].sum().reset_index().sort_values('Tanggal')
        avg_val = daily['Liter'].mean()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=daily['Tanggal'], y=daily['Liter'],
                            marker_color='#118AB2', name='Konsumsi', opacity=0.9,
                            text=daily['Liter'].apply(lambda v: f"{v:,.0f}"),
                            textposition='inside', textfont=dict(color='white', size=11)))
        fig.add_hline(y=avg_val, line_dash="dash", line_color="#06D6A0",
                     annotation_text=f"Avg: {avg_val:,.0f} L")
        fig.update_layout(template='plotly_dark', height=350,
                         margin=dict(t=40, b=30, l=40, r=20),
                         xaxis_title="", yaxis_title="Liter")
        st.plotly_chart(fig, use_container_width=True, key="ringkasan_chart_daily")


    with col2:
        section("🏢 Distribusi Perusahaan")
        co_dist = df_active.groupby('Perusahaan')['Liter'].sum().reset_index()
        co_dist = co_dist.sort_values('Liter', ascending=False)
        fig2 = px.pie(co_dist, values='Liter', names='Perusahaan', hole=0.45,
                     color_discrete_sequence=COLORS)
        fig2.update_layout(template='plotly_dark', height=350,
                          margin=dict(t=30, b=30, l=20, r=20),
                          showlegend=True, legend=dict(font_size=9))
        fig2.update_traces(textposition='inside', textinfo='percent+value',
                          texttemplate='%{percent:.0%}<br>%{value:,.0f} L')
        st.plotly_chart(fig2, use_container_width=True, key="ringkasan_chart_dist")


    # ─── CHART ROW 2: Top 5 Unit ──────────────────────────────
    section("🔥 Top 5 Unit Konsumsi Tertinggi")
    top5_u = unit_totals.nlargest(5).reset_index()
    top5_u.columns = ['Tipe_Unit', 'Total_Liter']
    top5_u = top5_u.sort_values('Total_Liter', ascending=True)
    fig_t1 = go.Figure()
    fig_t1.add_trace(go.Bar(
        x=top5_u['Total_Liter'], y=top5_u['Tipe_Unit'].str[:28],
        orientation='h', marker_color='#06D6A0',
        text=top5_u['Total_Liter'].apply(lambda v: f"{v:,.0f} L"),
        textposition='inside', textfont=dict(color='white', size=11, family='Arial Black')
    ))
    fig_t1.update_layout(template='plotly_dark', height=250,
                        margin=dict(t=30, b=20, l=20, r=20),
                        xaxis_title="Liter", yaxis_title="")
    st.plotly_chart(fig_t1, use_container_width=True, key="ringkasan_chart_top5")

    # ─── CHART ROW 3: Monthly comparison ──────────────────────
    if 'Bulan' in df_active.columns and df_active['Bulan'].nunique() >= 2:
        section("📅 Perbandingan Bulanan per Perusahaan")
        monthly_co = df_active.groupby(['Bulan', 'Perusahaan'])['Liter'].sum().reset_index()
        monthly_co['sort_key'] = monthly_co['Bulan'].map(BULAN_ORDER)
        monthly_co = monthly_co.sort_values('sort_key')
        fig3 = px.bar(monthly_co, x='Perusahaan', y='Liter', color='Bulan',
                     barmode='group', color_discrete_sequence=COLORS, text_auto=True)
        fig3.update_layout(template='plotly_dark', height=350,
                          margin=dict(t=30, b=30, l=40, r=20), xaxis_tickangle=-30)
        fig3.update_traces(texttemplate='%{y:,.0f}', textposition='inside', textfont=dict(color='white', size=11))
        st.plotly_chart(fig3, use_container_width=True, key="ringkasan_chart_monthly")

    # ─── REKAPITULASI PER PERUSAHAAN ──────────────────────────
    section("📋 Rekapitulasi per Perusahaan")

    recap_rows = []
    for co in sorted(co_totals.index):
        co_data = df_active[df_active['Perusahaan'] == co]
        co_total = co_data['Liter'].sum()
        co_days = co_data['Tanggal'].nunique()
        co_avg_daily = co_total / co_days if co_days > 0 else 0
        co_units = co_data['Tipe_Unit'].nunique()
        co_eff = co_data[
            (co_data['L_per_Jam'].notna()) & (co_data['L_per_Jam'] > 0) &
            (~co_data['Tipe_Unit'].apply(is_lkm_unit))
        ]
        co_avg_ljam = co_eff['L_per_Jam'].mean() if not co_eff.empty else 0
        pct = (co_total / total * 100) if total > 0 else 0
        recap_rows.append({
            'Perusahaan': co,
            'Total Liter': f"{co_total:,.0f}",
            'Avg/Hari (L)': f"{co_avg_daily:,.0f}",
            'Unit Aktif': co_units,
            'Avg L/Jam': f"{co_avg_ljam:.1f}" if co_avg_ljam > 0 else "-",
            '% Kontribusi': f"{pct:.1f}%"
        })

    recap_df = pd.DataFrame(recap_rows)
    recap_df['_sort'] = recap_df['Total Liter'].str.replace(',', '').astype(float)
    recap_df = recap_df.sort_values('_sort', ascending=False).drop(columns='_sort')

    st.dataframe(recap_df, use_container_width=True, hide_index=True, height=300)

    # Download button
    excel_buffer = io.BytesIO()
    recap_excel = pd.DataFrame(recap_rows)
    recap_excel['_sort'] = recap_excel['Total Liter'].str.replace(',', '').astype(float)
    recap_excel = recap_excel.sort_values('_sort', ascending=False).drop(columns='_sort')
    recap_excel.to_excel(excel_buffer, index=False, sheet_name='Rekapitulasi')
    st.download_button(
        label="📥 Download Rekapitulasi (Excel)",
        data=excel_buffer.getvalue(),
        file_name="rekapitulasi_bbm.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Anti-ghosting: pad the end of the page with empty slots to wipe out previous charts
    content_end_marker(count=25)
