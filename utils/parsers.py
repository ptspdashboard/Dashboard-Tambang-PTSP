import pandas as pd
import re
from datetime import datetime, timedelta, time

# ============================================================
# PARSING HELPERS
# ============================================================

def parse_excel_date(date_value):
    try:
        if isinstance(date_value, (datetime, pd.Timestamp)):
            return pd.Timestamp(date_value).date()
        if isinstance(date_value, str):
            parsed = pd.to_datetime(date_value, errors='coerce')
            if pd.notna(parsed): return parsed.date()
            return None
        if isinstance(date_value, (int, float)):
            excel_epoch = datetime(1899, 12, 30)
            date_result = excel_epoch + timedelta(days=int(date_value))
            return date_result.date()
        return None
        return None
    except Exception:
        return None

def parse_excel_time(time_val):
    try:
        if pd.isna(time_val): return None
        # Handle Excel Serial Date (Float) -> Time/Datetime Object
        if isinstance(time_val, (int, float)):
             # Excel base date
             excel_epoch = datetime(1899, 12, 30)
             dt = excel_epoch + timedelta(days=float(time_val))
             return dt # Return datetime object (1899-...) which pandas handles fine
        
        # Handle Strings
        if isinstance(time_val, str):
             return time_val.strip()

        if isinstance(time_val, time):
             return time_val.strftime("%H:%M:%S")
             
        return time_val
    except: return None

def safe_parse_date_column(date_series):
    return date_series.apply(parse_excel_date)

def normalize_excavator_name(name):
    if pd.isna(name) or not isinstance(name, str):
        return name
    name = str(name).strip().upper()
    clean = re.sub(r'[^A-Z0-9]', '', name)
    match = re.match(r'^PC(\d{3})(\d{2})$', clean)
    if match: return f"PC {match.group(1)}-{match.group(2)}"
    match = re.match(r'^PC[-\s]*(\d{3})[-\s]*(\d{2})$', name)
    if match: return f"PC {match.group(1)}-{match.group(2)}"
    return name

def normalize_excavator_column(df):
    if 'Excavator' in df.columns:
        df['Excavator'] = df['Excavator'].apply(normalize_excavator_name)
    return df

# ============================================================
# 1. PRODUCTION PARSER
# ============================================================

def parse_production_data(source):
    try:
        try:
            xls = pd.ExcelFile(source, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            xls = pd.ExcelFile(source)
        valid_dfs = []
        target_sheets = [s for s in xls.sheet_names if '2026' in str(s)]
        if not target_sheets:
            target_sheets = [s for s in xls.sheet_names if s.lower() not in ['menu', 'dashboard', 'summary', 'ref', 'config']]
            
        for sheet in target_sheets:
            try:
                # Header Scanning - Reading Full Sheet (Match Stockpile Logic)
                df_raw = pd.read_excel(xls, sheet_name=sheet, header=None)
                header_idx = 0
                for i in range(len(df_raw)):
                    row_str = df_raw.iloc[i].astype(str).str.cat(sep=' ').lower()
                    if ('date' in row_str or 'tanggal' in row_str) and \
                       ('shift' in row_str or 'dump truck' in row_str or 'unit' in row_str):
                        header_idx = i; break
                
                temp_df = pd.read_excel(xls, sheet_name=sheet, header=header_idx)
                temp_df.columns = [str(c).strip() for c in temp_df.columns]
                
                # Column Rename to Standard (for DB Mapping)
                # We map raw Excel headers to our Strict DB Model keys
                # DB Keys: Date, Shift, Time, Excavator, Commudity, Dump Truck, Rit, Tonnase, Front, Dump Loc
                
                col_map = {}
                for c in temp_df.columns:
                    cl = c.lower()
                    if 'date' in cl or 'tanggal' in cl: col_map[c] = 'Date'
                    elif 'shift' in cl: col_map[c] = 'Shift'
                    elif 'excavator' in cl: col_map[c] = 'Excavator'
                    elif 'commodity' in cl or 'commudity' in cl: col_map[c] = 'Commodity' # Fixed
                    elif 'unit' in cl or 'dump truck' in cl: col_map[c] = 'Dump Truck'
                    elif 'ritase' in cl or 'rit' == cl: col_map[c] = 'Rit'
                    elif 'tonnase' in cl or 'tonase' in cl: col_map[c] = 'Tonase' # User pref: Tonase
                    elif 'front' in cl: col_map[c] = 'Front'
                    elif 'dump' in cl and 'loc' in cl: col_map[c] = 'Dump Loc'
                    elif 'blok' in cl: col_map[c] = 'BLOK'
                    elif 'time' in cl or 'jam' in cl: col_map[c] = 'Time'
                
                temp_df = temp_df.rename(columns=col_map)
                
                if 'Date' not in temp_df.columns: continue
                
                temp_df['Date'] = safe_parse_date_column(temp_df['Date'])
                temp_df = temp_df.dropna(subset=['Date'])
                temp_df = normalize_excavator_column(temp_df)
                
                # Fill missing columns
                for req in ['Excavator', 'Front', 'Commodity', 'Dump Truck', 'Dump Loc', 'BLOK', 'Time', 'Shift']:
                    if req not in temp_df.columns: temp_df[req] = None

                # FILTER EMPTY ROWS (User Request)
                # Remove rows where Date is present but other keys are empty or '-'
                # Critical columns: Time, Shift, Excavator, Dump Truck
                def is_valid_row(row):
                    # Check if at least one critical column has real data (not None, NaN, or '-')
                    # Broadened check to include ALL data columns so we don't accidentally drop sparse rows
                    # EXCLUDE SHIFT: Shift alone is not enough to keep a row (User Bug Report)
                    criticals = [
                        row['Time'], row['Excavator'], row['Dump Truck'], 
                        row['Front'], row['Commodity'], row['Dump Loc'], row['BLOK'],
                        row.get('Rit', 0), row.get('Tonnase', 0)
                    ]
                    for val in criticals:
                        s = str(val).strip()
                        # Allow 0 for Rit/Tonase if explicitly valid? No, usually 0 means empty in this excel
                        if pd.notna(val) and s != '' and s != '-' and s != 'nan' and s != 'None':
                            # Special check for numerics 0
                            try:
                                if float(val) == 0: continue 
                            except: pass
                            
                            return True # Found something valid
                    return False

                valid_mask = temp_df.apply(is_valid_row, axis=1)
                temp_df = temp_df[valid_mask]
                    
                # Numerics
                for n in ['Rit', 'Tonnase']:
                    if n in temp_df.columns: 
                        temp_df[n] = pd.to_numeric(temp_df[n], errors='coerce').fillna(0)
                
                valid_dfs.append(temp_df)
            except: continue
                
        if valid_dfs: return pd.concat(valid_dfs, ignore_index=True)
        return pd.DataFrame()
    except: return pd.DataFrame()

# ============================================================
# 2. DOWNTIME PARSER (Indonesian)
# ============================================================

def parse_downtime_data(source):
    try:
        try:
            xls = pd.ExcelFile(source, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            xls = pd.ExcelFile(source)
        sheet_names = xls.sheet_names
        
        target_sheets = []
        if 'All' in sheet_names: target_sheets = ['All']
        else:
            mon_sheets = [s for s in sheet_names if 'monitoring' in str(s).lower()]
            mon_sheets.sort(reverse=True)
            target_sheets = mon_sheets[:1] if mon_sheets else ([sheet_names[0]] if sheet_names else [])
            
        all_dfs = []
        # DB Keys correspond to these exactly
        standard_cols = ['Tanggal', 'Shift', 'Start', 'End', 'Durasi', 'Crusher', 
                         'Alat', 'Remarks', 'Kelompok Masalah', 'Gangguan', 'Info CCR', 
                         'Sub Komponen', 'Keterangan', 'Penyebab', 'Identifikasi Masalah',
                         'Action', 'Plan', 'PIC', 'Status', 'Due Date', 'Spare Part', 
                         'Info Spare Part', 'Link/Lampiran', 'Extra']
                         
        for sheet in target_sheets:
            try:
                df_sheet = pd.read_excel(xls, sheet_name=sheet)
                if df_sheet.empty: continue
                
                df_sheet.columns = [str(c).strip() for c in df_sheet.columns]
                
                # Map Date
                col_map = {c.lower(): c for c in df_sheet.columns}
                if 'tanggal' in col_map: df_sheet = df_sheet.rename(columns={col_map['tanggal']: 'Tanggal'})
                
                if 'Tanggal' not in df_sheet.columns: continue
                
                # Parse Date
                df_sheet['Tanggal'] = safe_parse_date_column(df_sheet['Tanggal'])
                df_sheet = df_sheet.dropna(subset=['Tanggal'])
                
                # Shifted Column Logic 2026
                if 'Alat' in df_sheet.columns:
                    mask_shifted = df_sheet['Alat'].astype(str).str.contains(r'LSC|MS |Batu', case=False, na=False)
                    if 'Tahun' in df_sheet.columns: mask_shifted = mask_shifted | (df_sheet['Tahun'] == 2026)
                    if mask_shifted.any():
                        shift_map = [
                            ('Crusher', 'Alat'), ('Alat', 'Remarks'), ('Remarks', 'Kelompok Masalah'),
                            ('Kelompok Masalah', 'Gangguan'), ('Gangguan', 'Info CCR'),
                            ('Info CCR', 'Sub Komponen'), ('Sub Komponen', 'Keterangan'),
                            ('Keterangan', 'Penyebab'), ('Penyebab', 'Identifikasi Masalah'),
                            ('Identifikasi Masalah', 'Action'), ('Action', 'Plan'),
                            ('Plan', 'PIC'), ('PIC', 'Status'), ('Status', 'Due Date'),
                            ('Due Date', 'Spare Part'), ('Spare Part', 'Info Spare Part'),
                            ('Info Spare Part', 'Link/Lampiran')
                        ]
                        for new_col, old_col in shift_map:
                            if old_col in df_sheet.columns:
                                if new_col not in df_sheet.columns: df_sheet[new_col] = None
                                df_sheet.loc[mask_shifted, new_col] = df_sheet.loc[mask_shifted, old_col]
                                
                # Ensure cols
                for col in standard_cols:
                    if col not in df_sheet.columns: df_sheet[col] = None
                
                # Numerics & Time
                df_sheet['Durasi'] = pd.to_numeric(df_sheet['Durasi'], errors='coerce').fillna(0.0)
                
                # Fix Time Parsing (Start/End)
                if 'Start' in df_sheet.columns:
                    df_sheet['Start'] = df_sheet['Start'].apply(parse_excel_time)
                if 'End' in df_sheet.columns:
                    df_sheet['End'] = df_sheet['End'].apply(parse_excel_time)
                
                all_dfs.append(df_sheet)
            except: continue
        
        if all_dfs: return pd.concat(all_dfs, ignore_index=True)
        return pd.DataFrame()
    except: return pd.DataFrame()

# ============================================================
# 3. BBM PARSER
# ============================================================
# ============================================================
# 3. STOCKPILE PARSER (Monitoring.xlsx -> Sheet Stockpile Hopper)
# ============================================================
def parse_stockpile_hopper(source):
    try:
        try:
            xls = pd.ExcelFile(source, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            xls = pd.ExcelFile(source)
        # Use exact sheet name
        if 'Stockpile Hopper' not in xls.sheet_names:
            return pd.DataFrame()

        # Read header scan - READING FULL SHEET to find 2026 header
        df_raw = pd.read_excel(xls, sheet_name='Stockpile Hopper', header=None)
            
        # Header Scanning - Strict Match based on User User and Debug Findings (Row ~3399)
        # looking for: Date, Time, Shift, Dumping, Unit, Ritase
        header_idx = None
        
        # Header Scanning: User confirmed header is at Row 3399 for 2026 data
        # We must scan the FULL sheet again.
        header_idx = None
        df_raw = pd.read_excel(xls, sheet_name='Stockpile Hopper', header=None)
        
        # Optimization: Start scanning from row 3000 to save time and avoid old headers (2025 data)
        # User confirmed 2026 data starts at 3399.
        start_scan = 3000 if len(df_raw) > 3000 else 0
        
        for i in range(start_scan, len(df_raw)):
            row_str = df_raw.iloc[i].astype(str).str.cat(sep=' ').lower()
            # Strict check again because we know where it is roughly
            # Row 3399: Date, Time, Shift, Dumping, Unit, Rit
            if 'date' in row_str and 'dumping' in row_str and 'unit' in row_str:
                header_idx = i
                print(f"Found Stockpile Header at row {i}")
                break
        
        if header_idx is None:
            print("Stockpile Header not found.")
            return pd.DataFrame() 

        df = pd.read_excel(xls, sheet_name='Stockpile Hopper', header=header_idx)
        
        # Standardize Columns
        # Excel: Date/Tanggal, Time/Jam, Shift, Dumping, Unit, Ritase
        rename_dict = {}
        for col in df.columns:
            lower_col = str(col).lower().strip()
            if 'date' == lower_col or 'tanggal' == lower_col: rename_dict[col] = 'Tanggal'
            elif 'time' == lower_col or 'jam' == lower_col: rename_dict[col] = 'Jam'
            elif 'shift' == lower_col: rename_dict[col] = 'Shift'
            elif 'dumping' == lower_col or 'loader' == lower_col: rename_dict[col] = 'Loader'
            elif 'unit' == lower_col: rename_dict[col] = 'Unit'
            elif 'ritase' == lower_col: rename_dict[col] = 'Ritase'
            elif 'total' == lower_col: rename_dict[col] = 'Ritase' 
            elif 'rit' == lower_col: rename_dict[col] = 'Ritase' # Added 'Rit'

        df = df.rename(columns=rename_dict)
        
        if 'Tanggal' not in df.columns: 
            return pd.DataFrame()

        # Parse Date
        df['Tanggal'] = safe_parse_date_column(df['Tanggal'])
        df = df.dropna(subset=['Tanggal'])
        
        # FILTER EMPTY ROWS (Stockpile) - MOVED UP
        # Remove rows where Date is present but other keys are empty or '-'
        # Critical columns: Loader, Unit, Ritase, Jam, Shift
        def is_valid_stockpile_row(row):
            # Check Ritase
            rit = row['Ritase'] if 'Ritase' in row else 0
            try:
                if float(rit) > 0: return True
            except: pass
            
            # Check Text Cols
            # Use safe get
            loader = row.get('Loader', '')
            unit = row.get('Unit', '')
            jam = row.get('Jam', '')
            # EXCLUDE SHIFT: Shift alone is not enough (User Bug Report)
            
            criticals = [loader, unit, jam]
            for val in criticals:
                s = str(val).strip().lower()
                if pd.notna(val) and s != '' and s != '-' and s != 'nan' and s != 'unknown' and s != 'none':
                    return True
            return False

        valid_mask = df.apply(is_valid_stockpile_row, axis=1)
        df = df[valid_mask]

        if 'Jam' in df.columns:
            # Just clean whitespace, keep text
            df['Jam'] = df['Jam'].astype(str).str.strip()
        else:
            df['Jam'] = "Unknown"
            
        # Parse Shift (Format: "Shift 2" -> 2)
        def extract_shift(val):
            if pd.isna(val): return 1
            s = str(val).strip().lower()
            # Extract first digit found
            import re
            match = re.search(r'\d+', s)
            if match:
                return int(match.group())
            return 1 # Default
            
        if 'Shift' in df.columns:
            df['Shift'] = df['Shift'].apply(extract_shift)
        else:
            df['Shift'] = 1

        # Numerics
        if 'Ritase' in df.columns:
            df['Ritase'] = pd.to_numeric(df['Ritase'], errors='coerce').fillna(0)
            
        # Defaults
        if 'Loader' not in df.columns: df['Loader'] = 'Unknown'
        if 'Unit' not in df.columns: df['Unit'] = 'Unknown'
        
        # FILTER EMPTY ROWS (Stockpile)
        # Remove rows where Date is present but other keys are empty or '-'
        # Critical columns: Loader, Unit, Ritase, Jam, Shift
        def is_valid_stockpile_row(row):
            # Check if at least one critical column has real data
            # Ritase must be > 0 or Loader/Unit/Jam/Shift must be valid text
            
            # Check Ritase
            rit = row['Ritase'] if 'Ritase' in row else 0
            try:
                if float(rit) > 0: return True
            except: pass
            
            # Check Text Cols
            # Broader check: include Jam and Shift
            criticals = [row['Loader'], row['Unit'], row['Jam'], row['Shift']]
            for val in criticals:
                s = str(val).strip().lower()
                # 0 is considered "data" for Shift (e.g. Shift 0?) unlikely but safe.
                # But 'unknown' is default filler, so ignore that.
                if pd.notna(val) and s != '' and s != '-' and s != 'nan' and s != 'unknown':
                    return True
            return False

        valid_mask = df.apply(is_valid_stockpile_row, axis=1)
        df = df[valid_mask]

        return df[['Tanggal', 'Jam', 'Shift', 'Loader', 'Unit', 'Ritase']]
    except: return pd.DataFrame()

# ============================================================
# 4. SHIPPING PARSER (Monitoring.xlsx -> Sheet TONASE Pengiriman)
# ============================================================
def parse_shipping_data(source):
    try:
        if hasattr(source, 'seek'):
            source.seek(0)
        try:
            xls = pd.ExcelFile(source, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            xls = pd.ExcelFile(source)
            
        # Use exact sheet name with trailing space
        target_sheet = 'TONASE Pengiriman '
        if target_sheet not in xls.sheet_names:
            # Fallback check without space
            if 'TONASE Pengiriman' in xls.sheet_names:
                target_sheet = 'TONASE Pengiriman'
            else:
                return pd.DataFrame()
        
        # Read full sheet to scan horizontal blocks
        # Header is typically at row index 2 (Excel Row 3)
        df_raw = pd.read_excel(xls, sheet_name=target_sheet, header=None)
        
        header_row_idx = 2  # Confirmed by debug
        scan_limit_col = df_raw.shape[1]
        
        found_dfs = []
        
        for c in range(scan_limit_col):
            val = str(df_raw.iloc[header_row_idx, c]).strip().lower()
            if 'tanggal' == val:
                # Check data to confirm year 2026
                # Look ahead a few rows to confirm it's a valid data block
                is_valid_block = False
                try:
                    for r_offset in range(1, 4): # Check first 3 data rows
                        if header_row_idx + r_offset >= len(df_raw): break
                        sample_val = str(df_raw.iloc[header_row_idx+r_offset, c])
                        if '2026' in sample_val:
                             is_valid_block = True
                             break
                except: pass
                
                if is_valid_block:
                     # Extract Block (7 cols)
                     block_width = 7
                     if c + block_width > scan_limit_col: continue

                     df = df_raw.iloc[header_row_idx+1:, c : c+block_width].copy()
                     
                     # Rename Cols
                     cols = ['Date', 'Shift', 'AP_LS', 'AP_LS_MK3', 'AP_SS', 'Total_LS', 'Total_SS']
                     current_cols = len(df.columns)
                     df.columns = cols[:current_cols]
                     
                     # Clean Data
                     df = df.dropna(subset=['Date'])
                     
                     # Clean Numerics
                     num_cols = ['AP_LS', 'AP_LS_MK3', 'AP_SS', 'Total_LS', 'Total_SS']
                     for col in num_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                     
                     # Drop if all numeric are 0 (Empty rows)
                     # Only keep rows with at least some data
                     # But be careful not to drop valid 0s if that's possible?
                     # User said "hilangkan saja klo datanya masih 0 semua"
                     mask = (df[num_cols].sum(axis=1) > 0)
                     df = df[mask]
                     
                     if not df.empty:
                        # Date Convert
                        df['Date'] = safe_parse_date_column(df['Date'])
                        df = df.dropna(subset=['Date'])
                        
                        # Shift Convert
                        if 'Shift' in df.columns:
                            def clean_shift(x):
                                x = str(x).lower().replace('shift', '').strip()
                                import re
                                m = re.search(r'\d+', x)
                                if m: return int(m.group())
                                if x == 'i': return 1
                                if x == 'ii': return 2
                                if x == 'iii': return 3
                                return 1
                            df['Shift'] = df['Shift'].apply(clean_shift)
                        
                        found_dfs.append(df)
        
        if found_dfs:
            final_df = pd.concat(found_dfs, ignore_index=True)
            return final_df
        else:
            return pd.DataFrame()

    except Exception as e:
        print(f"Error parsing Shipping: {e}")
        return pd.DataFrame()

# ============================================================
# 5. DAILY PLAN PARSER
# ============================================================
def parse_daily_plan_data(source):
    try:
        # Header is at Row 3 (Index 2)
        try:
            df = pd.read_excel(source, sheet_name='Scheduling', header=2, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            df = pd.read_excel(source, sheet_name='Scheduling', header=2)
        if df.empty: return pd.DataFrame()
        
        if 'Tanggal' in df.columns:
            df['Tanggal'] = safe_parse_date_column(df['Tanggal'])
            df = df.dropna(subset=['Tanggal'])
        else: return pd.DataFrame()
        
        # Map columns
        # User confirmed headers: Hari, Tanggal, Shift, Batu Kapur, Silika, Clay, Alat Muat, Alat Angkut, Blok, Grid, ROM, Keterangan
        col_map = {
            'Hari': 'Hari',
            'Batu Kapur': 'Batu Kapur', 'Silika': 'Silika', 'Clay': 'Clay',
            'Alat Muat': 'Alat Muat', 'Alat Angkut': 'Alat Angkut',
            'Blok': 'Blok', 'Grid': 'Grid', 'ROM': 'ROM', 'Keterangan': 'Keterangan'
        }
        
        # Clean numeric
        for c in ['Batu Kapur', 'Silika', 'Clay']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
        return df
    except: return pd.DataFrame()

# ============================================================
# 6. TARGET PARSER (Analisa Produksi -> RKAP)
# ============================================================
def parse_target_data(source):
    try:
        try:
            xls = pd.ExcelFile(source, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            xls = pd.ExcelFile(source)
        if 'Analisa Produksi' not in xls.sheet_names:
            return pd.DataFrame()
            
        df = pd.read_excel(xls, sheet_name='Analisa Produksi', header=0)
        
        # Structure is dynamic: "Januari 2025", "Februari 2025" columns
        # We need to unpivot (melt) this.
        
        # 1. Identify Month Columns
        # Regex for 'Month Year' (Bahasa or English)
        # e.g. "Januari 2025", "Feb 2026"
        month_cols = []
        for c in df.columns:
            if re.match(r'.*\d{4}', str(c)):
                month_cols.append(c)
                
        if not month_cols: return pd.DataFrame()
        
        # 2. Extract values
        # Rows might be dates (1, 2, 3...) or Full Dates
        # Based on previous code in loader, it seemed to just grab the column?
        # Let's assume the rows 1..31 correspond to days.
        # But wait, looking at the previous loader attempt:
        # It relies on 'Unnamed: 0' or similar being the day?
        # Actually, let's assume the first column is Day (1-31).
        
        # Let's Inspect Row 0-35
        # Usually: Col 0 = Date/Day. Other Cols = Plan values.
        
        # Safe strategy: Melt everything
        df_melted = df.melt(var_name='MonthYear', value_name='Plan')
        
        # But we need the Day info.
        # Let's assume Index is Day-1? Or Column 0 is Day?
        # Re-read with header=None to check structure?
        # Let's stick to the previous loader logic which seemed to work (lines 1840+)
        # Wait, the previous loader FAILED or was slow.
        # Let's assume simple structure:
        # Col 0: "Tanggal" (1, 2, ..., 31)
        # Col 1: "Januari 2025"
        # Col 2: "Februari 2025"...
        
        if 'Tanggal' not in df.columns and 'Date' not in df.columns:
            # Maybe the first column is implicitly Date
            df = df.rename(columns={df.columns[0]: 'Day'})
        else:
            col = 'Tanggal' if 'Tanggal' in df.columns else 'Date'
            df = df.rename(columns={col: 'Day'})
            
        # Clean Day
        df['Day'] = pd.to_numeric(df['Day'], errors='coerce')
        df = df.dropna(subset=['Day'])
        df = df[(df['Day'] >= 1) & (df['Day'] <= 31)]
        
        records = []
        for _, row in df.iterrows():
            day = int(row['Day'])
            for m_col in month_cols:
                # Parse Month Year from Header
                try:
                    # m_col: "Januari 2025"
                    # Translate ID -> EN
                    m_str = m_col.lower().replace('januari', 'january').replace('februari', 'february') \
                                         .replace('maret', 'march').replace('mei', 'may') \
                                         .replace('juni', 'june').replace('juli', 'july') \
                                         .replace('agustus', 'august').replace('oktober', 'october') \
                                         .replace('desember', 'december')
                    
                    dt_month = pd.to_datetime(m_str, format='%B %Y')
                    
                    # Construct valid date
                    try:
                        full_date = datetime(dt_month.year, dt_month.month, day).date()
                        plan_val = pd.to_numeric(row[m_col], errors='coerce')
                        if pd.notna(plan_val):
                            records.append({'Date': full_date, 'Plan': float(plan_val)})
                    except ValueError:
                        continue # Dayout of range (e.g. Feb 30)
                except:
                    continue
                    
        return pd.DataFrame(records)
    except: return pd.DataFrame()


# ============================================================
# 7. SOLAR MONTHLY PARSER (Solar Excel -> Sheet Bulan: JAN/FEB/...)
# ============================================================
# Structure:
#   Row 0: Perusahaan | Jenis Alat | Tipe Unit | PEMAKAIAN SOLAR (LITER) | ...
#   Row 1: (empty)    | (empty)    | (empty)   | TANGGAL                 | ...
#   Row 2: (empty)    | (empty)    | (empty)   | 1 | 2 | 3 | ... | 31 | TOTAL | RATA-RATA | PERSENTASE
#   Row 3+: Data rows (Perusahaan & Jenis Alat are merged cells -> forward-fill)

def parse_solar_monthly(source, month_key, year=2026):
    """
    Parse solar monthly consumption sheet.
    month_key: e.g. "01" for January
    Returns DataFrame: [Perusahaan, Jenis_Alat, Tipe_Unit, Tanggal, Liter, Bulan, Tahun]
    """
    from config.settings import SOLAR_MONTH_SHEETS, SOLAR_MONTH_NAMES
    
    try:
        sheet_name = SOLAR_MONTH_SHEETS.get(month_key)
        month_name = SOLAR_MONTH_NAMES.get(month_key, "Unknown")
        month_int = int(month_key)
        
        if not sheet_name:
            return pd.DataFrame()
        
        try:
            xls = pd.ExcelFile(source, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            xls = pd.ExcelFile(source)
        
        # Find the sheet (case-insensitive, partial match)
        target_sheet = None
        for s in xls.sheet_names:
            if s.upper().strip() == sheet_name.upper().strip():
                target_sheet = s
                break
            # Also match full month names like "FUEL CONSUMPTION JANUARI"
            if sheet_name.upper() in s.upper():
                target_sheet = s
                break
        
        if not target_sheet:
            print(f"[Solar Parser] Sheet '{sheet_name}' not found. Available: {xls.sheet_names}")
            return pd.DataFrame()
        
        # Read raw to find structure
        df_raw = pd.read_excel(xls, sheet_name=target_sheet, header=None)
        
        if df_raw.empty:
            return pd.DataFrame()
        
        # Find the day-number row (row with 1, 2, 3... as tanggal)
        day_row_idx = None
        for i in range(min(10, len(df_raw))):
            row_vals = df_raw.iloc[i].values
            # Check if this row has sequential numbers 1, 2, 3...
            nums = []
            for v in row_vals[3:10]:  # Skip first 3 cols (Perusahaan, Jenis, Unit)
                try:
                    n = int(float(v))
                    nums.append(n)
                except:
                    pass
            if len(nums) >= 3 and nums[:3] == [1, 2, 3]:
                day_row_idx = i
                break
        
        if day_row_idx is None:
            # Fallback: assume row 2
            day_row_idx = 2
        
        # Extract day columns (skip first 3 meta columns)
        day_cols = {}
        for col_idx in range(3, len(df_raw.columns)):
            val = df_raw.iloc[day_row_idx, col_idx]
            try:
                day_num = int(float(val))
                if 1 <= day_num <= 31:
                    day_cols[col_idx] = day_num
            except:
                pass
        
        if not day_cols:
            return pd.DataFrame()
        
        # Data starts from day_row_idx + 1
        data_start = day_row_idx + 1
        
        records = []
        current_company = None
        current_jenis = None
        
        for i in range(data_start, len(df_raw)):
            row = df_raw.iloc[i]
            
            # Update company if present
            perusahaan = row.iloc[0] if len(row) > 0 else None
            jenis_alat = row.iloc[1] if len(row) > 1 else None
            tipe_unit = row.iloc[2] if len(row) > 2 else None
            
            if pd.notna(perusahaan):
                perusahaan_str = str(perusahaan).strip()
                # Skip total/summary rows
                if 'total' in perusahaan_str.lower():
                    continue
                current_company = perusahaan_str
            
            if pd.notna(jenis_alat):
                jenis_str = str(jenis_alat).strip()
                if 'total' not in jenis_str.lower():
                    current_jenis = jenis_str
            
            # Skip if no unit
            if pd.isna(tipe_unit) or not current_company:
                continue
            
            unit_str = str(tipe_unit).strip()
            if unit_str.lower() in ['nan', '', 'none'] or 'total' in unit_str.lower():
                continue
            
            # Extract daily liter values
            for col_idx, day_num in day_cols.items():
                try:
                    val = row.iloc[col_idx]
                    liter = float(val) if pd.notna(val) else 0.0
                except:
                    liter = 0.0
                
                # Construct date
                try:
                    tanggal = datetime(year, month_int, day_num).date()
                except ValueError:
                    continue  # Invalid date (e.g., Feb 30)
                
                records.append({
                    'Perusahaan': current_company,
                    'Jenis_Alat': current_jenis or 'Unknown',
                    'Tipe_Unit': unit_str,
                    'Tanggal': tanggal,
                    'Liter': liter,
                    'Bulan': month_name,
                    'Tahun': year
                })
        
        if records:
            df = pd.DataFrame(records)
            print(f"[Solar Parser] Parsed {len(df)} records from sheet '{target_sheet}'")
            return df
        
        return pd.DataFrame()
        
    except Exception as e:
        print(f"[Solar Parser] Error parsing monthly sheet: {e}")
        return pd.DataFrame()


# ============================================================
# 8. FUEL CONSUMPTION PARSER (Solar Excel -> Sheet FUEL CONSUMPTION)
# ============================================================
# Same structure as monthly sheet but values are L/Jam instead of Liters

def parse_fuel_consumption(source, month_key, year=2026):
    """
    Parse fuel consumption sheet.
    Returns DataFrame: [Perusahaan, Jenis_Alat, Tipe_Unit, Tanggal, L_per_Jam, Bulan, Tahun]
    """
    from config.settings import SOLAR_MONTH_NAMES
    
    try:
        month_name = SOLAR_MONTH_NAMES.get(month_key, "Unknown")
        month_int = int(month_key)
        
        # Find the FUEL CONSUMPTION sheet
        try:
            xls = pd.ExcelFile(source, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            xls = pd.ExcelFile(source)
        
        target_sheet = None
        for s in xls.sheet_names:
            if 'fuel consumption' in s.lower():
                target_sheet = s
                break
        
        if not target_sheet:
            print(f"[FC Parser] FUEL CONSUMPTION sheet not found. Available: {xls.sheet_names}")
            return pd.DataFrame()
        
        # Read raw
        df_raw = pd.read_excel(xls, sheet_name=target_sheet, header=None)
        
        if df_raw.empty:
            return pd.DataFrame()
        
        # Find day-number row
        day_row_idx = None
        for i in range(min(10, len(df_raw))):
            row_vals = df_raw.iloc[i].values
            nums = []
            for v in row_vals[3:10]:
                try:
                    n = int(float(v))
                    nums.append(n)
                except:
                    pass
            if len(nums) >= 3 and nums[:3] == [1, 2, 3]:
                day_row_idx = i
                break
        
        if day_row_idx is None:
            day_row_idx = 2
        
        # Extract day columns 
        day_cols = {}
        for col_idx in range(3, len(df_raw.columns)):
            val = df_raw.iloc[day_row_idx, col_idx]
            try:
                day_num = int(float(val))
                if 1 <= day_num <= 31:
                    day_cols[col_idx] = day_num
            except:
                pass
        
        if not day_cols:
            return pd.DataFrame()
        
        data_start = day_row_idx + 1
        records = []
        current_company = None
        current_jenis = None
        
        for i in range(data_start, len(df_raw)):
            row = df_raw.iloc[i]
            
            perusahaan = row.iloc[0] if len(row) > 0 else None
            jenis_alat = row.iloc[1] if len(row) > 1 else None
            tipe_unit = row.iloc[2] if len(row) > 2 else None
            
            if pd.notna(perusahaan):
                perusahaan_str = str(perusahaan).strip()
                if 'total' in perusahaan_str.lower():
                    continue
                current_company = perusahaan_str
            
            if pd.notna(jenis_alat):
                jenis_str = str(jenis_alat).strip()
                if 'total' not in jenis_str.lower():
                    current_jenis = jenis_str
            
            if pd.isna(tipe_unit) or not current_company:
                continue
            
            unit_str = str(tipe_unit).strip()
            if unit_str.lower() in ['nan', '', 'none'] or 'total' in unit_str.lower():
                continue
            
            for col_idx, day_num in day_cols.items():
                try:
                    val = row.iloc[col_idx]
                    if pd.notna(val):
                        l_per_jam = float(val)
                        if l_per_jam > 0:  # Only store positive FC values
                            try:
                                tanggal = datetime(year, month_int, day_num).date()
                            except ValueError:
                                continue
                            
                            records.append({
                                'Perusahaan': current_company,
                                'Jenis_Alat': current_jenis or 'Unknown',
                                'Tipe_Unit': unit_str,
                                'Tanggal': tanggal,
                                'L_per_Jam': l_per_jam,
                                'Bulan': month_name,
                                'Tahun': year
                            })
                except:
                    pass
        
        if records:
            df = pd.DataFrame(records)
            print(f"[FC Parser] Parsed {len(df)} records from sheet '{target_sheet}'")
            return df
        
        return pd.DataFrame()
        
    except Exception as e:
        print(f"[FC Parser] Error: {e}")
        return pd.DataFrame()


# ============================================================
# 9. SOLAR REFUELING PARSER (Solar Excel -> Sheet PENGISIAN)
# ============================================================
# Structure (very wide - 7 sub-columns per day):
#   Row 4: (empty) | Perusahaan | Jenis Alat | Tipe Unit | Day1 | ... | ... | ... | ... | ... | ... | Day2 | ...
#   Row 5: (empty) | (empty)    | (empty)    | (empty)   | PENGISIAN (LITER) | ... 
#   Row 6: (empty) | (empty)    | (empty)    | (empty)   | P | HM | S | HM | L/Jam | Jam Operasi | Liter | P | HM | ...
#   Row 7+: Data

def parse_solar_refueling(source, month_key, year=2026):
    """
    Parse PENGISIAN (refueling detail) sheet.
    Returns DataFrame: [Perusahaan, Jenis_Alat, Tipe_Unit, Tanggal, Shift, HM_Value, Liter, L_per_Jam, Jam_Operasi, Bulan, Tahun]
    """
    from config.settings import SOLAR_MONTH_NAMES
    
    try:
        month_name = SOLAR_MONTH_NAMES.get(month_key, "Unknown")
        month_int = int(month_key)
        
        try:
            xls = pd.ExcelFile(source, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            xls = pd.ExcelFile(source)
        
        if 'PENGISIAN' not in xls.sheet_names:
            return pd.DataFrame()
        
        df_raw = pd.read_excel(xls, sheet_name='PENGISIAN', header=None)
        
        if df_raw.empty or len(df_raw) < 8:
            return pd.DataFrame()
        
        # Find day-number row (Row 4 typically)
        day_row_idx = None
        for i in range(min(10, len(df_raw))):
            row_vals = df_raw.iloc[i].values[4:]  # Skip first 4 cols
            nums = []
            for v in row_vals[:20]:
                try:
                    n = int(float(v))
                    nums.append(n)
                except:
                    pass
            if len(nums) >= 2 and 1 in nums and 2 in nums:
                day_row_idx = i
                break
        
        if day_row_idx is None:
            day_row_idx = 4
        
        # Build day-column mapping
        # Each day has 7 sub-columns: P, HM, S, HM, L/Jam, Jam Operasi, Liter
        COLS_PER_DAY = 7
        day_start_cols = {}  # day_num -> start_col_index
        
        for col_idx in range(4, len(df_raw.columns)):
            val = df_raw.iloc[day_row_idx, col_idx]
            try:
                day_num = int(float(val))
                if 1 <= day_num <= 31:
                    day_start_cols[day_num] = col_idx
            except:
                pass
        
        if not day_start_cols:
            return pd.DataFrame()
        
        # Data starts from row after sub-headers (row 6 = column names, row 7 = data)
        data_start = day_row_idx + 3  # Skip day row, "PENGISIAN" row, column names row
        
        records = []
        current_company = None
        current_jenis = None
        
        for i in range(data_start, len(df_raw)):
            row = df_raw.iloc[i]
            
            perusahaan = row.iloc[1] if len(row) > 1 else None
            jenis_alat = row.iloc[2] if len(row) > 2 else None
            tipe_unit = row.iloc[3] if len(row) > 3 else None
            
            if pd.notna(perusahaan):
                perusahaan_str = str(perusahaan).strip()
                if 'total' in perusahaan_str.lower():
                    continue
                current_company = perusahaan_str
            
            if pd.notna(jenis_alat):
                jenis_str = str(jenis_alat).strip()
                if 'total' not in jenis_str.lower():
                    current_jenis = jenis_str
            
            if pd.isna(tipe_unit) or not current_company:
                continue
            
            unit_str = str(tipe_unit).strip()
            if unit_str.lower() in ['nan', '', 'none'] or 'total' in unit_str.lower():
                continue
            
            # Extract data for each day
            for day_num, start_col in day_start_cols.items():
                try:
                    tanggal = datetime(year, month_int, day_num).date()
                except ValueError:
                    continue
                
                # Sub-columns: P(0), HM(1), S(2), HM(3), L/Jam(4), Jam Operasi(5), Liter(6)
                def safe_float(idx):
                    try:
                        v = row.iloc[idx]
                        return float(v) if pd.notna(v) else None
                    except:
                        return None
                
                p_val = safe_float(start_col)      # P (Pagi liter)
                hm_p = safe_float(start_col + 1)   # HM Pagi
                s_val = safe_float(start_col + 2)   # S (Sore liter)
                hm_s = safe_float(start_col + 3)    # HM Sore
                l_per_jam = safe_float(start_col + 4)
                jam_operasi = safe_float(start_col + 5)
                total_liter = safe_float(start_col + 6)
                
                # GATEKEEPER: Only process this day if total_liter > 0
                # This prevents formula artifacts from unfilled days
                # appearing in the dashboard (matches production behavior)
                if total_liter is None or total_liter <= 0:
                    continue
                
                # Detect metric type: LV, Scania, Strada use L/Km; others use L/Jam
                def _is_lkm_unit(name):
                    name_upper = name.upper()
                    lkm_keywords = ['LV ', 'LV)', 'SCANIA', 'STRADA', 'PICK UP', 'PICKUP']
                    return any(kw in name_upper for kw in lkm_keywords)
                
                metric_type = 'L/Km' if _is_lkm_unit(unit_str) else 'L/Jam'
                
                # Record Pagi shift if data exists
                if p_val is not None and p_val != 0:
                    records.append({
                        'Perusahaan': current_company,
                        'Jenis_Alat': current_jenis or 'Unknown',
                        'Tipe_Unit': unit_str,
                        'Tanggal': tanggal,
                        'Shift': 'P',
                        'HM_Value': hm_p,
                        'Liter': p_val,
                        'L_per_Jam': l_per_jam,
                        'Jam_Operasi': jam_operasi,
                        'Bulan': month_name,
                        'Tahun': year,
                        'Metric_Type': metric_type
                    })
                
                # Record Sore shift if data exists
                if s_val is not None and s_val != 0:
                    records.append({
                        'Perusahaan': current_company,
                        'Jenis_Alat': current_jenis or 'Unknown',
                        'Tipe_Unit': unit_str,
                        'Tanggal': tanggal,
                        'Shift': 'S',
                        'HM_Value': hm_s,
                        'Liter': s_val,
                        'L_per_Jam': l_per_jam,
                        'Jam_Operasi': jam_operasi,
                        'Bulan': month_name,
                        'Tahun': year,
                        'Metric_Type': metric_type
                    })
        
        if records:
            df = pd.DataFrame(records)
            
            # ========================================
            # DATA NORMALIZATION
            # ========================================
            # 1. Filter out non-data rows (summary/flowmeter rows)
            SKIP_COMPANIES = {
                'SHIFT 1', 'SHIFT 2', 'SHIET 2', 'Total Pemakaian',
                'Flow Meter MS 18', 'Flowmeter MS 20',
            }
            df = df[~df['Perusahaan'].isin(SKIP_COMPANIES)]
            
            # 2. Normalize Perusahaan names
            COMPANY_MAP = {
                'PT. KEPSINDO': 'PT KEPSINDO',
                'PT. EKG': 'PT EKG',
                'PT. NJA': 'PT NJA',
                'PT. LTU': 'PT LTU',
                'PT. UTSG': 'PT UTSG',
                'PT. DAHANA': 'PT DAHANA',
                'PT. WBS': 'PT WBS',
            }
            df['Perusahaan'] = df['Perusahaan'].replace(COMPANY_MAP)
            
            # 3. Normalize Jenis Alat (title case, merge variants)
            JENIS_MAP = {
                'Alat muat': 'Alat Muat',
                'ALAT BANTU': 'Alat Bantu',
                'ALAT MUAT': 'Alat Muat',
                'ALAT ANGKUT': 'Alat Angkut',
                'Sarana Operasional': 'Sarana Operasi',
            }
            df['Jenis_Alat'] = df['Jenis_Alat'].replace(JENIS_MAP)
            
            # 4. Filter rows where Tipe_Unit contains 'total' or 'shift'
            mask = ~df['Tipe_Unit'].str.lower().str.contains(
                'total|shift|flowmeter|flow meter', na=False)
            df = df[mask]
            
            print(f"[Refueling Parser] Parsed {len(df)} records from PENGISIAN")
            return df
        
        return pd.DataFrame()
        
    except Exception as e:
        print(f"[Refueling Parser] Error: {e}")
        return pd.DataFrame()


def extract_day1_hm(source):
    """
    Extract HM values for Day 1 of a month from the PENGISIAN sheet.
    Returns dict: { unit_name: hm_pagi_value }
    Used for cross-month bridging: the Day 1 HM of month N+1 is needed
    to calculate Jam_Operasi on the last day of month N.
    """
    try:
        try:
            xls = pd.ExcelFile(source, engine='openpyxl')
        except:
            if hasattr(source, 'seek'): source.seek(0)
            xls = pd.ExcelFile(source)

        if 'PENGISIAN' not in xls.sheet_names:
            return {}

        df_raw = pd.read_excel(xls, sheet_name='PENGISIAN', header=None)
        if df_raw.empty or len(df_raw) < 8:
            return {}

        # Find day row
        day_row_idx = 4
        for i in range(min(10, len(df_raw))):
            row_vals = df_raw.iloc[i].values[4:]
            nums = []
            for v in row_vals[:20]:
                try:
                    nums.append(int(float(v)))
                except:
                    pass
            if len(nums) >= 2 and 1 in nums and 2 in nums:
                day_row_idx = i
                break

        # Find day 1 column
        day1_col = None
        for col_idx in range(4, len(df_raw.columns)):
            try:
                if int(float(df_raw.iloc[day_row_idx, col_idx])) == 1:
                    day1_col = col_idx
                    break
            except:
                pass

        if day1_col is None:
            return {}

        # Extract HM_Pagi (index +1) for each unit on Day 1
        hm_map = {}
        data_start = day_row_idx + 2  # typically row after sub-headers

        SKIP_KW = {'total', 'shift', 'flowmeter', 'flow meter'}

        for r in range(data_start, len(df_raw)):
            unit = df_raw.iloc[r, 3]
            if pd.isna(unit):
                continue
            unit_str = str(unit).strip()
            if any(kw in unit_str.lower() for kw in SKIP_KW):
                continue
            if not unit_str:
                continue

            # Get HM_Pagi (sub-col index 1) for day 1
            try:
                hm_p = df_raw.iloc[r, day1_col + 1]
                if pd.notna(hm_p):
                    hm_val = float(hm_p)
                    if hm_val > 0:
                        hm_map[unit_str] = hm_val
            except:
                pass

        return hm_map

    except Exception as e:
        print(f"[extract_day1_hm] Error: {e}")
        return {}

