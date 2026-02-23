# ============================================================
# DATA LOADER - FIXED FOR EXCEL SERIAL DATES
# ============================================================
# VERSION: 3.0 - Fixed Excel serial number date parsing

import pandas as pd
import streamlit as st
import requests
from io import BytesIO
import base64
import os
import sys
from datetime import datetime, timedelta
import time

from datetime import datetime, timedelta
from utils.db_manager import get_db_engine

# Import Settings
# Import Settings
try:
    from config.settings import MONITORING_EXCEL_PATH, PRODUKSI_FILE, GANGGUAN_FILE, CACHE_TTL, ONEDRIVE_LINKS
    
    LOCAL_FILE_NAMES = {
        "monitoring": [MONITORING_EXCEL_PATH, r"C:\Users\user\OneDrive\Dashboard_Tambang\Monitoring_2025_.xlsx"],
        "produksi": [PRODUKSI_FILE, r"C:\Users\user\OneDrive\Dashboard_Tambang\Produksi_UTSG_Harian.xlsx"],
        "gangguan": [GANGGUAN_FILE, r"C:\Users\user\OneDrive\Dashboard_Tambang\Gangguan_Produksi.xlsx"]
    }
except ImportError:
    # Fallback if config not found
    MONITORING_EXCEL_PATH = None
    PRODUKSI_FILE = None
    GANGGUAN_FILE = None
    CACHE_TTL = 3600 # 1 Hour Default
    ONEDRIVE_LINKS = {}
    LOCAL_FILE_NAMES = {}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def apply_global_filters(df, date_col='Date', shift_col='Shift'):
    """Apply sidebar filters to any dataframe"""
    if df.empty:
        return df
        
    # Get filters from session state
    filters = st.session_state.get('global_filters', {})
    date_range = filters.get('date_range')
    selected_shift = filters.get('shift')
    
    # 1. Filter Date
    if date_range and len(date_range) == 2 and date_col in df.columns:
        start_date, end_date = date_range
        
        # ROBUST DATE COMPARISON (String-based YYYY-MM-DD)
        # This avoids datetime.date vs Timestamp vs timezone issues across OS
        start_str = str(start_date)  # '2026-02-16'
        end_str = str(end_date)      # '2026-02-16'
        
        # Convert column to string dates for comparison
        df_copy = df.copy()
        try:
            # Handle various date formats: Timestamp, datetime.date, string
            if pd.api.types.is_datetime64_any_dtype(df_copy[date_col]):
                date_strings = df_copy[date_col].dt.strftime('%Y-%m-%d')
            else:
                date_strings = pd.to_datetime(df_copy[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
            
            mask = (date_strings >= start_str) & (date_strings <= end_str)
            df = df[mask]
        except Exception as e:
            print(f"[FILTER WARNING] Date filter error: {e}")
        
    # 2. Filter Shift
    # Check for both "All Dispatch" (corrected) and "All Displatch" (legacy typo) and "All" (just in case)
    ignore_shifts = ["All Dispatch", "All Displatch", "All"]
    if selected_shift and selected_shift not in ignore_shifts and shift_col in df.columns:
        # Normalize shift values (some might be int 1, some 'Shift 1')
        target_shift = 1 if "1" in str(selected_shift) else (2 if "2" in str(selected_shift) else 3)
        
        # Check if column is numeric or string
        if pd.api.types.is_numeric_dtype(df[shift_col]):
             df = df[df[shift_col] == target_shift]
        else:
             df = df[df[shift_col].astype(str).str.contains(str(target_shift), case=False, na=False)]
             
    # 3. Filter Front
    selected_front = filters.get('front')
    if selected_front and 'Front' in df.columns:
        df = df[df['Front'].isin(selected_front)]
        
    # 4. Filter Excavator
    selected_exca = filters.get('excavator')
    if selected_exca and 'Excavator' in df.columns:
        df = df[df['Excavator'].isin(selected_exca)]

    # 5. Filter Material (Commodity)
    selected_material = filters.get('material')
    if selected_material:
        # Check for both spellings (Commudity vs Commodity)
        if 'Commudity' in df.columns:
            df = df[df['Commudity'].isin(selected_material)]
        elif 'Commodity' in df.columns:
            df = df[df['Commodity'].isin(selected_material)]
        elif 'Material' in df.columns:
             df = df[df['Material'].isin(selected_material)]
             
    return df


def convert_onedrive_link(share_link, cache_bust=False):
    """Convert OneDrive share link ke direct download link"""
    if not share_link or share_link.strip() == "":
        return None
    
    share_link = share_link.strip()
    
    # Determine separator
    # For Strategy 1, we manually added ?download=1, so next is &
    # For Strategy 2, it might be ?
    
    # STRATEGY 1: Simple 'download=1' param replacement
    # Works for modern 1drv.ms/x/c/ links
    if "1drv.ms" in share_link or "onedrive.live.com" in share_link:
        try:
            # Remove existing query params (everything after ?)
            base_link = share_link.split('?')[0]
            
            final_link = f"{base_link}?download=1"
            if cache_bust:
                final_link += f"&t={int(time.time())}"
            return final_link
        except:
            pass

    # STRATEGY 2: Legacy API (u! encoding)
    try:
        encoded = base64.b64encode(share_link.encode()).decode()
        encoded = encoded.rstrip('=').replace('/', '_').replace('+', '-')
        
        final_link = f"https://api.onedrive.com/v1.0/shares/u!{encoded}/root/content"
        if cache_bust:
             final_link += f"?t={int(time.time())}"
        return final_link
    except Exception:
        return None


def download_from_onedrive(share_link, timeout=30, cache_bust=False):
    """Download file dari OneDrive"""
    direct_url = convert_onedrive_link(share_link, cache_bust=cache_bust)
    
    if not direct_url:
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(direct_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return BytesIO(response.content)
    except Exception as e:
        if cache_bust: # Propagate error if this is a manual sync
            raise e
        return None





def load_from_local(file_key):
    """Load file dari lokasi lokal"""
    if file_key not in LOCAL_FILE_NAMES:
        return None
    
    for file_path in LOCAL_FILE_NAMES[file_key]:
        normalized_path = os.path.normpath(file_path)
        
        if os.path.exists(normalized_path):
            try:
                if os.path.getsize(normalized_path) > 0:
                    return normalized_path
            except Exception:
                continue
    
    return None


def check_onedrive_status():
    """Enhanced status check"""
    status = {}
    
    for name, link in ONEDRIVE_LINKS.items():
        if link and link.strip() != "":
            try:
                file_buffer = download_from_onedrive(link, timeout=10)
                if file_buffer:
                    status[name] = "✅ Cloud (Online)"
                    continue
            except:
                pass
        
        status[name] = "❌ Cloud (Error/Offline)"
    
    return status


# ============================================================
# EXCEL SERIAL DATE PARSER
# ============================================================

def parse_excel_date(date_value):
    """
    Parse Excel serial date to Python date
    Excel stores dates as number of days since 1900-01-01
    Example: 45870 = 2025-07-12
    """
    try:
        # If already a date/datetime, return as is
        if isinstance(date_value, (datetime, pd.Timestamp)):
            return pd.Timestamp(date_value).date()
        
        # If string, try to parse
        if isinstance(date_value, str):
            parsed = pd.to_datetime(date_value, errors='coerce')
            if pd.notna(parsed):
                return parsed.date()
            return None
        
        # If number (Excel serial date)
        if isinstance(date_value, (int, float)):
            # Excel epoch starts at 1899-12-30 (not 1900-01-01 due to Excel bug)
            excel_epoch = datetime(1899, 12, 30)
            date_result = excel_epoch + timedelta(days=int(date_value))
            return date_result.date()
        
        return None
        
    except Exception:
        return None


def safe_parse_date_column(date_series):
    """Apply Excel date parsing to entire column"""
    return date_series.apply(parse_excel_date)


def normalize_excavator_name(name):
    """
    Normalize excavator name to format: PC XXX-YY
    Example: 'PC 850 01' -> 'PC 850-01', 'PC850-01' -> 'PC 850-01', 'PC-400-05' -> 'PC 400-05'
    """
    import re
    
    if pd.isna(name) or not isinstance(name, str):
        return name
    
    name = str(name).strip().upper()
    
    # Remove all separators first to get pure digits
    # Handle formats: PC 850 01, PC850-01, PC 850-01, PC85001, PC-850-01, PC-400-05
    clean = re.sub(r'[^A-Z0-9]', '', name)  # Remove all non-alphanumeric
    
    # Match PC followed by exactly 5 digits (3 for model + 2 for number)
    match = re.match(r'^PC(\d{3})(\d{2})$', clean)
    if match:
        return f"PC {match.group(1)}-{match.group(2)}"
    
    # Try original pattern for edge cases
    match = re.match(r'^PC[-\s]*(\d{3})[-\s]*(\d{2})$', name)
    if match:
        return f"PC {match.group(1)}-{match.group(2)}"
    
    return name


def normalize_excavator_column(df):
    """Apply excavator name normalization to dataframe"""
    if 'Excavator' in df.columns:
        df['Excavator'] = df['Excavator'].apply(normalize_excavator_name)
    return df


# ============================================================
# LOAD PRODUKSI - FIXED VERSION
# ============================================================

@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_produksi(start_date=None):
    """Load data produksi - FIXED & ROBUST with Header Scanning"""
    df = None
    debug_log = []


    
    # 0. TRY DATABASE LOAD (Priority)
    try:
        engine = get_db_engine()
        if engine:
            if start_date:
                query = f"SELECT * FROM production_logs WHERE date >= '{start_date}'"
            else:
                query = "SELECT * FROM production_logs WHERE date >= '2026-01-01'"
            # Optional: Add date filter if implemented parameters
            
            df_db = pd.read_sql(query, engine)
            print(f"[DEBUG] DB Load Result: {len(df_db)} rows. Columns: {list(df_db.columns)}")
            if not df_db.empty:
                # Map DB columns to Dashboard/Excel standard
                rename_map = {
                    'date': 'Date',
                    'shift': 'Shift',
                    'time': 'Time',
                    'blok': 'BLOK',
                    'dump_truck': 'Dump Truck',
                    'excavator': 'Excavator',
                    'front': 'Front',
                    'commodity': 'Commodity',
                    'rit': 'Rit',
                    'tonnase': 'Tonnase',
                    'dump_loc': 'Dump Loc'
                }
                df_db = df_db.rename(columns=rename_map)
                
                # Ensure Types
                if 'Date' in df_db.columns:
                    df_db['Date'] = pd.to_datetime(df_db['Date'])
                
                debug_log.append(f"Loaded {len(df_db)} rows from Database.")
                debug_log.append(f"Loaded {len(df_db)} rows from Database.")
                st.session_state['debug_log_produksi'] = debug_log
                
                # Telemetry: Mark as FRESH DB LOAD
                st.session_state['source_produksi'] = f"DATABASE (Fresh Load @ {datetime.now().strftime('%H:%M:%S')})"
                return df_db
    except Exception as e:
        print(f"[DEBUG] ❌ DB LOAD FAILED: {str(e)}")
        debug_log.append(f"DB Load Error: {str(e)}")
        return pd.DataFrame() # Force Stop
        
    # Generic loader
    def load_content(source):

        try:
            xls = pd.ExcelFile(source)
            valid_dfs = []
            
            # STRATEGY: Aggressively find '2026' sheets
            target_sheets = [s for s in xls.sheet_names if '2026' in str(s)]
            
            # Fallback
            if not target_sheets:
                target_sheets = [s for s in xls.sheet_names if s.lower() not in ['menu', 'dashboard', 'summary', 'ref', 'config']]
            
            debug_log.append(f"Target Sheets: {target_sheets}")
            
            for sheet in target_sheets:
                try:
                    # SMART HEADER SCANNING (Enhanced)
                    # 1. Read chunk
                    df_raw = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=100)
                    
                    header_idx = None
                    found_signature = ""
                    
                    # Scan for signature columns (Flexible)
                    for i in range(len(df_raw)):
                        row_str = df_raw.iloc[i].astype(str).str.cat(sep=' ').lower()
                        
                        # Signature 1: Standard (Date + Shift + Front)
                        if 'date' in row_str and 'shift' in row_str and 'front' in row_str:
                            header_idx = i; found_signature = "Standard (Date+Shift+Front)"; break
                        
                        # Signature 2: Alternative (Tanggal + Shift)
                        if 'tanggal' in row_str and 'shift' in row_str:
                             header_idx = i; found_signature = "Indo (Tanggal+Shift)"; break
                             
                        # Signature 3: Minimal (Date + Dump Truck/Unit)
                        if 'date' in row_str and ('dump truck' in row_str or 'unit' in row_str or 'dt' in row_str):
                              header_idx = i; found_signature = "Minimal (Date+Unit)"; break
                              
                    if header_idx is None:
                        # Fallback: Assume Row 0 if 'Date' or 'Tanggal' is there
                        row0 = df_raw.iloc[0].astype(str).str.cat(sep=' ').lower()
                        if 'date' in row0 or 'tanggal' in row0:
                            header_idx = 0; found_signature = "Fallback Row 0"
                        else:
                            debug_log.append(f"Sheet '{sheet}': Header Scan Failed (No signatures found in first 100 rows)")
                            continue

                    debug_log.append(f"Sheet '{sheet}': Header found at Row {header_idx} ({found_signature})")
                    
                    # 2. Read full sheet with correct header
                    temp_df = pd.read_excel(xls, sheet_name=sheet, header=header_idx)
                    
                    # Clean Column Names
                    temp_df.columns = [str(c).strip() for c in temp_df.columns]
                    
                    # Map Critical Columns (Date)
                    col_date = next((c for c in temp_df.columns if 'date' in c.lower() or 'tanggal' in c.lower()), None)
                    if col_date:
                        temp_df = temp_df.rename(columns={col_date: 'Date'})
                    
                    # Map Critical Columns (Shift)
                    col_shift = next((c for c in temp_df.columns if 'shift' in c.lower()), None)
                    if col_shift:
                        temp_df = temp_df.rename(columns={col_shift: 'Shift'})
                        
                    # Standardize Date
                    if 'Date' in temp_df.columns:
                        temp_df['Date'] = safe_parse_date_column(temp_df['Date'])
                        before_len = len(temp_df)
                        temp_df = temp_df.dropna(subset=['Date']) # Keep only valid dates
                        after_len = len(temp_df)
                        
                        debug_log.append(f"Sheet '{sheet}': Parsed {after_len} valid rows (dropped {before_len - after_len})")
                        
                        # Add to list if we have data
                        if not temp_df.empty:
                            valid_dfs.append(temp_df)
                    else:
                        debug_log.append(f"Sheet '{sheet}': 'Date' column not found after mapping. Cols: {list(temp_df.columns)}")
                            
                except Exception as e:
                    debug_log.append(f"Error reading sheet {sheet}: {str(e)}")
                    continue 
            
            if valid_dfs:
                return pd.concat(valid_dfs, ignore_index=True)
            return None
            
        except Exception as e:
            debug_log.append(f"Error opening Excel file: {str(e)}")
            return None

    # 1. FORCE CLOUD SYNC CHECK
    force_sync = st.session_state.get('force_cloud_reload', False)
    
    if force_sync:
        link = ONEDRIVE_LINKS.get("produksi")
        if link:
            try:
                # ENABLE CACHE BUSTING HERE
                debug_log.append(f"Attempting download. Link found: {link[:20]}...")
                
                # Manual trace of conversion
                direct_url = convert_onedrive_link(link, cache_bust=True)
                debug_log.append(f"Converted URL: {direct_url}")
                
                if not direct_url:
                     debug_log.append("Error: convert_onedrive_link returned None")
                
                file_buffer = download_from_onedrive(link, cache_bust=True)
                if file_buffer:
                    df = load_content(file_buffer)
                    if df is not None and not df.empty:
                        st.session_state['last_update_produksi'] = datetime.now().strftime("%H:%M")
                    else:
                        debug_log.append("Sync failed: Content load returned empty dataframe")
                else:
                    debug_log.append("Download failed: No buffer returned (despite URL)")
            except Exception as e:
                debug_log.append(f"Cloud Sync Error Triggered: {str(e)}")
        else:
            debug_log.append("Error: Production Link is EMPTY in settings")
    
    # 2. Try OneDrive (Fallback) - DISABLED FOR DB-ONLY ARCHITECTURE
    # if (df is None or df.empty) and ONEDRIVE_LINKS.get("produksi") and not force_sync:
    #     try:
    #         debug_log.append("Fallback Sync DISABLED: Dashboard is now DB-Only.")
            # file_buffer = download_from_onedrive(ONEDRIVE_LINKS["produksi"], cache_bust=False)
            # if file_buffer:
            #     df = load_content(file_buffer)
            #     if df is not None and not df.empty:
            #        st.session_state['last_update_produksi'] = datetime.now().strftime("%H:%M")
            #     else:
            #         debug_log.append("Fallback Sync: Content load returned empty")
            # else:
            #     debug_log.append("Fallback Sync: Download returned None (Silent Error)")
    #     except Exception as e:
    #          debug_log.append(f"Fallback Sync Error: {str(e)}")
    
    # SAVE DEBUG LOG TO SESSION STATE
    st.session_state['debug_log_produksi'] = debug_log
    
    if df is None or df.empty:
        return pd.DataFrame() # Return empty if all fails
    
    # ---------------------------------------------------------
    # POST-PROCESSING
    # ---------------------------------------------------------
    try:
        # Normalize Shift if exists
        if 'Shift' in df.columns:
            df['Shift'] = df['Shift'].astype(str).str.strip()
            df['Shift'] = df['Shift'].replace({
                '1': 'Shift 1', '2': 'Shift 2', '3': 'Shift 3',
                '1.0': 'Shift 1', '2.0': 'Shift 2', '3.0': 'Shift 3'
            })
        
        # Parse Time
        col_time = next((c for c in df.columns if 'time' in c.lower() or 'jam' in c.lower()), None)
        if col_time:
             df = df.rename(columns={col_time: 'Time'})
             df['Time'] = df['Time'].astype(str).fillna('')
        else:
            df['Time'] = ''
            
        # Standardize other columns (fuzzy match)
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if 'excavator' in cl: col_map[c] = 'Excavator'
            elif 'commodity' in cl or 'commudity' in cl or 'komoditas' in cl: col_map[c] = 'Commodity'
            elif 'unit' in cl or 'dump truck' in cl or 'dt' == cl: col_map[c] = 'Dump Truck'
            elif 'ritase' in cl or 'rit' == cl: col_map[c] = 'Rit'
            elif 'tonnase' in cl or 'tonase' in cl or 'ton' in cl: col_map[c] = 'Tonase'
            elif 'blok' in cl: col_map[c] = 'BLOK'
            elif 'front' in cl: col_map[c] = 'Front'
            elif 'dump' in cl and 'loc' in cl: col_map[c] = 'Dump Loc'
            
        df = df.rename(columns=col_map)
        
        # Numeric conversions
        for col in ['Rit', 'Tonase']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        # Normalize Excavator names
        if 'Excavator' in df.columns:
            df = normalize_excavator_column(df)
            
        return df
        
    except Exception as e:
        debug_log.append(f"Post-processing error: {str(e)}")
        st.session_state['debug_log_produksi'] = debug_log # Update log
        return df


# ============================================================
# OTHER LOAD FUNCTIONS (GANGGUAN, BBM, etc)
# ============================================================

@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_gangguan(bulan):
    """Load data gangguan per bulan (ringkasan)"""
    sheet = f'Monitoring {bulan}'
    df = None
    
    if ONEDRIVE_LINKS.get("gangguan"):
        file_buffer = download_from_onedrive(ONEDRIVE_LINKS["gangguan"])
        if file_buffer:
            try:
                df = pd.read_excel(file_buffer, sheet_name=sheet, skiprows=1)
            except:
                pass
    
    # if df is None:
    #     local_path = load_from_local("gangguan")
    #     if local_path:
    #         try:
    #             df = pd.read_excel(local_path, sheet_name=sheet, skiprows=1)
    #         except:
    #             pass
    
    if df is None:
        return pd.DataFrame()
    
    try:
        if len(df.columns) >= 3:
            df.columns = ['Row Labels', 'Frekuensi', 'Persentase']
        
        df = df[df['Row Labels'] != 'Row Labels']
        df = df[df['Row Labels'] != 'Grand Total']
        df['Frekuensi'] = pd.to_numeric(df['Frekuensi'], errors='coerce')
        df = df.dropna(subset=['Frekuensi'])
        df = df[df['Frekuensi'] > 0]
        df = df.reset_index(drop=True)
        
        return df
    except:
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_gangguan_all(start_date=None):
    """
    Load data gangguan lengkap (DEBUG MODE).
    Prioritizes 2026 data sheets (e.g., 'Monitoring Jan 2026').
    """
    file_path = None
    file_buffer = None
    debug_log = []
    
    # 0. TRY DATABASE LOAD (Priority)
    try:
        engine = get_db_engine()
        if engine:
            if start_date:
                query = f"SELECT * FROM downtime_logs WHERE tanggal >= '{start_date}'"
            else:
                query = "SELECT * FROM downtime_logs WHERE tanggal >= '2026-01-01'"
            
            df_db = pd.read_sql(query, engine)
            
            if not df_db.empty:
                rename_map = {
                    'tanggal': 'Tanggal',
                    'shift': 'Shift',
                    'start': 'Start',
                    'end': 'End',
                    'durasi': 'Durasi',
                    'crusher': 'Crusher',
                    'alat': 'Alat',
                    'remarks': 'Remarks',
                    'kelompok_masalah': 'Kelompok Masalah',
                    'gangguan': 'Gangguan',
                    'info_ccr': 'Info CCR',
                    'sub_komponen': 'Sub Komponen',
                    'keterangan': 'Keterangan',
                    'penyebab': 'Penyebab',
                    'identifikasi_masalah': 'Identifikasi Masalah',
                    'action': 'Action',
                    'plan': 'Plan',
                    'pic': 'PIC',
                    'status': 'Status',
                    'due_date': 'Due Date',
                    'spare_part': 'Spare Part',
                    'info_spare_part': 'Info Spare Part',
                    'link_lampiran': 'Link/Lampiran',
                    'extra': 'Extra'
                }
                df_db = df_db.rename(columns=rename_map)
                
                if 'Tanggal' in df_db.columns:
                     df_db['Tanggal'] = pd.to_datetime(df_db['Tanggal'])
                     
                     # 1. Add Bulan (Name - Indonesian)
                     MONTH_IND = {
                         1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
                         7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
                     }
                     df_db['Bulan'] = df_db['Tanggal'].dt.month.map(MONTH_IND)
                     # 2. Add Tahun
                     df_db['Tahun'] = df_db['Tanggal'].dt.year
                     # 3. Add Week
                     df_db['Week'] = df_db['Tanggal'].dt.isocalendar().week
                
                debug_log.append(f"Loaded {len(df_db)} rows from Database (Downtime).")
                st.session_state['debug_log_gangguan'] = debug_log
                return df_db
    except Exception as e:
        debug_log.append(f"DB Load Error: {str(e)}")

    # 0. Check Force Sync
    force_sync = st.session_state.get('force_cloud_reload', False)
    
    if force_sync:

        # Force reload config to ensure latest link
        import importlib
        import config.settings
        importlib.reload(config.settings)
        # Use different name to avoid UnboundLocalError shadowing global ONEDRIVE_LINKS
        from config.settings import ONEDRIVE_LINKS as RELOADED_LINKS
        
        link = RELOADED_LINKS.get("gangguan")
        if link:
            try:
                # Log FULL link for verification
                debug_log.append(f"🔗 Link Used: {link}")
                
                debug_log.append(f"Attempting download (Gangguan)...")
                direct_url = convert_onedrive_link(link, cache_bust=True)
                debug_log.append(f"Converted URL: {direct_url[:50]}...")
                
                file_buffer = download_from_onedrive(link, cache_bust=True)
                if file_buffer:
                     st.session_state['last_update_gangguan'] = datetime.now().strftime("%H:%M")
                else:
                     debug_log.append("Gangguan Sync failed: No buffer returned")
            except Exception as e:
                debug_log.append(f"Gangguan Sync Error: {str(e)}")
    
    # 1. Try OneDrive (Fallback) - DISABLED FOR DB-ONLY ARCHITECTURE
    # if file_path is None and file_buffer is None and ONEDRIVE_LINKS.get("gangguan") and not force_sync:
    #     try:
    #         debug_log.append("Fallback Sync DISABLED: Dashboard is now DB-Only.")
            # file_buffer = download_from_onedrive(ONEDRIVE_LINKS["gangguan"])
            # if file_buffer:
            #      st.session_state['last_update_gangguan'] = datetime.now().strftime("%H:%M")
    #     except Exception as e:
    #         debug_log.append(f"Gangguan Fallback Error: {str(e)}")
            
    # Save log
    st.session_state['debug_log_gangguan'] = debug_log
    
    if file_path is None and file_buffer is None:
        return pd.DataFrame()
    
    try:
        if file_path:
            xls = pd.ExcelFile(file_path)
        else:
            xls = pd.ExcelFile(file_buffer)
            
        sheet_names = xls.sheet_names
        
        # 0. STRICT PRIORITY: 'All' sheet
        # User explicitly requested to focus on 'All'
        target_sheets = []
        if 'All' in sheet_names:
            target_sheets = ['All']
            debug_log.append("Gangguan Sync: Priority 'All' sheet selected.")
            
            # --- PASSIVE CHECK: WARN IF STALE ---
            try:
                mon_sheets = [s for s in sheet_names if 'monitoring' in str(s).lower()]
                for ms in mon_sheets[:2]: # Check top 2 monitoring sheets
                    if file_path: df_mon = pd.read_excel(file_path, sheet_name=ms)
                    else: df_mon = pd.read_excel(file_buffer, sheet_name=ms)
                    
                    if 'Tanggal' in df_mon.columns:
                        dates = pd.to_datetime(df_mon['Tanggal'], errors='coerce')
                        if not dates.empty:
                            mon_max = dates.max()
                            debug_log.append(f"🔎 Check '{ms}': Max Date {mon_max}")
            except: pass
            # ------------------------------------
            
        else:
            # Fallback only if 'All' is missing
            # Fallback only if 'All' is missing
            debug_log.append("Gangguan Sync: 'All' sheet not found. Searching for Monitoring 2026...")
            mon_sheets = [s for s in sheet_names if 'monitoring' in str(s).lower()]
            mon_sheets.sort(reverse=True)
            if mon_sheets:
                target_sheets = [mon_sheets[0]]
            elif len(sheet_names) > 0:
                target_sheets = [sheet_names[0]]
                
        if not target_sheets:
            debug_log.append(f"Gangguan Sync: No valid sheets found. Available: {sheet_names}")
            st.session_state['debug_log_gangguan'] = debug_log
            return pd.DataFrame()
            
        debug_log.append(f"Gangguan Sync: Final Selection -> {target_sheets}")
        
        all_dfs = []
        standard_cols = ['Tanggal', 'Bulan', 'Tahun', 'Week', 'Shift', 'Start', 'End', 
                        'Durasi', 'Crusher', 'Alat', 'Remarks', 'Kelompok Masalah', 'Gangguan', 
                        'Info CCR', 'Sub Komponen', 'Keterangan', 'Penyebab', 
                        'Identifikasi Masalah', 'Action', 'Plan', 'PIC', 'Status', 'Due Date',
                        'Spare Part', 'Info Spare Part', 'Link/Lampiran', 'Extra']

        for sheet in target_sheets:
            try:
                # Read sheet - Assume Row 0 is header
                if file_path:
                    df_sheet = pd.read_excel(file_path, sheet_name=sheet)
                else:
                    df_sheet = pd.read_excel(file_buffer, sheet_name=sheet)
                
                if df_sheet.empty:
                    debug_log.append(f"Sheet '{sheet}' is empty. Skipping.")
                    continue
                
                # Log raw validation
                debug_log.append(f"Sheet '{sheet}': Read {len(df_sheet)} rows.")
                if 'Tanggal' in df_sheet.columns:
                     try:
                         # Quick check max date without modifying df yet
                         dates = pd.to_datetime(df_sheet['Tanggal'], errors='coerce')
                         debug_log.append(f"Sheet '{sheet}': Date Range {dates.min()} - {dates.max()}")
                     except: 
                         debug_log.append(f"Sheet '{sheet}': Could not parse dates for logging")

                # Normalize columns
                df_sheet.columns = [str(c).strip() for c in df_sheet.columns]
                
                # Check critical column 'Tanggal'
                if 'Tanggal' not in df_sheet.columns:
                     # Maybe case sensitivity issue?
                     col_map = {c.lower(): c for c in df_sheet.columns}
                     if 'tanggal' in col_map:
                         df_sheet = df_sheet.rename(columns={col_map['tanggal']: 'Tanggal'})
                     else:
                         continue # Skip this sheet if no Tanggal
                
                # Ensure Crusher column exists
                if 'Crusher' not in df_sheet.columns:
                    df_sheet['Crusher'] = None

                # Keep only relevant columns if they exist (to avoid excessive junk), 
                # but also allow dynamic columns? 
                # Better to align with standard_cols for the app views
                # We simply ensure standard cols exist, but keep others? 
                # Safer: Only keep standard cols to avoid issues with concat if they differ
                # Actually, adding missing standard cols is enough
                for col in standard_cols:
                    if col not in df_sheet.columns:
                        df_sheet[col] = None
                        
                # Reorder to standard (optional but good for debugging)
                current_cols = [c for c in standard_cols if c in df_sheet.columns]
                df_sheet = df_sheet[current_cols]
                        
                all_dfs.append(df_sheet)
                
            except Exception as e:
                # print(f"Error reading sheet {sheet}: {e}")
                continue
        
        if not all_dfs:
            return pd.DataFrame()
            
        df = pd.concat(all_dfs, ignore_index=True)
        
        # --- Post-Processing ---
        # Filter out potential repeats
        df = df[df['Bulan'] != 'Bulan'].copy()
        
        # Numeric conversions
        for col in ['Bulan', 'Shift', 'Durasi', 'Tahun', 'Week']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Date parsing
        # FIX: Use safe_parse_date_column to handle Excel serial numbers (45659 -> 2026)
        if 'Tanggal' in df.columns:
            df['Tanggal'] = safe_parse_date_column(df['Tanggal'])
            # CRITICAL: Convert to datetime64 to support .dt accessor and dashboard filtering
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        
        # Filter valid rows
        df = df[df['Bulan'].notna()]
        df = df[df['Durasi'].notna()]
        # Remove NaT dates 
        df = df[df['Tanggal'].notna()]
        
        # Enforce Start Date >= 2026-01-01 (Strict User Request)
        df = df[df['Tanggal'] >= pd.Timestamp('2026-01-01')]
        
        # FIX: Format Start/End Time to String (HH:MM) to avoid 1900-01-01 display
        def format_time_col(val):
            if pd.isna(val): return ""
            s_val = str(val)
            # If default datetime str "1900-01-01 04:30:00" -> extract "04:30"
            if " " in s_val:
                try:
                    return s_val.split(" ")[1][:5]
                except:
                    pass
            # If just a time "04:30:00" -> "04:30"
            if ":" in s_val and len(s_val) >= 5:
                return s_val[:5]
            return s_val

        if 'Start' in df.columns:
            df['Start'] = df['Start'].apply(format_time_col)
        if 'End' in df.columns:
            df['End'] = df['End'].apply(format_time_col)

        # -------------------------------------------------------------
        # CRITICAL FIX: HANDLE SHIFTED COLUMNS FOR 2026 (Missing Header)
        # -------------------------------------------------------------
        # Symptoms: 'Alat' contains Crusher names (LSC, MS), 'Remarks' contains Alat, etc.
        # This happens because 'Crusher' column is physically present in 2026 rows but missing in Header.
        
        # Check if shift is needed: Look for signatures in 'Alat'
        # Safely convert to string
        if 'Alat' in df.columns:
            mask_shifted = df['Alat'].astype(str).str.contains(r'LSC|MS |Batu', case=False, na=False) | (df['Tahun'] == 2026)
            
            if mask_shifted.any():
                # Define shift map: New_Column <- Current_Column
                # Based on Excel debug: Durasi -> [Crusher] -> Alat -> Remarks -> Kelompok...
                shift_map = [
                    ('Crusher', 'Alat'),
                    ('Alat', 'Remarks'),
                    ('Remarks', 'Kelompok Masalah'),
                    ('Kelompok Masalah', 'Gangguan'),
                    ('Gangguan', 'Info CCR'),
                    ('Info CCR', 'Sub Komponen'),
                    ('Sub Komponen', 'Keterangan'),
                    ('Keterangan', 'Penyebab'),
                    ('Penyebab', 'Identifikasi Masalah'),
                    ('Identifikasi Masalah', 'Action'),
                    ('Action', 'Plan'),
                    ('Plan', 'PIC'),
                    ('PIC', 'Status'),
                    ('Status', 'Due Date'),
                    ('Due Date', 'Spare Part'),
                    ('Spare Part', 'Info Spare Part'),
                    ('Info Spare Part', 'Link/Lampiran')
                ]
                
                # Apply shift ONLY to affected rows
                for new_col, old_col in shift_map:
                    if old_col in df.columns:
                        if new_col not in df.columns: df[new_col] = None
                        df.loc[mask_shifted, new_col] = df.loc[mask_shifted, old_col]

        # Standardize Kelompok Masalah
        kelompok_map = {
            'Delay Operational CC': 'Delay Operational CC',
            'Delay operational CC': 'Delay Operational CC',
            'delay Operational CC': 'Delay Operational CC',
            'Delay Operational DBLH': 'Delay Operational DBLH',
            'Downtime Belt Conveyor': 'Downtime Belt Conveyor',
            'Downtime belt conveyor': 'Downtime Belt Conveyor',
            'Downtime Crusher': 'Downtime Crusher',
            'downtime crusher': 'Downtime Crusher',
        }
        if 'Kelompok Masalah' in df.columns:
            df['Kelompok Masalah'] = df['Kelompok Masalah'].replace(kelompok_map)
            df = df[df['Kelompok Masalah'].notna()]
        
        # Map Bulan Names
        bulan_names = {
            1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
            5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
            9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
        }
        df['Bulan_Name'] = df['Bulan'].map(bulan_names)
        
        df = df.reset_index(drop=True)
        return df

    except Exception as e:
        print(f"Error loading gangguan: {e}")
        return pd.DataFrame()
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def get_gangguan_summary(df):
    """
    Generate summary statistics dari data gangguan
    Returns: dict dengan KPI metrics
    """
    if df.empty:
        return {
            'total_incidents': 0,
            'total_downtime': 0,
            'mttr': 0,
            'total_alat': 0,
            'top_gangguan': '-',
            'top_alat': '-'
        }
    
    return {
        'total_incidents': len(df),
        'total_downtime': df['Durasi'].sum(),
        'mttr': df['Durasi'].mean(),
        'total_alat': df['Alat'].nunique(),
        'top_gangguan': df['Gangguan'].value_counts().index[0] if len(df) > 0 else '-',
        'top_alat': df['Alat'].value_counts().index[0] if len(df) > 0 else '-'
    }





@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_ritase_enhanced():
    """
    Load and transform Ritase data to Long Format [Date, Shift, Location, Ritase]
    (DEBUG MODE ENABLED)
    """
    df = None
    sheet_name = 'Ritase'
    debug_log = []
    
    # 0. TRY DATABASE LOAD
    try:
        engine = get_db_engine()
        if engine:
            query = "SELECT * FROM ritase_logs"
            df_db = pd.read_sql(query, engine)
            if not df_db.empty:
                rename_map = {
                    'tanggal': 'Tanggal',
                    'shift': 'Shift',
                    'location': 'Location',
                    'ritase': 'Ritase'
                }
                df_db = df_db.rename(columns=rename_map)
                if 'Tanggal' in df_db.columns:
                     df_db['Tanggal'] = pd.to_datetime(df_db['Tanggal'])
                return df_db
    except Exception as e:
        debug_log.append(f"DB Load Error: {str(e)}")

    # 0. Check Force Sync
    force_sync = st.session_state.get('force_cloud_reload', False)
    
    if force_sync:
        link = ONEDRIVE_LINKS.get("monitoring")
        if link:
            try:
                debug_log.append(f"Attempting download (Ritase). Link: {link[:20]}...")
                direct_url = convert_onedrive_link(link, cache_bust=True)
                debug_log.append(f"Converted URL (Ritase): {direct_url}")
                
                file_buffer = download_from_onedrive(link, cache_bust=True)
                if file_buffer:
                    st.session_state['last_update_ritase'] = datetime.now().strftime("%H:%M")
                    try:
                        df = pd.read_excel(file_buffer, sheet_name=sheet_name)
                    except Exception as e:
                        debug_log.append(f"Ritase Excel Read Error: {str(e)}")
                else:
                    debug_log.append("Ritase Sync failed: No buffer returned")
            except Exception as e:
                debug_log.append(f"Ritase Cloud Sync Error: {str(e)}")

    # 1. Standard Cloud Load (Cloud Only) - DISABLED FOR DB-ONLY ARCHITECTURE
    # if (df is None or df.empty) and ONEDRIVE_LINKS.get("monitoring") and not force_sync:
    #     try:
    #         debug_log.append("Fallback Sync DISABLED: Dashboard is now DB-Only.")
            # file_buffer = download_from_onedrive(ONEDRIVE_LINKS["monitoring"])
            # if file_buffer:
            #     st.session_state['last_update_ritase'] = datetime.now().strftime("%H:%M")
            #     try:
            #         df = pd.read_excel(file_buffer, sheet_name=sheet_name)
            #     except: pass
    #     except Exception as e:
    #         debug_log.append(f"Ritase Fallback Error: {str(e)}")
            
    # Save log
    st.session_state['debug_log_ritase'] = debug_log
            
    if df is None or df.empty:
        return pd.DataFrame()
        
    try:
        # Standardize Date
        if 'Tanggal' not in df.columns:
             # Try finding date column by type
             for col in df.columns:
                 if pd.api.types.is_datetime64_any_dtype(df[col]):
                     df = df.rename(columns={col: 'Tanggal'})
                     break
                     
        if 'Tanggal' in df.columns:
            df['Tanggal'] = safe_parse_date_column(df['Tanggal'])
            df = df[df['Tanggal'].notna()]
        else:
             return pd.DataFrame() # Parsing failed
        
        # Clean Shift
        if 'Shift' in df.columns:
            df = df[df['Shift'].isin([1, 2, 3, '1', '2', '3'])]
            df['Shift'] = pd.to_numeric(df['Shift'], errors='coerce').astype('Int64')
        else:
            df['Shift'] = 1 # Default if missing
            
        # Identify Location columns (Fronts, Stockpiles, etc.)
        # Exclude metadata columns and 'Unnamed' junk
        exclude_cols = ['Tanggal', 'Shift', 'Pengawasan', 'Total', 'No', 'Day', 'Date']
        
        # Filter columns that are NOT metadata AND NOT Unnamed
        loc_cols = [c for c in df.columns if c not in exclude_cols and not str(c).startswith('Unnamed') and 'Total' not in str(c)]
        
        if not loc_cols:
            return pd.DataFrame()
            
        # Melt to Long Format
        df_melted = df.melt(id_vars=['Tanggal', 'Shift'], 
                           value_vars=loc_cols,
                           var_name='Location', value_name='Ritase')
        
        # Filter valid data
        df_melted['Ritase'] = pd.to_numeric(df_melted['Ritase'], errors='coerce').fillna(0)
        df_melted = df_melted[df_melted['Ritase'] > 0]
        
        # Clean Location Names (remove 'Sum of' if present)
        df_melted['Location'] = df_melted['Location'].astype(str).str.replace('Sum of ', '', regex=False)
        
        return df_melted[['Tanggal', 'Shift', 'Location', 'Ritase']].reset_index(drop=True)
        
    except Exception as e:
        print(f"Error loading Ritase enhanced: {e}")
        return pd.DataFrame()


# ==========================================
# BACKWARD COMPATIBILITY ALIASES
# ==========================================
# These functions are kept to prevent ImportErrors in other modules
# that might still reference the old names.
load_ritase = load_ritase_enhanced
load_gangguan_enhanced = load_gangguan_all

@st.cache_data(ttl=CACHE_TTL)
def load_gangguan():
    """Legacy wrapper for load_gangguan_all or load_gangguan_monitoring"""
    return load_gangguan_monitoring() # Basic fallback

@st.cache_data(ttl=CACHE_TTL)
def load_analisa_produksi(bulan='Januari'):
    """Legacy wrapper for backward compatibility"""
    # Load all data first
    df_all = load_analisa_produksi_all()
    if df_all.empty:
        return pd.DataFrame()
        
    # Filter by month name
    # Ensure bulan matches the new format or map it if necessary
    # The new function returns 'Month' column with full names (Januari, Februari, etc.)
    if 'Month' in df_all.columns:
        return df_all[df_all['Month'] == bulan]
    
    return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL)
def load_analisa_produksi_all():
    """Load Analisa Produksi for S-Curve (Plan vs Actual)"""
    df = None
    # LEGACY FUNCTION DISABLED
    return pd.DataFrame()
    # sheet_name = 'Analisa Produksi'
    
    # # 0. Check Force Sync
    # force_sync = st.session_state.get('force_cloud_reload', False)
    
    # if force_sync and ONEDRIVE_LINKS.get("monitoring"):
    #     file_buffer = download_from_onedrive(ONEDRIVE_LINKS["monitoring"], cache_bust=True)
    #     if file_buffer:
    #         try:
    #             df = pd.read_excel(file_buffer, sheet_name=sheet_name)
    #         except: pass

    # # 1. Standard Cloud Load (Cloud Only)
    # if (df is None or df.empty) and ONEDRIVE_LINKS.get("monitoring"):
    #     file_buffer = download_from_onedrive(ONEDRIVE_LINKS["monitoring"])
    #     if file_buffer:
    #         try:
    #             df = pd.read_excel(file_buffer, sheet_name=sheet_name)
    #         except: pass
            
    # if df is None or df.empty:
    #     return pd.DataFrame()
    
    # try:
    #     # The sheet has multiple months horizontally.
    #     # Structure: [Januari] [Februari] side by side
    #     # Need to iterate and extract
        
    #     processed_data = []
    #     months = {'Januari': 0, 'Februari': 5, 'Maret': 10, 'April': 15, 'Mei': 20, 'Juni': 25, 
    #               'Juli': 30, 'Agustus': 35, 'September': 40, 'Oktober': 45, 'November': 50, 'Desember': 55}
                  
    #     for month_name, start_col in months.items():
    #         try:
    #             if start_col + 3 >= len(df.columns):
    #                 continue
                    
    #             # Extract block
    #             df_month = df.iloc[1:33, start_col:start_col+4].copy() # Assuming 31 days max + 1 header
    #             df_month.columns = ['Day', 'Plan', 'Actual', 'Ach']
                
    #             # Clean
    #             df_month = df_month.dropna(subset=['Day'])
    #             df_month = df_month[pd.to_numeric(df_month['Day'], errors='coerce').notna()]
                
    #             # Add Metadata
    #             df_month['Month'] = month_name
                
    #             # Convert numbers
    #             df_month['Plan'] = pd.to_numeric(df_month['Plan'], errors='coerce').fillna(0)
    #             df_month['Actual'] = pd.to_numeric(df_month['Actual'], errors='coerce').fillna(0)
                
    #             # Create Date (Assuming Year 2025)
    #             # Need mapping for month number
    #             month_num = list(months.keys()).index(month_name) + 1
    #             dates = []
    #             for day in df_month['Day']:
    #                 try:
    #                     dates.append(pd.Timestamp(year=2025, month=month_num, day=int(day)))
    #                 except:
    #                     dates.append(pd.NaT)
    #             df_month['Date'] = dates
    #             df_month = df_month.dropna(subset=['Date'])
                
    #             processed_data.append(df_month[['Date', 'Month', 'Plan', 'Actual']])
                
    #         except Exception as e:
    #             continue
                
    #     if not processed_data:
    #         return pd.DataFrame()
            
    #     return pd.concat(processed_data, ignore_index=True)
        
    # except Exception as e:
    #     print(f"Error loading Analisa Produksi: {e}")
    #     return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL)
def load_ritase():
    """Load data ritase"""
    # LEGACY FUNCTION DISABLED
    return pd.DataFrame()
    # df = None
    # if ONEDRIVE_LINKS.get("monitoring"):
    #     file_buffer = download_from_onedrive(ONEDRIVE_LINKS["monitoring"])
    #     if file_buffer:
    #         try:
    #             df = pd.read_excel(file_buffer, sheet_name='Ritase')
    #         except:
    #             pass
    
    # if df is None:
    #     return pd.DataFrame()
    
    # try:
    #     cols_keep = ['Tanggal', 'Shift', 'Pengawasan', 'Front B LS', 'Front B Clay', 
    #                 'Front B LS MIX', 'Front C LS', 'Front C LS MIX', 'PLB LS', 
    #                 'PLB SS', 'PLT SS', 'PLT MIX', 'Timbunan', 'Stockpile 6  SS', 
    #                 'PLT LS MIX', 'Stockpile 6 ']
        
    #     available_cols = [col for col in cols_keep if col in df.columns]
    #     df = df[available_cols].copy()
        
    #     df['Tanggal'] = safe_parse_date_column(df['Tanggal'])
    #     df = df[df['Tanggal'].notna()]
        
    #     df = df[df['Shift'].isin([1, 2, 3, '1', '2', '3'])]
    #     df['Shift'] = df['Shift'].astype(str)
        
    #     numeric_cols = [col for col in df.columns if col not in ['Tanggal', 'Shift', 'Pengawasan']]
    #     for col in numeric_cols:
    #         df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
    #     df = df.reset_index(drop=True)
    #     return df
    # except:
    #     return pd.DataFrame()


# @st.cache_data(ttl=CACHE_TTL)
def load_daily_plan():
    """
    Load data daily plan scheduling (Redirects to DB Loader)
    """
    # 0. TRY DATABASE LOAD
    try:
        engine = get_db_engine()
        if engine:
            query = "SELECT * FROM daily_plan_logs"
            df_db = pd.read_sql(query, engine)
            if not df_db.empty:
                # DB has lowercase snake_case headers
                # App expects Title Case or exact headers from Excel
                # Map back:
                rename_map = {
                    'tanggal': 'Tanggal',
                    'shift': 'Shift',
                    'batu_kapur': 'Batu Kapur',
                    'silika': 'Silika',
                    'clay': 'Clay',
                    'timbunan': 'Timbunan',
                    'alat_muat': 'Alat Muat',
                    'alat_angkut': 'Alat Angkut',
                    'blok': 'Blok',
                    'grid': 'Grid',
                    'rom': 'ROM',
                    'keterangan': 'Keterangan'
                }
                df_db = df_db.rename(columns=rename_map)
                if 'Tanggal' in df_db.columns:
                     df_db['Tanggal'] = pd.to_datetime(df_db['Tanggal'])
                return df_db
    except Exception as e:
        debug_log.append(f"DB Load Error: {str(e)}")

    if df is None:
        return pd.DataFrame()
    
    try:
        new_cols = ['No', 'Hari', 'Tanggal', 'Shift', 'Batu Kapur', 'Silika', 
                    'Clay', 'Alat Muat', 'Alat Angkut', 'Blok', 'Grid', 'ROM', 'Keterangan']
        
        if len(df.columns) >= len(new_cols):
            df.columns = new_cols + list(df.columns[len(new_cols):])
        
        df = df.iloc[1:].copy()
        df['Tanggal'] = safe_parse_date_column(df['Tanggal'])
        
        df = df[df['Hari'].notna()]
        df = df[df['Hari'] != 'Hari']
        
        cols_keep = ['Hari', 'Tanggal', 'Shift', 'Batu Kapur', 'Silika', 'Clay', 
                     'Alat Muat', 'Alat Angkut', 'Blok', 'Grid', 'ROM', 'Keterangan']
        available = [c for c in cols_keep if c in df.columns]
        df = df[available].copy()
        
        df = df.dropna(how='all')
        df = df.reset_index(drop=True)
        
        return df
    except:
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL)
def load_realisasi():
    """Load data realisasi"""
    #                  'Timbunan', 'Alat Bor', 'Alat Muat', 'Alat Angkut', 'Blok', 
    #                  'Grid', 'ROM', 'Keterangan']
    #     available = [c for c in cols_keep if c in df.columns]
    #     df = df[available].copy()
        
    #     df = df.dropna(how='all')
    #     df = df.reset_index(drop=True)
        
    #     return df
    # except:
    #     return pd.DataFrame()




@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_daily_plan_data():
    """
    Load Daily Plan data from Database
    """
    try:
        engine = get_db_engine() # Ensure engine is available
        # Sort by ID ASC (Since we reversed input, ID 1 is the Latest Data)
        query = "SELECT * FROM daily_plan_logs WHERE tanggal >= '2026-01-01' ORDER BY id ASC"
        df = pd.read_sql(query, engine)
        
        if df.empty:
            return pd.DataFrame()
            
        # Rename for View Compatibility
        rename_map = {
            'tanggal': 'Tanggal', 'hari': 'Hari',
            'batu_kapur': 'Batu Kapur', 'silika': 'Silika', 'clay': 'Clay', 
            # 'timbunan': 'Timbunan', # Removed
            'alat_muat': 'Alat Muat', 'alat_angkut': 'Alat Angkut', 
            'blok': 'Blok', 'grid': 'Grid', 'rom': 'ROM', 'keterangan': 'Keterangan'
        }
        df = df.rename(columns=rename_map)
        
        # Ensure Date
        if 'Tanggal' in df.columns:
            df['Tanggal'] = pd.to_datetime(df['Tanggal'])
        
        # Reorder columns: Hari first - Include ID for sorting
        cols = [c for c in ['id', 'Hari', 'Tanggal', 'Shift', 'Batu Kapur', 'Silika', 'Clay', 'Alat Muat', 'Alat Angkut', 'Blok', 'Grid', 'ROM', 'Keterangan'] if c in df.columns]
        df = df[cols]
        
        return df
    except Exception as e:
        print(f"Error loading Daily Plan from DB: {e}")
        return pd.DataFrame()
    






# REFACTOR: Duplicate load_ritase_enhanced removed. 
# The correct version with DB logic is defined above at line 1066.



@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_ritase_by_front():
    """
    Load ritase aggregated by front/location.
    OPTIMIZED: Uses load_produksi (DB) instead of downloading raw Ritase sheet.
    """
    try:
        df_prod = load_produksi()
        if df_prod.empty:
             return pd.DataFrame()
             
        # Aggregate Rit by Front
        if 'Front' in df_prod.columns and 'Rit' in df_prod.columns:
            # Clean Front name
            df_prod['Front'] = df_prod['Front'].astype(str).str.strip()
            
            # Group
            totals = df_prod.groupby('Front')['Rit'].sum().reset_index()
            totals.columns = ['Front', 'Total_Ritase']
            totals = totals[totals['Total_Ritase'] > 0]
            totals = totals.sort_values('Total_Ritase', ascending=False)
            return totals
            
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL)
def load_tonase():
    """Load data tonase per jam"""
    # LEGACY FUNCTION DISABLED
    return pd.DataFrame()
    # df = None
    
    # if ONEDRIVE_LINKS.get("monitoring"):
    #     file_buffer = download_from_onedrive(ONEDRIVE_LINKS["monitoring"])
    #     if file_buffer:
    #         try:
    #             df = pd.read_excel(file_buffer, sheet_name='Tonase', header=1)
    #         except:
    #             pass
    
    # # if df is None:
    # #     local_path = load_from_local("monitoring")
    # #     if local_path:
    # #         try:
    # #             df = pd.read_excel(local_path, sheet_name='Tonase', header=1)
    # #         except:
    # #             pass
    
    # if df is None:
    #     return pd.DataFrame()
    
    # try:
    #     # Safety: Rename first column to Tanggal
    #     if len(df.columns) > 0:
    #          df = df.rename(columns={df.columns[0]: 'Tanggal', df.columns[1]: 'Ritase'})

    #     # Filter repeated headers (Fix DateParseError)
    #     # Filter repeated headers (Fix DateParseError)
    #     if 'Tanggal' in df.columns:
    #         df = df[df['Tanggal'].astype(str).str.strip() != 'Tanggal']
            
    #         # Handle Excel Serial Dates
    #         # Force numeric first
    #         df['Tanggal_Num'] = pd.to_numeric(df['Tanggal'], errors='coerce')
            
    #         # If successful (not all NaNs), use it
    #         if df['Tanggal_Num'].notna().any():
    #             df['Tanggal'] = pd.to_datetime(df['Tanggal_Num'], unit='D', origin='1899-12-30')
    #         else:
    #             df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
                
    #         df = df[df['Tanggal'].notna()]
        
    #     hour_cols = [col for col in df.columns if '-' in str(col) and col not in ['Tanggal', 'Ritase']]
    #     for col in hour_cols:
    #         df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
    #     if 'Total' in df.columns:
    #         df['Total'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
        
    #     if 'Tanggal' in df.columns:
    #         df['Bulan'] = df['Tanggal'].dt.month
            
    #     df = df.reset_index(drop=True)
    #     return df
    # except:
    #     return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL)
def load_tonase_hourly():
    """Load tonase in hourly format (melted)"""
    df = load_tonase()
    if df.empty:
        return pd.DataFrame()
    
    try:
        hour_cols = [col for col in df.columns if '-' in str(col) and col not in ['Tanggal', 'Ritase', 'Total']]
        if not hour_cols:
            return pd.DataFrame()
        
        df_melted = df.melt(
            id_vars=['Tanggal', 'Bulan'],
            value_vars=hour_cols,
            var_name='Jam',
            value_name='Tonase'
        )
        df_melted['Tonase'] = pd.to_numeric(df_melted['Tonase'], errors='coerce').fillna(0)
        return df_melted
    except:
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_analisa_produksi_all():
    """Load Target/Plan data from Database (migrated from Analisa Produksi)"""
    try:
        engine = get_db_engine()
        if engine:
            query = "SELECT * FROM target_logs ORDER BY date ASC"
            df_db = pd.read_sql(query, engine)
            if not df_db.empty:
                rename_map = {'date': 'Date', 'plan': 'Plan'}
                df_db = df_db.rename(columns=rename_map)
                if 'Date' in df_db.columns: df_db['Date'] = pd.to_datetime(df_db['Date'])
                st.session_state['last_update_targets'] = "Database"
                return df_db
    except Exception as e:
        print(f"Target DB Error: {e}")
        
    # FORCE STOP if DB missing - DO NOT fall back to Excel Download for Speed
    return pd.DataFrame()



@st.cache_data(ttl=CACHE_TTL)
def load_pengiriman():
    """Load data tonase pengiriman LS & SS"""
    df = None
    
    if ONEDRIVE_LINKS.get("monitoring"):
        file_buffer = download_from_onedrive(ONEDRIVE_LINKS["monitoring"])
        if file_buffer:
            try:
                df = pd.read_excel(file_buffer, sheet_name='TONASE Pengiriman ')
            except:
                pass
    
    # if df is None:
    #     local_path = load_from_local("monitoring")
    #     if local_path:
    #         try:
    #             df = pd.read_excel(local_path, sheet_name='TONASE Pengiriman ')
    #         except:
    #             pass
    
    if df is None:
        return pd.DataFrame()
    
    try:
        all_data = []
        bulan_sections = {
            'Juni': (1, 7), 'Juli': (8, 16), 'Agustus': (21, 29),
            'September': (30, 38), 'Oktober': (39, 47), 
            'November': (48, 56), 'Desember': (57, 64)
        }
        
        for bulan, (start, end) in bulan_sections.items():
            try:
                section = df.iloc[2:, start:end].copy()
                if section.shape[1] >= 6:
                    section.columns = ['Tanggal', 'Shift', 'AP_LS', 'AP_LS_MK3', 'AP_SS', 'Total_LS'][:section.shape[1]]
                    section['Bulan'] = bulan
                    section = section[section['Tanggal'].notna()]
                    all_data.append(section)
            except:
                continue
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            for col in ['Shift', 'AP_LS', 'AP_LS_MK3', 'AP_SS', 'Total_LS']:
                if col in result.columns:
                    result[col] = pd.to_numeric(result[col], errors='coerce').fillna(0)
            return result
        return pd.DataFrame()
    except:
        return pd.DataFrame()


def parse_durasi_value(value):
    """
    Parse Durasi column - handle various formats safely.
    Durasi can be: numeric hours, timedelta, datetime, or time string.
    Returns hours as float, capped at reasonable max (24 hours).
    """
    MAX_DURASI_HOURS = 24  # Maximum reasonable downtime per incident
    
    if pd.isna(value):
        return 0.0
    
    try:
        # If already numeric (float/int)
        if isinstance(value, (int, float)):
            hours = float(value)
            # Check if it looks like an Excel serial time (0-1 range = fraction of day)
            if 0 < hours < 1:
                hours = hours * 24  # Convert fraction of day to hours
            # Cap at max reasonable value
            return min(abs(hours), MAX_DURASI_HOURS)
        
        # If it's a timedelta
        if isinstance(value, pd.Timedelta):
            hours = value.total_seconds() / 3600
            return min(abs(hours), MAX_DURASI_HOURS)
        
        # If it's a datetime/time (interpret as duration from midnight)
        if isinstance(value, (datetime, pd.Timestamp)):
            # Extract hours and minutes as duration
            hours = value.hour + value.minute / 60
            return min(hours, MAX_DURASI_HOURS)
        
        # If it's a string like "2:30" or "02:30:00"
        if isinstance(value, str):
            value = value.strip()
            if ':' in value:
                parts = value.split(':')
                hours = int(parts[0]) + int(parts[1]) / 60
                return min(hours, MAX_DURASI_HOURS)
            # Try parsing as float
            hours = float(value)
            if 0 < hours < 1:
                hours = hours * 24
            return min(abs(hours), MAX_DURASI_HOURS)
        
        return 0.0
    except:
        return 0.0


@st.cache_data(ttl=CACHE_TTL)
def load_gangguan_monitoring():
    """Load gangguan dari sheet Gangguan di file Monitoring"""
    # LEGACY FUNCTION DISABLED
    return pd.DataFrame()
    # df = None
    
    # if ONEDRIVE_LINKS.get("monitoring"):
    #     file_buffer = download_from_onedrive(ONEDRIVE_LINKS["monitoring"])
    #     if file_buffer:
    #         try:
    #             df = pd.read_excel(file_buffer, sheet_name='Gangguan')
    #         except:
    #             pass
    
    # if df is None:
    #     local_path = load_from_local("monitoring")
    #     if local_path:
    #         try:
    #             df = pd.read_excel(local_path, sheet_name='Gangguan')
    #         except:
    #             pass
    
    # if df is None:
    #     return pd.DataFrame()
    
    # try:
    #     all_data = []
    #     bulan_cols = ['Tanggal', 'Week', 'Shift', 'Start', 'End', 'Durasi', 'Kendala', 'Masalah']
        
    #     for i in range(12):
    #         start_col = i * 9
    #         try:
    #             section = df.iloc[:, start_col:start_col+8].copy()
    #             if section.shape[1] < 8:
    #                 continue
    #             section.columns = bulan_cols
    #             section = section[section['Tanggal'].notna()]
    #             section = section[section['Durasi'].notna()]
    #             section['Tanggal'] = pd.to_datetime(section['Tanggal'], errors='coerce')
                
    #             # FIX: Use safe Durasi parser to prevent overflow
    #             section['Durasi'] = section['Durasi'].apply(parse_durasi_value)
                
    #             section['Shift'] = pd.to_numeric(section['Shift'], errors='coerce').fillna(1)
    #             section = section[section['Tanggal'].notna()]
    #             section = section[section['Durasi'] > 0]
    #             if not section.empty:
    #                 all_data.append(section)
    #         except:
    #             continue
        
    #     if all_data:
    #         result = pd.concat(all_data, ignore_index=True)
    #         result['Bulan'] = result['Tanggal'].dt.month
    #         return result
    #     return pd.DataFrame()
    # except:
    #     return pd.DataFrame()


# ============================================================
# SUMMARY FUNCTIONS FOR MONITORING
# ============================================================


def get_ritase_summary(df_ritase):
    """Calculate ritase summary statistics"""
    if df_ritase is None or df_ritase.empty:
        return {'total_ritase': 0, 'avg_per_shift': 0, 'avg_per_day': 0}
    
    total_ritase = df_ritase['Total_Ritase'].sum() if 'Total_Ritase' in df_ritase.columns else 0
    avg_per_shift = df_ritase['Total_Ritase'].mean() if 'Total_Ritase' in df_ritase.columns else 0
    
    avg_per_day = 0
    if 'Tanggal' in df_ritase.columns and 'Total_Ritase' in df_ritase.columns:
        daily = df_ritase.groupby('Tanggal')['Total_Ritase'].sum()
        avg_per_day = daily.mean() if len(daily) > 0 else 0
    
    return {'total_ritase': total_ritase, 'avg_per_shift': round(avg_per_shift, 0), 
            'avg_per_day': round(avg_per_day, 0)}


def get_production_summary(df_prod):
    """Calculate production achievement summary"""
    if df_prod is None or df_prod.empty:
        return {'total_plan': 0, 'total_aktual': 0, 'achievement_pct': 0, 'days_achieved': 0}
    
    total_plan = df_prod['Plan'].sum() if 'Plan' in df_prod.columns else 0
    total_aktual = df_prod['Aktual'].sum() if 'Aktual' in df_prod.columns else 0
    achievement_pct = (total_aktual / total_plan * 100) if total_plan > 0 else 0
    
    days_achieved = 0
    if 'Ketercapaian' in df_prod.columns:
        days_achieved = len(df_prod[df_prod['Ketercapaian'] >= 1.0])
    
    return {'total_plan': total_plan, 'total_aktual': total_aktual,
            'achievement_pct': round(achievement_pct, 1), 'days_achieved': days_achieved}

# ============================================================
# STANDARDIZED RAW LOADERS (FOR MONITORING VIEW)
# ============================================================
# These functions provide direct access to Excel sheets
# Used by views/monitoring.py to maintain 0% visual change

@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_stockpile_hopper():
    """
    Load and process Stockpile Hopper data based on Transactional Structure.
    Scans for header row containing 'Date', 'Time', 'Shift', 'Dumping', 'Ritase', 'Rit'.
    (DEBUG MODE ENABLED)
    """
    try:
        source = None
        df = None
        debug_log = []
        
        # 0. TRY DATABASE LOAD
        try:
            engine = get_db_engine()
            if engine:
                # OPTIMIZED: Filter only 2026+ data
                query = "SELECT * FROM stockpile_logs WHERE date >= '2026-01-01' ORDER BY created_at DESC, id DESC"
                df_db = pd.read_sql(query, engine)
                if not df_db.empty:
                    rename_map = {
                        'date': 'Tanggal', 'time': 'Jam', 'shift': 'Shift',
                        'dumping': 'Dumping', 'unit': 'Unit', 'ritase': 'Ritase'
                    }
                    df_db = df_db.rename(columns=rename_map)
                    if 'Tanggal' in df_db.columns: df_db['Tanggal'] = pd.to_datetime(df_db['Tanggal'])
                    st.session_state['last_update_stockpile'] = "Database"
                    return df_db
        except Exception as e:
            debug_log.append(f"DB Load Error: {str(e)}")

    except Exception:
        pass
    
    # FORCE STOP if DB Logic fails - Prevent Slow Cloud Fallback
    return pd.DataFrame()


def load_raw_from_cloud(sheet_name, header=0):
    """Helper to load raw sheet from Cloud (Monitoring.xlsx) - Cloud Only"""
    if ONEDRIVE_LINKS.get("monitoring"):
        try:
            # Check Force Sync state to determine cache busting
            force_sync = st.session_state.get('force_cloud_reload', False)
            
            # Download (with cache bust if forced)
            file_buffer = download_from_onedrive(ONEDRIVE_LINKS["monitoring"], cache_bust=force_sync)
            if file_buffer:
                return pd.read_excel(file_buffer, sheet_name=sheet_name, header=header)
        except Exception as e:
            # print(f"Error loading raw cloud sheet {sheet_name}: {e}")
            pass
    return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_ritase_raw():
    """Load Ritase sheet directly (Raw) - Cloud Only"""
    return load_raw_from_cloud('Ritase')

@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_analisa_produksi_raw():
    """Load Analisa Produksi sheet directly - Cloud Only"""
    return load_raw_from_cloud('Analisa Produksi')

@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_gangguan_raw():
    """Load Gangguan sheet directly - Cloud Only"""
    return load_raw_from_cloud('Gangguan')

@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_tonase_raw():
    """Load Tonase sheet directly - Cloud Only"""
    try:
        df = load_raw_from_cloud('Tonase', header=1)
        
        # Safety: Rename first column to Tanggal if needed
        if len(df.columns) > 0:
            df = df.rename(columns={df.columns[0]: 'Tanggal'})
            
        # Filter repeated headers
        if 'Tanggal' in df.columns:
            df = df[df['Tanggal'].astype(str).str.strip() != 'Tanggal']
            df = df[df['Tanggal'].notna()]
            
        return df
    except Exception as e:
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL, persist="disk")
def load_shipping_data():
    """
    Load data pengiriman from Database (shipping_logs table).
    Fallback: OneDrive cloud download (disabled for speed).
    """
    debug_log = []
    
    # 0. TRY DATABASE LOAD
    try:
        engine = get_db_engine()
        if engine:
            query = "SELECT tanggal, shift, ap_ls, ap_ls_mk3, ap_ss, total_ls, total_ss FROM shipping_logs WHERE tanggal >= '2026-01-01' ORDER BY id ASC"
            df_db = pd.read_sql(query, engine)
            print(f"[Shipping Loader] DB returned {len(df_db)} rows")
            
            if not df_db.empty:
                 rename_map = {
                    'tanggal': 'Date', 
                    'shift': 'Shift'
                 }
                 df_db = df_db.rename(columns=rename_map)
                 if 'Date' in df_db.columns: 
                     df_db['Date'] = pd.to_datetime(df_db['Date'])
                 
                 # Quantity calculation for Dashboard global view
                 if 'total_ls' in df_db.columns and 'total_ss' in df_db.columns:
                     df_db['Quantity'] = df_db['total_ls'].fillna(0) + df_db['total_ss'].fillna(0)
                 else:
                     c_list = ['ap_ls', 'ap_ls_mk3', 'ap_ss']
                     for c in c_list: 
                         if c not in df_db.columns: df_db[c] = 0
                     df_db['Quantity'] = df_db['ap_ls'].fillna(0) + df_db['ap_ls_mk3'].fillna(0) + df_db['ap_ss'].fillna(0)
                 
                 return df_db
            else:
                 print("[Shipping Loader] WARNING: DB query returned 0 rows!")
        else:
            print("[Shipping Loader] ERROR: No DB engine available!")
    except Exception as e:
        print(f"[Shipping Loader] DB Error: {e}")
        debug_log.append(f"Shipping DB Query Error: {e}")
                 
    # FORCE STOP if DB Logic fails - Prevent Slow Cloud Fallback
    return pd.DataFrame()
    
    # 0. CHECK FORCE SYNC
    force_sync = st.session_state.get('force_cloud_reload', False)
    
    if force_sync:
        link = ONEDRIVE_LINKS.get("monitoring")
        if link:
            try:
                debug_log.append(f"Attempting download (Shipping). Link: {link[:20]}...")
                direct_url = convert_onedrive_link(link, cache_bust=True)
                debug_log.append(f"Converted URL (Shipping): {direct_url}")
                
                file_buffer = download_from_onedrive(link, cache_bust=True)
                if file_buffer:
                    source = file_buffer
                    st.session_state['last_update_shipping'] = datetime.now().strftime("%H:%M")
                else: 
                     debug_log.append("Shipping Sync failed: No buffer returned")
                     source = None
            except Exception as e:
                debug_log.append(f"Shipping Cloud Sync Error: {e}")
                source = None
        else:
            source = None
    else:
        source = None

    # Standard Path Resolution (Cloud Only Mode)
    if not source:
        link = ONEDRIVE_LINKS.get("monitoring")
        if link:
             try:
                 source = download_from_onedrive(link)
                 if source:
                     st.session_state['last_update_shipping'] = datetime.now().strftime("%H:%M")
             except Exception as e:
                 debug_log.append(f"Shipping Fallback Error: {e}")

    # Save log
    st.session_state['debug_log_shipping'] = debug_log

    if not source:
        return pd.DataFrame()

    try:
        xls = pd.ExcelFile(source)
        
        # Fuzzy Match Sheet Name
        sheet_name = None
        candidates = ['TONASE PENGIRIMAN ', 'TONASE PENGIRIMAN', 'PENGIRIMAN', 'SHIPPING']
        for s in xls.sheet_names:
            if s.strip().upper() in [c.strip().upper() for c in candidates]:
                sheet_name = s
                break
        
        if not sheet_name:
            return pd.DataFrame()

        # Read Header Row (Row 2 in specific file, Index 2)
        # But let's read a chunk to be safe
        if hasattr(source, 'seek'): source.seek(0)
        df_raw = pd.read_excel(source, sheet_name=sheet_name, header=None, nrows=5)
        
        # Find Header Row Index (Looking for 'Tanggal' and 'Shift')
        header_idx = -1
        for i in range(len(df_raw)):
            row_str = df_raw.iloc[i].astype(str).str.cat(sep=' ').lower()
            if 'tanggal' in row_str and 'shift' in row_str:
                header_idx = i
                break
        
        if header_idx == -1: return pd.DataFrame() # Header not found

        # Read Full Data with correct header
        if hasattr(source, 'seek'): source.seek(0)
        df_full = pd.read_excel(source, sheet_name=sheet_name, header=header_idx)
        
        # IDENTIFY BLOCKS
        # Pattern: [Tanggal, Shift, ..., Total LS, Total SS] repeated
        # We look for all columns named 'Tanggal' (pandas handles duplicate cols by appending .1, .2)
        
        all_blocks = []
        
        # Iterate columns to find 'Tanggal' starts
        # Since pandas dedups names, we check the original content or just fuzzy match columns
        # Easier: Iterate by index
        
        # Reload without header to map indices accurately
        if hasattr(source, 'seek'): source.seek(0)
        df_nheader = pd.read_excel(source, sheet_name=sheet_name, header=None, skiprows=header_idx)
        # Row 0 is now the header
        header_row = df_nheader.iloc[0]
        
        # Indices where header is 'Tanggal'
        block_starts = []
        for c in range(len(header_row)):
            val = str(header_row.iloc[c]).strip().lower()
            if val == 'tanggal':
                block_starts.append(c)
        
        for start_col in block_starts:
            try:
                # Extract Block (Assuming standard width ~7-8 cols)
                # Look for 'Total SS' or 'Total_SS' to end? Or just take fixed width 7
                # Based on debug: Tanggal, Shift, AP LS, AP LS(MK3), AP SS, Total LS, Total SS.
                # Width = 7
                
                block = df_nheader.iloc[1:, start_col:start_col+7].copy()
                
                # Assign Standard Names
                # We expect 7 columns. If fewer, pad.
                if block.shape[1] < 7: continue
                
                block.columns = ['Date', 'Shift', 'AP_LS', 'AP_LS_MK3', 'AP_SS', 'Total_LS', 'Total_SS']
                
                # Clean Data
                block = block.dropna(subset=['Date'])
                block['Date'] = safe_parse_date_column(block['Date'])
                block = block[block['Date'].notna()]
                block['Date'] = pd.to_datetime(block['Date'])
                
                # Filter Valid Shifts
                block = block[block['Shift'].astype(str).str.contains(r'1|2|3')]
                
                # Numeric Conversion
                cols_num = ['AP_LS', 'AP_LS_MK3', 'AP_SS', 'Total_LS', 'Total_SS']
                for c in cols_num:
                    block[c] = pd.to_numeric(block[c], errors='coerce').fillna(0)
                
                # Calculate Total Quantity (Sum of Components, not usage of sparse Total columns)
                # Note: Some blocks might not have MK3, but we normalized to 0
                block['Quantity'] = block['AP_LS'] + block['AP_LS_MK3'] + block['AP_SS']
                
                # Append
                all_blocks.append(block[['Date', 'Shift', 'AP_LS', 'AP_LS_MK3', 'AP_SS', 'Quantity']])
                
            except Exception as e:
                continue
        
        if all_blocks:
            final_df = pd.concat(all_blocks, ignore_index=True)
            
            # FILTER: ONLY 2026+
            final_df = final_df[final_df['Date'] >= pd.Timestamp('2026-01-01')]
            
            # SORT: DESCENDING (Latest Input First)
            final_df = final_df.sort_values(['Date', 'Shift'], ascending=False)
            
            return final_df
            
            return final_df
            
        return pd.DataFrame()

    except Exception as e:
        print(f"Error loading shipping: {e}")
        return pd.DataFrame()

# ============================================================
# OPTIMIZED SQL LOADERS (AGGREGATION)
# ============================================================

@st.cache_data(ttl=CACHE_TTL)
def get_filter_options():
    """
    Get distinct filter options directly from SQL.
    Super fast (< 0.1s) even for 1 million rows.
    """
    options = {
        'shift': [],
        'front': [],
        'excavator': [],
        'material': []
    }
    
    try:
        engine = get_db_engine()
        if engine:
            with engine.connect() as conn:
                from sqlalchemy import text
                
                # 1. Shifts
                try:
                    res_shift = conn.execute(text("SELECT DISTINCT shift FROM production_logs ORDER BY shift")).fetchall()
                    options['shift'] = [str(row[0]) for row in res_shift if row[0] is not None]
                except:
                    options['shift'] = ["Shift 1", "Shift 2"]

                # 2. Fronts (Active Only - appearing in 2026)
                res_front = conn.execute(text("SELECT DISTINCT front FROM production_logs WHERE date >= '2026-01-01' ORDER BY front")).fetchall()
                options['front'] = [row[0] for row in res_front if row[0] is not None]
                
                # 3. Excavators
                res_exca = conn.execute(text("SELECT DISTINCT excavator FROM production_logs WHERE date >= '2026-01-01' ORDER BY excavator")).fetchall()
                options['excavator'] = [row[0] for row in res_exca if row[0] is not None]
                
                # 4. Material
                res_mat = conn.execute(text("SELECT DISTINCT commodity FROM production_logs WHERE date >= '2026-01-01' ORDER BY commodity")).fetchall()
                options['material'] = [row[0] for row in res_mat if row[0] is not None]
                
    except Exception as e:
        print(f"Filter Load Error: {e}")
        
    return options

@st.cache_data(ttl=CACHE_TTL)
def get_production_kpi_summary(start_date=None, end_date=None):
    """
    Calculate KPIs directly in SQL. 
    Returns: (Total Tonnase, Total Rit, Last Date)
    """
    try:
        engine = get_db_engine()
        if engine:
             # Basic SQL construction
             where_clause = "WHERE date >= '2026-01-01'"
             if start_date and end_date:
                 where_clause += f" AND date BETWEEN '{start_date}' AND '{end_date}'"
                 
             query = f"""
             SELECT 
                SUM(tonnase) as total_ton, 
                SUM(rit) as total_rit,
                MAX(date) as last_date
             FROM production_logs 
             {where_clause}
             """
             df = pd.read_sql(query, engine)
             if not df.empty:
                 return df.iloc[0]
    except Exception as e:
        print(f"KPI Query Error: {e}")
    return pd.Series({'total_ton': 0, 'total_rit': 0, 'last_date': None})