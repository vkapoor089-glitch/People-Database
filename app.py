import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pypdf
import json
import pandas as pd

# 1. Setup Page Configurations
st.set_page_config(page_title="IT Sourcing Engine", page_icon="💼", layout="wide")
st.title("🤖 Intelligent IT Sourcing & Matching Engine")

st.sidebar.header("🔑 Configuration")

# 2. Check for AI API Key Configuration
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    st.sidebar.success("Gemini API Key loaded from Secrets")
else:
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
    if api_key:
        genai.configure(api_key=api_key)
    else:
        st.sidebar.warning("Please enter your Gemini API key to activate AI features.")

# Future-proofing: Dropdown to switch models dynamically if Google updates strings
selected_model = st.sidebar.selectbox(
    "🤖 Gemini Model Version",
    ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
    index=0,
    help="If you encounter a 404 error, switch to a newer version like gemini-2.5-flash."
)

# 3. Detect and Initialize Database Strategy (GSheets vs. Session State Fallback)
use_gsheets = False
if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        use_gsheets = True
        st.sidebar.success("🔒 Connected to Google Sheets Live Database")
    except Exception as conn_err:
        st.sidebar.error(f"Failed to bind Google Sheet: {str(conn_err)}")

if not use_gsheets:
    st.info("ℹ️ Running on local temporary memory. Set up 'connections.gsheets' in Streamlit Secrets to persist data to Google Sheets permanently.")
    if "candidate_db" not in st.session_state:
        st.session_state.candidate_db = []

# Helper function to reliably fetch current data pool as a Pandas DataFrame
def load_data_pool():
    required_cols = ['name', 'expected_budget_lpa', 'current_location', 'total_experience_years', 'keyskills', 'top_projects']
    if use_gsheets:
        try:
            df_sheet = conn.read(ttl=0)
            if df_sheet.empty:
                return pd.DataFrame(columns=required_cols)
            for col in required_cols:
                if col not in df_sheet.columns:
                    df_sheet[col] = ""
            return df_sheet[required_cols]
        except Exception:
            return pd.DataFrame(columns=required_cols)
    else:
        if not st.session_state.candidate_db:
            return pd.DataFrame(columns=required_cols)
        return pd.DataFrame(st.session_state.candidate_db)

# Helper function to save current state back to the active database layer
def save_data_pool(updated_df):
    if use_gsheets:
        conn.update(data=updated_df)
    else:
        st.session_state.candidate_db = updated_df.to_dict(orient="records")

# --- APP TABS ---
tab1, tab2, tab3 = st.tabs(["📤 Upload Resumes", "🗂️ Candidate Database", "🎯 Match Job Description"])

# ==========================================
# TAB 1: RESUME UPLOAD & PARSING
# ==========================================
with tab1:
    st.header("Upload Candidate Resumes")
    uploaded_files = st.file_uploader("Drop PDF resumes here", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_files and not api_key:
        st.error("API key configuration required to extract resume insights.")
        
    if uploaded_files and api_key:
        if st.button("Parse and Index Resumes"):
            current_pool_df = load_data_pool()
            new_rows = []
            
            for uploaded_file in uploaded_files:
                with st.spinner(f"Processing {uploaded_file.name}..."):
                    try:
                        pdf_reader = pypdf.PdfReader(uploaded_file)
                        resume_text = ""
                        for page in pdf_reader.pages:
                            text = page.extract_text()
                            if text:
                                resume_text += text + "\n"
                        
                        # Utilizing the model selected in the sidebar configuration
                        model = genai.GenerativeModel(selected_model)
                        prompt = f"""
                        You are an expert IT technical recruiter. Parse the following resume text and extract the information into a valid JSON object.
                        Do not include any markdown formatting wrappers (like ```json). Return ONLY the raw JSON string.
                        
                        Required JSON structure:
                        {{
                            "name": "Candidate Full Name or 'Unknown'",
                            "total_experience_years": 0.0,
                            "keyskills": ["Skill1", "Skill2"],
                            "top_projects": ["Project summary 1", "Project summary 2"]
                        }}

                        Resume text to parse:
                        {resume_text}
                        """
                        
                        response = model.generate_content(prompt)
                        clean_json = response.text.strip().replace("```json", "").replace("```", "")
                        candidate_data = json.loads(clean_json)
                        
                        skills_string = ", ".join(candidate_data.get("keyskills", []))
                        projects_string = " | ".join(candidate_data.get("top_projects", []))
                        
                        structured_row = {
                            "name": candidate_data.get("name", "Unknown"),
                            "expected_budget_lpa": 0.0,
                            "current_location": "Not Specified",
                            "total_experience_years": float(candidate_data.get("total_experience_years", 0.0)),
                            "keyskills": skills_string,
                            "top_projects": projects_string
                        }
                        
                        new_rows.append(structured_row)
                        st.success(f"Successfully processed details for {structured_row['name']}!")
                        
                    except Exception as e:
                        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
            
            if new_rows:
                new_data_df = pd.DataFrame(new_rows)
                combined_df = pd.concat([current_pool_df, new_data_df], ignore_index=True)
                save_data_pool(combined_df)
                st.toast("All records successfully written to database!", icon="🚀")

# ==========================================
# TAB 2: CENTRAL DATABASE & EDITING
# ==========================================
with tab2:
    st.header("Talent Pool Database")
    st.write("Review parsed technical specs and manually add Budget/CTC (in LPA) and Location constraints.")
    
    df_pool = load_data_pool()
    
    if df_pool.empty:
        st.info("No candidates uploaded yet. Head over to the upload tab!")
    else:
        edited_df = st.data_editor(
            df_pool, 
            num_rows="dynamic",
            column_config={
                "name": st.column_config.TextColumn("Candidate Name", disabled=True),
                "expected_budget_lpa": st.column_config.NumberColumn("Expected Budget (LPA)", format="%.2f"),
                "current_location": st.column_config.TextColumn("Current Location"),
                "total_experience_years": st.column_config.NumberColumn("Exp (Years)", disabled=True),
                "keyskills": st.column_config.TextColumn("Extracted Keyskills", disabled=True),
                "top_projects": st.column_config.TextColumn("Key Projects", disabled=True)
            },
            key="db_editor"
        )
        
        if st.button("Save Database Changes"):
            save_data_pool(edited_df)
            st.toast("Database modifications committed successfully!", icon="💾")

# ==========================================
# TAB 3: JOB DESCRIPTION MATCHING
# ==========================================
with tab3:
    st.header("Smart Match Job Description")
    
    col1, col2 = st.columns(2)
    with col1:
        max_budget = st.number_input("Max Budget Constraint (LPA)", min_value=0.0, value=15.0)
    with col2:
        target_location = st.text_input("Target Location Filter (e.g., Delhi, Noida, Remote)", value="")
        
    jd_text = st.text_area("Paste the Job Description (JD) here", height=250)
    
    if st.button("Run AI Sourcing Matcher") and jd_text:
        df_pool = load_data_pool()
        
        if df_pool.empty:
            st.warning("Your database pool is empty. Please upload resumes first.")
        elif not api_key:
            st.error("AI API key verification missing.")
        else:
            with st.spinner("Analyzing profile configurations..."):
                candidates_list = df_pool.to_dict(orient="records")
                
                filtered_candidates = []
                for c in candidates_list:
                    if float(c['expected_budget_lpa']) > max_budget and float(c['expected_budget_lpa']) != 0.0:
                        continue
                    if target_location and target_location.lower() not in str(c['current_location']).lower():
                        continue
                    filtered_candidates.append(c)
                
                if not filtered_candidates:
                    st.error("No database files passed your operational location or cost parameter ceiling.")
                else:
                    try:
                        model = genai.GenerativeModel(selected_model)
                        
                        match_prompt = f"""
                        You are an advanced recruitment matching engine. Rank the following candidates against the provided Job Description (JD).
                        Assign a match percentage (0 to 100) based on skill overlap, project relevance, and experience alignment.
                        Provide a brief 1-sentence technical justification for your score.
                        Return ONLY a raw JSON array matching this structure, sorted from highest score to lowest:
                        [
                            {{
                                "name": "Candidate Name",
                                "match_score": 85,
                                "justification": "Candidate has strong alignment with the technical stack parameters required."
                            }}
                        ]

                        Job Description:
                        {jd_text}

                        Candidates Data Pool:
                        {json.dumps(filtered_candidates)}
                        """
                        
                        response = model.generate_content(match_prompt)
                        clean_match_json = response.text.strip().replace("```json", "").replace("```", "")
                        match_results = json.loads(clean_match_json)
                        
                        st.subheader("🎯 Best Fit Matches Found")
                        for rank, match in enumerate(match_results, 1):
                            score = match['match_score']
                            score_color = "🟢" if score >= 80 else ("🟡" if score >= 50 else "🔴")
                                
                            with st.container(border=True):
                                st.markdown(f"### {score_color} {rank}. {match['name']} — **{score}% Match**")
                                st.write(f"**AI Evaluation:** {match['justification']}")
                                
                    except Exception as e:
                        st.error(f"Failed to calculate semantic matching index: {str(e)}")
