code = """import streamlit as st
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
                        
                        prompt = f\"\"\"
                        You are an expert IT technical recruiter. Parse the following resume text and extract the information into a valid JSON object.
                        Do not include any markdown formatting wrappers (like ```
```text?code_stdout&code_event_index=2
SyntaxError found: unterminated string literal (detected at line 52) (app.py, line 52)

```json). Return ONLY the raw JSON string.
                        
                        Required JSON structure:
                        {{
                            "name": "Candidate Full Name or 'Unknown'",
                            "total_experience_years": 0.0,
                            "keyskills": ["Skill1", "Skill2", "Skill3"],
                            "top_projects": ["Brief description of project 1", "Brief description of project 2"]
                        }}

                        Resume text to parse:
                        {resume_text}
                        \"\"\"
                        
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
                "expected_budget_lpa": st.column_config.NumberColumn("Expected Budget (LPA)", format="%.2f"),
                "current_location": st.column_config.TextColumn("Current Location"),
                "total_experience_years": st.column_config.NumberColumn("Exp (Years)", disabled=True),
                "keyskills": st.column_config.ListColumn("Extracted Keyskills", disabled=True),
                "top_projects": st.column_config.ListColumn("Key Projects", disabled=True)
            },
            key="db_editor"
        )
        
        # Save modifications back to session state
        if st.button("Save Database Changes"):
            st.session_state.candidate_db = edited_df.to_dict(orient="records")
            st.toast("Database updated successfully!", icon="💾")

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
        if not st.session_state.candidate_db:
            st.warning("Your database is empty. Please upload resumes first.")
        elif not api_key:
            st.error("API key is missing.")
        else:
            with st.spinner("Analyzing profile matches using semantic layer..."):
                # 1. Apply operational hard filters first
                filtered_candidates = []
                for c in st.session_state.candidate_db:
                    # Budget Check
                    if c['expected_budget_lpa'] > max_budget and c['expected_budget_lpa'] != 0.0:
                        continue
                    # Simple Location Check (case-insensitive string match)
                    if target_location and target_location.lower() not in str(c['current_location']).lower():
                        continue
                    filtered_candidates.append(c)
                
                if not filtered_candidates:
                    st.error("No candidates passed your initial Budget or Location filter guardrails.")
                else:
                    try:
                        # 2. Use Gemini to contextually rank the candidates who passed the hard filters
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        match_prompt = f\"\"\"
                        You are an advanced recruitment matching engine. Rank the following candidates against the provided Job Description (JD).
                        Assign a match percentage (0 to 100) based on skill overlap, project relevance, and years of experience depth.
                        Provide a brief 1-sentence technical justification for your score.
                        Return ONLY a raw JSON array matching this structure, sorted from highest score to lowest:
                        [
                            {{
                                "name": "Candidate Name",
                                "match_score": 85,
                                "justification": "Candidate has strong React experience matching the frontend stack required."
                            }}
                        ]

                        Job Description:
                        {jd_text}

                        Candidates Data Pool:
                        {json.dumps(filtered_candidates)}
                        \"\"\"
                        
                        response = model.generate_content(match_prompt)
                        clean_match_json = response.text.strip().replace("```json", "").replace("```", "")
                        match_results = json.loads(clean_match_json)
                        
                        # Display Results Matrix
                        st.subheader("🎯 Best Fit Matches Found")
                        for rank, match in enumerate(match_results, 1):
                            score = match['match_score']
                            
                            # Visual health cues based on match strength
                            if score >= 80:
                                score_color = "🟢"
                            elif score >= 50:
                                score_color = "🟡"
                            else:
                                score_color = "🔴"
                                
                            with st.container(border=True):
                                st.markdown(f"### {score_color} {rank}. {match['name']} — **{score}% Match**")
                                st.write(f"**AI Evaluation:** {match['justification']}")
                                
                    except Exception as e:
                        st.error(f"Failed to calculate semantic matches: {str(e)}")
"""

try:
    compile(code, "app.py", "exec")
    print("No syntax error found in code literal!")
except SyntaxError as e:
    print(f"SyntaxError found: {e}")
