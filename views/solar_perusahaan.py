"""
Solar Module 4: Analisis Perusahaan (Company Analysis)
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


def show_solar_perusahaan():
    df_full, df = load_and_filter()
    header("Analisis Perusahaan", "Perbandingan Konsumsi & Efisiensi Antar Kontraktor", "🏢")

    if df.empty:
        st.warning("Belum ada data. Klik **Sync & Refresh Data** di sidebar.")
        return

    df_active = df[df['Liter'] > 0]
    total = df_active['Liter'].sum()
    companies = df_active['Perusahaan'].nunique()
    total_units = df_active['Tipe_Unit'].nunique()
    days = df_active['Tanggal'].nunique()

    # Top company
    co_totals = df_active.groupby('Perusahaan')['Liter'].sum()
    top_co = co_totals.idxmax() if len(co_totals) > 0 else 'N/A'
    top_pct = (co_totals.max() / total * 100) if total > 0 else 0

    # Avg per unit per day
    unit_daily = df_active.groupby(['Tipe_Unit', 'Tanggal'])['Liter'].sum()
    avg_unit_day = unit_daily.mean() if len(unit_daily) > 0 else 0

    # KPIs (4)
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Perusahaan Aktif", f"{companies}", icon="🏢")
    with c2: kpi_card("Kontribusi Terbesar", f"{top_co[:18]}", icon="👑",
                       help_text=f"{top_pct:.1f}% dari total")
    with c3: kpi_card("Avg/Unit/Hari", fmt(avg_unit_day, " L"), icon="📊",
                       help_text=f"Dari {total_units} unit aktif")
    with c4: kpi_card("Total Unit", f"{total_units}", icon="🚜")

    spacer()

    # ─── CHART 1 + 2: Side by side ────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        section("📊 Konsumsi per Perusahaan")
        co_rank = co_totals.reset_index()
        co_rank.columns = ['Perusahaan', 'Total_Liter']
        co_rank = co_rank.sort_values('Total_Liter', ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=co_rank['Total_Liter'], y=co_rank['Perusahaan'],
            orientation='h', marker_color='#118AB2',
            text=co_rank['Total_Liter'].apply(lambda v: f"{v:,.0f} L"),
            textposition='inside', textfont=dict(color='white', size=11)
        ))
        fig.update_layout(template='plotly_dark',
                         height=400,
                         margin=dict(t=30, b=30, l=10, r=20),
                         xaxis_title="Liter", yaxis_title="",
                         yaxis=dict(automargin=True))
        st.plotly_chart(fig, use_container_width=True, key="perusahaan_chart_konsumsi")


    with col2:
        section("⚡ Efisiensi L/Jam per Perusahaan")
        df_eff_co = df_active[
            (df_active['L_per_Jam'].notna()) & (df_active['L_per_Jam'] > 0) &
            (~df_active['Tipe_Unit'].apply(is_lkm_unit))
        ]
        if not df_eff_co.empty:
            co_eff = df_eff_co.groupby('Perusahaan')['L_per_Jam'].mean().reset_index()
            co_eff.columns = ['Perusahaan', 'Avg_LJam']
            co_eff = co_eff.sort_values('Avg_LJam', ascending=True)
            avg_all = co_eff['Avg_LJam'].mean()
            bar_colors = ['#22c55e' if v <= avg_all else '#ef4444' for v in co_eff['Avg_LJam']]
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=co_eff['Avg_LJam'], y=co_eff['Perusahaan'],
                orientation='h', marker_color=bar_colors,
                text=co_eff['Avg_LJam'].apply(lambda v: f"{v:.1f}"),
                textposition='inside', textfont=dict(color='white', size=11)
            ))
            fig2.add_vline(x=avg_all, line_dash="dash", line_color="#FFB627",
                          annotation_text=f"Avg: {avg_all:.1f}", annotation_position="top")
            fig2.update_layout(template='plotly_dark',
                              height=400,
                              margin=dict(t=30, b=30, l=10, r=40),
                              xaxis_title="L/Jam (rendah = efisien)",
                              yaxis_title="",
                              yaxis=dict(automargin=True))
            st.plotly_chart(fig2, use_container_width=True, key="perusahaan_chart_efisiensi")
        else:
            st.info("Belum ada data efisiensi L/Jam.")


    # ─── CHART 3: Avg/Unit/Hari per Perusahaan ────────────────
    section("📈 Rata-rata Konsumsi per Unit per Hari")
    co_detail = []
    for co in co_totals.index:
        co_d = df_active[df_active['Perusahaan'] == co]
        co_unit_daily = co_d.groupby(['Tipe_Unit', 'Tanggal'])['Liter'].sum().mean()
        co_detail.append({'Perusahaan': co, 'Avg_Unit_Day': co_unit_daily})
    co_detail_df = pd.DataFrame(co_detail).sort_values('Avg_Unit_Day', ascending=True)
    fig_aud = go.Figure()
    fig_aud.add_trace(go.Bar(
        x=co_detail_df['Avg_Unit_Day'], y=co_detail_df['Perusahaan'],
        orientation='h', marker_color='#06D6A0',
        text=co_detail_df['Avg_Unit_Day'].apply(lambda v: f"{v:,.0f} L"),
        textposition='inside', textfont=dict(color='white', size=11)
    ))
    fig_aud.update_layout(template='plotly_dark', height=300,
                         margin=dict(t=30, b=30, l=20, r=20),
                         xaxis_title="Avg L/Unit/Hari", yaxis_title="")
    st.plotly_chart(fig_aud, use_container_width=True, key="perusahaan_chart_avg_unit")

    # ─── CHART 4: Detail per Company (dropdown) ───────────────
    section("🔍 Detail Unit per Perusahaan")
    selected_co = st.selectbox("Pilih Perusahaan:",
                               sorted(df_active['Perusahaan'].unique()),
                               key="perusahaan_detail")

    co_data = df_active[df_active['Perusahaan'] == selected_co]
    co_units = co_data.groupby(['Tipe_Unit', 'Jenis_Alat'])['Liter'].sum().reset_index()
    co_units = co_units.sort_values('Liter', ascending=True)
    co_units['Label'] = co_units['Tipe_Unit'].str[:30]

    fig3 = px.bar(co_units, x='Liter', y='Label', orientation='h', color='Jenis_Alat',
                 color_discrete_sequence=COLORS, text_auto=True)
    fig3.update_traces(texttemplate='%{x:,.0f} L', textposition='inside', textfont=dict(color='white', size=11))
    fig3.update_layout(template='plotly_dark',
                      height=max(300, len(co_units) * 25 + 100),
                      margin=dict(t=30, b=30, l=20, r=60),
                      yaxis_title="", legend_title="Jenis Alat")
    st.plotly_chart(fig3, use_container_width=True, key="perusahaan_chart_detail_co")

    # Summary Table
    with st.expander("📋 Ringkasan per Perusahaan", expanded=False):
        summary = df_active.groupby('Perusahaan').agg(
            Total_Liter=('Liter', 'sum'),
            Jumlah_Unit=('Tipe_Unit', 'nunique'),
            Hari_Aktif=('Tanggal', 'nunique'),
        ).reset_index()
        summary['Rata_rata_Harian'] = (summary['Total_Liter'] / summary['Hari_Aktif']).round(0)
        summary['Persentase'] = (summary['Total_Liter'] / summary['Total_Liter'].sum() * 100).round(1)
        summary = summary.sort_values('Total_Liter', ascending=False)

        st.dataframe(summary, use_container_width=True)

        excel_data = convert_df_to_excel(summary)
        st.download_button("📥 Download Excel", data=excel_data,
                          file_name="analisis_perusahaan.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Anti-ghosting: pad the end of the page with empty slots to wipe out previous charts
    content_end_marker(count=25)
