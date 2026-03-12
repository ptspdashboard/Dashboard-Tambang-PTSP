import pandas as pd
import streamlit as st
import traceback
from datetime import datetime
from config.settings import ONEDRIVE_LINKS
from utils.network import download_from_onedrive
from utils.parsers import (
    parse_shipping_data, 
    parse_daily_plan_data, 
    parse_stockpile_hopper, 
    parse_production_data, 
    parse_downtime_data, 
    parse_target_data,
    parse_solar_refueling,
    extract_day1_hm
)
from utils.models import (
    ShippingLog, 
    DailyPlanLog, 
    StockpileLog, 
    ProductionLog, 
    DowntimeLog, 
    TargetLog,
    SolarRefueling
)
from utils.db_manager import get_db_engine
from sqlalchemy.orm import sessionmaker

# ==============================================================================
# HELPERS
# ==============================================================================

def format_time_val(val):
    if pd.isna(val): return None
    s = str(val).strip()
    if ' ' in s:
        try:
            dt = pd.to_datetime(s)
            return dt.strftime('%H:%M:%S')
        except: pass
    return s

def filter_records_by_year(records, date_attr='date', year=2026):
    """Filter list of objects/dicts by year"""
    filtered = []
    cutoff = datetime(year, 1, 1).date()
    
    for r in records:
        val = getattr(r, date_attr, None)
        if isinstance(val, (datetime, pd.Timestamp)):
            val = val.date()
            
        if val and val >= cutoff:
            filtered.append(r)
            
    return filtered

# ==============================================================================
# PERIOD-BASED SYNC CONFIGURATION
# ==============================================================================
SYNC_PERIOD_DAYS = 30  # Only sync last 30 days (keeps sync time constant)

def filter_records_by_period(records, date_attr='date', days=SYNC_PERIOD_DAYS):
    """Filter records to only include last N days"""
    from datetime import timedelta
    filtered = []
    cutoff = (datetime.now() - timedelta(days=days)).date()
    
    for r in records:
        val = getattr(r, date_attr, None)
        if isinstance(val, (datetime, pd.Timestamp)):
            val = val.date()
        elif isinstance(val, str):
            try:
                val = pd.to_datetime(val).date()
            except:
                continue
            
        if val and val >= cutoff:
            filtered.append(r)
            
    return filtered

def safe_bulk_insert_report(session, model_class, records, label="Data", date_column='date'):
    """
    FULL SYNC: Delete ALL data and insert ALL records.
    This ensures 100% data accuracy - any changes in Excel will be reflected.
    
    Trade-off: Slightly slower as data grows, but guaranteed accuracy.
    """
    if not records:
        return f"⚠️ {label}: Empty (No Data in Excel)"
    
    try:
        # Delete ALL records (Full Replace)
        session.query(model_class).delete()
        
        # Insert all records
        session.bulk_save_objects(records)
        session.commit()
        
        return f"✅ {label}: Success ({len(records)} rows synced)"
    except Exception as e:
        session.rollback()
        return f"❌ {label}: Error ({str(e)[:50]})"

# ==============================================================================
# MAIN SYNC FUNCTION
# ==============================================================================

def sync_all_data():
    """
    Synchronize ALL data from OneDrive to Database.
    Returns a dictionary of status strings.
    """
    status_report = {}
    
    engine = get_db_engine()
    if not engine:
        return {"ERROR": "Database Connection Failed"}
        
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. PRODUCTION
    try:
        source_prod = download_from_onedrive(ONEDRIVE_LINKS['produksi'])
        if source_prod:
            df_prod = parse_production_data(source_prod)
            if not df_prod.empty:
                records_prod = []
                for _, row in df_prod.iloc[::-1].iterrows():
                    kwargs = {
                        'date': row['Date'],
                        'shift': int(float(str(row['Shift']).lower().replace('shift', '').strip())) if pd.notna(row['Shift']) else 1,
                        'time': str(row['Time']) if pd.notna(row['Time']) else None,
                        'excavator': str(row['Excavator']) if pd.notna(row['Excavator']) else None,
                        'commodity': str(row['Commodity']) if 'Commodity' in row and pd.notna(row['Commodity']) else None,
                        'dump_truck': str(int(float(row['Dump Truck']))) if pd.notna(row['Dump Truck']) and str(row['Dump Truck']).replace('.0','').isdigit() else str(row['Dump Truck']) if pd.notna(row['Dump Truck']) else None,
                        'rit': int(row['Rit']) if pd.notna(row['Rit']) else 0,
                        'tonnase': float(row['tonnase']) if 'tonnase' in row and pd.notna(row['tonnase']) else float(row['Tonase']) if pd.notna(row['Tonase']) else 0.0,
                        'front': str(row['Front']) if pd.notna(row['Front']) else None,
                        'dump_loc': str(row['Dump Loc']) if pd.notna(row['Dump Loc']) else None,
                        'blok': str(row['BLOK']) if 'BLOK' in row and pd.notna(row['BLOK']) else None,
                    }
                    records_prod.append(ProductionLog(**kwargs))
                
                records_prod = filter_records_by_year(records_prod, 'date', 2026)
                status_report['Produksi'] = safe_bulk_insert_report(session, ProductionLog, records_prod, "Production", date_column='date')
            else:
                status_report['Produksi'] = "⚠️ Empty Data"
        else:
             status_report['Produksi'] = "❌ Download Failed"
    except Exception as e:
        status_report['Produksi'] = f"❌ Error: {str(e)[:50]}"

    # 2. SHIPPING & STOCKPILE (Monitoring.xlsx)
    try:
        source_mon = download_from_onedrive(ONEDRIVE_LINKS['monitoring'])
        if source_mon:
            # Shipping
            df_ship = parse_shipping_data(source_mon)
            if not df_ship.empty:
                records = []
                for _, row in df_ship.iloc[::-1].iterrows():
                    rec = ShippingLog(
                        tanggal=row['Date'],
                        shift=int(row['Shift']),
                        ap_ls=float(row['AP_LS']),
                        ap_ls_mk3=float(row['AP_LS_MK3']),
                        ap_ss=float(row['AP_SS']),
                        total_ls=float(row['Total_LS']),
                        total_ss=float(row['Total_SS'])
                    )
                    records.append(rec)
                records = filter_records_by_year(records, 'tanggal', 2026)
                status_report['Shipping'] = safe_bulk_insert_report(session, ShippingLog, records, "Shipping", date_column='tanggal')
            else:
                status_report['Shipping'] = "⚠️ Empty Data"

            # Stockpile
            if hasattr(source_mon, 'seek'): source_mon.seek(0)
            df_stock = parse_stockpile_hopper(source_mon)
            if not df_stock.empty:
                records_st = []
                for _, row in df_stock.iloc[::-1].iterrows():
                    rec = StockpileLog(
                        date=row['Tanggal'],
                        time=str(row['Jam']),
                        shift=int(row['Shift']) if pd.notna(row['Shift']) else 1,
                        dumping=str(row['Loader']) if 'Loader' in row else None,
                        unit=str(row['Unit']) if 'Unit' in row else None,
                        ritase=float(row['Ritase']) if 'Ritase' in row else 0.0
                    )
                    records_st.append(rec)
                records_st = filter_records_by_year(records_st, 'date', 2026)
                status_report['Stockpile'] = safe_bulk_insert_report(session, StockpileLog, records_st, "Stockpile", date_column='date')
            else:
                 status_report['Stockpile'] = "⚠️ Empty Data"
                 
            # Targets
            if hasattr(source_mon, 'seek'): source_mon.seek(0)
            df_tgt = parse_target_data(source_mon)
            if not df_tgt.empty:
                records_tgt = []
                for _, row in df_tgt.iterrows():
                    rec = TargetLog(date=row['Date'], plan=row['Plan'])
                    records_tgt.append(rec)
                records_tgt = filter_records_by_year(records_tgt, 'date', 2026)
                status_report['Targets'] = safe_bulk_insert_report(session, TargetLog, records_tgt, "Targets", date_column='date')
            else:
                status_report['Targets'] = "⚠️ Empty Data"

        else:
             status_report['Monitoring'] = "❌ Download Failed"
    except Exception as e:
        status_report['Monitoring'] = f"❌ Error: {str(e)[:50]}"

    # 3. DAILY PLAN
    try:
        source_dp = download_from_onedrive(ONEDRIVE_LINKS['daily_plan'])
        if source_dp:
            df_dp = parse_daily_plan_data(source_dp)
            if not df_dp.empty:
                records_dp = []
                days_map = {
                    'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu',
                    'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'
                }
                for _, row in df_dp.iloc[::-1].iterrows():
                    hari_val = row['Hari'] if 'Hari' in row else None
                    if pd.notna(hari_val):
                        try:
                            dt_hari = pd.to_datetime(hari_val)
                            day_eng = dt_hari.day_name()
                            hari_val = days_map.get(day_eng, day_eng)
                        except: hari_val = str(hari_val)
                    else:
                        try:
                            dt_tgl = pd.to_datetime(row['Tanggal'])
                            day_eng = dt_tgl.day_name()
                            hari_val = days_map.get(day_eng, day_eng)
                        except: hari_val = None
                        
                    kwargs = {
                        'tanggal': row['Tanggal'],
                        'hari': hari_val,
                        'shift': str(row['Shift']) if 'Shift' in row and pd.notna(row['Shift']) else None,
                        'batu_kapur': float(row['Batu Kapur']) if 'Batu Kapur' in row else 0,
                        'silika': float(row['Silika']) if 'Silika' in row else 0,
                        'clay': float(row['Clay']) if 'Clay' in row else 0,
                        'alat_muat': str(row['Alat Muat']) if 'Alat Muat' in row else None,
                        'alat_angkut': str(row['Alat Angkut']) if 'Alat Angkut' in row else None,
                        'blok': str(row['Blok']) if 'Blok' in row else None,
                        'grid': str(row['Grid']) if 'Grid' in row else None,
                        'rom': str(row['ROM']) if 'ROM' in row else None,
                        'keterangan': str(row['Keterangan']) if 'Keterangan' in row else None,
                    }
                    records_dp.append(DailyPlanLog(**kwargs))
                    
                records_dp = filter_records_by_year(records_dp, 'tanggal', 2026)
                status_report['Daily Plan'] = safe_bulk_insert_report(session, DailyPlanLog, records_dp, "Daily Plan", date_column='tanggal')
            else:
                status_report['Daily Plan'] = "⚠️ Empty Data"
        else:
             status_report['Daily Plan'] = "❌ Download Failed"
    except Exception as e:
        status_report['Daily Plan'] = f"❌ Error: {str(e)[:50]}"

    # 4. DOWNTIME
    try:
        source_dt = download_from_onedrive(ONEDRIVE_LINKS['gangguan'])
        if source_dt:
            df_dt = parse_downtime_data(source_dt)
            if not df_dt.empty:
                records_dt = []
                for _, row in df_dt.iloc[::-1].iterrows():
                    kwargs = {
                        'tanggal': row['Tanggal'],
                        'shift': str(row['Shift']) if pd.notna(row['Shift']) else None,
                        'start': format_time_val(row['Start']),
                        'end': format_time_val(row['End']),
                        'durasi': round(float(row['Durasi']), 2) if pd.notna(row['Durasi']) else 0.0,
                        'gangguan': str(row['Gangguan']) if pd.notna(row['Gangguan']) else None,
                        'alat': str(row['Alat']) if pd.notna(row['Alat']) else None,
                        'kelompok_masalah': str(row['Kelompok Masalah']) if pd.notna(row['Kelompok Masalah']) else None,
                        'info_ccr': str(row['Info CCR']) if pd.notna(row['Info CCR']) else None,
                        'remarks': str(row['Remarks']) if pd.notna(row['Remarks']) else None,
                        'penyebab': str(row['Penyebab']) if pd.notna(row['Penyebab']) else None,
                        'action': str(row['Action']) if pd.notna(row['Action']) else None,
                        'status': str(row['Status']) if pd.notna(row['Status']) else None,
                        'crusher': str(row['Crusher']) if pd.notna(row['Crusher']) else None,
                        'sub_komponen': str(row['Sub Komponen']) if pd.notna(row['Sub Komponen']) else None,
                        'keterangan': str(row['Keterangan']) if pd.notna(row['Keterangan']) else None,
                        'identifikasi_masalah': str(row['Identifikasi Masalah']) if pd.notna(row['Identifikasi Masalah']) else None,
                        'plan': str(row['Plan']) if pd.notna(row['Plan']) else None,
                        'pic': str(row['PIC']) if pd.notna(row['PIC']) else None,
                        'due_date': str(row['Due Date']) if pd.notna(row['Due Date']) else None,
                        'spare_part': str(row['Spare Part']) if pd.notna(row['Spare Part']) else None,
                        'info_spare_part': str(row['Info Spare Part']) if pd.notna(row['Info Spare Part']) else None,
                        'link_lampiran': str(row['Link/Lampiran']) if pd.notna(row['Link/Lampiran']) else None,
                        'extra': str(row['Extra']) if pd.notna(row['Extra']) else None
                    }
                    records_dt.append(DowntimeLog(**kwargs))
                    
                records_dt = filter_records_by_year(records_dt, 'tanggal', 2026)
                status_report['Downtime'] = safe_bulk_insert_report(session, DowntimeLog, records_dt, "Downtime", date_column='tanggal')
            else:
                 status_report['Downtime'] = "⚠️ Empty Data"
        else:
             status_report['Downtime'] = "❌ Download Failed"
    except Exception as e:
        status_report['Downtime'] = f"❌ Error: {str(e)[:50]}"

    # 5. SOLAR / BBM — Single table: SolarRefueling (from PENGISIAN sheet)
    try:
        from config.settings import SOLAR_LINKS
        import calendar
        
        all_refueling_records = []
        # Store downloaded sources for cross-month bridging
        # { month_int: source_bytesio }
        downloaded_sources = {}
        sorted_periods = sorted(SOLAR_LINKS.keys())  # e.g. ['2026-01', '2026-02', '2026-03']
        
        for month_period in sorted_periods:
            link = SOLAR_LINKS[month_period]
            if not link:
                continue
            try:
                year_str, month_key = month_period.split('-')
                year = int(year_str)
                month_int = int(month_key)
                
                source_solar = download_from_onedrive(link)
                if not source_solar:
                    status_report[f'Solar {month_period}'] = "❌ Download Failed"
                    continue
                
                # Store for bridging
                downloaded_sources[month_int] = source_solar
                
                # Parse PENGISIAN only (single source of truth)
                df_ref = parse_solar_refueling(source_solar, month_key, year)
                if not df_ref.empty:
                    for _, row in df_ref.iterrows():
                        if pd.notna(row.get('Tanggal')) and float(row.get('Liter', 0)) != 0:
                            all_refueling_records.append(SolarRefueling(
                                perusahaan=str(row['Perusahaan']),
                                jenis_alat=str(row['Jenis_Alat']),
                                tipe_unit=str(row['Tipe_Unit']),
                                tanggal=row['Tanggal'],
                                bulan=str(row['Bulan']),
                                tahun=int(row['Tahun']),
                                shift=str(row.get('Shift', '')),
                                hm_value=float(row['HM_Value']) if pd.notna(row.get('HM_Value')) else None,
                                liter=float(row['Liter']),
                                l_per_jam=float(row['L_per_Jam']) if pd.notna(row.get('L_per_Jam')) else None,
                                jam_operasi=float(row['Jam_Operasi']) if pd.notna(row.get('Jam_Operasi')) else None,
                                metric_type=str(row.get('Metric_Type', 'L/Jam'))
                            ))
                
                ref_count = len(df_ref) if not df_ref.empty else 0
                status_report[f'Solar {month_period}'] = f"✅ {ref_count} records from PENGISIAN"
            except Exception as e:
                status_report[f'Solar {month_period}'] = f"❌ Error: {str(e)[:50]}"
        
        # ========================================
        # CROSS-MONTH BRIDGE: Fill Jam_Operasi and L/Jam for last day of each month
        # ========================================
        bridge_count = 0
        month_ints = sorted(downloaded_sources.keys())
        
        for i, m in enumerate(month_ints):
            if i + 1 >= len(month_ints):
                break  # No next month available
            
            next_m = month_ints[i + 1]
            year_for_m = 2026  # Hardcoded for now
            last_day = calendar.monthrange(year_for_m, m)[1]
            last_date = datetime(year_for_m, m, last_day).date()
            
            # Extract Day 1 HM from next month
            next_source = downloaded_sources[next_m]
            if hasattr(next_source, 'seek'):
                next_source.seek(0)
            day1_hm = extract_day1_hm(next_source)
            
            if not day1_hm:
                continue
            
            # Find records on last_date that are missing jam_operasi
            for rec in all_refueling_records:
                if rec.tanggal != last_date:
                    continue
                if rec.jam_operasi is not None and rec.jam_operasi > 0:
                    continue  # Already has data
                if rec.hm_value is None:
                    continue  # No HM to bridge with
                
                unit = rec.tipe_unit
                next_hm = day1_hm.get(unit)
                if next_hm is None:
                    continue
                
                # Calculate Jam Operasi = HM(Day1 next month) - HM(last day)
                jam_op = next_hm - rec.hm_value
                if jam_op > 0 and jam_op < 24:  # Sanity: max 24 hours in a day
                    rec.jam_operasi = round(jam_op, 2)
                    if rec.liter and rec.liter > 0:
                        rec.l_per_jam = round(rec.liter / jam_op, 2)
                    bridge_count += 1
        
        if bridge_count > 0:
            print(f"[Bridge] Fixed {bridge_count} records at month boundaries")
        
        # Bulk insert refueling (single table)
        if all_refueling_records:
            status_report['Solar Refueling'] = safe_bulk_insert_report(
                session, SolarRefueling, all_refueling_records, "Solar Refueling", date_column='tanggal'
            )
    except Exception as e:
        status_report['Solar'] = f"❌ Error: {str(e)[:50]}"
    
    # 5. SAVE SYNC TIME TO DATABASE (PERSISTENT LOG)
    try:
        from utils.models import SystemLog
        
        # Check if key exists
        log_entry = session.query(SystemLog).filter_by(key='last_sync').first()
        import pytz
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        current_time_str = datetime.now(jakarta_tz).strftime("%H:%M")
        
        if log_entry:
            log_entry.value = current_time_str
        else:
            log_entry = SystemLog(key='last_sync', value=current_time_str)
            session.add(log_entry)
            
        session.commit()
    except Exception as e:
        print(f"Failed to log sync time: {e}")

    session.close()
    return status_report
