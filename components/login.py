# ============================================================
# LOGIN - Authentication Components
# ============================================================

import streamlit as st
from config import USERS, verify_password
from utils.helpers import get_logo_base64


def login(username, password):
    """Authenticate user with hashed password"""
    if username in USERS:
        user = USERS[username]
        if verify_password(password, user.get('password_hash', '')):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = user['role']
            st.session_state.name = user['name']
            return True
    return False


def logout():
    """Logout user"""
    for key in ['logged_in', 'username', 'role', 'name']:
        st.session_state[key] = None if key != 'logged_in' else False


def show_login():
    """Render login page"""
    
    # Force hide sidebar completely on login page
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                display: none !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    logo_base64 = get_logo_base64()
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        # Logo section
        if logo_base64:
            logo_html = f'<img src="data:image/jpeg;base64,{logo_base64}" alt="Logo" style="width:100px; height:auto; margin-bottom:1rem; border-radius:16px; box-shadow: 0 8px 32px rgba(212,168,75,0.3);">'
        else:
            logo_html = '<div class="login-logo-icon">⛏️</div>'
        
        st.markdown(f"""
        <div class="login-container">
            <div class="login-card">
                <div class="login-logo">
                    {logo_html}
                    <h1 class="login-title">Mining Dashboard</h1>
                    <p class="login-subtitle">Semen Padang Operations Center</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            st.markdown("##### 👤 Username")
            username = st.text_input("Username", label_visibility="collapsed", placeholder="Enter username")
            
            st.markdown("##### 🔒 Password")
            password = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Enter password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.form_submit_button("🚀 Sign In", use_container_width=True, type="primary"):
                if login(username, password):
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
                    
    # --- GHOSTING FIX: Login Trailing Padding ---
    # When a user logs out from a long dashboard page, Streamlit might retain
    # the trailing elements of the dashboard beneath the login widget.
    # This padding ensures the DOM is fully overwritten with empty slots.
    for _ in range(25):
        st.empty()
        

