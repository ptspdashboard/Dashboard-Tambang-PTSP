# ============================================================
# DAILY PLAN - Interactive Mining Map Visualization
# ============================================================
# Displays daily plan from Excel with excavator positions on satellite map
# Layout matches reference image: map + data table + legend

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import os
import base64
from PIL import Image

# Import grid coordinates
try:
    from config.grid_coords import get_grid_position, get_zone_color, MAP_WIDTH, MAP_HEIGHT
except ImportError:
    MAP_WIDTH, MAP_HEIGHT = 1400, 990
    def get_grid_position(g, b=None): return None
    def get_zone_color(b): return '#00BFFF'

# Import settings
try:
    from config.settings import CACHE_TTL
except ImportError:
    CACHE_TTL = 300

# Import data loader
from utils.data_loader import load_daily_plan

# File paths
ONEDRIVE_FILE = r"C:\Users\user\OneDrive\Dashboard_Tambang\DAILY_PLAN.xlsx"

try:
    from config.settings import ASSETS_DIR
    MAP_IMAGE_PATH = str(ASSETS_DIR / "peta_grid_tambang_opt.jpg")
except ImportError:
    # Fallback for local testing if config missing
    MAP_IMAGE_PATH = "assets/peta_grid_tambang_opt.jpg"

# ============================================================
# DATA LOADER
# ============================================================

# Redundant local loader removed - using centralized loader
def load_daily_plan_data():
    return load_daily_plan()



@st.cache_data(ttl=3600*24) # Cache image for 24 hours
def get_image_base64(image_path):
    """Convert image to base64 for Plotly"""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None


# ============================================================
# MAP VISUALIZATION HELPERS
# ============================================================

def resolve_location_id(row):
    """
    Centralized logic to resolve Location ID from Grid/Blok.
    Used by both Map Plotting and KPI Calculation to ensure consistency.
    """
    grid = str(row['Grid']).strip() if pd.notna(row['Grid']) else ''
    blok = str(row['Blok']).strip().upper() if pd.notna(row['Blok']) else ''
    
    # Normalize Blok for comparison (remove spaces)
    blok_clean = blok.replace(' ', '').replace('-', '').upper()
    
    # Rule: Blok SP6 / SP 6 overrides Grid choice -> Maps to K3
    # Match SP6, STOCKPILE6, etc.
    if 'SP6' in blok_clean or 'STOCKPILE6' in blok_clean:
        return 'K3'
        
    # Rule: Blok SP3 / SP 3 overrides -> Maps to SP3 (Top Left)
    if 'SP3' in blok_clean or 'STOCKPILE3' in blok_clean:
        return 'SP3'
    
    # Rule: Jika Grid terisi -> lokasi_id = Grid
    if grid and grid.lower() != 'nan':
        return grid
    
    # Rule: Jika Grid kosong dan Blok terisi -> lokasi_id = Blok
    if blok and blok.lower() != 'nan':
        return blok
    
    return None

# ============================================================
# MAP VISUALIZATION
# ============================================================

@st.cache_data(ttl=CACHE_TTL)
def create_mining_map(df_filtered, selected_date, selected_shifts_label):
    """
    Create the mining map with strict logic matching user requirements:
    1. Filter: Must have Tanggal, Shift, Alat Muat, Alat Angkut, ROM, and (Grid or Blok)
    2. Location: Grid > Blok. Custom: SP6 (no grid) -> Top Left, SP3 -> K3
    3. Grouping: Same Location, Equipment, ROM -> Merge Shifts
    4. Format: 3 lines (Equipment, Shift, ROM) in Blue Box
    """
    
    # Get image as base64
    img_base64 = get_image_base64(MAP_IMAGE_PATH)
    
    if not img_base64:
        st.error("Gagal memuat gambar peta.")
        return go.Figure()
    
    # Create figure
    fig = go.Figure()
    
    # Add background map image
    fig.add_layout_image(
        dict(
            source=f"data:image/jpeg;base64,{img_base64}",
            xref="x",
            yref="y",
            x=0,
            y=MAP_HEIGHT,
            sizex=MAP_WIDTH,
            sizey=MAP_HEIGHT,
            sizing="stretch",
            opacity=1,
            layer="below"
        )
    )
    
    # ------------------------------------------------------------
    # 1. LOAD DATA (REMOVED REDUNDANT LOAD & UI SIDE EFFECTS)
    # ----------------------------------------
    # Data is already passed via df_filtered argument.
    # UI elements (st.caption, st.expander) removed from cached function.
    
    mask = (
        df_filtered['Tanggal'].notna() &
        df_filtered['Shift'].notna() & df_filtered['Shift'].astype(str).str.strip().ne('') &
        df_filtered['Alat Muat'].notna() &
        df_filtered['Alat Angkut'].notna() &
        df_filtered['ROM'].notna() &
        (df_filtered['Grid'].notna() | df_filtered['Blok'].notna())
    )
    df_map = df_filtered[mask].copy()
    
    if df_map.empty:
        return fig

    # ------------------------------------------------------------
    # 2. DETERMINE LOCATION ID (MAPPING)
    # ------------------------------------------------------------
    # Logic moved to global helper resolve_location_id for consistency with KPIs

    df_map['lokasi_id'] = df_map.apply(resolve_location_id, axis=1)

    # Remove rows where location couldn't be resolved
    df_map = df_map[df_map['lokasi_id'].notna()]

    # ------------------------------------------------------------
    # 3. GROUPING
    # ------------------------------------------------------------
    # Group fields
    group_cols = ['lokasi_id', 'Alat Muat', 'Alat Angkut']
    if 'Tanggal' in df_map.columns:
         group_cols.insert(0, 'Tanggal')

    # Aggregation: Shift AND ROM -> Combine unique sorted
    grouped = df_map.groupby(group_cols).agg({
        'Shift': 'unique',
        'ROM': 'unique'
    }).reset_index()

    # ------------------------------------------------------------
    # 4. PLOTTING & FORMATTING
    # ------------------------------------------------------------
    
    # Store all annotations to perform collision adjustment
    annotations = []
    
    # COLOR SETTING: Lighter Blue (Reverted)
    BOX_COLOR = '#00BFFF' 
    
    for _, row in grouped.iterrows():
        loc_id = row['lokasi_id']
        alat_muat = row['Alat Muat']
        alat_angkut = row['Alat Angkut']
        rom_list = row['ROM'] # Now an array/list
        shifts = row['Shift']
        
        # Get Coordinates
        x, y = None, None
        
        # SP3 Logic: If loc_id is strictly SP3, use specific coordinates
        if loc_id == 'SP3':
            # SP3 in Top Left Corner - Hardcode if get_grid_position doesn't handle it
            pos = get_grid_position(loc_id, loc_id)
            if pos:
                x, y = pos
            else:
                 # Fallback for SP3 if not in config: Top Left corner near N8 area
                 x, y = 100, 100 
        else:
            # Use standard mapping
            pos = get_grid_position(loc_id)
            if pos:
                x, y = pos
        
        if x is None or y is None:
            continue
            
        # Flip Y for plotting (Map coords usually origin top-left, Plotly origin bottom-left)
        # Assuming MAP_HEIGHT is correct height
        y_plot = MAP_HEIGHT - y
        
        # Format Text
        # Line 1: <Alat Muat> + <Alat Angkut>
        line1 = f"<b>{alat_muat} + {alat_angkut}</b>"
        
        # Line 2: Shift <hasil gabungan>
        try:
            sorted_shifts = sorted(shifts, key=lambda x: int(str(x)) if str(x).isdigit() else str(x))
        except:
            sorted_shifts = sorted(shifts.astype(str))
            
        shift_str = " & ".join([str(s) for s in sorted_shifts])
        line2 = f"Shift {shift_str}"
        
        # Line 3: LS> <ROM> (Combined)
        valid_roms = [str(r) for r in rom_list if pd.notna(r) and str(r).strip() not in ['', 'nan', 'None']]
        unique_roms = sorted(list(set(valid_roms)))
        rom_str = " & ".join(unique_roms)
        line3 = f"LS> {rom_str}"
        
        # Combined Box Text
        box_text = f"{line1}<br>{line2}<br>{line3}"
        
        annotations.append({
            'x': x,
            'y': y_plot,
            'text': box_text,
            'loc_id': loc_id,
            'color': BOX_COLOR 
        })

    # COLLISION AVOIDANCE ALGORITHM (SPIRAL GREEDY SEARCH V3 - USABLE AREA)
    # ---------------------------------------------------------------------
    # 1. Flexible Spiral Search for Label Boxes
    # 2. Strict Usable Area Clamping (Exclude Legend/Borders)
    # 3. Enhanced Channel Allocator for Leader Lines (Anti-Overlap)
    
    # Define USABLE MAP AREA (Estimate from image)
    # Legend is on Right side. Bottom has labels.
    # Map Width 1400. Legend seems to take ~300px.
    USABLE_MIN_X = 50
    USABLE_MAX_X = MAP_WIDTH - 350 # Increased margin to avoid Legend
    USABLE_MIN_Y = 50
    USABLE_MAX_Y = MAP_HEIGHT - 60
    
    annotations.sort(key=lambda k: (-k['y'], k['x']))
    
    placed_boxes = [] # List of {x, y, w, h}
    
    # Parameters
    BOX_W = 150 
    BOX_H = 110 
    
    # Helper: Absolute Boundary Clamp
    def safe_clamp(val, min_val, max_val):
        return max(min_val, min(max_val, val))

    # Helper: Check collision
    def check_collision(cx, cy, boxes):
        # Strict margin check against USABLE AREA
        margin_w = BOX_W/2 + 10
        margin_h = BOX_H/2 + 10
        
        if cx < USABLE_MIN_X + margin_w or cx > USABLE_MAX_X - margin_w: return True
        if cy < USABLE_MIN_Y + margin_h or cy > USABLE_MAX_Y - margin_h: return True
        
        # Check vs other boxes
        for b in boxes:
            pad = 40  # Increased to 40 for better separation (prevent overlapping)
            if (abs(cx - b['x']) * 2 < (BOX_W + b['w'] + pad) and 
                abs(cy - b['y']) * 2 < (BOX_H + b['h'] + pad)):
                return True
        return False

    # Helper: Check if a line segment from (x1,y1) to (x2,y2) intersects a box
    def line_intersects_box(x1, y1, x2, y2, bx, by, bw, bh, pad=10):
        """Check if line segment crosses through a placed box (with padding)."""
        # Box boundaries with padding
        left = bx - bw/2 - pad
        right = bx + bw/2 + pad
        top = by + bh/2 + pad
        bottom = by - bh/2 - pad
        
        # Quick reject: both endpoints on same side of box
        if max(x1, x2) < left or min(x1, x2) > right: return False
        if max(y1, y2) < bottom or min(y1, y2) > top: return False
        
        # Check if line segment intersects any of the 4 box edges
        # Using parametric line intersection
        dx = x2 - x1
        dy = y2 - y1
        
        # Check intersections with vertical edges (left, right)
        for edge_x in [left, right]:
            if abs(dx) > 0.001:
                t = (edge_x - x1) / dx
                if 0 <= t <= 1:
                    iy = y1 + t * dy
                    if bottom <= iy <= top:
                        return True
        
        # Check intersections with horizontal edges (top, bottom)
        for edge_y in [bottom, top]:
            if abs(dy) > 0.001:
                t = (edge_y - y1) / dy
                if 0 <= t <= 1:
                    ix = x1 + t * dx
                    if left <= ix <= right:
                        return True
        
        return False

    # Helper: Check if the L-shaped manifold path crosses any placed box
    def trunk_crosses_boxes(tx, ty, cx, cy, boxes, placed_trunks):
        """
        Check if the L-shaped leader line path from target dot to label box
        crosses other boxes. The actual path is:
          1. Horizontal trunk: (tx, ty) -> (cx, ty)  [or bus_x approximation]
          2. Vertical segment: (cx, ty) -> (cx, cy)
        Also checks if existing trunks from already-placed labels would cross
        through this new candidate box position.
        """
        visual_bw = 110  # must match visual_box_w used in rendering
        bus_off = 20
        
        # Approximate the bus_x position for the candidate
        if cx > tx:  # Box is Right of Target
            approx_bus_x = cx - visual_bw/2 - bus_off
        else:  # Box is Left of Target
            approx_bus_x = cx + visual_bw/2 + bus_off
        
        # Segment 1: Horizontal trunk from target to bus_x
        # Segment 2: Vertical from bus_x at target's Y to box's Y
        for b in boxes:
            # Check horizontal trunk segment against each placed box
            if line_intersects_box(tx, ty, approx_bus_x, ty, b['x'], b['y'], b['w'], b['h'], pad=12):
                return True
            # Check vertical segment against each placed box
            if line_intersects_box(approx_bus_x, ty, approx_bus_x, cy, b['x'], b['y'], b['w'], b['h'], pad=12):
                return True
        
        # Also check: would existing placed trunks cross through this NEW candidate box?
        cand_w = BOX_W
        cand_h = BOX_H
        for trunk in placed_trunks:
            # Check existing horizontal trunk against candidate box
            if line_intersects_box(trunk['tx'], trunk['ty'], trunk['bus_x'], trunk['ty'],
                                   cx, cy, cand_w, cand_h, pad=12):
                return True
            # Check existing vertical segment against candidate box
            if line_intersects_box(trunk['bus_x'], trunk['ty'], trunk['bus_x'], trunk['cy'],
                                   cx, cy, cand_w, cand_h, pad=12):
                return True
        
        return False
    
    # Track placed trunk lines for bi-directional collision checks
    placed_trunks = []

    # GROUPING BY TARGET LOCATION (Aligned Stacking)
    # ----------------------------------------------
    grouped_annotations = {}
    for ann in annotations:
        key = (ann['x'], ann['y'])
        if key not in grouped_annotations:
            grouped_annotations[key] = []
        grouped_annotations[key].append(ann)
    
    final_placements = []
    
    # Sort groups by Y (top to bottom) then X for consistent placement order
    sorted_keys = sorted(grouped_annotations.keys(), key=lambda k: (-k[1], k[0]))
    
    for key in sorted_keys:
        group_anns = grouped_annotations[key]
        item_count = len(group_anns)
        
        t_x, t_y = key
        
        # Calculate "Mega Box" dimensions (Vertical Stack)
        STACK_PAD = 5  # Reduced gap for tighter stacking
        total_h = item_count * BOX_H + (item_count - 1) * STACK_PAD
        
        # Spiral Radii - Expanded to find more space
        radii = [90, 100, 115, 130, 160, 200, 250, 320, 400, 500, 600, 700]
        
        # Determine logical center
        usable_center_x = (USABLE_MIN_X + USABLE_MAX_X) / 2
        
        # Angles Logic
        # User requested Priority: LEFT.
        # UPDATED: Split based on Map Center (approx 450px threshold).
        # - Left of 450 -> Go Left.
        # - Right of 450 -> Go Right.
        
        if t_x > 450: 
            # Right side of map -> Go Right
            angles = [0, 30, 330, 60, 300, 90, 270, 180]
        else:
            # Left side of map -> Go Left
            angles = [180, 150, 210, 120, 240, 90, 270, 0]
            
        full_angles = angles
        

        
        # Check overrides (use first item's loc_id)
        first_ann = group_anns[0]
        loc_id = first_ann.get('loc_id')
        
        if loc_id == 'SP3': full_angles = [180, 150, 210] 
        if loc_id == 'N8': full_angles = [60, 120, 90]   # N8 Bottom/Side (Avoid 90 to prevent line overlap)
        if loc_id == 'E5': full_angles = [180, 150, 210] # E5 Left
        if loc_id == 'D6': full_angles = [0, 30, 330]    # D6 Right 
        if loc_id == 'K3': full_angles = [180, 150, 210] # K3 Left 
        if loc_id == 'M10': full_angles = [0, 30, 330]   # M10 Right (Requested)
        if loc_id == 'F5': full_angles = [0, 30, 330, 90, 270, 60, 300] # F5 Right + Vertical (closer options)
        if loc_id == 'J5': full_angles = [0, 30, 330, 90, 270, 60, 300] # J5 Right + Vertical (closer options)
        
        best_x, best_y = t_x, t_y
        found = False
        import math
        
        # Search placement for the MEGA BOX
        for r in radii:
            for angle_deg in full_angles:
                angle_rad = math.radians(angle_deg)
                c_x = t_x + r * math.cos(angle_rad)
                c_y = t_y + r * math.sin(angle_rad)
                
                # Check collision for MEGA BOX
                collision = False
                
                # Usable Area Check
                margin_w = BOX_W/2 + 10
                margin_h_total = total_h/2 + 10
                
                if c_x < USABLE_MIN_X + margin_w or c_x > USABLE_MAX_X - margin_w: collision = True
                if c_y < USABLE_MIN_Y + margin_h_total or c_y > USABLE_MAX_Y - margin_h_total: collision = True
                
                if not collision:
                    for b in placed_boxes:
                        pad = 15 # Reduced to 15 for tighter vertical stacking (was 50)
                        
                        dist_x = abs(c_x - b['x']) * 2
                        dist_y = abs(c_y - b['y']) * 2
                        sum_w = BOX_W + b['w'] + pad
                        sum_h = total_h + b['h'] + pad
                        
                        if dist_x < sum_w and dist_y < sum_h:
                            collision = True
                            break
                
                # Also check if L-shaped trunk line would cross through any placed box
                if not collision:
                    if trunk_crosses_boxes(t_x, t_y, c_x, c_y, placed_boxes, placed_trunks):
                        collision = True
                
                if not collision:
                    best_x, best_y = c_x, c_y
                    found = True
                    break
            if found: break
        
        # Fallback
        if not found:
            dir_to_center = 1 if t_x < usable_center_x else -1
            dir_y = 0
            
            # OVERRIDE FALLBACK DIRECTIONS
            if loc_id == 'K3': dir_to_center = -0.75 # Increased from -0.5 to ensure space for Line Trunk
            if loc_id == 'E5': dir_to_center = -1
            if loc_id == 'D6': dir_to_center = 1
            if loc_id == 'M10': dir_to_center = 1
            if loc_id == 'N8': 
                dir_to_center = 0.2 # Slight right
                dir_y = 1 # Force Down
            
            best_x = t_x + (dir_to_center * 150)
            best_y = t_y + (dir_y * 100) # Apply Y offset
            
            # Safe Clamp
            margin_w = BOX_W/2 + 5
            margin_h_total = total_h/2 + 5
            min_x_constraint = USABLE_MIN_X
            if loc_id == 'K3': min_x_constraint = 5 # Relax constraint further
            
            best_x = safe_clamp(best_x, min_x_constraint + margin_w, USABLE_MAX_X - margin_w)
            best_y = safe_clamp(best_y, USABLE_MIN_Y + margin_h_total, USABLE_MAX_Y - margin_h_total)

        # Register MEGA BOX to collision list
        placed_boxes.append({'x': best_x, 'y': best_y, 'w': BOX_W, 'h': total_h})
        
        # Record trunk geometry for future bi-directional collision checks
        visual_bw = 110
        bus_off = 20
        if best_x > t_x:
            rec_bus_x = best_x - visual_bw/2 - bus_off
        else:
            rec_bus_x = best_x + visual_bw/2 + bus_off
        placed_trunks.append({'tx': t_x, 'ty': t_y, 'bus_x': rec_bus_x, 'cy': best_y})
        
        # UNPACK Individual Boxes
        start_y = best_y + (total_h / 2) - (BOX_H / 2)
        
        for i, ann in enumerate(group_anns):
            item_y = start_y - i * (BOX_H + STACK_PAD)
            final_placements.append({
                'ann': ann,
                'x': best_x,
                'y': item_y,
                'tx': t_x,
                'ty': t_y,
                'is_grouped': len(group_anns) > 1,
                'group_role': 'top' if i == 0 else 'member', # Tag role if needed
                'group_x': best_x # Shared axis
            })

    # MANIFOLD / BUS ROUTER
    # -----------------------
    # Matches user preference: Target -> Horizontal Trunk -> Vertical Bus -> Horizontal Branches -> Boxes
    # The Bus is offset from the boxes to create a clear "forking" visual.
    
    # Identify Stacks
    stacks = {} # Key: x_coord -> [placements]
    for p in final_placements:
        k = p['x']
        if k not in stacks: stacks[k] = []
        stacks[k].append(p)
        
    visual_box_w = 110
    visual_box_h = 70
        
    for stack_x, items in stacks.items():
        if not items: continue
        
        first = items[0]
        tx, ty = first['tx'], first['ty']
        
        # Determine Box Anchor X (Side of box facing target)
        # And Bus X (The vertical line position)
        BUS_OFFSET = 20 # Distance from box side to vertical bus
        MIN_TRUNK = 15  # Minimum length of trunk from dot
        
        if stack_x > tx: # Stack is Right of Target
            anchor_x = stack_x - visual_box_w/2 # Box Left Side
            bus_x = anchor_x - BUS_OFFSET       # Bus is to the Left of Box
            
            # Enforce Minimum Trunk Length
            if bus_x < tx + MIN_TRUNK:
                bus_x = tx + MIN_TRUNK
            
        else: # Stack is Left of Target
            anchor_x = stack_x + visual_box_w/2 # Box Right Side
            bus_x = anchor_x + BUS_OFFSET       # Bus is to the Right of Box
            
            # Enforce Minimum Trunk Length (to the Left)
            if bus_x > tx - MIN_TRUNK:
                bus_x = tx - MIN_TRUNK
            
        # Draw Lines
        is_multi = len(items) > 1
        
        # Determine Vertical Extent of Bus
        y_coords = [p['y'] for p in items]
        
        # If SINGLE item, we still want the "Manifold" look if requested, 
        # or simplified? User image shows multi-branch.
        # Even for single item, T -> Bus -> Box looks "Technical".
        # Let's use the same logic for consistency.
        
        # Bus Top/Bottom should cover all branches + maybe connect to Trunk.
        # Trunk connects at Target Y level.
        
        min_y = min(y_coords + [ty])
        max_y = max(y_coords + [ty])
        
        # Actually, Bus should go from min(BranchYs) to max(BranchYs)?
        # And Trunk connects to Bus at ty?
        # Yes.
        
        # But if ty is outside the range of branches, the bus needs to extend to ty.
        # So Bus Range = [min(ys + [ty]), max(ys + [ty])]
        
        bus_top = max(y_coords + [ty])
        bus_bottom = min(y_coords + [ty])
        
        # 1. TRUNK: Target -> Bus (Horizontal)
        path_trunk = f"M {tx},{ty} L {bus_x},{ty}"
        
        # 2. BUS: Vertical Line
        path_bus = f"M {bus_x},{bus_top} L {bus_x},{bus_bottom}"
        
        # 3. BRANCHES: Bus -> Box Anchor (Horizontal) (For each item)
        path_branches = ""
        for p in items:
            iy = p['y']
            path_branches += f" M {bus_x},{iy} L {anchor_x},{iy}"
            
        full_path = path_trunk + " " + path_bus + " " + path_branches
        
        # Draw Shape
        fig.add_shape(
            type="path", path=full_path,
            line=dict(color=first['ann']['color'], width=2), layer="above"
        )

        # Draw Boxes & Dots
        for p in items:
            ann = p['ann']
            fig.add_annotation(
                x=p['x'], y=p['y'], text=ann['text'],
                showarrow=False, bgcolor=ann['color'], 
                bordercolor='white', borderwidth=1, borderpad=4,
                font=dict(size=9, color='black', family='Arial, sans-serif'), 
                opacity=0.9, width=visual_box_w
            )
            
        # Target Dot
        fig.add_trace(go.Scatter(
            x=[tx], y=[ty], mode='markers',
            marker=dict(size=12, color=items[0]['ann']['color'], line=dict(color='white', width=2)),
            showlegend=False, hoverinfo='skip'
        ))
    
    # Configure layout
    fig.update_layout(
        xaxis=dict(range=[-20, MAP_WIDTH + 20], showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(range=[-20, MAP_HEIGHT + 20], showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
        margin=dict(l=0, r=0, t=0, b=0),
        height=1000,
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        dragmode='pan'
    )
    
    return fig


def create_data_table(df_filtered):
    """Create data table with ALL columns from Excel"""
    # Only keep relevant columns and formatting
    cols = ['Hari', 'Tanggal', 'Shift', 'Batu Kapur', 'Silika', 'Clay', 'Alat Muat', 'Alat Angkut', 'Blok', 'Grid', 'ROM', 'Keterangan']
    # Filter columns that exist
    cols = [c for c in cols if c in df_filtered.columns]
    
    display_df = df_filtered[cols].copy()
    
    # Format date
    if 'Tanggal' in display_df.columns:
        display_df['Tanggal'] = pd.to_datetime(display_df['Tanggal']).dt.strftime('%d-%m-%Y')
        
    return display_df


def show_daily_plan():
    # ... header setup ...
    st.markdown("""
    <style>
    .date-header {
        font-size: 24px;
        font-weight: bold;
        color: white;
        text-align: center;
        background: #1a1a2e;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
        border: 1px solid #333;
    }
    </style>
    """, unsafe_allow_html=True)
    
    active_filters = {}
    
    # Load data
    df = load_daily_plan_data()
    if df is None:
        st.error("Gagal memuat data Daily Plan.")
        return

    # Sidebar Filters (Re-integrated cleanly if needed, assuming existing code handles it)
    # ...
    
    # Processing Logic (Simplified for replacement context)
    # ...
    # Assume we have filtered df -> df_filtered, selected_date, selected_shifts etc.
    
    # For replacement, we need to match the View rendering block
    
    return # Placeholder



# ============================================================
# DATA TABLE
# ============================================================
# ... (create_data_table function stays same) ...


# ============================================================
# MAIN VIEW
# ============================================================

def show_daily_plan():
    # ... (header code same) ... 
    
    # Load data
    df = load_daily_plan_data()
    # ... (error handling same) ...
    
    # ... (header html removed or kept minimal) ...
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                padding: 20px; border-radius: 12px; margin-bottom: 20px;
                border-left: 4px solid #00D4FF;">
        <h1 style="margin: 0; color: white; font-size: 28px;">
            🗺️ Daily Plan - Peta Penambangan
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    # ... (filters code same) ... (omitted for brevity, assume filters exist)
    # Re-inserting filters section and processing logic would be huge diff
    # I will focus replacing the MAP DISPLAY part below
    
    # ... (apply filters logic same) ...



# ============================================================
# DATA TABLE
# ============================================================

def create_data_table(df_filtered):
    """Create data table with ALL columns from Excel"""
    if df_filtered.empty:
        return pd.DataFrame()
    
    # Show ALL relevant columns from Excel (using exact Excel column names)
    # Include 'id' for sorting (will be dropped after sort in show_daily_plan)
    cols_to_show = ['id', 'Hari', 'Tanggal', 'Shift', 'Batu Kapur', 'Silika', 'Clay',
                    'Alat Muat', 'Alat Angkut', 'Blok', 'Grid', 'ROM', 'Keterangan']
    
    # Only include columns that exist in dataframe
    available_cols = [col for col in cols_to_show if col in df_filtered.columns]
    display_df = df_filtered[available_cols].copy()
    
    # Format Tanggal if present
    if 'Tanggal' in display_df.columns:
        display_df['Tanggal'] = pd.to_datetime(display_df['Tanggal'], errors='coerce').dt.strftime('%Y-%m-%d')
        
    # Calculate Hari if missing (from Tanggal)
    if 'Hari' not in display_df.columns and 'Tanggal' in display_df.columns:
        try:
            day_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
            display_df['Hari'] = pd.to_datetime(display_df['Tanggal']).dt.dayofweek.map(day_map)
        except:
            pass
            
    # Format Hari (Fix for datetime appearing as 2026-01-26)
    if 'Hari' in display_df.columns:
        day_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
        def fix_hari(val):
            # Same logic as before
            if isinstance(val, (pd.Timestamp, datetime)):
                try:
                    ts = pd.Timestamp(val)
                    return day_map.get(ts.dayofweek, '')
                except:
                    return ''
            s = str(val)
            if '202' in s and '-' in s: 
                try:
                    dt = pd.to_datetime(s)
                    return day_map.get(dt.dayofweek, s)
                except:
                    return s
            return s
            
        display_df['Hari'] = display_df['Hari'].apply(fix_hari)
    
    # Format numerical columns
    for col in ['Batu Kapur', 'Silika', 'Clay']:
        if col in display_df.columns:
            # Convert to numeric and format
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce')
            # Replace NaN with empty string for display
            display_df[col] = display_df[col].apply(lambda x: '' if pd.isna(x) else f'{int(x):,}' if x == int(x) else f'{x:,.1f}')
            
    # RENAME HEADERS TO DB FORMAT (LOWERCASE) PER USER REQUEST
    # Internal logic used Title Case, but Display must be lowercase
    rename_db = {
        'Hari': 'Hari', # Keep Hari as is? Or hari? DB doesn't have Hari. Let's keep Hari Title Case as it's computed? Or User probably wants 'hari'? Let's try 'hari' for consistency.
        'Tanggal': 'tanggal',
        'Shift': 'shift',
        'Batu Kapur': 'batu_kapur',
        'Silika': 'silika',
        'Clay': 'clay',
        'Alat Muat': 'alat_muat',
        'Alat Angkut': 'alat_angkut',
        'Blok': 'blok',
        'Grid': 'grid',
        'ROM': 'rom',
        'Keterangan': 'keterangan'
    }
    display_df = display_df.rename(columns=rename_db)
    
    # RENAME HEADERS TO TITLE CASE (User Request: "Sesuai Database" structure but better display)
    header_map = {
        'hari': 'Hari',
        'tanggal': 'Tanggal',
        'shift': 'Shift',
        'batu_kapur': 'Batu Kapur',
        'silika': 'Silika',
        'clay': 'Clay',
        'alat_muat': 'Alat Muat',
        'alat_angkut': 'Alat Angkut',
        'blok': 'Blok',
        'grid': 'Grid',
        'rom': 'ROM',
        'keterangan': 'Keterangan'
    }
    display_df = display_df.rename(columns=header_map)
    
    # Sort is now handled in show_daily_plan() using ID column
    
    return display_df


# ============================================================
# MAIN VIEW
# ============================================================

def show_daily_plan():
    """Render Daily Plan Dashboard with professional multi-select filters"""
    
    # Load data
    # Load data
    df = load_daily_plan_data()
    
    if df.empty:
        st.warning("⚠️ Data Rencana Harian tidak tersedia. Pastikan file Excel ditutup.")
        # Show debug log if empty
        if 'debug_log_daily_plan' in st.session_state and st.session_state['debug_log_daily_plan']:
             with st.expander("🛠️ DEBUG DATA INFO (Klik untuk analisa)"):
                 st.code(st.session_state['debug_log_daily_plan'])
        return

    # Ensure Tanggal is datetime
    if 'Tanggal' in df.columns:
        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        
    # FIX: Calculate 'Hari' if missing (essential for Filters sidebar)
    if 'Hari' not in df.columns and 'Tanggal' in df.columns:
        day_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
        # Handle errors gracefully
        try:
             df['Hari'] = df['Tanggal'].dt.dayofweek.map(day_map).fillna('')
        except:
             df['Hari'] = ''

    # ============================================================
    # HEADER (Already rendered above, skipping re-render if not needed)
    
    # ... (skipping existing header code lines 700-741 as they are just comments/HTML) ...
    # Wait, replace_file_content replaces the chunk. I must include context carefully.
    
    # I will target lines 693 to 752 (start of available_dates).
    # But 705-737 is a huge HTML block. I should avoid replacing it if possible.
    # I will replace the top part (loading) and the line 752 separately?
    # No, I can insert the conversion right after loading.

    # Let's do a smaller replacement around line 693.

    # 1. Inspect lines near 693.
    # 693: df = load_daily_plan_data()
    # 694: 
    # 695: if df.empty:
    # ...
    
    # I will replace lines 693-698.

    
    # ============================================================
    # HEADER
    # ============================================================
    # ============================================================
    # HEADER
    # ============================================================
    st.markdown("""
    <style>
    /* FORCE OVERRIDE FOR CONTAINERS */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        /* VISIBLE CONTRAST CARD STYLE */
        background: linear-gradient(145deg, #1c2e4a 0%, #16253b 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 16px !important;
        padding: 1.25rem !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.5) !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(255, 255, 255, 0.3) !important;
        background: linear-gradient(145deg, #233554 0%, #1c2e4a 100%) !important;
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.6) !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
       pointer-events: auto; 
    }
    </style>
    
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                padding: 20px; border-radius: 12px; margin-bottom: 20px;
                border-left: 4px solid #00D4FF;">
        <h1 style="margin: 0; color: white; font-size: 28px;">
            🗺️ Daily Plan - Peta Penambangan
        </h1>
        <p style="margin: 5px 0 0 0; color: #B0B0B0; font-size: 14px;">
            Visualisasi rencana harian penambangan bahan baku
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # DEBUG: Show data sample - REMOVED per user request

    
    # ============================================================
    # FILTER: Tanggal Only
    # ============================================================
    available_dates = sorted(df['Tanggal'].dropna().dt.date.unique(), reverse=True)
    
    # Retrieve Global Filters (if any)
    global_filters = st.session_state.get('global_filters', {})
    global_date_range = global_filters.get('date_range')
    
    filter_cols = st.columns([3, 1])
    
    with filter_cols[0]:
        st.markdown("**📅 Tanggal**")
        default_date = available_dates[0] if available_dates else datetime.now().date()
        
        if global_date_range and isinstance(global_date_range, tuple) and len(global_date_range) > 1:
            target_date = global_date_range[1]
            if target_date in available_dates:
                default_date = target_date
                
        if len(available_dates) > 0:
            selected_date = st.date_input(
                "Tanggal",
                value=default_date,
                key='dp_date',
                label_visibility="collapsed"
            )
        else:
            selected_date = datetime.now().date()
    
    with filter_cols[1]:
        st.markdown("**🔄 Refresh**")
        if st.button("🔄 Refresh", use_container_width=True, key='dp_refresh'):
            st.cache_data.clear()
            st.rerun()
    
    # Set default values for removed filters (needed by downstream code)
    selected_shifts = ['Semua']
    selected_bloks = ['Semua']
    selected_grids = ['Semua']
    selected_hari = ['Semua']
    selected_alat = ['Semua']
    selected_alat_angkut = ['Semua']
    selected_rom = ['Semua']
    selected_material = ['Semua']
    
    # ============================================================
    # APPLY FILTERS
    # ============================================================
    df_filtered = df.copy()
    
    # Date filter (only active filter)
    if 'Tanggal' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Tanggal'].dt.date == selected_date]
    
    # Calculate Total Target (Ton)
    total_target = 0
    mat_cols = ['Batu Kapur', 'Silika', 'Clay']
    for col in mat_cols:
        if col in df_filtered.columns:
            total_target += pd.to_numeric(df_filtered[col], errors='coerce').fillna(0).sum()
    
    kpi_cols = st.columns(4)
    
    with kpi_cols[0]:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #00D4FF22, #00D4FF11); 
                    padding: 15px; border-radius: 10px; text-align: center;
                    border: 1px solid #00D4FF44;">
            <div style="font-size: 28px; font-weight: bold; color: #00D4FF;">{total_target:,.0f}</div>
            <div style="font-size: 12px; color: #B0B0B0;">TOTAL TARGET PRODUKSI (TON)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_cols[1]:
        active_exc = df_filtered['Alat Muat'].dropna().nunique() if 'Alat Muat' in df_filtered.columns else 0
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #FFD70022, #FFD70011); 
                    padding: 15px; border-radius: 10px; text-align: center;
                    border: 1px solid #FFD70044;">
            <div style="font-size: 28px; font-weight: bold; color: #FFD700;">{active_exc}</div>
            <div style="font-size: 12px; color: #B0B0B0;">TOTAL ALAT MUAT (UNIT)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_cols[2]:
        import re
        total_hauler = 0
        if 'Alat Angkut' in df_filtered.columns:
            for val in df_filtered['Alat Angkut'].dropna():
                match = re.match(r'^(\d+)', str(val).strip())
                if match:
                    total_hauler += int(match.group(1))
                else:
                    total_hauler += 1
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #FFA50022, #FFA50011); 
                    padding: 15px; border-radius: 10px; text-align: center;
                    border: 1px solid #FFA50044;">
            <div style="font-size: 28px; font-weight: bold; color: #FFA500;">{total_hauler}</div>
            <div style="font-size: 12px; color: #B0B0B0;">TOTAL ALAT ANGKUT (UNIT)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_cols[3]:
        active_grids = 0
        if 'Grid' in df_filtered.columns and 'Blok' in df_filtered.columns:
             df_kpi = df_filtered.copy()
             df_kpi['lokasi_id'] = df_kpi.apply(resolve_location_id, axis=1)
             active_grids = df_kpi['lokasi_id'].dropna().nunique()

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #00FF8822, #00FF8811); 
                    padding: 15px; border-radius: 10px; text-align: center;
                    border: 1px solid #00FF8844;">
            <div style="font-size: 28px; font-weight: bold; color: #00FF88;">{active_grids}</div>
            <div style="font-size: 12px; color: #B0B0B0;">TOTAL LOKASI AKTIF</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ============================================================
    # MAIN CONTENT: FULL-WIDTH MAP ON TOP, TABLE BELOW
    # ============================================================
    
    # ============================================================
    # MAIN CONTENT: DATE ON LEFT, MAP ON RIGHT (MATCHING REFERENCE)
    # ============================================================
    
    # Date formatting for display
    day_names = {
        'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu',
        'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'
    }
    month_names = {
        1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
        7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
    }
    
    day_name_en = pd.Timestamp(selected_date).strftime('%A')
    day_id = day_names.get(day_name_en, day_name_en)
    month_id = month_names.get(selected_date.month, str(selected_date.month))
    date_str = f"{selected_date.day} {month_id} {selected_date.year}"
    
    # DEBUG: Show sync info
    if 'debug_log_daily_plan' in st.session_state and st.session_state['debug_log_daily_plan']:
        with st.expander("🛠️ DEBUG DATA INFO (Klik untuk analisa)"):
            st.warning("⚠️ Jika data tidak muncul, kirimkan pesan di bawah ini ke tim developer:")
            st.code(st.session_state['debug_log_daily_plan'])
            st.divider()
            st.write(f"Total Data (Raw): {len(df)}")
            if len(df) > 0:
                st.write("5 Baris Teratas:", df.head())

    # Generate Map
    shift_label = ', '.join(selected_shifts) if len(selected_shifts) <= 3 else f"{len(selected_shifts)} shifts"
    fig = create_mining_map(df_filtered, pd.Timestamp(selected_date), shift_label)
    
    # 2-Column Layout
    with st.container(border=True):
        # DATE HEADER (Full Width Top)
        st.markdown(f"""
        <div style="background: white; border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 10px; border: 1px solid #ccc;">
            <span style="font-size: 24px; font-weight: bold; color: black; margin-right: 15px;">{day_id},</span>
            <span style="font-size: 24px; color: black;">{date_str}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # MAP (Full Width)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={
                'displayModeBar': True,
                'modeBarButtonsToRemove': ['lasso2d'], 
                'scrollZoom': False, 
                'displaylogo': False,
                'toImageButtonOptions': {
                    'format': 'jpeg',
                    'filename': f'Daily Scheduling {date_str}',
                    'height': MAP_HEIGHT,
                    'width': MAP_WIDTH,
                    'scale': 3 
                }
            })
            
            st.markdown("""
            <div style="text-align: right; color: #666; font-size: 11px; margin-top: -5px;">
                🔍 Gunakan tombol di atas kanan peta untuk Zoom/Pan | 📷 Ikon Kamera: Download PNG
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("ℹ️ Tidak ada data untuk ditampilkan pada filter yang dipilih.")
    
    # ============================================================
    # TABLE SECTION (FULL WIDTH BELOW MAP)
    # ============================================================
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                padding: 15px; border-radius: 10px; margin-bottom: 15px; margin-top: 20px;
                border-left: 4px solid #00D4FF;">
        <h3 style="margin: 0; color: white; font-size: 18px;">📋 Detail Rencana Operasi Harian</h3>
    </div>
    """, unsafe_allow_html=True)
    
    if not df_filtered.empty:
        display_df = create_data_table(df_filtered)
        
        # 1. Dashboard Display (LIFO - Latest Input/ID 1 at Top)
        if 'id' in display_df.columns:
            df_view = display_df.sort_values(by='id', ascending=True)
            df_download = display_df.sort_values(by='id', ascending=False)
            
            # Drop ID for display/download
            df_view = df_view.drop(columns=['id'])
            df_download = df_download.drop(columns=['id'])
        else:
            # Fallback
            df_view = display_df
            df_download = display_df
            
        st.dataframe(df_view, use_container_width=True, hide_index=True, height=400)
        
        # Excel Download
        from utils.helpers import convert_df_to_excel
        excel_data = convert_df_to_excel(df_download)
        
        st.download_button(
            label="📥 Unduh Data Rencana (Excel)",
            data=excel_data,
            file_name=f"PTSP_Rencana_Harian_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.info("Tidak ada data operasi untuk filter yang dipilih.")
    
    # Production targets (below table)
    # ... (Keep existing target code if needed or just end here)
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 12px;">
        Mining Dashboard v4.0 &copy; 2025 Semen Padang
    </div>
    """, unsafe_allow_html=True)
    
    # --- GHOSTING FIX: Trailing Padding ---
    # Append empty slots to overwrite any trailing DOM remnants from other longer modules
    for _ in range(25):
        st.empty()