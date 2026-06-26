import streamlit as st
import google.generativeai as genai
import pypdf
import json
import pandas as pd

# 1. Setup Page Configurations
st.set_page_config(page_title="IT Sourcing Engine", page_icon="💼", layout="wide")
st.title("🤖 Intelligent IT Sourcing & Matching Engine")
st.write("Upload resumes, enrich profiles with budget/location, and match them against JDs instantly.")

# 2. API Key Configuration (Checks Secrets first, falls back to sidebar if missing)
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
else:
    st.sidebar.header("🔑 Configuration")
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password", help="Get a free key from Google AI Studio")
    if api_key:
        genai.configure(api_key=api_key)
    else:
        st.sidebar.warning("Please enter your Gemini API key to activate the AI features.")

# 3. Initialize Our In-Memory Database
if "candidate_db" not in st.session_state:
    st.session_state.candidate_db = []

# --- APP TABS ---
tab1, tab2, tab3 = st.tabs(["📤 Upload Resumes", "🗂️ Candidate Database", "🎯 Match Job Description"])

# ==========================================
# TAB 1: RESUME UPLOAD & PARSING
# ==========================================
with tab1:
    st.header("Upload Candidate Resumes")
    uploaded_files = st.file_uploader("Drop PDF resumes here", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_files and not api_key:
        st.error("Please add your Gemini API Key via Streamlit Secrets or the sidebar to parse these resumes!")
        
    if uploaded_files and api_key:
        if st.button("Parse and Index Resumes"):
            for uploaded_file in uploaded_files:
                with st.spinner(f"Processing {uploaded_file.name}..."):
                    try:
                        # Extract text from PDF
                        pdf_reader = pypdf.PdfReader(uploaded_file)
                        resume_text = ""
                        for page in pdf_reader.pages:
                            text = page.extract_text()
                            if text:
                                resume_text += text + "\n"
                        
                        # Call Gemini to parse into strict structured JSON
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        prompt = f"""
                        You are an expert IT technical recruiter. Parse the following resume text and extract the information into a valid JSON object.
                        Do not include any markdown formatting wrappers (like ```json). Return ONLY the raw JSON string.
                        
                        Required JSON structure:
                        {{
                            "name": "Candidate Full Name or 'Unknown'",
                            "total_experience_years": 0.0,
                            "keyskills": ["Skill1", "Skill2", "Skill3"],
                            "top_projects": ["Brief description of project 1", "Brief description of project 2"]
                        }}

                        Resume text to parse:
                        {resume_text}
                        """
                        
                        response = model.generate_content(prompt)
                        
                        # Standardize text to clean potential markdown wrappers if LLM includes them
                        clean_json = response.text.strip().replace("```json", "").replace("```", "")
                        candidate_data = json.loads(clean_json)
                        
                        # Add operational defaults that resumes don't usually explicitly state
                        candidate_data["expected_budget_lpa"] = 0.0  # Default 0, editable later
                        candidate_data["current_location"] = "Not Specified"
                        
                        # Save to our session database
                        st.session_state.candidate_db.append(candidate_data)
                        st.success(f"Successfully indexed {candidate_data['name']}!")
                        
                    except Exception as e:
                        st.error(f"Error processing {uploaded_file.name}: {str(e)}")

# ==========================================
# TAB 2: CENTRAL DATABASE & EDITING
# ==========================================
with tab2:
    st.header("Talent Pool Database")
    st.write("Review parsed technical specs and manually add Budget/CTC (in LPA) and Location constraints.")
    
    if not st.session_state.candidate_db:
        st.info("No candidates uploaded yet. Head over to the upload tab!")
    else:
        # Convert database to a DataFrame for editing via Streamlit's Data Editor
        df = pd.DataFrame(st.session_state.candidate_db)
        
        # Reorder columns for operational ease
        cols = ['name', 'expected_budget_lpa', 'current_location', 'total_experience_years', 'keyskills', 'top_projects']
        df = df[cols]
        
        # Display editable table
        edited_df = st.data_editor(
            df, 
            num_rows="dynamic",
            column_config={
                "name": st.column_config.TextColumn("Candidate Name", disabled=True),
                "expected_budget_lpa": st.column_config.
