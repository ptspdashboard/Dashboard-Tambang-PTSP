# ============================================================
# SIDEBAR - Navigation Component
# ============================================================

import streamlit as st
from config import CACHE_TTL
# check_onedrive_status removed - using static Database indicator for speed
from utils.helpers import get_logo_base64
from .login import logout


def render_sidebar():
    """Render sidebar navigation"""
    logo_base64 = get_logo_base64()
    
    with st.sidebar:
        # Logo & Brand
        if logo_base64:
            logo_html = f'<img src="data:image/jpeg;base64,{logo_base64}" alt="Logo" style="width:60px; height:auto; border-radius:10px; margin-bottom:0.5rem; box-shadow: 0 4px 16px rgba(0,0,0,0.3);">'
        else:
            logo_html = '<span style="font-size:2rem;">⛏️</span>'
        
        st.markdown(f"""
        <div style="text-align:center; padding:1rem 0 0.5rem 0;">
            {logo_html}
            <p style="color:#d4a84b; font-weight:700; font-size:1.1rem; margin:0.5rem 0 0 0;">
                MINING OPS
            </p>
            <p style="color:#64748b; font-size:0.7rem; margin:0;">Semen Padang</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # User Card
        st.markdown(f"""
        <div class="user-card">
            <div class="user-avatar">👤</div>
            <p class="user-name">{st.session_state.name}</p>
            <p class="user-role">{st.session_state.role}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Connection Status - Database Mode (No OneDrive check for speed)
        st.markdown('<p class="nav-label">📡 Data Status</p>', unsafe_allow_html=True)
        
        # Static status since we're using Database, not OneDrive
        # This avoids 10-14 second delay from check_onedrive_status()
        st.markdown('''
        <div class="status-grid">
            <div class="status-item">
                <span class="status-name">Database</span>
                <span class="status-value status-ok">✅ Connected</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)
            
        # Unified Sync Button (Professional Single-Click Action)
        if st.button("🔄 Sync & Refresh Data", use_container_width=True, type="primary", help="Ambil data terbaru dari OneDrive dan perbarui tampilan"):
            with st.status("🔄 Sinkronisasi Data OneDrive...", expanded=True) as status:
                st.write("Menghubungkan ke Database...")
                
                # 1. Clear ALL caches BEFORE sync
                st.cache_data.clear()
                st.cache_resource.clear()
                
                # 2. Clear ALL session state data
                keys_to_clear = [
                    'df_prod', 'df_gangguan', 'df_shipping', 'df_stockpile', 
                    'df_ritase', 'df_daily_plan', 'df_target',
                    'df_solar', 'df_fuel', 'df_refueling', 'df_solar_ref',
                    'last_sync_time', 'data_loaded', '_sync_time_checked'
                ]
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                
                try:
                    from utils.sync_manager import sync_all_data
                    st.write("📥 Mengunduh & Memperbarui Data...")
                    
                    report = sync_all_data()
                    
                    for module, result in report.items():
                        st.write(f"{module}: {result}")
                    
                    # 3. Mark sync as complete with timestamp
                    import pytz
                    from datetime import datetime
                    jakarta_tz = pytz.timezone('Asia/Jakarta')
                    current_time = datetime.now(jakarta_tz).strftime("%H:%M")
                    st.session_state['last_sync_time'] = current_time
                    
                    status.update(label="✅ Sinkronisasi Selesai!", state="complete", expanded=False)
                    st.toast("Data Berhasil Diperbarui!", icon="✅")
                    
                    # 4. Force immediate rerun without delay
                    st.rerun()
                    
                except Exception as e:
                    status.update(label="❌ Sinkronisasi Gagal", state="error")
                    st.error(f"Error: {str(e)}")
            
        # Display Last Sync Time (Actual sync time, not just render time)
        last_sync = st.session_state.get('last_sync_time')
        
        # Helper to convert to WIB if needed
        def to_wib(time_val):
            if not time_val: return None
            try:
                import pytz
                from datetime import datetime
                
                # If it's already a string, assume it's correct or needs parsing
                if isinstance(time_val, str):
                    # Try to parse if it lacks timezone info, but for now we trust the string from DB
                    return time_val
                
                # If datetime object
                if isinstance(time_val, datetime):
                    jakarta_tz = pytz.timezone('Asia/Jakarta')
                    if time_val.tzinfo is None:
                        # Assume UTC if no tzinfo, then convert
                        return pytz.utc.localize(time_val).astimezone(jakarta_tz).strftime("%H:%M")
                    else:
                        return time_val.astimezone(jakarta_tz).strftime("%H:%M")
            except:
                pass
            return time_val
        
        # If not in session, try to fetch from DB ONCE per session (not every render)
        if not last_sync and not st.session_state.get('_sync_time_checked', False):
            try:
                from utils.db_manager import get_db_engine
                from sqlalchemy import text
                engine = get_db_engine()
                if engine:
                    with engine.connect() as conn:
                        result = conn.execute(text("SELECT value FROM system_logs WHERE key = 'last_sync'"))
                        row = result.fetchone()
                        if row and row[0]:
                            last_sync = row[0]
                            st.session_state['last_sync_time'] = last_sync
            except:
                pass
            st.session_state['_sync_time_checked'] = True

        if last_sync:
            st.markdown(f'<p style="color:#64748b; font-size:0.75rem; text-align:center; margin-top:0.5rem;">Last Sync: {last_sync}</p>', unsafe_allow_html=True)
        else:
            st.markdown(f'<p style="color:#64748b; font-size:0.75rem; text-align:center; margin-top:0.5rem; font-style:italic;">Belum disinkronisasi hari ini</p>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ============================================================
        # ROLE-BASED NAVIGATION & FILTERS
        # ============================================================
        user_role = st.session_state.get('role', 'viewer')
        
        if user_role == 'admin_solar':
            _render_solar_sidebar()
        else:
            _render_production_sidebar()
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        # Logout
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()
            st.rerun()
            st.rerun()
        
        # Footer
        st.markdown("""
        <div style="text-align:center; margin-top:2rem; padding-top:1rem; border-top:1px solid #1e3a5f;">
            <p style="color:#64748b; font-size:0.7rem; margin:0;">
                Mining Dashboard v4.0<br>
                © 2025 Semen Padang
            </p>
        </div>
        """, unsafe_allow_html=True)


def _render_solar_sidebar():
    """Sidebar khusus admin_solar — Global Filters + 6 module navigation
    Matches production sidebar layout: filters in expander above navigation.
    """
    import pandas as pd
    from datetime import date
    from utils.data_loader import load_solar_refueling
    
    today = date.today()
    default_start = date(today.year, today.month, 1)
    
    # Initialize solar filters
    if 'solar_filters' not in st.session_state:
        st.session_state.solar_filters = {
            'date_range': (default_start, today),
            'perusahaan': [],
            'jenis_alat': [],
            'unit': []
        }
    
    # Load data for filter options
    df_solar = st.session_state.get('df_solar_ref', None)
    if df_solar is None or (hasattr(df_solar, 'empty') and df_solar.empty):
        df_solar = load_solar_refueling()
        if df_solar is not None and not df_solar.empty:
            st.session_state['df_solar_ref'] = df_solar
    
    # ---- GLOBAL FILTERS (in expander, like production) ----
    with st.expander("🔍 Global Filters", expanded=True):
        if df_solar is not None and not df_solar.empty:
            # Reset Button
            if st.button("♻️ Reset Filter (Semua)", use_container_width=True, help="Kembalikan filter ke default"):
                st.session_state.solar_filters = {
                    'date_range': (default_start, today),
                    'perusahaan': [],
                    'jenis_alat': [],
                    'unit': []
                }
                st.rerun()
            
            # 1. Date range filter
            date_range = st.date_input(
                "📅 Rentang Tanggal",
                value=st.session_state.solar_filters.get('date_range', (default_start, today)),
                key="sf_date_range"
            )
            
            # 2. Perusahaan filter
            avail_co = sorted(df_solar['Perusahaan'].dropna().unique().tolist()) if 'Perusahaan' in df_solar.columns else []
            
            current_co = st.session_state.solar_filters.get('perusahaan', [])
            valid_co = [c for c in current_co if c in avail_co]
            
            sel_co = st.multiselect(
                "🏢 Perusahaan",
                options=avail_co,
                default=valid_co,
                placeholder="Semua Perusahaan",
                key="sf_perusahaan"
            )
            
            # 3. Jenis Alat — cascading from Perusahaan
            mask = pd.Series([True] * len(df_solar), index=df_solar.index)
            if sel_co:
                mask &= df_solar['Perusahaan'].isin(sel_co)
            avail_jenis = sorted(df_solar[mask]['Jenis_Alat'].dropna().unique().tolist()) if 'Jenis_Alat' in df_solar.columns else []
            
            current_jenis = st.session_state.solar_filters.get('jenis_alat', [])
            valid_jenis = [j for j in current_jenis if j in avail_jenis]
            
            sel_jenis = st.multiselect(
                "🔧 Jenis Alat",
                options=avail_jenis,
                default=valid_jenis,
                placeholder="Semua Jenis Alat",
                key="sf_jenis"
            )
            
            # 4. Tipe Unit — cascading from Perusahaan + Jenis Alat
            mask2 = mask.copy()
            if sel_jenis:
                mask2 &= df_solar['Jenis_Alat'].isin(sel_jenis)
            avail_unit = sorted(df_solar[mask2]['Tipe_Unit'].dropna().unique().tolist()) if 'Tipe_Unit' in df_solar.columns else []
            
            current_unit = st.session_state.solar_filters.get('unit', [])
            valid_unit = [u for u in current_unit if u in avail_unit]
            
            sel_unit = st.multiselect(
                "🚜 Tipe Unit",
                options=avail_unit,
                default=valid_unit,
                placeholder="Semua Unit",
                key="sf_unit"
            )
            
            # Store filters
            st.session_state.solar_filters = {
                'date_range': date_range,
                'perusahaan': sel_co,
                'jenis_alat': sel_jenis,
                'unit': sel_unit
            }
        else:
            st.caption("_Belum ada data. Klik Sync & Refresh Data._")
    
    st.markdown("---")
    
    # ---- NAVIGATION (6 modules) ----
    st.markdown('<p class="nav-label">📋 Navigation</p>', unsafe_allow_html=True)
    
    menus = [
        ("🏠", "Ringkasan BBM"),
        ("🛢️", "Pemakaian Solar"),
        ("⚡", "Efisiensi BBM"),
        ("🏢", "Analisis Perusahaan"),
        ("📊", "Hour Meter & Operasi"),
        ("📈", "Trend & Perbandingan"),
    ]
    
    def set_menu(menu_name):
        st.session_state.current_menu = menu_name
    
    for icon, menu in menus:
        btn_type = "primary" if st.session_state.current_menu == menu else "secondary"
        st.button(
            f"{icon}  {menu}",
            key=f"nav_{menu}",
            use_container_width=True,
            type=btn_type,
            on_click=set_menu,
            args=(menu,)
        )


def _render_production_sidebar():
    """Sidebar produksi (existing) — unchanged for admin_produksi"""
    
    # ============================================================
    # GLOBAL FILTERS (PRODUCTION)
    # ============================================================
    from datetime import date
    today = date.today()
    default_start = date(today.year, today.month, 1)
    
    if 'global_filters' not in st.session_state:
        st.session_state.global_filters = {
            'date_range': (default_start, today),
            'shift': 'All Displatch',
            'front': [],
            'excavator': [],
            'material': []
        }

    with st.expander("🔍 Global Filters", expanded=True):
        if st.button("♻️ Reset Filter (Bulan Ini)", use_container_width=True, help="Kembalikan filter ke Bulan Ini"):
            st.session_state.global_filters = {
                'date_range': (default_start, today),
                'shift': 'All Displatch',
                'front': [],
                'excavator': [],
                'material': []
            }
            st.rerun()

        date_range = st.date_input(
            "📅 Rentang Tanggal",
            value=st.session_state.global_filters.get('date_range', (default_start, today)),
            key="filter_date_range"
        )
        
        filter_options = st.session_state.get('filter_options', None)
        if not filter_options:
            from utils.data_loader import get_filter_options
            filter_options = get_filter_options()
            st.session_state['filter_options'] = filter_options

        shift_options = ["All Displatch"]
        shift_options.extend(filter_options.get('shift', []))
            
        current_shift = st.session_state.global_filters.get('shift', 'All Displatch')
        if current_shift not in shift_options:
            current_shift = 'All Displatch'
            
        shift_select = st.selectbox(
            "🕒 Shift Operasional",
            shift_options,
            index=shift_options.index(current_shift),
            key="filter_shift"
        )
        
        front_select = st.multiselect(
            "📍 Lokasi Kerja (Front)",
            options=filter_options.get('front', []),
            default=st.session_state.global_filters.get('front', []),
            placeholder="Pilih Front (Opsional)",
            key="filter_front"
        )
        
        exca_select = st.multiselect(
            "🚜 Unit Excavator",
            options=filter_options.get('excavator', []),
            default=st.session_state.global_filters.get('excavator', []),
            placeholder="Pilih Unit (Opsional)",
            key="filter_exca"
        )
        
        mat_select = st.multiselect(
            "🪨 Jenis Material",
            options=filter_options.get('material', []),
            default=st.session_state.global_filters.get('material', []),
            placeholder="Pilih Material (Opsional)",
            key="filter_mat"
        )
        
        st.session_state.global_filters['date_range'] = date_range
        st.session_state.global_filters['shift'] = shift_select
        st.session_state.global_filters['front'] = front_select
        st.session_state.global_filters['excavator'] = exca_select
        st.session_state.global_filters['material'] = mat_select
    
    st.markdown("---")
    
    # Navigation
    st.markdown('<p class="nav-label">📋 Navigation</p>', unsafe_allow_html=True)
    
    menus = [
        ("🏠", "Ringkasan Eksekutif"),
        ("⛏️", "Kinerja Produksi"),
        ("🚛", "Aktivitas Ritase"),
        ("⚙️", "Stockpile & Pengolahan"),
        ("🚨", "Analisa Kendala"),
        ("🚢", "Pengiriman & Logistik"),
        ("📋", "Rencana Harian"),
    ]
    
    def set_menu(menu_name):
        st.session_state.current_menu = menu_name

        
    for icon, menu in menus:
        btn_type = "primary" if st.session_state.current_menu == menu else "secondary"
        st.button(
            f"{icon}  {menu}", 
            key=f"nav_{menu}", 
            use_container_width=True, 
            type=btn_type,
            on_click=set_menu,
            args=(menu,)
        )

