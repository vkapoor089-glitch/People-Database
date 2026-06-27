import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import google.generativeai as genai
import json

# 1. Page Configuration
st.set_page_config(
    page_title="Talent Sourcing & CV Analytics Platform",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("💼 Talent Sourcing & CV Analytics Platform")
st.markdown("---")

# 2. Initialize Gemini AI Engine
if "GEMINI_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
        st.sidebar.success("🤖 Gemini AI Parsing Engine Active")
    except Exception as ai_err:
        st.sidebar.error(f"❌ Gemini Initialization Failed: {str(ai_err)}")
        ai_model = None
else:
    st.sidebar.warning("⚠️ GEMINI_API_KEY missing from Secrets.")
    ai_model = None

# 3. Initialize Form State Variables for Seamless Pre-filling
state_keys = {
    "c_name": "",
    "c_role": "",
    "c_location": "",
    "c_budget": "",
    "c_email": "",
    "c_skills": "",
    "c_summary": ""
}
for key, default_val in state_keys.items():
    if key not in st.session_state:
        st.session_state[key] = default_val

# 4. Detect and Initialize Database Strategy
use_gsheets = False
conn = None
df = None

DB_COLUMNS = ["Candidate Name", "Role/Category", "Location", "Budget", "Email", "Key Skills", "AI Summary"]

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    use_gsheets = True
    st.sidebar.success("🔒 Connected to Live Candidates Database")
except Exception as conn_err:
    use_gsheets = False
    st.sidebar.error(f"❌ Live Sheets Connection Failed: {str(conn_err)}")
    
    if 'candidate_db' not in st.session_state:
        st.session_state.candidate_db = pd.DataFrame(columns=DB_COLUMNS)
    df = st.session_state.candidate_db

if not use_gsheets:
    st.info("ℹ️ Running on local temporary memory. Set up 'connections.gsheets' in Streamlit Secrets to persist data permanently.")

# Data Normalization
if df is None or df.empty:
    df = pd.DataFrame(columns=DB_COLUMNS)
else:
    for col in DB_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[DB_COLUMNS]

# 5. UI Layout Tabs
tab_view, tab_parse, tab_ai = st.tabs(["🗂️ Candidate Database", "🧬 CV Parsing & Manual Input", "🤖 AI Talent Assistant"])

# --- TAB 1: VIEW & FILTER DATABASE ---
with tab_view:
    st.subheader("Current Candidate Pool")
    
    # Active Search and Filters
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        search_role = st.text_input("🔍 Filter by Role / Skill:", "")
    with col_f2:
        search_loc = st.text_input("📍 Filter by Location:", "")
    with col_f3:
        search_budget = st.text_input("💰 Filter by Budget / CTC:", "")
        
    if not df.empty:
        filtered_df = df.copy()
        if search_role:
            filtered_df = filtered_df[
                filtered_df['Role/Category'].astype(str).str.contains(search_role, case=False, na=False) |
                filtered_df['Key Skills'].astype(str).str.contains(search_role, case=False, na=False)
            ]
        if search_loc:
            filtered_df = filtered_df[filtered_df['Location'].astype(str).str.contains(search_loc, case=False, na=False)]
        if search_budget:
            filtered_df = filtered_df[filtered_df['Budget'].astype(str).str.contains(search_budget, case=False, na=False)]
            
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        st.metric(label="Total Sourced Candidates", value=len(filtered_df))
    else:
        st.warning("The talent database is currently empty. Extract or input profiles in the next tab.")

# --- TAB 2: CV PARSING & MANUAL ENTRY ---
with tab_parse:
    st.subheader("Profile Ingestion Portal")
    
    st.markdown("### Step 1: Automatic CV Data Extraction")
    uploaded_file = st.file_uploader("Drop candidate resume here (PDF format)", type=["pdf"])
    
    if uploaded_file is not None:
        if ai_model is None:
            st.error("AI configuration missing. Cannot parse automatically.")
        else:
            if st.button("Extract Data with Gemini AI", type="secondary"):
                with st.spinner("Analyzing resume content structure..."):
                    try:
                        parse_prompt = """
                        Analyze the attached resume PDF document. Extract key information and map it exactly into a raw JSON format. 
                        Do not include any formatting wrappers, backticks, or '```json' annotations. Return ONLY the raw JSON string matching this pattern:
                        {
                            "Candidate Name": "Extract full name",
                            "Role/Category": "Extract core title or function",
                            "Location": "Extract city/country if present",
                            "Budget": "Extract expected/current salary if mentioned, else leave blank",
                            "Email": "Extract primary contact email",
                            "Key Skills": "Comma-separated core competencies",
                            "AI Summary": "Provide a clean 2-sentence summary of candidate credentials"
                        }
                        """
                        response = ai_model.generate_content([
                            {"mime_type": "application/pdf", "data": uploaded_file.getvalue()},
                            parse_prompt
                        ])
                        
                        # Sanitize alternative response patterns cleanly
                        raw_response = response.text.strip()
                        clean_json_str = raw_response.replace("```json", "").replace("```", "").strip()
                        extracted_json = json.loads(clean_json_str)
                        
                        # Bind extracted metrics directly to UI states
                        st.session_state["c_name"] = extracted_json.get("Candidate Name", "")
                        st.session_state["c_role"] = extracted_json.get("Role/Category", "")
                        st.session_state["c_location"] = extracted_json.get("Location", "")
                        st.session_state["c_budget"] = extracted_json.get("Budget", "")
                        st.session_state["c_email"] = extracted_json.get("Email", "")
                        st.session_state["c_skills"] = extracted_json.get("Key Skills", "")
                        st.session_state["c_summary"] = extracted_json.get("AI Summary", "")
                        
                        st.success("✨ Context pulled! Review, modify or fill missing details below.")
                        st.rerun()
                    except Exception as parse_err:
                        st.error(f"Parsing process hit an anomaly: {str(parse_err)}")

    st.markdown("---")
    st.markdown("### Step 2: Verify Profile Details (Manual Location & Budget Override)")
    
    # Render layout using connected operational states
    col_in1, col_in2 = st.columns(2)
    with col_in1:
        name_input = st.text_input("Candidate Name *", key="c_name")
        role_input = st.text_input("Role / Functional Category *", key="c_role")
        location_input = st.text_input("Manual Location Specifics *", key="c_location", help="Provide or adjust geographical assignment.")
    
    with col_in2:
        budget_input = st.text_input("Budget Assignment / CTC Expected *", key="c_budget", help="Specify candidate rate requirements or role constraints.")
        email_input = st.text_input("Contact Email Address", key="c_email")
        skills_input = st.text_input("Key Core Skills", key="c_skills")
        
    summary_input = st.text_area("Profile Abstract / AI Summary Notes", key="c_summary")
    
    if st.button("Commit Profile to Database", type="primary"):
        if not name_input or not role_input or not location_input or not budget_input:
            st.error("Cannot execute save: Name, Role, Location, and Budget fields are strictly mandatory.")
        else:
            new_candidate = {
                "Candidate Name": name_input.strip(),
                "Role/Category": role_input.strip(),
                "Location": location_input.strip(),
                "Budget": budget_input.strip(),
                "Email": email_input.strip(),
                "Key Skills": skills_input.strip(),
                "AI Summary": summary_input.strip()
            }
            
            candidate_df = pd.DataFrame([new_candidate])
            updated_master_df = pd.concat([df, candidate_df], ignore_index=True)
            
            if use_gsheets and conn is not None:
                try:
                    conn.update(data=updated_master_df)
                    st.success(f"🚀 Success! '{name_input}' cleanly written to Google Sheets Database.")
                    
                    # Clear values to default for fresh entries
                    for k in state_keys.keys():
                        st.session_state[k] = ""
                    st.rerun()
                except Exception as update_err:
                    st.error(f"Live sync dropped: {str(update_err)}")
            else:
                st.session_state.candidate_db = updated_master_df
                st.success(f"💾 Saved locally to active browser session storage.")
                
                for k in state_keys.keys():
                    st.session_state[k] = ""
                st.rerun()

# --- TAB 3: AI TALENT ASSISTANT ---
with tab_ai:
    st.subheader("Recruitment Communication & Screening Copilot")
    
    if ai_model is None:
        st.error("Copilot is offline due to a lack of an active Gemini key.")
    else:
        ai_action = st.selectbox(
            "Choose a workload action:",
            [
                "Draft initial Candidate Screening Outreach Email",
                "Generate Technical Interview Screening Questions",
                "Review Profile against custom Job Specification"
            ]
        )
        
        pool_options = ["General Framework"]
        if not df.empty:
            pool_options.extend(df["Candidate Name"].unique().tolist())
            
        target_profile = st.selectbox("Select Target Profile Context:", pool_options)
        
        context_block = ""
        if target_profile != "General Framework" and not df.empty:
            c_row = df[df["Candidate Name"] == target_profile].iloc[0]
            context_block = (
                f"\n--- CANDIDATE DOSSIER ---\n"
                f"Name: {c_row['Candidate Name']}\n"
                f"Target Domain: {c_row['Role/Category']}\n"
                f"Location Assignment: {c_row['Location']}\n"
                f"Financial Param/Budget: {c_row['Budget']}\n"
                f"Skills: {c_row['Key Skills']}\n"
                f"Profile Abstract: {c_row['AI Summary']}\n"
                f"--------------------------\n"
            )
            
        if "Outreach" in ai_action:
            prompt_input = st.text_input("Enter company or project specific perks/context:", placeholder="e.g., TechCorp's new automated supply chain platform project")
            sys_directive = f"You are an executive talent acquisition partner. Write a highly compelling, personalized outreach email based on this candidate's profile data. {context_block}"
        elif "Questions" in ai_action:
            prompt_input = st.text_input("Specify critical tech stack components or topics to test:", placeholder="e.g., Python concurrency, data validation pipelines")
            sys_directive = f"You are a technical vetting manager. Draft 5 nuanced, non-generic screening questions customized to probe this profile's listed skills and target role. {context_block}"
        else:
            prompt_input = st.text_area("Paste the baseline Target Job Description below:")
            sys_directive = f"You are a talent evaluation specialist. Evaluate this profile context against the target job description. List clear Match Strengths, potential Gap Risks, and an onboarding budget verdict based on financial context. {context_block}"

        if st.button("Generate Strategy Output", type="primary"):
            if not prompt_input:
                st.warning("Please supply descriptive parameters to proceed.")
            else:
                with st.spinner("Compiling insights..."):
                    try:
                        final_prompt = f"{sys_directive}\n\nInput Context Parameters: {prompt_input}"
                        out_res = ai_model.generate_content(final_prompt)
                        st.markdown("### 📄 Compiled Output")
                        st.text_area("Output Data Workspace", value=out_res.text, height=450)
                    except Exception as generic_ai_err:
                        st.error(f"Generation interrupted: {str(generic_ai_err)}")
