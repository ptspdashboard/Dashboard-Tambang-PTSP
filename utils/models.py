from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, Text, BigInteger
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

# 1. PRODUCTION (Produksi_UTSG_Harian.xlsx)
class ProductionLog(Base):
    __tablename__ = 'production_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, index=True, nullable=False) # 'Date'
    time = Column(String(50))                       # 'Time'
    shift = Column(Integer, default=1)              # 'Shift'
    blok = Column(String(100))                      # 'BLOK'
    front = Column(String(100))                     # 'Front'
    commodity = Column(String(100))                 # 'Commodity' (Fixed typo)
    excavator = Column(String(100))                 # 'Excavator'
    dump_truck = Column(String(100))                # 'Dump Truck'
    dump_loc = Column(String(100))                  # 'Dump Loc'
    rit = Column(Integer, default=0)                # 'Rit'
    tonnase = Column(Float, default=0.0)             # 'Tonnase'
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ProductionLog(date={self.date}, dt={self.dump_truck}, rit={self.rit})>"


# 2. DOWNTIME / GANGGUAN (Gangguan_Produksi.xlsx)
class DowntimeLog(Base):
    __tablename__ = 'downtime_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tanggal = Column(Date, index=True, nullable=False) # 'Tanggal'
    shift = Column(String(50))                         # 'Shift'
    start = Column(String(50))                         # 'Start'
    end = Column(String(50))                           # 'End'
    durasi = Column(Float, default=0.0)                # 'Durasi'
    
    crusher = Column(String(100))                      # 'Crusher'
    alat = Column(String(100))                         # 'Alat'
    remarks = Column(Text)                             # 'Remarks'
    kelompok_masalah = Column(String(255))             # 'Kelompok Masalah'
    gangguan = Column(Text)                            # 'Gangguan'
    
    info_ccr = Column(Text)                            # 'Info CCR'
    sub_komponen = Column(String(255))                 # 'Sub Komponen'
    keterangan = Column(Text)                          # 'Keterangan'
    penyebab = Column(Text)                            # 'Penyebab'
    identifikasi_masalah = Column(Text)                # 'Identifikasi Masalah'
    
    action = Column(Text)                              # 'Action'
    plan = Column(Text)                                # 'Plan'
    pic = Column(String(100))                          # 'PIC'
    status = Column(String(100))                       # 'Status'
    due_date = Column(String(100))                     # 'Due Date'
    spare_part = Column(Text)                          # 'Spare Part'
    info_spare_part = Column(Text)                     # 'Info Spare Part'
    link_lampiran = Column(Text)                       # 'Link/Lampiran'
    extra = Column(Text)                               # 'Extra'
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DowntimeLog(tangal={self.tanggal}, alat={self.alat}, masalah={self.gangguan})>"


# 3. STOCKPILE (Monitoring.xlsx -> Sheet Stockpile Hopper)
class StockpileLog(Base):
    __tablename__ = 'stockpile_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, index=True, nullable=False)    # 'Date'
    time = Column(String(50))                          # 'Time' (Now String "13:00-14:00")
    shift = Column(Integer, default=1)                 # 'Shift'
    dumping = Column(String(100), nullable=True)       # 'Dumping'
    unit = Column(String(100), nullable=True)          # 'Unit'
    ritase = Column(Float, default=0.0)                # 'Ritase'
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<StockpileLog(date={self.date}, time={self.time}, rit={self.ritase})>"


# 4. SHIPPING (Monitoring.xlsx -> Sheet TONASE Pengiriman)
class ShippingLog(Base):
    __tablename__ = 'shipping_logs'

    id = Column(Integer, primary_key=True)
    tanggal = Column(Date)                              # 'Tanggal' (Matched to Excel)
    shift = Column(Integer)                            # 'Shift'
    ap_ls = Column(Float, default=0.0)                 # 'AP_LS'
    ap_ls_mk3 = Column(Float, default=0.0)             # 'AP_LS_MK3'
    ap_ss = Column(Float, default=0.0)                 # 'AP_SS'
    total_ls = Column(Float, default=0.0)              # 'Total_LS'
    total_ss = Column(Float, default=0.0)              # 'Total SS'
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ShippingLog(date={self.tanggal}, total_ls={self.total_ls})>"

# 5. DAILY PLAN (DAILY_PLAN.xlsx)
class DailyPlanLog(Base):
    __tablename__ = 'daily_plan_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    hari = Column(String(20))                          # 'Hari' (New)
    tanggal = Column(Date, index=True, nullable=False) # 'Tanggal'
    shift = Column(String(50))                         # 'Shift'
    
    # Target / Plan Numeric Columns
    batu_kapur = Column(Float, default=0.0)
    silika = Column(Float, default=0.0)
    clay = Column(Float, default=0.0)
    # timbunan column removed per user spec
    
    alat_muat = Column(Text)
    alat_angkut = Column(Text)
    blok = Column(String(100))
    grid = Column(String(100))
    rom = Column(String(100))
    keterangan = Column(Text)
    
    # Distinction between Plan and Realisasi? 
    # Usually they are similar structures. For now assuming this covers the main "Scheduling" or "Realisasi"
    # To keep it simple, we use one generic table, or maybe type column?
    # User's code loads 'Scheduling' and 'W22 Realisasi'. 
    # Let's add a 'type' column to distinguish Schema vs Realisasi if needed.
    # For now, adhering to load_daily_plan columns.
    
    created_at = Column(DateTime, default=datetime.utcnow)

# 6. TARGET LOGS (From Analisa Produksi)
class TargetLog(Base):
    __tablename__ = 'target_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, index=True, nullable=False)    # 'Date'
    plan = Column(Float, default=0.0)                  # 'Plan' (Target Production)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TargetLog(date={self.date}, plan={self.plan})>"

# 7. SYSTEM LOGS (For Sync Status)
class SystemLog(Base):
    __tablename__ = 'system_logs'
    
    key = Column(String(50), primary_key=True)   # e.g., 'last_sync'
    value = Column(String(255))                  # e.g., '2026-02-09 17:00'
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemLog({self.key}={self.value})>"

# ============================================================
# 8. SOLAR REFUELING (Single source of truth for all solar data)
# ============================================================
# Replaces 3 old tables (solar_daily, fuel_efficiency, solar_refueling)
# All KPIs (total liter, L/Jam, shift breakdown) derived from this table.
class SolarRefueling(Base):
    __tablename__ = 'solar_refueling'

    id = Column(Integer, primary_key=True, autoincrement=True)
    perusahaan = Column(String(100))
    jenis_alat = Column(String(100))
    tipe_unit = Column(String(150))
    tanggal = Column(Date, index=True)
    bulan = Column(String(20))
    tahun = Column(Integer)
    shift = Column(String(10))        # 'P' (Pagi), 'S' (Sore)
    hm_value = Column(Float, nullable=True)
    liter = Column(Float, default=0.0)
    l_per_jam = Column(Float, nullable=True)     # L/Jam for heavy equipment, L/Km for LV/Scania
    jam_operasi = Column(Float, nullable=True)   # Jam for heavy equipment, Km for LV/Scania
    metric_type = Column(String(10), default='L/Jam')  # 'L/Jam' or 'L/Km'

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SolarRefueling(date={self.tanggal}, unit={self.tipe_unit}, shift={self.shift})>"

