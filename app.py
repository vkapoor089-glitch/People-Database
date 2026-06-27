import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Setup Configuration
st.set_page_config(page_title="Candidate Sourcing DB")
st.title("📄 Candidate PDF to Sheets")

# Initialize connections
conn = st.connection("gsheets", type=GSheetsConnection)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 2. Cached Function to save Quota
@st.cache_data(show_spinner=True)
def extract_info_from_pdf(pdf_bytes):
    """
    Parses PDF and extracts key fields using Gemini.
    Cached to prevent hitting the 20-request daily limit during refreshes.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Uploading file as data for Gemini
    file_data = genai.upload_file(pdf_bytes) 
    
    prompt = """
    Extract the following details from this resume: 
    Full Name, Current Role, Location, Expected Budget, Key Skills.
    Return the output in a clean, comma-separated format:
    Name, Role, Location, Budget, Skills
    """
    
    response = model.generate_content([prompt, file_data])
    return response.text

# 3. Main Interface
uploaded_file = st.file_uploader("Upload Candidate Resume (PDF)", type="pdf")

if uploaded_file:
    # Process with AI
    with st.spinner("Analyzing resume..."):
        ai_data = extract_info_from_pdf(uploaded_file)
        # Assuming AI returns: "John Doe, Engineer, New York, 50k, Python"
        parsed_data = ai_data.split(',')
        
        # Display extracted data
        st.success("Analysis Complete!")
        df_new = pd.DataFrame([parsed_data], columns=["Name", "Role", "Location", "Budget", "Skills"])
        st.table(df_new)
        
        # Save to Google Sheets
        if st.button("Save to Database"):
            existing_data = conn.read()
            updated_df = pd.concat([existing_data, df_new], ignore_index=True)
            conn.update(data=updated_df)
            st.success("Saved to Google Sheets!")

# 4. View Database
st.subheader("Current Database")
data = conn.read()
st.dataframe(data)
