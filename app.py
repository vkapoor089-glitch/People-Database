import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import google.generativeai as genai

# 1. Page Configuration
st.set_page_config(
    page_title="Sourcing Database & AI Assistant",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Sourcing Database & AI Assistant")
st.markdown("---")

# 2. Initialize Gemini AI Engine
if "GEMINI_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Using the recommended standard model for general text tasks
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
        st.sidebar.success("🤖 Gemini AI Engine Active")
    except Exception as ai_err:
        st.sidebar.error(f"❌ Gemini Initialization Failed: {str(ai_err)}")
        ai_model = None
else:
    st.sidebar.warning("⚠️ GEMINI_API_KEY missing from Secrets.")
    ai_model = None

# 3. Detect and Initialize Database Strategy
use_gsheets = False
conn = None
df = None

# Define a strict column schema to keep data uniform
DB_COLUMNS = ["Vendor Name", "Category", "Contact Person", "Email", "Lead Time (Days)", "Notes"]

try:
    # Direct invocation bypassing proxy checks
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Read the data sheet (clearing cache with ttl=0 to ensure real-time accuracy during testing)
    df = conn.read(ttl=0)
    use_gsheets = True
    st.sidebar.success("IN 🔒 Connected to Google Sheets Live Database")
except Exception as conn_err:
    use_gsheets = False
    st.sidebar.error(f"❌ Google Sheets Connection Failed: {str(conn_err)}")
    
    # Standard fallback to local session state memory
    if 'local_db' not in st.session_state:
        st.session_state.local_db = pd.DataFrame(columns=DB_COLUMNS)
    df = st.session_state.local_db

if not use_gsheets:
    st.info("ℹ️ Running on local temporary memory. Set up 'connections.gsheets' in Streamlit Secrets to persist data permanently.")

# 4. Data Normalization & Cleaning
if df is None or df.empty:
    df = pd.DataFrame(columns=DB_COLUMNS)
else:
    # Force alignment with the baseline schema to protect against layout drift
    for col in DB_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[DB_COLUMNS]

# 5. Application Interface Layout (Tabs)
tab_view, tab_add, tab_ai = st.tabs(["🗂️ View & Search Database", "➕ Add New Entry", "🤖 AI Sourcing Assistant"])

# --- TAB 1: VIEW & SEARCH ---
with tab_view:
    st.subheader("Current Database Records")
    
    # Search and Filter Mechanics
    search_query = st.text_input("🔍 Quick Search by Vendor Name or Category:", "")
    
    if not df.empty:
        filtered_df = df.copy()
        if search_query:
            filtered_df = filtered_df[
                filtered_df['Vendor Name'].astype(str).str.contains(search_query, case=False, na=False) |
                filtered_df['Category'].astype(str).str.contains(search_query, case=False, na=False)
            ]
        
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        st.metric(label="Total Tracked Vendors", value=len(filtered_df))
    else:
        st.warning("The database is currently empty. Head over to the 'Add New Entry' tab to get started.")

# --- TAB 2: ADD NEW ENTRY ---
with tab_add:
    st.subheader("Register a New Vendor Source")
    
    with st.form(key="vendor_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            vendor_name = st.text_input("Vendor Name *")
            category = st.text_input("Category / Component Class *")
            contact_person = st.text_input("Contact Person Name")
        
        with col2:
            email = st.text_input("Contact Email")
            lead_time = st.number_input("Est. Lead Time (Days)", min_value=0, max_value=365, step=1)
            notes = st.text_area("Operational Notes / Capacity Details")
            
        submit_btn = st.form_submit_button(label="Commit Entry to Database")
        
        if submit_btn:
            if not vendor_name or not category:
                st.error("Submission failed: 'Vendor Name' and 'Category' are mandatory fields.")
            else:
                # Create a uniform dictionary matching our core schema
                new_row = {
                    "Vendor Name": vendor_name.strip(),
                    "Category": category.strip(),
                    "Contact Person": contact_person.strip(),
                    "Email": email.strip(),
                    "Lead Time (Days)": int(lead_time),
                    "Notes": notes.strip()
                }
                
                # Append data row cleanly to the in-memory dataframe
                new_entry_df = pd.DataFrame([new_row])
                updated_df = pd.concat([df, new_entry_df], ignore_index=True)
                
                # Execution writeback route selection
                if use_gsheets and conn is not None:
                    try:
                        conn.update(data=updated_df)
                        st.success(f"🚀 Success! '{vendor_name}' safely synchronized with Google Sheets.")
                        st.rerun()
                    except Exception as write_err:
                        st.error(f"Failed to synchronize live sheet: {str(write_err)}")
                else:
                    st.session_state.local_db = updated_df
                    st.success(f"💾 Entry stored locally. '{vendor_name}' will remain available for this active browser session.")
                    st.rerun()

# --- TAB 3: AI SOURCING ASSISTANT ---
with tab_ai:
    st.subheader("Gemini Operational Assistant")
    st.markdown("Use this space to draft immediate communications or evaluate vendor parameters.")
    
    if ai_model is None:
        st.error("The AI interface is offline because a valid GEMINI_API_KEY was not provided in Secrets.")
    else:
        # Prompt Quick-Select Templates to streamline operations
        ai_mode = st.selectbox(
            "Select an action:",
            [
                "Draft an initial Request for Quote (RFQ) Email",
                "Draft a Lead Time Escalation Notice",
                "Custom Vendor Analytics Query"
            ]
        )
        
        # Pull latest available vendor list for context matching
        vendor_options = ["None / General Context"]
        if not df.empty:
            vendor_options.extend(df["Vendor Name"].unique().tolist())
            
        selected_vendor = st.selectbox("Inject Target Vendor context:", vendor_options)
        
        # Context compilation engine
        vendor_context_str = ""
        if selected_vendor != "None / General Context" and not df.empty:
            v_data = df[df["Vendor Name"] == selected_vendor].iloc
