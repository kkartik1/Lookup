import streamlit as st
import pandas as pd
import os
import io
import time
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="Excel Processor",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS to make the interface more compact
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    .stButton button {
        width: 100%;
    }
    .stDataFrame {
        max-height: 300px;
        overflow-y: auto;
    }
    /* Hide the Streamlit footer */
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Create a header
st.subheader("Excel Processing Tool")

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

# Create a layout with three columns
col1, col2, col3 = st.columns(3)

# File upload widgets in each column
with col1:
    st.write("Master Lookup")
    master_file = st.file_uploader("Upload Master Lookup", type=["xlsx", "xls"], key="master")

with col2:
    st.write("COSMOS Lookup")
    cosmos_file = st.file_uploader("Upload COSMOS Lookup", type=["xlsx", "xls"], key="cosmos")

with col3:
    st.write("Source Excel")
    source_file = st.file_uploader("Upload Source Excel", type=["xlsx", "xls"], key="source")

# Container for file summaries
summary_container = st.container()

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

# File summaries
with summary_container:
    if master_file or cosmos_file or source_file:
        st.write("File Summaries")
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
        
        # Display summary table
        if summary_data:
            st.dataframe(pd.DataFrame(summary_data), use_container_width=False, hide_index=True)
    
# Process button
if master_file and cosmos_file and source_file and not st.session_state.job_submitted:
    if st.button("Process Files"):
        with st.spinner("Processing files..."):
            # Simulate processing delay
            time.sleep(2)
            
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
    st.success(f"Job submitted successfully! Job ID: {st.session_state.job_id}")
    st.info("You will be notified via email when processing is complete.")
    
    # Add a reset button to start over
    if st.button("Start New Job"):
        # Reset the session state
        st.session_state.job_submitted = False
        st.session_state.job_id = None
        st.session_state.account_tab = None
        st.session_state.customer_tab = None
        st.session_state.department_tab = None
        st.experimental_rerun()
