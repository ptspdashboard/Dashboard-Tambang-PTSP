"""
Solar Module 5: Hour Meter & Operasi (Equipment Usage Tracking)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from views.solar_common import (
    COLORS, fmt, header, kpi_card, section, spacer, is_lkm_unit, load_and_filter,
    content_end_marker
)


def show_solar_hourmeter():
    df_full, df = load_and_filter()
    header("Hour Meter & Operasi", "Tracking Jam Operasi (Alat Berat) dan Kilometer (LV & Scania)", "📊")

    if df.empty:
        st.warning("Belum ada data. Klik **Sync & Refresh Data** di sidebar.")
        return

    # Split by unit type: Jam (alat berat) vs Km (LV/Scania)
    def _is_lkm(row):
        name = str(row.get('Tipe_Unit', '')).upper()
        return any(kw in name for kw in ['LV ', 'LV)', 'SCANIA', 'STRADA', 'PICK UP', 'PICKUP'])

    df_ops = df[df['Jam_Operasi'].notna() & (df['Jam_Operasi'] > 0)].copy()
    df_hm = df[df['HM_Value'].notna() & (df['HM_Value'] > 0)].copy()

    if df_ops.empty:
        st.info("Data Jam Operasi / Kilometer belum tersedia dari file PENGISIAN.")
        return

    mask_lkm = df_ops.apply(_is_lkm, axis=1)
    df_jam = df_ops[~mask_lkm].copy()   # Alat berat → Jam
    df_km = df_ops[mask_lkm].copy()     # LV/Scania → Kilometer

    # ==================== SECTION 1: Jam Operasi (Alat Berat) ====================
    st.markdown("---")
    section("🔧 Jam Operasi Alat Berat")

    if not df_jam.empty:
        total_jam = df_jam['Jam_Operasi'].sum()
        units_jam = df_jam['Tipe_Unit'].nunique()
        avg_jam = total_jam / units_jam if units_jam > 0 else 0
        unit_jam_sum = df_jam.groupby('Tipe_Unit')['Jam_Operasi'].sum()
        most_active_j = unit_jam_sum.idxmax() if len(unit_jam_sum) > 0 else 'N/A'
        most_active_jv = unit_jam_sum.max() if len(unit_jam_sum) > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi_card("Total Jam Operasi", fmt(total_jam, " Jam"), icon="⏱️")
        with c2: kpi_card("Avg Jam/Unit", f"{avg_jam:.1f} Jam", icon="📈",
                           help_text=f"Dari {units_jam} unit aktif")
        with c3: kpi_card("Unit Paling Aktif", f"{most_active_j[:20]}", icon="🔧",
                           help_text=f"{fmt(most_active_jv)} Jam total")
        with c4: kpi_card("Hari Operasi", f"{df_jam['Tanggal'].nunique()}", icon="📅")

        spacer()

        col1, col2 = st.columns(2)
        with col1:
            section("⏱️ Jam Operasi Harian")
            daily_jam = df_jam.groupby('Tanggal')['Jam_Operasi'].sum().reset_index().sort_values('Tanggal')
            fig = go.Figure()
            fig.add_trace(go.Bar(x=daily_jam['Tanggal'], y=daily_jam['Jam_Operasi'],
                                marker_color='#06D6A0', opacity=0.9,
                                text=daily_jam['Jam_Operasi'].apply(lambda v: f"{v:,.0f}"),
                                textposition='inside', textfont=dict(color='white', size=11)))
            avg_daily = daily_jam['Jam_Operasi'].mean()
            fig.add_hline(y=avg_daily, line_dash="dash", line_color="#FFB627",
                         annotation_text=f"Avg: {avg_daily:,.0f} Jam")
            fig.update_layout(template='plotly_dark', height=350,
                             margin=dict(t=40, b=30, l=40, r=20), yaxis_title="Jam")
            st.plotly_chart(fig, use_container_width=True, key="hourmeter_chart_jam_daily")


        with col2:
            section("🔧 Jam per Jenis Alat")
            jenis_jam = df_jam.groupby('Jenis_Alat')['Jam_Operasi'].sum().reset_index()
            jenis_jam = jenis_jam.sort_values('Jam_Operasi', ascending=True)
            fig2 = px.bar(jenis_jam, x='Jam_Operasi', y='Jenis_Alat', orientation='h',
                         text_auto=True, color_discrete_sequence=['#118AB2'])
            fig2.update_traces(texttemplate='%{x:,.0f} Jam', textposition='inside',
                              textfont=dict(color='white', size=11))
            fig2.update_layout(template='plotly_dark', height=350,
                              margin=dict(t=30, b=30, l=20, r=60), yaxis_title="")
            st.plotly_chart(fig2, use_container_width=True, key="hourmeter_chart_jam_jenis")


        section("🏆 Top 10 Unit Jam Operasi Tertinggi")
        top10_j = df_jam.groupby(['Tipe_Unit', 'Perusahaan'])['Jam_Operasi'].sum().reset_index()
        top10_j = top10_j.nlargest(10, 'Jam_Operasi').sort_values('Jam_Operasi', ascending=True)
        top10_j['Label'] = top10_j['Tipe_Unit'].str[:25] + ' (' + top10_j['Perusahaan'].str[:8] + ')'
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=top10_j['Jam_Operasi'], y=top10_j['Label'],
            orientation='h', marker_color='#06D6A0',
            text=top10_j['Jam_Operasi'].apply(lambda v: f"{v:,.0f} Jam"),
            textposition='inside', textfont=dict(color='white', size=11)
        ))
        fig3.update_layout(template='plotly_dark', height=400,
                          margin=dict(t=30, b=30, l=20, r=60),
                          yaxis_title="")
        st.plotly_chart(fig3, use_container_width=True, key="hourmeter_chart_jam_top10")
    else:
        st.info("Belum ada data Jam Operasi untuk alat berat.")

    # ==================== SECTION 2: Kilometer (LV & Scania) ====================
    st.markdown("---")
    section("🚛 Kilometer LV & Scania")

    if not df_km.empty:
        total_km = df_km['Jam_Operasi'].sum()
        units_km = df_km['Tipe_Unit'].nunique()
        avg_km = total_km / units_km if units_km > 0 else 0
        unit_km_sum = df_km.groupby('Tipe_Unit')['Jam_Operasi'].sum()
        most_active_k = unit_km_sum.idxmax() if len(unit_km_sum) > 0 else 'N/A'
        most_active_kv = unit_km_sum.max() if len(unit_km_sum) > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi_card("Total Kilometer", fmt(total_km, " Km"), icon="🛣️")
        with c2: kpi_card("Avg Km/Unit", f"{avg_km:,.0f} Km", icon="📈",
                           help_text=f"Dari {units_km} unit aktif")
        with c3: kpi_card("Unit Paling Aktif", f"{most_active_k[:20]}", icon="🚛",
                           help_text=f"{fmt(most_active_kv)} Km total")
        with c4: kpi_card("Unit Beroperasi", f"{units_km}", icon="🚗")

        spacer()

        col1, col2 = st.columns(2)
        with col1:
            section("🛣️ Kilometer Harian")
            daily_km = df_km.groupby('Tanggal')['Jam_Operasi'].sum().reset_index().sort_values('Tanggal')
            fig4 = go.Figure()
            fig4.add_trace(go.Bar(x=daily_km['Tanggal'], y=daily_km['Jam_Operasi'],
                                marker_color='#118AB2', opacity=0.9,
                                text=daily_km['Jam_Operasi'].apply(lambda v: f"{v:,.0f}"),
                                textposition='inside', textfont=dict(color='white', size=11)))
            avg_daily_km = daily_km['Jam_Operasi'].mean()
            fig4.add_hline(y=avg_daily_km, line_dash="dash", line_color="#FFB627",
                          annotation_text=f"Avg: {avg_daily_km:,.0f} Km")
            fig4.update_layout(template='plotly_dark', height=350,
                              margin=dict(t=40, b=30, l=40, r=20), yaxis_title="Km")
            st.plotly_chart(fig4, use_container_width=True, key="hourmeter_chart_km_daily")


        with col2:
            section("🏆 Top 10 Unit Km Tertinggi")
            top10_k = df_km.groupby(['Tipe_Unit', 'Perusahaan'])['Jam_Operasi'].sum().reset_index()
            top10_k = top10_k.nlargest(10, 'Jam_Operasi').sort_values('Jam_Operasi', ascending=True)
            top10_k['Label'] = top10_k['Tipe_Unit'].str[:25] + ' (' + top10_k['Perusahaan'].str[:8] + ')'
            fig5 = go.Figure()
            fig5.add_trace(go.Bar(
                x=top10_k['Jam_Operasi'], y=top10_k['Label'],
                orientation='h', marker_color='#118AB2',
                text=top10_k['Jam_Operasi'].apply(lambda v: f"{v:,.0f} Km"),
                textposition='inside', textfont=dict(color='white', size=11)
            ))
            fig5.update_layout(template='plotly_dark', height=350,
                              margin=dict(t=30, b=30, l=20, r=60),
                              yaxis_title="")
            st.plotly_chart(fig5, use_container_width=True, key="hourmeter_chart_km_top10")

    else:
        st.info("Belum ada data Kilometer untuk LV & Scania.")

    # Anti-ghosting: pad the end of the page with empty slots to wipe out previous charts
    content_end_marker(count=25)
