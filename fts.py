import streamlit as st
import pandas as pd
import os
import io
import re
import time
from datetime import datetime
import fts_main
from fts_main import *
import threading
import fts_validate  
from fts_validate import * 
# Add required email imports
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
# Import for thread context management
from streamlit.runtime.scriptrunner import add_script_run_ctx

# Load CSS from external file
def load_css(css_file):
    with open(css_file, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def load_system_file(sys_type):
    """Load the system mapping CSV file that should be present at deployment site"""
    try:
        sys_conf = pd.read_csv("System_Details.csv")
        # In production, use the actual path where the mapping file is stored
        return sys_conf[sys_conf['System']==sys_type]
    except FileNotFoundError:
        st.error("System mapping file not found. Please place it in the application directory.")
        return None

def load_mapping_file(sys_type):
    """Load the mapping CSV file that should be present at deployment site"""
    try:
        # In production, use the actual path where the mapping file is stored
        if sys_type == 'COSMOS':
            return pd.read_csv("FTS_Mapping.csv")
        else:
            return pd.read_csv("FTS_Dental_Mapping.csv")
    except FileNotFoundError:
        st.error("Mapping file for {sys_type} not found. Please place it in the application directory.")
        return None


def validate_file_extension(file):
    """Validate if the file has an Excel extension"""
    if file is None:
        return False
    
    filename = file.name
    _, file_extension = os.path.splitext(filename)
    
    # Check if the file extension is valid
    valid_extensions = ['.xlsx', '.xls']
    return file_extension.lower() in valid_extensions


def validate_required_columns(df, required_columns):
    """Validate if the dataframe contains all required columns"""
    missing_columns = [col for col in required_columns if col not in df.columns]
    return len(missing_columns) == 0, missing_columns



def get_required_columns_from_mapping(mapping_df, column_type):
    """Get required columns from mapping file based on type (IN)"""
    if column_type != 'Target':
        in_mappings = mapping_df[mapping_df['Type'] == 'IN']
    else:
        in_mappings = mapping_df
    # Filter out None/NaN values before returning the list
    return [col for col in in_mappings[column_type].unique().tolist() if pd.notna(col)]

def check_special_chars(summary_data, file_df, mapping_df, tab_lst):
    for i in range(len(file_df)):
        er = False
        err = []
        # Check for special characters in all files
        invalid_cells = check_special_characters(file_df[i], [x for x in mapping_df[tab_lst[i]].dropna().tolist() if x != 'LOOKUP_CODE'])
        if invalid_cells:
            err.append("{summary_data['File Name'].iloc[i]} contains invalid special characters:")
            for idx, col, value, chars in invalid_cells[:5]:  # Show first 5
               err.append(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
            return er, err
    return False, []
    

def check_special_characters(df, cols):
    """Check for special characters in all columns except allowed ones"""
    allowed_chars = ['%', '-', '/', ')', '(', '>', '<', '.', '+']
    allowed_pattern = r'^[a-zA-Z0-9\s' + ''.join([re.escape(c) for c in allowed_chars]) + ']*$'
    
    invalid_cells = []
    
    for col in cols:
        for idx, value in df[col].astype(str).items():
            if not re.match(allowed_pattern, value):
                invalid_chars = [c for c in value if c not in allowed_chars and not c.isalnum() and not c.isspace()]
                if invalid_chars:
                    invalid_cells.append((idx, col, value, ''.join(set(invalid_chars))))
    
    return invalid_cells


# Function to identify tabs based on naming patterns
def identify_special_tabs(excel_file, sys_df):  
    tabs=[]
    map_tabs = []
    xls = pd.ExcelFile(excel_file)
    sheet_names = xls.sheet_names    
    for sheet in sheet_names:
        for index, row in sys_df.iterrows():
            if row['Tab'] in sheet:
                tabs.append(sheet)
                map_tabs.append(row['Tab'])
    return tabs, map_tabs

def validate_email(email):
    """Validate email format for specific domains: uhc.com and optum.com only"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@(?:uhc\.com|optum\.com)$'
    return re.match(email_pattern, email) is not None


def process_file_errors(inp_file, sys_df, mapping_df, summary_data, file_df, tab_lst):
    er = False
    err = ''
    try:
        if not validate_file_extension(inp_file):
            er = True
            err = "Only Excel files (.xlsx, .xls) are allowed."
            return er, err, summary_data, file_df, tab_lst  
        print(sys_df)
        
        if len(sys_df) > 1:
            inp_file.seek(0)
            # Identify special tabs
            tabs, map_tabs = identify_special_tabs(inp_file, sys_df)
            if len(tabs) != len(sys_df):
                er = True
                err = f"{sys_df['File'].iloc[0]} file doesn't contain the required tabs."
                return er, err, summary_data, file_df, tab_lst
            # Reset file pointer again before reading
            inp_file.seek(0)
        xls = pd.ExcelFile(inp_file)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(inp_file, sheet_name=sheet_name)
            file_df.append(df)
            if  len(sys_df) > 1:
                if sheet_name in tabs:
                    tab_lst.append(map_tabs[tabs.index(sheet_name)])
                    required_columns = get_required_columns_from_mapping(mapping_df, map_tabs[tabs.index(sheet_name)])
                else:
                    continue
            else:
                tab_lst.append(sys_df['Tab'].iloc[0])
                required_columns = get_required_columns_from_mapping(mapping_df, sys_df['Tab'].iloc[0])
            # Validate required columns in Account file
            account_valid, account_missing = validate_required_columns(df, required_columns)
            if not account_valid:
                err = f"{inp_file.name} is missing required columns: {', '.join(account_missing)}"
                er = True
                return er, err, summary_data, file_df, tab_lst   
            summary_data.append({
                "File Name": inp_file.name,
                "Tab Name": sheet_name,
                "Row Count": len(df),
                "Column Count": len(df.columns)
            })
        return er, err, summary_data, file_df, tab_lst   
    except Exception as e:
        st.error(f"Error reading Source Excel: {e}")

# Function to process the files (placeholder for actual processing)
def process_files(master_lookup, cosmos_lookup, source_file, account_tab, customer_tab, department_tab,email):
    # This is a placeholder function that would normally perform processing
    # In a real application, this would process the data and submit a job
    s = False
    try:
        df_target = pd.read_excel(source_file  , dtype=str)
        df_master = pd.read_excel(master_lookup , dtype=str)
        df_account = pd.read_excel(cosmos_lookup , sheet_name=account_tab, dtype=str)
        df_customer = pd.read_excel(cosmos_lookup , sheet_name=customer_tab, dtype=str)
        df_department = pd.read_excel(cosmos_lookup , sheet_name=department_tab, dtype=str)    
        df_map = pd.read_csv('FTS_MappingSheet.csv')
        
        background_thread = threading.Thread(target=fts_main.main, args=(df_target, df_master, df_account, df_customer, df_department, df_map,email))
        # Add script context to thread
        add_script_run_ctx(background_thread)
        # Start the thread
        background_thread.start()
        s = True
    except Exception as e:
        s = False
        print(e)
    print("Exiting process_files() with status: ",s)
    return s

def main():
    # Set page configuration
    st.set_page_config(
        page_title="Financial Tagging Services | UHC",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Load the UHC style CSS
    load_css("uhc_style.css")

    # Initialize page state if not exists
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'main'

    # Header with logo and title
    colx, coly, colz = st.columns([0.05, 0.8, 0.15])
    with colx:
        with st.container():
            st.text(" ")
            st.text(" ")
            # Display logo
            st.image("UHC.png", width=45)  # Adjust width as needed

    with coly:
        with st.container():  # Rest of your app
            st.text(" ")
            st.text(" ")
            st.markdown('<h2 class="main-header"; style="color: var(--uhc-blue);">Financial Tagging Service – Precheck Solution</h2>', unsafe_allow_html=True)
    
    # Data Comparison button in top right - only show on main page with fixed width
    with colz:
        with st.container():
            st.text(" ")
            # Only show the button on the main page
            if st.session_state.current_page == 'main':
                # Use markdown to create a styled button container
                st.markdown("""
                <style>
                .stButton > button {
                    white-space: nowrap;
                    min-width: 130px;
                }
                </style>
                """, unsafe_allow_html=True)
                if st.button("Data Comparison", key="data_comparison_btn"):
                    st.session_state.current_page = 'comparison'
                    st.rerun()
    
    # Display the appropriate page based on session state
    if st.session_state.current_page == 'comparison':
        render_comparison_page()
    else:
        render_main_page()
    
    # Updated footer with UHC styling
    st.markdown("""
    <div style="background-color: #002677; padding: 0.8rem; color: white; border-radius: 4px; margin-top: 2rem; font-size: 0.8rem; text-align: center;">
        © 2025 UnitedHealthcare Services, Inc. All rights reserved.
    </div>
    """, unsafe_allow_html=True)

def render_comparison_page():
    """Render the data comparison page"""
    st.markdown('<h3 style="color: var(--uhc-blue);">Data Comparison</h3>', unsafe_allow_html=True)
    
    col_val1, col_val2 = st.columns(2)
    
    with col_val1:
        with st.container():
            st.markdown('<h6 style="color: var(--uhc-blue);">Upload FTS Pre-Check generated output file</h6>', unsafe_allow_html=True)
            source_validation_file = st.file_uploader("Upload FTS Pre-Check generated output file", type=["xlsx", "xls"], key="source_comparison", label_visibility="collapsed")
    
    with col_val2:
        with st.container():
            st.markdown('<h6 style="color: var(--uhc-blue);">Upload FTS Tagged Source file</h6>', unsafe_allow_html=True)
            target_validation_file = st.file_uploader("Upload FTS Tagged Source file", type=["xlsx", "xls"], key="target_comparison", label_visibility="collapsed")
    
    # Better CSS for button alignment
    st.markdown("""
    <style>
    /* Ensure button is vertically centered with input field */
    div[data-testid="column"]:nth-child(3) .stButton {
        margin-top: 0px;
        padding-top: 0px;
        height: 38px;
        display: flex;
        align-items: center;
    }
    div[data-testid="column"]:nth-child(3) .stButton > button {
        margin-top: 0px;
        height: 38px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Email notification section with better aligned button
    colx, coly, colz = st.columns([0.35, 0.30, 0.35])
    with colx:
        st.markdown('Please enter an Email ID to receive notification:</p>', unsafe_allow_html=True)
    with coly:
        if 'comparison_email' not in st.session_state:
            st.session_state.comparison_email = st.session_state.validation_email if 'validation_email' in st.session_state else None
        email = st.text_input(" ", value=st.session_state.comparison_email, key="comparison_email_input", label_visibility="collapsed")
    
    # Initialize comparison submitted state if not exists
    if 'comparison_submitted' not in st.session_state:
        st.session_state.comparison_submitted = st.session_state.validation_submitted if 'validation_submitted' in st.session_state else False
    
    # Create notification area below email section
    notification_area = st.container()
    
    # Button state tracking
    button_clicked = False
    
    if source_validation_file and target_validation_file:
        # Validate file extensions
        if not validate_file_extension(source_validation_file) or not validate_file_extension(target_validation_file):
            with notification_area:
                st.error("Only Excel files (.xlsx, .xls) are allowed.")
        else:
            # Check email validity
            email_valid = True
            if not email:
                with notification_area:
                    st.error("Email address is required.")
                email_valid = False
            elif not validate_email(email):
                with notification_area:
                    st.error("Please enter a valid email address ending with optum.com or uhc.com.")
                email_valid = False
            else:
                st.session_state.comparison_email = email
            
            # Display the compare button in the third column if email is valid
            with colz:
                if email_valid and not st.session_state.comparison_submitted:
                    if st.button("Compare Files"):
                        button_clicked = True
            
            if button_clicked:
                with notification_area:
                    with st.spinner("Comparing files..."):
                        try:
                            # Read the Excel files - ensure correct assignment
                            df_source = pd.read_excel(source_validation_file, dtype=str)  # Process generated Output
                            df_target = pd.read_excel(target_validation_file, dtype=str)  # FTS Tagged Output
                            
                            # Create a background thread for comparison
                            def validation_thread():
                                try:
                                    # Call the validation function and get the results
                                    comparison_results = fts_validate.main(df_source, df_target, email)  # Keep parameter order
                                    # Store results in session state for display
                                    st.session_state.comparison_results = comparison_results
                                except Exception as e:
                                    print(f"Error in comparison thread: {str(e)}")
                    
                            # Start the background thread
                            background_thread = threading.Thread(target=validation_thread)
                            # Add script context to thread
                            add_script_run_ctx(background_thread)
                            background_thread.start()
                            
                            # Mark as submitted
                            st.session_state.comparison_submitted = True
                            
                            # Display notifications horizontally below email section
                            not_col1, not_col2 = st.columns(2)
                            with not_col1:
                                st.success("Sheets submitted for comparison!")
                            with not_col2:
                                st.info(f"You'll receive an email with the comparison file at: {email}")
                            
                        except Exception as e:
                            st.error(f"Error during comparison: {str(e)}")
                            import traceback
                            st.error(traceback.format_exc())
            
            elif st.session_state.comparison_submitted:
                with notification_area:
                    st.warning('Comparison already submitted, please start a new session to rerun.')
    
    # Display comparison results if available
    if 'comparison_results' in st.session_state and st.session_state.comparison_results is not None:
        st.markdown('<h5 style="color: var(--uhc-blue);">Comparison Results</h5>', unsafe_allow_html=True)
        
        # Display the dataframe
        st.dataframe(st.session_state.comparison_results)
        
        # Add download button for Excel file
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            st.session_state.comparison_results.to_excel(writer, index=False, sheet_name='Comparison_Results')
        
        buffer.seek(0)
        
        st.download_button(
            label="Download Results as Excel",
            data=buffer,
            file_name=f"comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.ms-excel"
        )

def render_main_page():
    """Render the main application page"""
    # Create layout with label and radio on the same line
    col1, col2 = st.columns([1, 5])
    with col1:
        st.markdown('')
        st.markdown('')
        st.markdown('<h6 style="color: var(--uhc-blue);">Select Platform</h6>', unsafe_allow_html=True)
    with col2:
        sys_type = st.radio(
            label="",
            options=["COSMOS", "FACETS"],
            index=0,
            horizontal=True,
            key="platform_choice"
        )
    # Load the systems file
    sys_df = load_system_file(sys_type)
    if sys_df is None:
        return
    # Load the mapping file
    mapping_df = load_mapping_file(sys_type)
    if mapping_df is None:
        return
    if sys_type == 'COSMOS':
        # Create a layout with three columns for file uploads
        col1, col2, col3 = st.columns(3)
        # File upload widgets in each column with UHC styled containers
        with col1:
            with st.container():
                st.markdown('<h6 style="color: var(--uhc-blue);">Upload MASTER COSGP PS LOOKUP</h6>', unsafe_allow_html=True)
                master_file = st.file_uploader("Upload Master Lookup file", type=["xlsx", "xls"], key="master", label_visibility="collapsed")
        with col2:
            with st.container():
                st.markdown('<h6 style="color: var(--uhc-blue);">Upload COSMOS9 CL PS LOOKUP</h6>', unsafe_allow_html=True)
                cosmos_file = st.file_uploader("Upload COSMOS Lookup file", type=["xlsx", "xls"], key="cosmos", label_visibility="collapsed")        
        with col3:
            with st.container():
                st.markdown('<h6 style="color: var(--uhc-blue);">Upload COSMOS SOURCE</h6>', unsafe_allow_html=True)
                source_file = st.file_uploader("Upload Source Excel file", type=["xlsx", "xls"], key="cos_src", label_visibility="collapsed")
                
    else:
        # Create a layout with FOUR columns for file uploads
        col1, col2, col3, col4 = st.columns(4)
        
        # File upload widgets in each column with UHC styled containers
        with col1:
            with st.container():
                st.markdown('<h6 style="color: var(--uhc-blue);">Upload UHSBPS9 CL PS LOOKUP</h6>', unsafe_allow_html=True)
                facets_master_file = st.file_uploader("Upload Master Lookup file", type=["xlsx", "xls"], key="lookup", label_visibility="collapsed")
        with col2:
            with st.container():
                st.markdown('<h6 style="color: var(--uhc-blue);">Upload UHCSB POST TAGGING</h6>', unsafe_allow_html=True)
                facets_post_file = st.file_uploader("Upload COSMOS Lookup file", type=["xlsx", "xls"], key="tagging", label_visibility="collapsed")        
        with col3:
            with st.container():
                st.markdown('<h6 style="color: var(--uhc-blue);">Upload UHCSB POST TAG CLM</h6>', unsafe_allow_html=True)
                facets_post_clm = st.file_uploader("Upload Source Excel file", type=["xlsx", "xls"], key="tagclm", label_visibility="collapsed")
        with col4:
            with st.container():
                st.markdown('<h6 style="color: var(--uhc-blue);">Upload FACETS SOURCE</h6>', unsafe_allow_html=True)
                facets_source_file = st.file_uploader("Upload Source Excel file", type=["xlsx", "xls"], key="source", label_visibility="collapsed")
    
    # Initialize session state variables if they don't exist
    if 'email' not in st.session_state:
        st.session_state.email = None
    if 'job_submitted' not in st.session_state:
        st.session_state.job_submitted = False
    # Email notification section
    colx, coly, colz = st.columns([0.35, 0.30, .35])
    with colx:
        st.markdown('Please enter an Email ID to receive notification:</p>', unsafe_allow_html=True)
    with coly:
        email = st.text_input(" ", value=st.session_state.email, key="email_input", label_visibility="collapsed")
        
    #create compact layout with two columns
    cola, colb = st.columns(2)
    with cola: 
        summary_data = []
        file_df = []
        tab_lst = []
        if sys_type == 'COSMOS':
            if master_file or cosmos_file or source_file:
                st.markdown('<h6 class="section-header"; style="color: var(--uhc-blue);">File Summary</h6>', unsafe_allow_html=True)
                if master_file:
                    sys_inp_df = sys_df[(sys_df['System'] == 'COSMOS') & (sys_df['Tab'] == 'MASTER')]
                    er, err, summary_data, file_df, tab_lst = process_file_errors(master_file, sys_inp_df, mapping_df, summary_data, file_df, tab_lst)
                    if er:
                        st.error(err)
                        return
                if cosmos_file:
                    sys_inp_df = sys_df[(sys_df['System'] == 'COSMOS') & (sys_df['File'] == 'COSMOS9 CL PS LOOKUP')]
                    er, err, summary_data, file_df, tab_lst = process_file_errors(cosmos_file, sys_inp_df, mapping_df, summary_data, file_df, tab_lst)
                    if er:
                        st.error(err)
                        return
                if source_file:
                    sys_inp_df = sys_df[(sys_df['System'] == 'COSMOS') & (sys_df['Tab'] == 'Target')]
                    er, err, summary_data, file_df, tab_lst = process_file_errors(source_file, sys_inp_df, mapping_df, summary_data, file_df, tab_lst)
                    if er:
                        st.error(err)
                        return
        else:
            if facets_master_file or facets_post_file or facets_post_clm or facets_source_file:
                if facets_master_file:
                    sys_inp_df = sys_df[(sys_df['System'] == 'FACETS') & (sys_df['File'] == 'UHSBPS9 CL PS LOOKUP')]
                    er, err, summary_data, file_df, tab_lst = process_file_errors(facets_master_file, sys_inp_df, mapping_df, summary_data, file_df, tab_lst)
                    if er:
                        st.error(err)
                        return
                if facets_post_file:
                    sys_inp_df = sys_df[(sys_df['System'] == 'FACETS') & (sys_df['File'] == 'UHCSB POST TAGGING')]
                    er, err, summary_data, file_df, tab_lst = process_file_errors(facets_post_file, sys_inp_df, mapping_df, summary_data, file_df, tab_lst)
                    if er:
                        st.error(err)
                        return
                if facets_post_clm:
                    sys_inp_df = sys_df[(sys_df['System'] == 'FACETS') & (sys_df['File'] == 'UHCSB POST TAG CLM')]
                    er, err, summary_data, file_df, tab_lst = process_file_errors(facets_post_clm, sys_inp_df, mapping_df, summary_data, file_df, tab_lst)
                    if er:
                        st.error(err)
                        return
                if facets_source_file:
                    print(sys_df)
                    sys_inp_df = sys_df[(sys_df['System'] == 'FACETS') & (sys_df['Tab'] == 'Target')]
                    print(sys_inp_df)
                    er, err, summary_data, file_df, tab_lst = process_file_errors(facets_source_file, sys_inp_df, mapping_df, summary_data, file_df, tab_lst)
                    if er:
                        st.error(err)
                        return
            # Get required columns for validation
            
        # Display summary table with UHC styling
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            
            # Apply UHC styling to dataframe
            st.dataframe(df_summary, hide_index=True)
    with colb:
        # Validate files and extract metadata if all files are uploaded
        if sys_type == 'COSMOS' and master_file and cosmos_file and source_file:           
            try:
                er, err = check_special_chars(summary_data, file_df, mapping_df, tab_lst)
                if er:
                    for i in range(len(err)):
                        st.error(err)
                    return  
       
                st.markdown('<h6 class="section-header"; style="color: var(--uhc-blue);">Process Files</h6>', unsafe_allow_html=True)
            
                if not st.session_state.job_submitted:
                    # Use standard Streamlit warning with UHC styling
                    st.info('Files uploaded successfully!')
                    # Validate email before processing
                    email_valid = True
                    if not email:
                        st.error("Email address is required.")
                        email_valid = False
                        return
                    elif not validate_email(email):
                        st.error("Please enter a valid email address ending with optum.com or uhc.com.")
                        email_valid = False
                        return
                    else:
                        st.session_state.email_error = None
                        st.session_state.email = email
                
                    if email_valid:
                        col1, col2, col3 = st.columns([1, 1, 1])
                        with col2:
                            if st.button("Process Files"):
                                with st.spinner("Processing files..."):
                                    # Call the process function
                                    success = process_files(
                                        master_file, 
                                        cosmos_file, 
                                        source_file,
                                        email
                                    )

                                    if success:
                                        st.session_state.job_submitted = True
                                        # No rerun - will update on next interaction
                                    else:
                                        st.error("Job not submitted.")
                else:
                    st.warning('Job already submitted, please start a new session to rerun.')
                
                # Show success message if job was submitted
                if st.session_state.job_submitted:
                    # Use standard Streamlit success message
                    st.success("Job submitted successfully!")
                    
                    # Use standard Streamlit info message
                    st.info("You will be notified via email when processing is complete.")
                    
            except Exception as e:
                st.error(f"Error during processing: {str(e)}")
                import traceback
                st.error(traceback.format_exc())
if __name__ == "__main__":
    main()


