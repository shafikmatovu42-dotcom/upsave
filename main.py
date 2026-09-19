import streamlit as st
import pandas as pd
import os
import db
import updater
from version import __version__, __repo__
from datetime import datetime
import time as tm

# Initialize Database and preserve developer account
# Existing DB is kept; schema is created if missing.
db.init_db()
db.ensure_default_developer()

# Page Setup
st.set_page_config(
    page_title="Agali Awamu | Savings Group Manager",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'selected_role' not in st.session_state:
    st.session_state.selected_role = 'user'
if 'product_key_entered' not in st.session_state:
    st.session_state.product_key_entered = False


def login_ui():
    st.markdown("<div style='padding: 1.5rem; background: #ffffff; border-radius: 18px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#0f766e; margin-bottom:0.5rem;'>Secure Login</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#475569;'>Select role to login or create an account.</p>", unsafe_allow_html=True)

    mode = st.radio("Action", ["Login", "Create account"], index=0, horizontal=True, key="login_action")

    if mode == "Create account":
        new_username = st.text_input("New username", key="new_username")
        company_name = st.text_input("Company name", key="new_company_name")
        motto = st.text_input("Company motto", key="new_motto")
        new_password = st.text_input("New password", type="password", key="new_password")
        confirm_password = st.text_input("Confirm password", type="password", key="confirm_password")
        product_key = st.text_input("Enter product key (required)", key="create_product_key")
        if st.button("✅ Create account", key="create_account_btn"):
            if not new_username or not new_password:
                st.error("Username and password are required.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif db.get_user_by_username(new_username):
                st.error("Username already exists.")
            elif not product_key:
                st.error("Product key is required to create an account.")
            elif not db.is_product_key_valid(product_key):
                st.error("Invalid or expired product key.")
            else:
                db.add_user(new_username, new_password, role='user', company_name=company_name, motto=motto)
                db.mark_product_key_verified(new_username)
                st.success("User account created and product key verified. You can now log in.")
        st.markdown("</div>", unsafe_allow_html=True)
        return False

    role = st.selectbox("Login as", ["user", "developer"], index=0, key="login_role")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("🔐 Login", key="login_btn"):
        user = db.authenticate_user(username, password)
        if not user:
            st.error("Invalid username or password.")
        elif user['role'] != role:
            st.error("Selected role does not match user role.")
        else:
            st.session_state.logged_in = True
            st.session_state.current_user = user
            st.success(f"Welcome {user['username']}!")
            return False

    st.markdown("</div>", unsafe_allow_html=True)
    return False


def developer_panel():
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("🔑 Developer Control Panel")
    active_key = db.get_active_product_key()
    if active_key:
        expiry_text = active_key['expires_at'] or "Never"
        st.write(f"**Active Product Key:** `{active_key['key']}`")
        st.write(f"**Expires At:** {expiry_text}")
        st.text_input("Copy Key", value=active_key['key'], key="copy_key_field")
        if st.button("Copy Key", key="copy_key_button"):
            st.success("Key displayed above; use Ctrl+C to copy.")
    else:
        st.warning("No active product key is available.")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("Generate New Key", key="gen_new_key"):
            new_key = db.create_product_key(permanent=False)
            st.session_state.generated_key = new_key
    with col2:
        if st.button("Generate Permanent Key", key="gen_perm_key"):
            new_key = db.create_product_key(permanent=True)
            st.session_state.generated_key = new_key
    with col3:
        if st.button("🚪 Logout", key="dev_logout_btn"):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.product_key_entered = False
            st.session_state.login_attempt_user = None

    if 'generated_key' in st.session_state:
        st.info(f"Generated Key: `{st.session_state.generated_key}`")

    with st.expander("Manage user accounts"):
        users = db.get_all_users()
        if users:
            selectable = [u['username'] for u in users if u['username'] != st.session_state.current_user['username']]
            if selectable:
                selected_user = st.selectbox("Select account to delete", selectable, key="delete_user_select")
                if st.button("Delete selected account", key="delete_user_btn"):
                    if db.delete_user(selected_user):
                        st.success(f"Deleted account `{selected_user}`.")
                    else:
                        st.error("Failed to delete the selected account.")
            else:
                st.info("No other accounts available to delete.")
        else:
            st.info("No accounts found.")

    # App update controls (developer only)
    with st.expander("App Updates"):
        try:
            st.write(f"**Current version:** {__version__}")
            if st.button("Check for updates", key="check_updates_btn"):
                with st.spinner("Checking GitHub releases..."):
                    update = updater.check_for_update()
                if not update:
                    st.success("No updates available.")
                else:
                    tag = update['tag']
                    asset = update['asset']
                    st.info(f"Update available: {tag} — asset: {asset.get('name')}")
                    if st.button("Download update", key="download_update_btn"):
                        dest = os.path.join(os.getcwd(), asset.get('name'))
                        try:
                            with st.spinner("Downloading update..."):
                                updater.download_asset(asset.get('browser_download_url'), dest)
                            st.success(f"Downloaded update to {dest}")
                            st.info("Run the downloaded installer or extract the zip to update the app.")
                        except Exception as e:
                            st.error(f"Failed to download update: {e}")
        except Exception as e:
            st.error(f"Update check failed: {e}")

    st.markdown("</div>", unsafe_allow_html=True)


def ensure_user_logged_in():
    if not st.session_state.logged_in:
        if not login_ui():
            st.stop()


def ensure_developer_logged_in():
    if not st.session_state.logged_in or st.session_state.current_user['role'] != 'developer':
        st.warning("Developer login required.")
        if not login_ui():
            st.stop()

# Premium Styling & Typography injection
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap');

    /* Global Typography */
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Outfit', sans-serif;
    }

    /* Main Header Styling */
    .app-header {
        background: linear-gradient(135deg, #115e59 0%, #0f766e 50%, #0d9488 100%);
        padding: 2.5rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        position: relative;
        overflow: hidden;
    }
    
    .app-header::before {
        content: "";
        position: absolute;
        top: -50%;
        right: -10%;
        width: 300px;
        height: 300px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 50%;
        pointer-events: none;
    }

    .app-title {
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        margin: 0;
    }

    .app-subtitle {
        font-size: 1.1rem;
        font-weight: 300;
        opacity: 0.9;
        margin-top: 0.5rem;
    }

    /* Glassmorphism Metric Cards */
    .metric-card {
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid rgba(229, 231, 235, 1);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        margin-bottom: 1rem;
    }

    .dark-theme .metric-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(51, 65, 85, 1);
    }

    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px -3px rgba(13, 148, 136, 0.15), 0 4px 6px -2px rgba(13, 148, 136, 0.05);
        border-color: rgba(13, 148, 136, 0.4);
    }

    .metric-label {
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-bottom: 0.5rem;
    }

    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0f766e;
        line-height: 1;
    }

    .metric-trend {
        font-size: 0.8rem;
        margin-top: 0.5rem;
        color: #10b981;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    /* Section Cards */
    .section-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 1.5rem;
    }

    /* Custom Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #0f766e 0%, #0d9488 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }

    .stButton>button:hover {
        transform: scale(1.02) !important;
        box-shadow: 0 4px 12px rgba(13, 148, 136, 0.3) !important;
    }

    /* Hide default CSV export on data tables */
    [data-testid="stDataFrame"] [data-testid="stElementToolbar"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# Fetch current KPI stats from database
kpis = db.get_dashboard_kpis()

# Format Currency Helper (using UGX / Shillings)
def format_ugx(val):
    return f"UGX {val:,.0f}"

def _fpdf_to_bytes(pdf):
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, (bytes, bytearray)):
        return bytes(pdf_output)
    return pdf_output.encode('latin-1')

def _pdf_safe_text(value):
    return str(value).encode('latin-1', errors='replace').decode('latin-1')

def _pdf_add_branded_header(pdf, subtitle):
    content_width = pdf.w - 20
    pdf.set_fill_color(15, 94, 89)
    pdf.rect(10, 10, content_width, 25, 'F')
    pdf.set_xy(10, 13)
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(content_width, 8, 'AGALI AWAMU SAVINGS GROUP', align='C', ln=True)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.set_text_color(204, 251, 241)
    pdf.cell(content_width, 6, _pdf_safe_text(subtitle), align='C', ln=True)
    pdf.set_y(40)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, f'Generated on: {datetime.today().strftime("%Y-%m-%d %H:%M:%S")}', align='R', ln=True)
    pdf.ln(5)

def _pdf_add_summary_metrics(pdf, metrics):
    if not metrics:
        return

    usable_width = pdf.w - 20
    metric_width = usable_width / len(metrics)
    pdf.set_fill_color(240, 253, 250)
    pdf.set_draw_color(13, 148, 136)
    pdf.rect(10, pdf.get_y(), usable_width, 24, 'FD')
    current_y = pdf.get_y()

    pdf.set_y(current_y + 2)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(13, 148, 136)
    for label, _ in metrics:
        pdf.cell(metric_width, 6, _pdf_safe_text(label), align='C')
    pdf.ln()

    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    for _, value in metrics:
        pdf.cell(metric_width, 8, _pdf_safe_text(value), align='C')
    pdf.ln()
    pdf.set_y(current_y + 28)

def _pdf_add_dataframe_table(pdf, df):
    headers = [_pdf_safe_text(h) for h in df.columns]
    rows = [[_pdf_safe_text(v) for v in row] for row in df.astype(str).values.tolist()]
    usable_width = pdf.w - 20
    col_count = max(len(headers), 1)
    font_size = 9 if col_count <= 6 else (8 if col_count <= 9 else 7)
    col_widths = [usable_width / col_count] * col_count

    pdf.set_font('Helvetica', 'B', font_size)
    pdf.set_fill_color(13, 148, 136)
    pdf.set_text_color(255, 255, 255)
    for header, width in zip(headers, col_widths):
        pdf.cell(width, 8, header[:36], border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font('Helvetica', '', font_size)
    pdf.set_text_color(15, 23, 42)
    fill = False
    for row in rows:
        if fill:
            pdf.set_fill_color(248, 250, 252)
        else:
            pdf.set_fill_color(255, 255, 255)
        for value, width in zip(row, col_widths):
            pdf.cell(width, 8, value[:48], border=1, fill=True)
        pdf.ln()
        fill = not fill

    pdf.ln(8)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 8, 'Agali Awamu Savings Group Manager - Confidential Document', align='C')

def generate_table_pdf(subtitle, df, landscape=None, summary_metrics=None):
    from fpdf import FPDF

    export_df = df.copy()
    if export_df.empty:
        export_df = pd.DataFrame({"Message": ["No data available"]})

    if landscape is None:
        landscape = len(export_df.columns) > 6

    pdf = FPDF(orientation='L' if landscape else 'P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _pdf_add_branded_header(pdf, subtitle)
    _pdf_add_summary_metrics(pdf, summary_metrics)
    _pdf_add_dataframe_table(pdf, export_df)
    return _fpdf_to_bytes(pdf)

def display_table_with_pdf(df, subtitle, file_stem, table_key, landscape=None, summary_metrics=None):
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        label="📥 Download as PDF",
        data=generate_table_pdf(subtitle, df, landscape=landscape, summary_metrics=summary_metrics),
        file_name=f"{file_stem}_{datetime.today().strftime('%Y-%m-%d')}.pdf",
        mime="application/pdf",
        key=table_key,
    )

# --- SIDEBAR CONTENT ---
with st.sidebar:
    st.image("https://img.icons8.com/illustrations/external-flaticons-lineal-color-flat-icons/128/external-savings-mutual-funds-flaticons-lineal-color-flat-icons.png", width=90)
    sidebar_company = st.session_state.current_user.get('company_name', 'FIKMEN INCO') if st.session_state.current_user else 'FIKMEN INCO'
    sidebar_motto = st.session_state.current_user.get('motto', 'TELL: 0709 889 228') if st.session_state.current_user else 'TELL: 0709 889 228'
    st.markdown(f"<h2 style='color:#0f766e; font-weight:800; margin-top: 0px;'>{sidebar_company}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='font-size:0.9rem; color:#64748b; margin-top:-10px;'>{sidebar_motto}</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("### 📊 System Health")
    st.info("Database Connected: Active")
    st.success("Target Achievement: 94.2%")
    
    st.markdown("---")
    st.markdown("### ⚙️ Quick Database Admin")
    if st.button("🔄 Reset & Seed Sample Data"):
        db.init_db()
        db.seed_dummy_data()

    if st.session_state.logged_in:
        st.markdown("---")
        st.markdown(f"**Logged in as:** {st.session_state.current_user['username']} ({st.session_state.current_user['role']})")
        if st.button("🚪 Logout", key="sidebar_logout_btn"):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.product_key_entered = False
            st.session_state.login_attempt_user = None

        if st.session_state.current_user and st.session_state.current_user.get('role') == 'developer':
            st.markdown("---")
            st.markdown("### 🧹 Member Data Reset")
            reset_choice = st.radio(
                "Select reset action",
                ["Keep member profiles only", "Wipe all member data"],
                index=0,
                key="member_reset_choice"
            )
            if st.button("Execute reset", key="member_reset_btn"):
                if reset_choice == "Keep member profiles only":
                    db.clear_member_transaction_data()
                    st.success("Member profiles kept. All associated transaction data cleared.")
                else:
                    db.delete_all_members_and_data()
                    st.success("All members and their related data have been wiped.")

# Ensure application access is authenticated
ensure_user_logged_in()

# --- HEADER SECTION ---
company_name = st.session_state.current_user.get('company_name', 'Agali Awamu Savings Group') if st.session_state.current_user else 'Agali Awamu Savings Group'
company_motto = st.session_state.current_user.get('motto', 'Empowering financial growth, together. Manage members, contributions, and microloans seamlessly.') if st.session_state.current_user else 'Empowering financial growth, together. Manage members, contributions, and microloans seamlessly.'

st.markdown(f"""
<div class="app-header">
    <div class="app-title">{company_name}</div>
    <div class="app-subtitle">{company_motto}</div>
</div>
""", unsafe_allow_html=True)

if st.session_state.current_user and st.session_state.current_user['role'] == 'developer':
    developer_panel()

# --- TAB NAVIGATION ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Dashboard Overview", 
    "👥 Member Directory", 
    "💰 Savings & Withdraws", 
    "🤝 Loans & Repayments", 
    "📋 System Reports",
    "🕒 Activity Timeline"
])

# ==================== TAB 1: DASHBOARD OVERVIEW ====================
with tab1:
    # 1. Metric Cards Grid
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Savings Pool</div>
            <div class="metric-value">{format_ugx(kpis['total_savings'])}</div>
            <div class="metric-trend">▲ +12% from last month</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Active Loan Book</div>
            <div class="metric-value">{format_ugx(kpis['active_loans_principal'])}</div>
            <div class="metric-trend" style="color: #f59e0b;">● 2 Outstanding Loans</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Repayments</div>
            <div class="metric-value">{format_ugx(kpis['total_repayments'])}</div>
            <div class="metric-trend">▲ 100% On-time Rate</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Active Members</div>
            <div class="metric-value">{kpis['total_members']} Members Active</div>
            <div class="metric-trend">▲ +1 new join this week</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. Charts Section
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("📈 Monthly Savings Growth Trend")
        
        # Load and prepare monthly data
        savings_history = db.get_monthly_savings_data()
        if savings_history:
            df_savings = pd.DataFrame(savings_history)
            df_savings.rename(columns={"month": "Month", "total": "Amount (UGX)"}, inplace=True)
            df_savings.set_index("Month", inplace=True)
            st.area_chart(df_savings, color="#0d9488")
        else:
            st.info("No savings history available yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with chart_col2:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("📊 Contribution Distribution by Saving Type")
        
        # Load type distribution
        savings_types = db.get_savings_by_type()
        if savings_types:
            df_types = pd.DataFrame(savings_types)
            df_types.rename(columns={"type": "Saving Type", "total": "Amount (UGX)"}, inplace=True)
            df_types.set_index("Saving Type", inplace=True)
            st.bar_chart(df_types, color="#0f766e")
        else:
            st.info("No contributions categorised yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    # 3. Recent Activity & Action Shortcuts
    bottom_col1, bottom_col2 = st.columns([2, 1])
    
    with bottom_col1:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("🔔 Recent Activities")
        
        # Quick table view of latest contributions
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.amount, s.date, s.saving_type, m.name
            FROM savings s
            JOIN members m ON s.member_id = m.id
            ORDER BY s.date DESC LIMIT 5
        """)
        recent_savings = cursor.fetchall()
        conn.close()
        
        if recent_savings:
            activities = []
            for row in recent_savings:
                activities.append({
                    "Date": row["date"],
                    "Member": row["name"],
                    "Saving Type": row["saving_type"],
                    "Amount": format_ugx(row["amount"])
                })
            df_activities = pd.DataFrame(activities)
            display_table_with_pdf(
                df_activities,
                "Recent Savings Activities",
                "recent_activities",
                "pdf_recent_activities",
            )
        else:
            st.write("No recent activities.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with bottom_col2:
        st.markdown("<div class='section-card' style='height: 100%;'>", unsafe_allow_html=True)
        st.subheader("⚡ Quick Shortcuts")
        st.write("Perform everyday tasks in a click:")
        
        # We will connect these tabs to direct page interactions in subsequent steps
        st.info("💡 Pro-Tip: Go to **Member Directory** to register new savings group members.")
        st.info("💡 Pro-Tip: Use **Savings & Withdraws** to record new weekly contributions and withdrawals.")
        st.markdown("</div>", unsafe_allow_html=True)

# ==================== TAB 2: MEMBER DIRECTORY ====================
with tab2:
    st.markdown("<h3 style='color:#0f766e; font-weight:700;'>👥 Members Directory </h3>", unsafe_allow_html=True)
    
    # Member stats
    members_data = db.get_all_members()
    total_m = len(members_data)
    active_m = sum(1 for m in members_data if m['status'] == 'Active')
    inactive_m = total_m - active_m
    
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Total Members", total_m)
    m_col2.metric("Active Members", active_m)
    m_col3.metric("Inactive Members", inactive_m)
    
    st.markdown("---")
    
    # 1. Register Member Form (Expander)
    with st.expander("➕ Register New Savings Group Member", expanded=False):
        with st.form("register_member_form", clear_on_submit=True):
            reg_name = st.text_input("Full Name*", placeholder="e.g. John Doe")
            col_ph, col_em = st.columns(2)
            reg_phone = col_ph.text_input("Phone Number", placeholder="e.g. +256 700 000000")
            reg_email = col_em.text_input("Email Address", placeholder="e.g. john@example.com")
            reg_date = st.date_input("Join Date", value=datetime.today())
            reg_status = st.selectbox("Initial Status", ["Active", "Inactive"])
            
            submit_reg = st.form_submit_button("Register Member")
            if submit_reg:
                if reg_name.strip() == "":
                    st.error("Name is a required field.")
                else:
                    db.add_member(reg_name.strip(), reg_phone.strip(), reg_email.strip(), reg_date.strftime("%Y-%m-%d"), reg_status)
                    st.success(f"Successfully registered {reg_name}!")
                    st.rerun()

    # 2. Directory & Manage Selection
    dir_col1, dir_col2 = st.columns([3, 2])
    
    with dir_col1:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("🔍 Search Members")
        search_q = st.text_input("Search by Name, Phone or Email", placeholder="Type to search...", label_visibility="collapsed")
        
        filtered_members = db.get_all_members(search_q)
        if filtered_members:
            df_m = pd.DataFrame(filtered_members)
            df_m.rename(columns={
                "id": "ID",
                "name": "Name",
                "phone": "Phone",
                "email": "Email",
                "join_date": "Join Date",
                "status": "Status"
            }, inplace=True)
            df_m = df_m[["ID", "Name", "Phone", "Email", "Join Date", "Status"]]
            display_table_with_pdf(
                df_m,
                "Member Directory",
                "member_directory",
                "pdf_member_directory",
            )
        else:
            st.info("No members found matching the search criteria.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with dir_col2:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("⚙️ Manage Member Details")
        
        if filtered_members:
            member_names = [f"{m['name']} (ID: {m['id']})" for m in filtered_members]
            selected_m_index = st.selectbox("Select a member to edit / view details", range(len(member_names)), format_func=lambda x: member_names[x])
            selected_m = filtered_members[selected_m_index]
            
            # Form to edit member details
            with st.form("edit_member_form"):
                st.write(f"Editing: **{selected_m['name']}**")
                edit_name = st.text_input("Full Name", value=selected_m['name'])
                edit_phone = st.text_input("Phone Number", value=selected_m['phone'] or "")
                edit_email = st.text_input("Email Address", value=selected_m['email'] or "")
                
                status_index = 0 if selected_m['status'] == 'Active' else 1
                edit_status = st.selectbox("Status", ["Active", "Inactive"], index=status_index)
                
                submit_edit = st.form_submit_button("Save Changes")
                if submit_edit:
                    if edit_name.strip() == "":
                        st.error("Name cannot be empty.")
                    else:
                        db.update_member(selected_m['id'], edit_name.strip(), edit_phone.strip(), edit_email.strip(), edit_status)
                        st.success("Member details updated successfully!")
                        st.rerun()
            
            # Danger Zone for deleting member
            st.markdown("<hr style='border: 1px solid #fee2e2;' />", unsafe_allow_html=True)
            st.markdown("<h4 style='color:#dc2626; font-weight:700;'>⚠️ Danger Zone</h4>", unsafe_allow_html=True)
            st.write("Deleting a member will permanently wipe all their savings and loan history from the system.")
            confirm_del = st.checkbox(f"I confirm I want to wipe all data for {selected_m['name']}", key=f"del_confirm_{selected_m['id']}")
            
            if st.button("🗑️ Permanently Delete Member", key=f"del_btn_{selected_m['id']}", disabled=not confirm_del, type="primary"):
                if db.delete_member(selected_m['id']):
                    st.success(f"Successfully deleted {selected_m['name']}!")
                    st.rerun()
                else:
                    st.error("Failed to delete member.")
        else:
            st.info("No members available to manage.")
        st.markdown("</div>", unsafe_allow_html=True)

    # 3. Simple View of Deleted Members
    st.markdown("---")
    with st.expander("📜 View Deleted Members Log", expanded=False):
        deleted_list = db.get_deleted_members()
        if deleted_list:
            df_del = pd.DataFrame(deleted_list)
            df_del.rename(columns={
                "original_member_id": "Original ID",
                "name": "Name",
                "phone": "Phone",
                "email": "Email",
                "deleted_at": "Deletion Date"
            }, inplace=True)
            df_del = df_del[["Original ID", "Name", "Phone", "Email", "Deletion Date"]]
            display_table_with_pdf(
                df_del,
                "Deleted Members Log",
                "deleted_members",
                "pdf_deleted_members",
            )
        else:
            st.info("No members have been deleted yet.")

# ==================== TAB 3: SAVINGS & SHARES ====================
with tab3:
    st.markdown("<h3 style='color:#0f766e; font-weight:700;'>💰 Savings & Withdraws Ledger</h3>", unsafe_allow_html=True)
    
    # Load savings summaries 
    savings_by_type = db.get_savings_by_type()
    type_map = {t['type']: t['total'] for t in savings_by_type}
    regular_s = type_map.get('Regular', 0.0)
    welfare_s = type_map.get('Welfare Fees', 0.0)
    withdraw_s = db.get_total_withdraws()
    total_savings = regular_s + welfare_s - withdraw_s
    
    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    s_col1.metric("Total income collected", format_ugx(total_savings))
    s_col2.metric("Regular Savings", format_ugx(kpis["total_savings"]))
    s_col3.metric("Welfare Fees", format_ugx(welfare_s))
    s_col4.metric("Withdrawals", format_ugx(withdraw_s))
    
    st.markdown("---") 

    st.subheader("📅 Active Week")

    current_week = db.get_active_week()

    st.info(f"Current Week: {current_week}")

    new_week = st.text_input(
        "Set Active Week",
        value=current_week
    )

    if st.button("Update Week"):
        db.set_active_week(new_week)
        st.success(f"Week changed to {new_week}")
        st.rerun()
    st.markdown("---")
    
    # Columns for Record and View
    sav_col1, sav_col2 = st.columns([1, 2])
    
    all_members = db.get_all_members()
    
    with sav_col1:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("➕ Record Contribution")
        if all_members:
            with st.form("record_saving_form", clear_on_submit=True):
                member_options = [f"{m['name']} (ID: {m['id']})" for m in all_members]
                selected_m_idx = st.selectbox("Select Member", range(len(member_options)), format_func=lambda x: member_options[x])
                chosen_member = all_members[selected_m_idx]
                
                sav_amount = st.number_input("Amount (UGX)*", min_value=1000, value=50000, step=5000)
                sav_type = st.selectbox("Saving Type", ["Regular", "Welfare"])
                sav_date = st.date_input("Date Received", value=datetime.today())
                
                submit_saving = st.form_submit_button("Record Transaction")
                if submit_saving:
                    db.add_saving(chosen_member['id'], sav_amount, sav_date.strftime("%Y-%m-%d"), sav_type)
                    st.success(f"Recorded {format_ugx(sav_amount)} {sav_type} contribution for {chosen_member['name']}!")
                    st.rerun()

            st.markdown("<hr style='margin-top: 1rem; margin-bottom: 1rem;' />", unsafe_allow_html=True)
            st.subheader("➖ Record Withdrawal")
            with st.form("record_withdraw_form", clear_on_submit=True):
                w_member_options = [f"{m['name']} (ID: {m['id']})" for m in all_members]
                w_selected_idx = st.selectbox("Select Member", range(len(w_member_options)), format_func=lambda x: w_member_options[x], key="w_member")
                w_chosen = all_members[w_selected_idx]
                w_amount = st.number_input("Withdrawal Amount (UGX)*", min_value=1000, value=50000, step=5000, key="w_amount")
                w_date = st.date_input("Date of Withdrawal", value=datetime.today(), key="w_date")
                w_note = st.text_input("Note (optional)")
                submit_w = st.form_submit_button("Record Withdrawal")
                if submit_w:
                    success, message = db.add_withdraw(
                        w_chosen['id'],
                        w_amount,
                        w_date.strftime("%Y-%m-%d"),
                        w_note
                    )
                    if success:
                        st.success(f"Recorded withdrawal of {format_ugx(w_amount)} for {w_chosen['name']}!")
                        tm.sleep(6)
                    else:
                        st.error(f"Failed to record withdrawal: {message}")
                        tm.sleep(6)
                    st.rerun()
        else:
            st.warning("Please register members first before recording savings.")
        st.markdown("</div>", unsafe_allow_html=True)
    with sav_col2:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("📊 Member Savings Balances")
        
        member_balances = db.get_savings_summary_by_member()
        if member_balances:
            df_bal = pd.DataFrame(member_balances)
            df_bal.rename(columns={
                "name": "Member Name",
                "total_savings": "Total Saved",
                "regular_savings": "Regular Savings",
                "welfare_fees": "Welfare Fees",
                "total_withdrawals": "Withdrawals"
            }, inplace=True)
            df_bal = df_bal[["Member Name", "Total Saved", "Regular Savings", "Welfare Fees", "Withdrawals"]]
            for col in ["Total Saved", "Regular Savings", "Welfare Fees", "Withdrawals"]:
                df_bal[col] = df_bal[col].apply(format_ugx)

            display_table_with_pdf(
                df_bal,
                "Member Savings Balances",
                "member_savings_balances",
                "pdf_member_savings_balances",
            )
        else:
            st.info("No savings recorded yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    # Transaction History List
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("📜 Recent Savings Contributions")
    
    f_col1, f_col2, f_col3= st.columns(3)
    with f_col1:
        m_filter_options = ["All Members"] + [f"{m['name']} (ID: {m['id']})" for m in all_members]
        selected_m_filter_idx = st.selectbox("Filter by Member", range(len(m_filter_options)), format_func=lambda x: m_filter_options[x])
        m_filter_id = None if selected_m_filter_idx == 0 else all_members[selected_m_filter_idx - 1]['id']
        
    with f_col2:
        t_filter_options = ["All Types", "Regular", "Welfare"]
        selected_t_filter = st.selectbox("Filter by Saving Type", t_filter_options)
        t_filter = None if selected_t_filter == "All Types" else selected_t_filter
    
    with f_col3:
        week_options = ["All Weeks"] + db.get_all_weeks()

        selected_week = st.selectbox(
            "Filter by Week",
            week_options,
            key="savings_filter_week"
        )

        week_filter = None if selected_week == "All Weeks" else selected_week

    savings_history = db.get_all_savings(member_id=m_filter_id, saving_type=t_filter,week_name=week_filter)
    if savings_history:
        df_hist = pd.DataFrame(savings_history)
        df_hist.rename(columns={
            "member_name": "Member Name",
            "saving_type": "Saving Type",
            "amount": "Amount",
            "date": "Date",
            "week_name": "Week NO"
        }, inplace=True)
        df_hist = df_hist[["Date", "Week NO","Member Name", "Saving Type", "Amount"]]
        df_hist["Amount"] = df_hist["Amount"].apply(format_ugx)
        display_table_with_pdf(
            df_hist,
            "Recent Savings Contributions",
            "savings_contributions",
            "pdf_savings_contributions",
        )
    else:
        st.info("No contributions found matching the filters.")
    st.markdown("</div>", unsafe_allow_html=True)

    # Withdrawals Section
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("📉 Recent Withdrawals")
    withdraws = db.get_all_withdraws(member_id=m_filter_id)
    if withdraws:
        df_w = pd.DataFrame(withdraws)
        df_w.rename(columns={
            "date": "Date",
            "member_name": "Member Name",
            "amount": "Amount",
            "note": "Note"
        }, inplace=True)
        df_w = df_w[["Date", "Member Name", "Amount", "Note"]]
        df_w["Amount"] = df_w["Amount"].apply(format_ugx)

        display_table_with_pdf(
            df_w,
            "Recent Withdrawals",
            "recent_withdrawals",
            "pdf_recent_withdrawals",
        )
    else:
        st.info("No withdrawals recorded yet.")
    st.markdown("</div>", unsafe_allow_html=True)

# ==================== TAB 4: LOANS & REPAYMENTS ====================
with tab4:
    st.markdown("<h3 style='color:#0f766e; font-weight:700;'>🤝 Loans & Repayments Ledger</h3>", unsafe_allow_html=True)
    
    loans_data = db.get_all_loans()
    
    # Loan stats
    total_active_principal = sum(l['amount'] for l in loans_data if l['status'] in ('Active', 'Defaulted'))
    total_repayable = sum(l['total_repayable'] for l in loans_data if l['status'] in ('Active', 'Defaulted'))
    total_repaid = sum(l['total_repaid'] for l in loans_data if l['status'] in ('Active', 'Defaulted'))
    outstanding_bal = sum(l['remaining_balance'] for l in loans_data if l['status'] in ('Active', 'Defaulted'))
    
    l_col1, l_col2, l_col3, l_col4 = st.columns(4)
    l_col1.metric("Active Loan Book (Principal)", format_ugx(total_active_principal))
    l_col2.metric("Total Repayable (with Interest)", format_ugx(total_repayable))
    l_col3.metric("Total Repayments Collected", format_ugx(total_repaid))
    l_col4.metric("Outstanding Balance", format_ugx(outstanding_bal))
    
    st.markdown("---")
    
    loan_form_col, repay_form_col = st.columns(2)
    
    with loan_form_col:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("🚀 Disburse New Loan")
        if all_members:
            active_members = [m for m in all_members if m['status'] == 'Active']
            if active_members:
                with st.form("new_loan_form", clear_on_submit=True):
                    m_opts = [f"{m['name']} (ID: {m['id']})" for m in active_members]
                    sel_m_idx = st.selectbox("Select Borrower", range(len(m_opts)), format_func=lambda x: m_opts[x])
                    loan_borrower = active_members[sel_m_idx]
                    
                    l_amount = st.number_input("Loan Principal (UGX)*", min_value=10000, value=200000, step=10000)
                    l_rate = st.number_input("Flat Interest Rate (%)*", min_value=0.0, max_value=100.0, value=10.0, step=0.5)
                    l_term = st.number_input("Loan Term (Months)*", min_value=1, max_value=24, value=3, step=1)
                    l_date = st.date_input("Disbursal Date", value=datetime.today())
                    
                    submit_loan = st.form_submit_button("Disburse Loan")
                    if submit_loan:
                        db.add_loan(loan_borrower['id'], l_amount, l_rate, l_term, l_date.strftime("%Y-%m-%d"), "Active")
                        st.success(f"Successfully disbursed loan of {format_ugx(l_amount)} to {loan_borrower['name']}!")
                        st.rerun()
            else:
                st.warning("No active members available for borrowing.")
        else:
            st.warning("Please register members first.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with repay_form_col:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("💵 Record Loan Repayment")
        active_loan_choices = db.get_loan_choices_for_repayment()
        if active_loan_choices:
            with st.form("record_repayment_form", clear_on_submit=True):
                loan_opts = [f"Loan ID: {l['id']} - {l['member_name']} (Disbursed: {format_ugx(l['amount'])} on {l['start_date']})" for l in active_loan_choices]
                sel_l_idx = st.selectbox("Select Active Loan", range(len(loan_opts)), format_func=lambda x: loan_opts[x])
                chosen_loan = active_loan_choices[sel_l_idx]
                
                rep_amount = st.number_input("Repayment Amount (UGX)*", min_value=1000, value=50000, step=5000)
                rep_date = st.date_input("Repayment Date", value=datetime.today())
                
                submit_rep = st.form_submit_button("Record Repayment")
                if submit_rep:
                    db.add_repayment(chosen_loan['id'], rep_amount, rep_date.strftime("%Y-%m-%d"))
                    st.success(f"Recorded repayment of {format_ugx(rep_amount)} for Loan ID {chosen_loan['id']}!")
                    st.rerun()
        else:
            st.info("No active or pending loans needing repayments.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    # Loans Table View
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("📋 Loan Registry")
    
    if loans_data:
        df_loans = pd.DataFrame(loans_data)
        df_loans['Progress'] = df_loans.apply(lambda r: f"{(r['total_repaid']/r['total_repayable']*100):.1f}%" if r['total_repayable'] > 0 else "0.0%", axis=1)
        
        df_loans_disp = df_loans.rename(columns={
            "id": "Loan ID",
            "member_name": "Borrower",
            "amount": "Principal",
            "interest_rate": "Int. Rate",
            "term_months": "Term (Mo)",
            "start_date": "Disbursed Date",
            "status": "Status",
            "total_repayable": "Total Repayable",
            "total_repaid": "Total Repaid",
            "remaining_balance": "Remaining Bal.",
            "Progress": "Progress"
        })
        
        df_loans_disp = df_loans_disp[["Loan ID", "Borrower", "Principal", "Int. Rate", "Term (Mo)", "Disbursed Date", "Total Repayable", "Total Repaid", "Remaining Bal.", "Progress", "Status"]]
        
        for col in ["Principal", "Total Repayable", "Total Repaid", "Remaining Bal."]:
            df_loans_disp[col] = df_loans_disp[col].apply(format_ugx)

        display_table_with_pdf(
            df_loans_disp,
            "Loan Registry",
            "loan_registry",
            "pdf_loan_registry",
            landscape=True,
        )
        
        # Detail view expander for individual loans
        st.markdown("---")
        st.subheader("🔍 View Loan Repayment Schedule & History")
        loan_detail_opts = [f"Select Loan to view details..."] + [f"Loan ID: {l['id']} - {l['member_name']} (Principal: {format_ugx(l['amount'])})" for l in loans_data]
        sel_detail_idx = st.selectbox("Select Loan", range(len(loan_detail_opts)), format_func=lambda x: loan_detail_opts[x], label_visibility="collapsed")
        
        if sel_detail_idx > 0:
            target_loan_id = loans_data[sel_detail_idx - 1]['id']
            ld = db.get_loan_details(target_loan_id)
            if ld:
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    st.write(f"**Borrower**: {ld['member_name']}")
                    st.write(f"**Contact**: {ld['member_phone'] or 'N/A'} | {ld['member_email'] or 'N/A'}")
                    st.write(f"**Disbursed**: {format_ugx(ld['amount'])} on {ld['start_date']}")
                    st.write(f"**Terms**: {ld['term_months']} Months at {ld['interest_rate']}% flat")
                with d_col2:
                    st.write(f"**Total Repayable**: {format_ugx(ld['total_repayable'])}")
                    st.write(f"**Total Repaid**: {format_ugx(ld['total_repaid'])}")
                    st.write(f"**Remaining Balance**: **{format_ugx(ld['remaining_balance'])}**")
                    st.write(f"**Status**: {ld['status']}")
                
                st.markdown("##### Repayment Transactions")
                if ld['repayments']:
                    df_reps = pd.DataFrame(ld['repayments'])
                    df_reps.rename(columns={"date": "Payment Date", "amount": "Amount Paid"}, inplace=True)
                    df_reps = df_reps[["Payment Date", "Amount Paid"]]
                    df_reps["Amount Paid"] = df_reps["Amount Paid"].apply(format_ugx)
                    display_table_with_pdf(
                        df_reps,
                        f"Loan Repayment History - Loan ID {target_loan_id}",
                        f"loan_{target_loan_id}_repayments",
                        f"pdf_loan_repayments_{target_loan_id}",
                    )
                else:
                    st.info("No repayments recorded for this loan yet.")
    else:
        st.info("No loans disbursed yet.")
    st.markdown("</div>", unsafe_allow_html=True)

# ==================== TAB 5: SYSTEM REPORTS ====================
with tab5:
    st.markdown("<h3 style='color:#0f766e; font-weight:700;'>📋 System Reports & Financial Statements</h3>", unsafe_allow_html=True)
    
    reports_data = db.get_system_reports_data()
    
    if reports_data:
        df_rep = pd.DataFrame(reports_data)
        
        total_sav = df_rep['total_savings'].sum()
        total_loan_p = df_rep['loans_principal'].sum()
        total_repaid_c = df_rep['total_repaid'].sum()
        total_outstanding = df_rep['outstanding_balance'].sum()
        
        # Key Financial Insights
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("💡 Portfolio Analysis & Key Indicators")
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        
        avg_savings = df_rep['total_savings'].mean() if len(df_rep) > 0 else 0.0
        loan_to_savings_ratio = (total_outstanding / total_sav * 100) if total_sav > 0 else 0.0
        
        r_col1.metric("Average Savings per Member", format_ugx(avg_savings))
        r_col2.metric("Portfolio Risk Ratio (Loan-to-Savings)", f"{loan_to_savings_ratio:.1f}%")
        r_col3.metric("Capital Utilisation Rate", f"{(total_loan_p / total_sav * 100 if total_sav > 0 else 0.0):.1f}%")
        r_col4.metric("Active Borrowers", len(df_rep[df_rep['loans_principal'] > 0]))
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Detailed table
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("📊 Member Balances & Financial Position")
        
        df_rep_disp = df_rep.rename(columns={
            "name": "Member Name",
            "status": "Status",
            "total_savings": "Total Savings",
            "loans_principal": "Disbursed Loans",
            "total_repayable": "Total Repayable",
            "total_repaid": "Total Repaid",
            "outstanding_balance": "Outstanding Balance"
        })
        
        df_rep_disp = df_rep_disp[["Member Name", "Status", "Total Savings", "Disbursed Loans", "Total Repayable", "Total Repaid", "Outstanding Balance"]]
        
        for col in ["Total Savings", "Disbursed Loans", "Total Repayable", "Total Repaid", "Outstanding Balance"]:
            df_rep_disp[col] = df_rep_disp[col].apply(format_ugx)

        report_summary = [
            ("TOTAL SAVINGS", format_ugx(total_sav)),
            ("ACTIVE LOANS", format_ugx(total_loan_p)),
            ("TOTAL REPAYMENTS", format_ugx(total_repaid_c)),
            ("OUTSTANDING BAL.", format_ugx(total_outstanding)),
        ]
        display_table_with_pdf(
            df_rep_disp,
            "Member Balances & Financial Position Report",
            "agali_awamu_financial_report",
            "pdf_financial_report",
            landscape=True,
            summary_metrics=report_summary,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No data available to generate reports. Please add members and transactions first.")

# ==================== TAB 6: ACTIVITY TIMELINE ====================
with tab6:
    st.markdown("<h3 style='color:#0f766e; font-weight:700;'>🕒 Member Activity Timeline</h3>", unsafe_allow_html=True)
    st.write("Track a chronological order of all actions performed by a member, including group registration, savings, loan disbursals, and repayments.")
    
    # Refresh all member list
    all_members_tl = db.get_all_members()

    if all_members_tl:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Select Member to View Activity")

        filter_col1, filter_col2 = st.columns(2)

        with filter_col1:
            member_options = [
                f"{m['name']} (ID: {m['id']})"
                for m in all_members_tl
            ]

            selected_m_tl_idx = st.selectbox(
                "Select Member for Timeline",
                range(len(member_options)),
                format_func=lambda x: member_options[x]
            )

            chosen_m_tl = all_members_tl[selected_m_tl_idx]

        with filter_col2:
            weeks = ["All Weeks"] + db.get_all_weeks()

            selected_week = st.selectbox(
                "Filter by Week",
                weeks,
                key="timeline_filter_week"
            )

            week_filter = (
                None if selected_week == "All Weeks"
                else selected_week
            )

        # Display selected member summary
        st.markdown(
            f"Showing chronological activities for: "
            f"**{chosen_m_tl['name']}** "
            f"(ID: {chosen_m_tl['id']}, "
            f"Status: `{chosen_m_tl['status']}`)"
        )

        # Fetch activity log
        activity_log = db.get_member_activity_timeline(
            chosen_m_tl['id'],
            week_name=week_filter
        )

        if activity_log:
            timeline_items = []

            for act in activity_log:
                timeline_items.append({
                    "Date": act["date"],
                    "Week": act.get("week_name", "N/A"),
                    "Activity Type": act["type"],
                    "Details": act["details"],
                    "Amount": (
                        format_ugx(act["amount"])
                        if act["amount"] is not None
                        else "N/A"
                    )
                })

            df_timeline = pd.DataFrame(timeline_items)

            display_table_with_pdf(
                df_timeline,
                f"Activity Timeline - {chosen_m_tl['name']}",
                f"activity_timeline_{chosen_m_tl['id']}",
                f"pdf_activity_timeline_{chosen_m_tl['id']}",
            )

        else:
            st.info(
                "No registered activities found "
                "for this member matching the selected filters."
            )

        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.warning(
            "Please register members first "
            "to view their timelines."
        )