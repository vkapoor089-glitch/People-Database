import os
import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Page Config & Initialization
st.set_page_config(page_title="Candidate Sourcing DB", layout="wide")
st.title("📄 Candidate PDF to Sheets")

conn = st.connection("gsheets", type=GSheetsConnection)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 2. Cached Function to handle API Quota & File Processing
@st.cache_data(show_spinner=True)
def extract_info_from_pdf(uploaded_file_bytes, file_name):
    """
    Saves file to temp, processes with Gemini, and cleans up.
    """
    temp_path = f"temp_{file_name}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file_bytes)
    
    file_data = genai.upload_file(temp_path)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Extract these details from this resume: Full Name, Role, Location, Budget, Skills.
    Return ONLY in this CSV format: Name, Role, Location, Budget, Skills
    """
    
    response = model.generate_content([prompt, file_data])
    
    # Cleanup
    os.remove(temp_path)
    return response.text

# 3. UI Layout with Tabs
tab1, tab2, tab3 = st.tabs(["Upload Profile", "Database", "AI Comparison"])

with tab1:
    st.header("Upload Candidate Profile")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    
    if uploaded_file:
        if st.button("Process & Save"):
            try:
                raw_data = extract_info_from_pdf(uploaded_file.getvalue(), uploaded_file.name)
                parsed = raw_data.split(',')
                df_new = pd.DataFrame([parsed], columns=["Name", "Role", "Location", "Budget", "Skills"])
                
                st.write("Extracted Data:", df_new)
                
                # Append to Sheet
                existing = conn.read()
                updated = pd.concat([existing, df_new], ignore_index=True)
                conn.update(data=updated)
                st.success("Successfully added to database!")
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.header("Candidate Database")
    data = conn.read()
    st.dataframe(data)

with tab3:
    st.header("AI Comparison")
    st.info("Upload and process profiles to see side-by-side AI analysis here.")
