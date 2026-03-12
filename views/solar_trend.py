"""
Solar Module 6: Trend & Perbandingan (Month-over-Month Analysis)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from views.solar_common import (
    COLORS, ACCENT, BULAN_ORDER,
    fmt, header, kpi_card, section, spacer, load_and_filter,
    content_end_marker
)


def show_solar_trend():
    df_full, df = load_and_filter()
    header("Trend & Perbandingan", "Analisis Month-over-Month dan Perbandingan Lintas Dimensi", "📈")

    if df.empty:
        st.warning("Belum ada data. Klik **Sync & Refresh Data** di sidebar.")
        return

    df_active = df[df['Liter'] > 0]

    # Get month list
    bulan_list = sorted(df_active['Bulan'].dropna().unique(),
                       key=lambda x: BULAN_ORDER.get(x, 99))

    if len(bulan_list) < 2:
        st.info("Perlu minimal 2 bulan data untuk analisis trend. Saat ini hanya ada: "
                + ", ".join(bulan_list))
        # Show single month summary
        section("📊 Ringkasan Bulan " + (bulan_list[0] if bulan_list else ""))
        if bulan_list:
            m_data = df_active[df_active['Bulan'] == bulan_list[0]]
            total = m_data['Liter'].sum()
            days = m_data['Tanggal'].nunique()
            units = m_data['Tipe_Unit'].nunique()
            c1, c2, c3 = st.columns(3)
            with c1: kpi_card("Total", fmt(total, " L"), icon="⛽")
            with c2: kpi_card("Hari", f"{days}", icon="📅")
            with c3: kpi_card("Unit", f"{units}", icon="🚜")
        return

    # Month selector dropdowns (default: last two months)
    col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 2])
    with col_sel1:
        prev_month = st.selectbox("Bulan Awal", bulan_list,
                                   index=len(bulan_list) - 2,
                                   key="trend_prev_month")
    with col_sel2:
        cur_month = st.selectbox("Bulan Akhir", bulan_list,
                                  index=len(bulan_list) - 1,
                                  key="trend_cur_month")

    if prev_month == cur_month:
        st.warning("Pilih 2 bulan yang berbeda untuk perbandingan.")
        return

    cur_data = df_active[df_active['Bulan'] == cur_month]
    prev_data = df_active[df_active['Bulan'] == prev_month]

    cur_total = cur_data['Liter'].sum()
    prev_total = prev_data['Liter'].sum()
    growth = ((cur_total - prev_total) / prev_total * 100) if prev_total > 0 else 0
    diff = cur_total - prev_total

    cur_days = cur_data['Tanggal'].nunique()
    prev_days = prev_data['Tanggal'].nunique()
    cur_avg = cur_total / cur_days if cur_days > 0 else 0
    prev_avg = prev_total / prev_days if prev_days > 0 else 0

    # Growth based on avg daily (fair comparison regardless of days)
    avg_growth = ((cur_avg - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0
    growth_label = f"↑ Naik {abs(avg_growth):.1f}%" if avg_growth > 0 else f"↓ Turun {abs(avg_growth):.1f}%"
    diff_avg = cur_avg - prev_avg

    # KPIs (3)
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Growth MoM", growth_label, delta=avg_growth, icon="📈",
                       help_text=f"Perbandingan rata-rata harian {prev_month} vs {cur_month}")
    with c2: kpi_card(f"Avg Harian ({cur_month[:3]})", fmt(cur_avg, " L"), icon="📊",
                       help_text=f"{cur_days} hari data")
    with c3: kpi_card(f"Avg Harian ({prev_month[:3]})", fmt(prev_avg, " L"), icon="📊",
                       help_text=f"{prev_days} hari data")

    spacer()

    # Chart 1: Overlay Jan vs Feb (day-of-month)
    section(f"📊 Overlay {prev_month} vs {cur_month} (per Tanggal)")

    cur_daily = cur_data.groupby('Tanggal')['Liter'].sum().reset_index()
    cur_daily['Day'] = cur_daily['Tanggal'].dt.day
    prev_daily = prev_data.groupby('Tanggal')['Liter'].sum().reset_index()
    prev_daily['Day'] = prev_daily['Tanggal'].dt.day

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=prev_daily['Day'], y=prev_daily['Liter'],
                            mode='lines+markers', name=prev_month,
                            line=dict(color='#94a3b8', width=2, dash='dot'),
                            marker=dict(size=5)))
    fig.add_trace(go.Scatter(x=cur_daily['Day'], y=cur_daily['Liter'],
                            mode='lines+markers', name=cur_month,
                            line=dict(color=ACCENT, width=3),
                            marker=dict(size=6), fill='tonexty',
                            fillcolor='rgba(255,107,53,0.1)'))
    fig.update_layout(template='plotly_dark', height=400,
                     margin=dict(t=30, b=30, l=40, r=20),
                     xaxis_title="Tanggal", yaxis_title="Liter",
                     legend=dict(orientation='h', y=1.05))
    st.plotly_chart(fig, use_container_width=True, key="trend_chart_overlay")

    # Chart 2: Waterfall by Company (what drove the change)
    col1, col2 = st.columns(2)

    with col1:
        section(f"🏗️ Perubahan per Perusahaan (Avg Harian)")
        cur_co = cur_data.groupby('Perusahaan')['Liter'].sum() / cur_days if cur_days > 0 else cur_data.groupby('Perusahaan')['Liter'].sum()
        prev_co = prev_data.groupby('Perusahaan')['Liter'].sum() / prev_days if prev_days > 0 else prev_data.groupby('Perusahaan')['Liter'].sum()
        all_cos = sorted(set(cur_co.index) | set(prev_co.index))

        delta_data = []
        for co in all_cos:
            c_val = cur_co.get(co, 0)
            p_val = prev_co.get(co, 0)
            delta_data.append({'Perusahaan': co, 'Delta': c_val - p_val})

        delta_df = pd.DataFrame(delta_data).sort_values('Delta', ascending=True)
        delta_df['Color'] = delta_df['Delta'].apply(lambda x: '#ef4444' if x > 0 else '#22c55e')
        delta_df['Label'] = delta_df['Delta'].apply(lambda x: f"↑{x:,.0f}" if x > 0 else f"↓{abs(x):,.0f}")

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=delta_df['Delta'], y=delta_df['Perusahaan'],
                             orientation='h', marker_color=delta_df['Color'],
                             text=delta_df['Label'], textposition='inside',
                             textfont=dict(color='white', size=11)))
        fig2.add_vline(x=0, line_color='white', line_width=1)
        fig2.update_layout(template='plotly_dark', height=400,
                          margin=dict(t=30, b=30, l=20, r=60),
                          xaxis_title="Selisih Avg Harian (L)", yaxis_title="")
        st.plotly_chart(fig2, use_container_width=True, key="trend_chart_waterfall_co")


    with col2:
        section(f"🔝 Top Movers Unit (Avg Harian)")
        cur_unit = cur_data.groupby('Tipe_Unit')['Liter'].sum() / cur_days if cur_days > 0 else cur_data.groupby('Tipe_Unit')['Liter'].sum()
        prev_unit = prev_data.groupby('Tipe_Unit')['Liter'].sum() / prev_days if prev_days > 0 else prev_data.groupby('Tipe_Unit')['Liter'].sum()
        all_units = set(cur_unit.index) | set(prev_unit.index)

        unit_delta = []
        for u in all_units:
            c_val = cur_unit.get(u, 0)
            p_val = prev_unit.get(u, 0)
            unit_delta.append({'Unit': u[:25], 'Delta': c_val - p_val, 'Abs': abs(c_val - p_val)})

        unit_delta_df = pd.DataFrame(unit_delta)
        top_movers = unit_delta_df.nlargest(10, 'Abs').sort_values('Delta', ascending=True)
        top_movers['Color'] = top_movers['Delta'].apply(lambda x: '#ef4444' if x > 0 else '#22c55e')

        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=top_movers['Delta'], y=top_movers['Unit'],
                             orientation='h', marker_color=top_movers['Color'],
                             text=top_movers['Delta'].apply(lambda x: f"↑{x:,.0f}" if x > 0 else f"↓{abs(x):,.0f}"),
                             textposition='inside', textfont=dict(color='white', size=11)))
        fig3.add_vline(x=0, line_color='white', line_width=1)
        fig3.update_layout(template='plotly_dark', height=400,
                          margin=dict(t=30, b=30, l=20, r=60),
                          xaxis_title="Selisih Avg Harian (L)", yaxis_title="")
        st.plotly_chart(fig3, use_container_width=True, key="trend_chart_waterfall_unit")


    # Chart 3: Monthly summary comparison table
    section("📋 Perbandingan Detail")

    cur_units = cur_data['Tipe_Unit'].nunique()
    prev_units = prev_data['Tipe_Unit'].nunique()
    cur_cos = cur_data['Perusahaan'].nunique()
    prev_cos = prev_data['Perusahaan'].nunique()
    top_prev = prev_data.groupby('Tipe_Unit')['Liter'].sum().idxmax() if not prev_data.empty else 'N/A'
    top_cur = cur_data.groupby('Tipe_Unit')['Liter'].sum().idxmax() if not cur_data.empty else 'N/A'

    comparison = pd.DataFrame({
        'Metrik': ['Rata-rata Harian (L)', 'Total Konsumsi (L)', 'Unit Aktif',
                   'Perusahaan Aktif', 'Top Consumer Unit'],
        f'{prev_month} ({prev_days} hari)': [
            f"{prev_avg:,.0f}",
            f"{prev_total:,.0f}",
            str(prev_units),
            str(prev_cos),
            top_prev
        ],
        f'{cur_month} ({cur_days} hari)': [
            f"{cur_avg:,.0f}",
            f"{cur_total:,.0f}",
            str(cur_units),
            str(cur_cos),
            top_cur
        ],
        'Perubahan': [
            f"{'↓' if avg_growth < 0 else '↑'} {abs(avg_growth):.1f}%",
            f"{cur_days} dari ~31 hari",
            f"{cur_units - prev_units:+d}",
            f"{cur_cos - prev_cos:+d}",
            ""
        ]
    })
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    # Anti-ghosting: pad the end of the page with empty slots to wipe out previous charts
    content_end_marker(count=25)
