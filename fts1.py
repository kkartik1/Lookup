import streamlit as st
import pandas as pd
import os
import io
import time
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="Financial Tagging Services | UHC",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# UHC-inspired theme and styling with correct UHC colors
st.markdown("""
<style>
    /* UHC Color Palette */
    :root {
        --uhc-blue: #002677;        /* Primary UHC blue */
        --uhc-light-blue: #0091da;  /* UHC light blue */
        --uhc-lighter-blue: #edf5fa; /* Very light blue for backgrounds */
        --uhc-gray: #5c5c5c;        /* Standard gray for text */
        --uhc-light-gray: #f2f2f2;  /* Light gray for backgrounds */
        --uhc-border-color: #d8dbe0; /* Border color */
    }
    
    /* Global Styling */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 1200px;
    }
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Arial', sans-serif;
        color: var(--uhc-blue);
        font-weight: 600;
    }
    
    .main-header {
        color: var(--uhc-blue);
        font-size: 2rem;
        margin-bottom: 0;
        font-weight: 600;
        margin-left: 1rem;
    }
    
    .header-line {
        border-bottom: 1px solid var(--uhc-light-blue);
        margin-bottom: 2rem;
        padding-bottom: 0.5rem;
    }
    
    /* Section Headers */
    .section-header {
        color: var(--uhc-blue);
        font-size: 1.5rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        font-weight: 500;
        border-bottom: 1px solid var(--uhc-border-color);
        padding-bottom: 0.5rem;
    }
    
    /* File upload areas */
    .upload-container {
        border: 1px dashed var(--uhc-border-color);
        border-radius: 5px;
        background-color: #f8f9fa;
        padding: 15px;
        margin-bottom: 1rem;
        height: 95%;
    }
    
    /* Buttons */
    .stButton button {
        background-color: var(--uhc-blue) !important;
        color: white !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
        padding: 0.5rem 2rem !important;
        border: none !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton button:hover {
        background-color: var(--uhc-light-blue) !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.15) !important;
    }
    
    /* Hide Streamlit branding */
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* Logo */
    .logo-container {
        display: flex;
        align-items: center;
        margin-bottom: 1rem;
    }
    
    .uhc-logo {
        background-color: var(--uhc-blue);
        width: 100px;
        height: 60px;
        border-radius: 4px;
        margin-right: 1rem;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 5px;
    }
    
    /* Custom UHC logo using CSS */
    .uhc-shield {
        position: relative;
        width: 24px;
        height: 40px;
        background: white;
        border-radius: 2px 2px 10px 10px;
        margin-right: 8px;
    }
    
    .uhc-shield::before {
        content: "";
        position: absolute;
        top: 5px;
        left: 6px;
        width: 4px;
        height: 30px;
        background: var(--uhc-blue);
        border-radius: 1px;
    }
    
    .uhc-shield::after {
        content: "";
        position: absolute;
        top: 5px;
        left: 14px;
        width: 4px;
        height: 30px;
        background: var(--uhc-blue);
        border-radius: 1px;
    }
    
    .uhc-text {
        color: white;
        font-family: Arial, sans-serif;
        font-weight: bold;
        font-size: 11px;
    }
    
    /* Custom styling for Streamlit elements */
    .stAlert {
        border-radius: 4px !important;
        border-width: 0px !important;
    }
    
    .stAlert > div {
        padding: 0.75rem 1rem !important;
    }
    
    /* Data tables with UHC styling */
    div[data-testid="stDataFrame"] > div {
        border: 1px solid var(--uhc-border-color) !important;
        border-radius: 4px !important;
    }
    
    div[data-testid="stDataFrame"] th {
        background-color: var(--uhc-blue) !important;
        color: white !important;
        font-weight: 600 !important;
    }
    
    div[data-testid="stDataFrame"] tr:nth-child(even) {
        background-color: var(--uhc-lighter-blue) !important;
    }
    
    div[data-testid="stDataFrame"] tr:hover {
        background-color: #e6f0f7 !important;
    }
    
    /* Progress bar UHC styling */
    div[data-testid="stProgressBar"] > div {
        background-color: var(--uhc-light-blue) !important;
    }
    
    /* Warning and success message styling */
    div[data-testid="stAlert"] {
        border-radius: 4px !important;
    }
</style>
""", unsafe_allow_html=True)
colx, coly = st.columns([0.1, 0.9])
with colx:
    with st.container():
        # Display logo
        st.image("UHC.png", width=50)  # Adjust width as needed

with coly:
    with st.container():# Rest of your app
        st.title("Financial Tagging Services")

# Function to identify tabs based on naming patterns
def identify_special_tabs(excel_file):
    account_tab = None
    customer_tab = None
    department_tab = None
    
    xls = pd.ExcelFile(excel_file)
    sheet_names = xls.sheet_names
    
    for sheet in sheet_names:
        if "ACC_A" in sheet:
            account_tab = sheet
        elif "CUST_A" in sheet:
            customer_tab = sheet
        elif "DEP_A" in sheet:
            department_tab = sheet
    
    return account_tab, customer_tab, department_tab

# Function to process the files (placeholder for actual processing)
def process_files(master_lookup, cosmos_lookup, source_file, account_tab, customer_tab, department_tab):
    # This is a placeholder function that would normally perform processing
    # In a real application, this would process the data and submit a job
    
    # For demonstration, we're just returning success
    st.session_state.job_id = f"JOB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return True


# Create a layout with three columns for file uploads
col1, col2, col3 = st.columns(3)

# File upload widgets in each column with UHC styled containers
with col1:
    with st.container():
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown('<strong style="color: var(--uhc-blue);">Master Lookup</strong>', unsafe_allow_html=True)
        master_file = st.file_uploader("Upload Master Lookup file", type=["xlsx", "xls"], key="master", label_visibility="collapsed")
        if master_file:
            st.markdown('<div style="margin-top: 0.5rem;"><span style="color: #28a745;">✅ File uploaded</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color: var(--uhc-gray); font-size: 0.9rem;">Upload Excel file (.xlsx, .xls)</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

with col2:
    with st.container():
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown('<strong style="color: var(--uhc-blue);">COSMOS Lookup</strong>', unsafe_allow_html=True)
        cosmos_file = st.file_uploader("Upload COSMOS Lookup file", type=["xlsx", "xls"], key="cosmos", label_visibility="collapsed")
        if cosmos_file:
            st.markdown('<div style="margin-top: 0.5rem;"><span style="color: #28a745;">✅ File uploaded</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color: var(--uhc-gray); font-size: 0.9rem;">Upload Excel file (.xlsx, .xls)</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
with col3:
    with st.container():
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown('<strong style="color: var(--uhc-blue);">Source Excel</strong>', unsafe_allow_html=True)
        source_file = st.file_uploader("Upload Source Excel file", type=["xlsx", "xls"], key="source", label_visibility="collapsed")
        if source_file:
            st.markdown('<div style="margin-top: 0.5rem;"><span style="color: #28a745;">✅ File uploaded</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color: var(--uhc-gray); font-size: 0.9rem;">Upload Excel file (.xlsx, .xls)</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
# Initialize session state variables if they don't exist
if 'account_tab' not in st.session_state:
    st.session_state.account_tab = None
if 'customer_tab' not in st.session_state:
    st.session_state.customer_tab = None
if 'department_tab' not in st.session_state:
    st.session_state.department_tab = None
if 'job_submitted' not in st.session_state:
    st.session_state.job_submitted = False
if 'job_id' not in st.session_state:
    st.session_state.job_id = None

# File summary section
if master_file or cosmos_file or source_file:
    st.markdown('<h2 class="section-header">File Summary</h2>', unsafe_allow_html=True)
    
    summary_data = []
    
    # Process Master Lookup if uploaded
    if master_file:
        try:
            xls = pd.ExcelFile(master_file)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(master_file, sheet_name=sheet_name)
                summary_data.append({
                    "File Name": master_file.name,
                    "Tab Name": sheet_name,
                    "Row Count": len(df),
                    "Column Count": len(df.columns)
                })
        except Exception as e:
            st.error(f"Error reading Master Lookup: {e}")
    
    # Process COSMOS Lookup if uploaded and identify special tabs
    if cosmos_file:
        try:
            # Reset file pointer
            cosmos_file.seek(0)
            
            # Identify special tabs
            account_tab, customer_tab, department_tab = identify_special_tabs(cosmos_file)
            st.session_state.account_tab = account_tab
            st.session_state.customer_tab = customer_tab
            st.session_state.department_tab = department_tab
            
            # Reset file pointer again before reading
            cosmos_file.seek(0)
            xls = pd.ExcelFile(cosmos_file)
            
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(cosmos_file, sheet_name=sheet_name)
                tab_type = ""
                if sheet_name == account_tab:
                    tab_type = " (Account)"
                elif sheet_name == customer_tab:
                    tab_type = " (Customer)"
                elif sheet_name == department_tab:
                    tab_type = " (Department)"
                    
                summary_data.append({
                    "File Name": cosmos_file.name,
                    "Tab Name": f"{sheet_name}{tab_type}",
                    "Row Count": len(df),
                    "Column Count": len(df.columns)
                })
        except Exception as e:
            st.error(f"Error reading COSMOS Lookup: {e}")
    
    # Process Source Excel if uploaded
    if source_file:
        try:
            xls = pd.ExcelFile(source_file)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(source_file, sheet_name=sheet_name)
                summary_data.append({
                    "File Name": source_file.name,
                    "Tab Name": sheet_name,
                    "Row Count": len(df),
                    "Column Count": len(df.columns)
                })
        except Exception as e:
            st.error(f"Error reading Source Excel: {e}")
    
    # Add updated UHC table styling
    st.markdown("""
    <style>
    .uhc-table {
        border-collapse: collapse;
        width: 100%;
        font-family: Arial, sans-serif;
        margin-bottom: 1rem;
    }
    .uhc-table th {
        background-color: #002677;
        color: white;
        font-weight: 600;
        text-align: left;
        padding: 12px 15px;
        border-bottom: 2px solid #ddd;
    }
    .uhc-table td {
        background-color: #002677;
        padding: 10px 15px;
        border-bottom: 1px solid #d8dbe0;
    }
    .uhc-table tr:nth-child(even) {
        background-color: #002677;
    }
    .uhc-table tr:hover {
        background-color: #e6f0f7;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Display summary table with UHC styling
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        
        # Apply UHC styling to dataframe
        st.dataframe(
            df_summary, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "File Name": st.column_config.TextColumn("File Name", width="medium"),
                "Tab Name": st.column_config.TextColumn("Tab Name", width="medium"),
                "Row Count": st.column_config.NumberColumn("Row Count", format="%d"),
                "Column Count": st.column_config.NumberColumn("Column Count", format="%d")
            }
        )

# Process button and status section
if master_file and cosmos_file and source_file:
    st.markdown('<h2 class="section-header">Process Files</h2>', unsafe_allow_html=True)
    
    if not st.session_state.job_submitted:
        # Use standard Streamlit warning with UHC styling
        st.warning('Files uploaded successfully. Click the button below to process files and generate tags.')
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Process Files"):
                with st.spinner("Processing files..."):
                    # Progress bar for visual feedback
                    progress_bar = st.progress(0)
                    for i in range(100):
                        time.sleep(0.02)
                        progress_bar.progress(i + 1)
                    
                    # Call the process function
                    success = process_files(
                        master_file, 
                        cosmos_file, 
                        source_file,
                        st.session_state.account_tab,
                        st.session_state.customer_tab,
                        st.session_state.department_tab
                    )
                    
                    if success:
                        st.session_state.job_submitted = True
                        st.experimental_rerun()
    
    # Show success message if job was submitted
    if st.session_state.job_submitted:
        # Use standard Streamlit success message
        st.success(f"Job submitted successfully! Job ID: {st.session_state.job_id}")
        
        # Use standard Streamlit info message
        st.info("You will be notified via email when processing is complete.")
        
        # Add a button to start new job
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Start New Job"):
                # Reset the session state
                for key in st.session_state.keys():
                    del st.session_state[key]
                st.experimental_rerun()

# Updated footer with UHC styling
st.markdown("""
<div style="background-color: #002677; padding: 0.8rem; color: white; border-radius: 4px; margin-top: 2rem; font-size: 0.8rem; text-align: center;">
    © 2025 UnitedHealthcare Services, Inc. All rights reserved.
</div>
""", unsafe_allow_html=True)
