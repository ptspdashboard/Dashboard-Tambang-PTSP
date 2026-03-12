"""
Solar Module 2: Pemakaian Solar (Consumption Detail)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from views.solar_common import (
    COLORS, fmt, header, kpi_card, section, spacer, load_and_filter,
    content_end_marker
)
from utils.helpers import convert_df_to_excel


def show_solar_pemakaian():
    df_full, df = load_and_filter()
    header("Pemakaian Solar", "Detail Konsumsi Harian dengan Breakdown Shift Pagi & Sore", "🛢️")

    if df.empty:
        st.warning("Belum ada data. Klik **Sync & Refresh Data** di sidebar.")
        return

    df_active = df[df['Liter'] > 0]
    total = df_active['Liter'].sum()
    days = df_active['Tanggal'].nunique()
    avg_daily = total / days if days > 0 else 0

    # Shift breakdown
    total_pagi = df_active[df_active['Shift'] == 'P']['Liter'].sum()
    total_sore = df_active[df_active['Shift'] == 'S']['Liter'].sum()

    # Top consumer
    top_unit_agg = df_active.groupby('Tipe_Unit')['Liter'].sum()
    top_name = top_unit_agg.idxmax() if len(top_unit_agg) > 0 else 'N/A'
    top_val = top_unit_agg.max() if len(top_unit_agg) > 0 else 0

    # Avg per unit per day
    unit_daily = df_active.groupby(['Tipe_Unit', 'Tanggal'])['Liter'].sum()
    avg_per_unit = unit_daily.mean()

    # KPIs (5)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi_card("Total Pemakaian", fmt(total, " L"), icon="⛽")
    with c2: kpi_card("Pengisian Pagi", fmt(total_pagi, " L"), icon="🌅",
                       help_text=f"{total_pagi/total*100:.0f}% dari total" if total > 0 else "")
    with c3: kpi_card("Pengisian Sore", fmt(total_sore, " L"), icon="🌆",
                       help_text=f"{total_sore/total*100:.0f}% dari total" if total > 0 else "")
    with c4: kpi_card("Top Consumer", f"{top_name[:22]}", icon="🏆",
                       help_text=f"{fmt(top_val)} L total")
    with c5: kpi_card("Avg/Unit/Hari", fmt(avg_per_unit, " L"), icon="📊")

    spacer()

    # Chart 1: Daily consumption trend with max annotation
    section("📊 Tren Pemakaian Harian")
    daily = df_active.groupby('Tanggal')['Liter'].sum().reset_index().sort_values('Tanggal')
    avg_val = daily['Liter'].mean()
    max_day = daily.loc[daily['Liter'].idxmax()]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily['Tanggal'], y=daily['Liter'],
                        marker_color='#118AB2', name='Total', opacity=0.9,
                        text=daily['Liter'].apply(lambda v: f"{v:,.0f}"),
                        textposition='inside', textfont=dict(color='white', size=11)))
    fig.add_hline(y=avg_val, line_dash="dash", line_color="#06D6A0",
                 annotation_text=f"Avg: {avg_val:,.0f}")
    fig.add_annotation(x=max_day['Tanggal'], y=max_day['Liter'],
                      text=f"Max: {max_day['Liter']:,.0f}",
                      showarrow=True, arrowhead=2, font=dict(color='#ef4444', size=11))
    fig.update_layout(template='plotly_dark', height=350,
                     margin=dict(t=40, b=30, l=40, r=20))
    st.plotly_chart(fig, use_container_width=True, key="pemakaian_chart_daily")

    # Charts Row 2
    col1, col2 = st.columns(2)

    with col1:
        section("🌅 Shift Pagi vs 🌆 Sore (Stacked)")
        shift_daily = df_active.groupby(['Tanggal', 'Shift'])['Liter'].sum().reset_index()
        if not shift_daily.empty:
            shift_daily['Shift_Label'] = shift_daily['Shift'].map({'P': 'Pagi', 'S': 'Sore'})
            fig2 = px.bar(shift_daily, x='Tanggal', y='Liter', color='Shift_Label',
                         color_discrete_map={'Pagi': '#FFB627', 'Sore': '#118AB2'},
                         barmode='stack', text_auto=True)
            fig2.update_traces(texttemplate='%{y:,.0f}', textposition='inside', textfont=dict(color='white', size=10))
            fig2.update_layout(template='plotly_dark', height=350,
                              margin=dict(t=30, b=30, l=40, r=20),
                              legend_title="Shift")
            st.plotly_chart(fig2, use_container_width=True)


    with col2:
        section("🔧 Distribusi per Jenis Alat")
        jenis_dist = df_active.groupby('Jenis_Alat')['Liter'].sum().reset_index()
        jenis_dist = jenis_dist.sort_values('Liter', ascending=True)
        jenis_dist['Persen'] = (jenis_dist['Liter'] / jenis_dist['Liter'].sum() * 100).round(1)
        jenis_dist['Label'] = jenis_dist.apply(
            lambda r: f"{fmt(r['Liter'])} L ({r['Persen']}%)", axis=1)

        fig3 = px.bar(jenis_dist, x='Liter', y='Jenis_Alat', orientation='h',
                     text='Label', color_discrete_sequence=['#06D6A0'])
        fig3.update_layout(template='plotly_dark', height=350,
                          margin=dict(t=30, b=30, l=20, r=20), yaxis_title="")
        fig3.update_traces(textposition='inside', textfont=dict(color='white', size=11))
        st.plotly_chart(fig3, use_container_width=True, key="pemakaian_chart_jenis")


    # Chart 3: Top 10 Unit
    section("🏆 Top 10 Unit Konsumsi Tertinggi")
    top10 = df_active.groupby(['Tipe_Unit', 'Perusahaan'])['Liter'].sum().reset_index()
    top10 = top10.nlargest(10, 'Liter').sort_values('Liter', ascending=True)
    top10['Label'] = top10['Tipe_Unit'].str[:25] + ' (' + top10['Perusahaan'].str[:10] + ')'

    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
        x=top10['Liter'], y=top10['Label'],
        orientation='h', marker_color='#118AB2',
        text=top10['Liter'].apply(lambda v: f"{v:,.0f} L"),
        textposition='inside', textfont=dict(color='white', size=11)
    ))
    fig4.update_layout(template='plotly_dark', height=400,
                      margin=dict(t=30, b=30, l=20, r=60),
                      yaxis_title="")
    st.plotly_chart(fig4, use_container_width=True, key="pemakaian_chart_top10")

    # Data Table + Download
    with st.expander("📋 Data Detail Pemakaian", expanded=False):
        display_cols = [c for c in ['Perusahaan', 'Jenis_Alat', 'Tipe_Unit', 'Tanggal',
                                     'Shift', 'Liter', 'Bulan'] if c in df_active.columns]
        display_df = df_active[display_cols].copy()
        display_df['Tanggal'] = display_df['Tanggal'].dt.strftime('%Y-%m-%d')
        display_df = display_df.sort_values(
            ['Tanggal', 'Perusahaan', 'Tipe_Unit'], ascending=[False, True, True])
        st.dataframe(display_df, use_container_width=True, height=400)

        excel_data = convert_df_to_excel(display_df)
        st.download_button("📥 Download Excel", data=excel_data,
                          file_name="pemakaian_solar.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Anti-ghosting: pad the end of the page with empty slots to wipe out previous charts
    content_end_marker(count=25)
