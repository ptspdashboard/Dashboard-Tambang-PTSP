# ============================================================
# STYLES - CSS Styling untuk Dashboard
# ============================================================

import streamlit as st

def inject_css():
    """Inject professional mining dashboard CSS"""
    st.markdown("""
<style>
/* ===== IMPORTS ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ===== ROOT VARIABLES ===== */
:root {
    --bg-primary: #0a1628;
    --bg-secondary: #0f2744;
    --bg-card: #122a46;
    --bg-card-hover: #1a3a5c;
    --accent-gold: #d4a84b;
    --accent-gold-light: #e8c97a;
    --accent-blue: #3b82f6;
    --accent-green: #10b981;
    --accent-red: #ef4444;
    --accent-orange: #f59e0b;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --border-color: #1e3a5f;
    --shadow: 0 4px 24px rgba(0,0,0,0.4);
}

/* ===== GLOBAL STYLES ===== */
.stApp {
    background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
    font-family: 'Inter', -apple-system, sans-serif;
}

/* Hide default streamlit elements */
#MainMenu, footer {visibility: hidden;}
header[data-testid="stHeader"], [data-testid="stHeader"], .stAppToolbar, [data-testid="stToolbar"], .stDecoration {
    visibility: hidden !important;
    display: none !important;
}
.block-container {padding: 1rem 2rem 2rem 2rem !important; max-width: 100% !important;}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #071020 0%, #0a1628 100%);
    border-right: 1px solid var(--border-color);
}
section[data-testid="stSidebar"] .block-container {padding: 1rem !important;}

/* Sidebar buttons */
section[data-testid="stSidebar"] button {
    background: transparent !important;
    border: 1px solid transparent !important;
    color: var(--text-secondary) !important;
    text-align: left !important;
    transition: all 0.2s ease !important;
    border-radius: 8px !important;
    margin: 2px 0 !important;
}
section[data-testid="stSidebar"] button:hover {
    background: var(--bg-card) !important;
    border-color: var(--border-color) !important;
    color: var(--text-primary) !important;
}
section[data-testid="stSidebar"] button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent-gold) 0%, #b8942f 100%) !important;
    color: #0a1628 !important;
    font-weight: 600 !important;
    border: none !important;
}

/* ===== TYPOGRAPHY ===== */
h1, h2, h3, h4 {color: var(--text-primary) !important; font-weight: 600 !important;}

.page-header {
    background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-secondary) 100%);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.page-header-icon {
    width: 56px;
    height: 56px;
    background: linear-gradient(135deg, var(--accent-gold) 0%, #b8942f 100%);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.75rem;
}
.page-header-text h1 {
    margin: 0 !important;
    font-size: 1.75rem !important;
    background: linear-gradient(90deg, var(--text-primary) 0%, var(--accent-gold-light) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.page-header-text p {
    margin: 0.25rem 0 0 0;
    color: var(--text-secondary);
    font-size: 0.9rem;
}

/* ===== KPI CARDS ===== */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.kpi-card {
    background: linear-gradient(145deg, var(--bg-card) 0%, var(--bg-secondary) 100%);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 1.25rem;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background: var(--card-accent, var(--accent-gold));
}
.kpi-card:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow);
    border-color: var(--card-accent, var(--accent-gold));
}
.kpi-icon {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
    opacity: 0.9;
}
.kpi-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 500;
    margin-bottom: 0.25rem;
}
.kpi-value {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
}
.kpi-subtitle {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
}
.kpi-trend {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    margin-top: 0.5rem;
}
.kpi-trend.up {background: rgba(16,185,129,0.15); color: var(--accent-green);}
.kpi-trend.down {background: rgba(239,68,68,0.15); color: var(--accent-red);}

/* ===== CHART CONTAINER ===== */
.chart-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}
.chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-color);
}
.chart-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.chart-badge {
    background: var(--accent-gold);
    color: var(--bg-primary);
    font-size: 0.65rem;
    font-weight: 600;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    text-transform: uppercase;
}

/* ===== SECTION DIVIDER ===== */
.section-divider {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 2rem 0 1.5rem 0;
}
.section-divider-line {
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, var(--border-color) 0%, transparent 100%);
}
.section-divider-text {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--accent-gold);
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ===== LOGIN PAGE ===== */
.login-container {
    max-width: 420px;
    margin: 0 auto;
    padding: 2rem;
}
.login-card {
    background: linear-gradient(145deg, var(--bg-card) 0%, var(--bg-secondary) 100%);
    border: 1px solid var(--border-color);
    border-radius: 24px;
    padding: 2.5rem;
    box-shadow: var(--shadow);
}
.login-logo {
    text-align: center;
    margin-bottom: 2rem;
}
.login-logo-icon {
    width: 80px;
    height: 80px;
    background: linear-gradient(135deg, var(--accent-gold) 0%, #b8942f 100%);
    border-radius: 20px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 2.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 8px 32px rgba(212,168,75,0.3);
}
.login-title {
    font-size: 1.75rem;
    font-weight: 700;
    background: linear-gradient(90deg, var(--text-primary) 0%, var(--accent-gold-light) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.login-subtitle {
    color: var(--text-secondary);
    font-size: 0.9rem;
    margin-top: 0.5rem;
}

/* ===== USER CARD (Sidebar) ===== */
.user-card {
    background: linear-gradient(145deg, var(--bg-card) 0%, rgba(212,168,75,0.1) 100%);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 1.25rem;
    text-align: center;
    margin-bottom: 1.5rem;
}
.user-avatar {
    width: 64px;
    height: 64px;
    background: linear-gradient(135deg, var(--accent-gold) 0%, #b8942f 100%);
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.75rem;
    margin-bottom: 0.75rem;
    box-shadow: 0 4px 16px rgba(212,168,75,0.3);
}
.user-name {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
}
.user-role {
    font-size: 0.75rem;
    color: var(--accent-gold);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 0.25rem;
}

/* ===== STATUS INDICATOR ===== */
.status-grid {
    display: grid;
    gap: 0.5rem;
    margin-bottom: 1rem;
}
.status-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
    font-size: 0.8rem;
}
.status-name {color: var(--text-secondary);}
.status-value {font-weight: 500;}
.status-ok {color: var(--accent-green);}
.status-warn {color: var(--accent-orange);}
.status-err {color: var(--accent-red);}

/* ===== NAV LABEL ===== */
.nav-label {
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
    margin: 1rem 0 0.5rem 0.5rem;
}

/* ===== STREAMLIT OVERRIDES ===== */
div[data-testid="stMetric"] {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 1rem;
}
div[data-testid="stMetric"] label {color: var(--text-muted) !important; font-size: 0.8rem !important;}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {color: var(--text-primary) !important; font-size: 1.5rem !important;}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background: var(--bg-secondary);
    padding: 0.5rem;
    border-radius: 12px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 8px;
    color: var(--text-secondary);
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    background: var(--bg-card) !important;
    color: var(--accent-gold) !important;
}

/* Selectbox & Inputs */
div[data-baseweb="select"] > div {
    background: var(--bg-secondary) !important;
    border-color: var(--border-color) !important;
    border-radius: 8px !important;
}
div[data-baseweb="input"] > div {
    background: var(--bg-secondary) !important;
    border-color: var(--border-color) !important;
}
input {color: var(--text-primary) !important;}

/* Dataframe */
.stDataFrame {border-radius: 12px; overflow: hidden;}

/* Expander */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border-radius: 8px !important;
}

/* ===== NATIVE BORDER CONTAINER REPLACEMENT ===== */
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlock"][style*="border"], 
div.element-container:has(> iframe[title="stream"]) {   
    /* VISIBLE CONTRAST CARD STYLE */
    background: linear-gradient(145deg, #1c2e4a 0%, #16253b 100%) !important; /* Lighter than main BG */
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 16px !important;
    padding: 1.25rem !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5) !important;
    margin-bottom: 1rem !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:hover,
div[data-testid="stVerticalBlock"][style*="border"]:hover {
    border-color: rgba(255, 255, 255, 0.3) !important;
    background: linear-gradient(145deg, #233554 0%, #1c2e4a 100%) !important; /* Even lighter on hover */
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.6) !important;
    transition: all 0.3s ease !important;
}

/* Ensure Charts are visible on top of this background */
div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {
    background: transparent !important;
}

/* ===== MOBILE RESPONSIVENESS (MAX-WIDTH: 640px) ===== */
@media only screen and (max-width: 640px) {
    /* 1. Reduce Global Padding */
    .block-container {
        padding: 1rem 0.5rem 2rem 0.5rem !important; /* Much tighter padding */
    }
    
    /* 2. Page Header Stacking */
    .page-header {
        flex-direction: column;
        text-align: center;
        padding: 1rem;
        gap: 0.5rem;
    }
    .page-header-icon {
        margin: 0 auto; /* Center icon */
    }
    .page-header-text h1 {
        font-size: 1.5rem !important; /* Smaller Title */
    }
    
    /* 3. KPI Grid - Single Column or 2-up */
    .kpi-grid {
        grid-template-columns: repeat(2, 1fr) !important; /* Force 2 columns on mobile */
        gap: 0.5rem !important;
    }
    .kpi-card {
        padding: 0.75rem !important;
        min-height: auto !important;
    }
    .kpi-value {
        font-size: 1.25rem !important; /* Smaller value text */
    }
    .kpi-icon {
        font-size: 1.25rem !important;
    }
    .kpi-label {
        font-size: 0.65rem !important;
    }
    
    /* 4. Chart Containers */
    .chart-container {
        padding: 0.75rem !important;
    }
    .chart-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }
    
    /* 5. Hide auxiliary elements if needed */
    .section-divider {
        margin: 1.5rem 0 1rem 0;
    }

    /* 6. Tabs Scrollable */
    .stTabs [data-baseweb="tab-list"] {
        overflow-x: auto;
        white-space: nowrap;
        padding-bottom: 0.5rem;
    }
}
</style>
""", unsafe_allow_html=True)
