import streamlit as st
import pandas as pd
import os
import re

# Load CSS from external file
def load_css(css_file):
    with open(css_file, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def load_mapping_file():
    """Load the mapping CSV file that should be present at deployment site"""
    try:
        # In production, use the actual path where the mapping file is stored
        return pd.read_csv("FTS_Mapping.csv")
    except FileNotFoundError:
        st.error("Mapping file (FTS_Mapping.csv) not found. Please place it in the application directory.")
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

def validate_email(email):
    """Validate email format using regex"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None

def get_required_columns_from_mapping(mapping_df, column_type):
    """Get required columns from mapping file based on type (IN)"""
    if column_type != 'Target':
        in_mappings = mapping_df[mapping_df['Type'] == 'IN']
    else:
        in_mappings = mapping_df
    # Filter out None/NaN values before returning the list
    return [col for col in in_mappings[column_type].unique().tolist() if pd.notna(col)]

def check_special_characters(df, cols):
    """Check for special characters in all columns except allowed ones"""
    allowed_chars = ['%', '-', '/', ')', '(', '>', '<']
    allowed_pattern = r'^[a-zA-Z0-9\s' + ''.join([re.escape(c) for c in allowed_chars]) + ']*$'
    
    invalid_cells = []
    
    # Only check columns that exist in the dataframe
    existing_cols = [col for col in cols if col in df.columns]
    
    for col in existing_cols:
        for idx, value in df[col].astype(str).items():
            if not re.match(allowed_pattern, value):
                invalid_chars = [c for c in value if c not in allowed_chars and not c.isalnum() and not c.isspace()]
                if invalid_chars:
                    invalid_cells.append((idx, col, value, ''.join(set(invalid_chars))))
    
    return invalid_cells

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
def process_files(master_lookup, cosmos_lookup, source_file, account_tab, customer_tab, department_tab, email):
    # This is a placeholder function that would normally perform processing
    # In a real application, this would process the data and submit a job
    # The email parameter would be used to notify the user when processing is complete
    return True

def main():
    # Set page configuration
    st.set_page_config(
        page_title="Financial Tagging Services | UHC",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Load the UHC style CSS
    load_css("minimal_uhc_style.css")

    # Initialize session state
    if 'job_submitted' not in st.session_state:
        st.session_state.job_submitted = False
    
    if 'file_data' not in st.session_state:
        st.session_state.file_data = {
            'master': None,
            'account': None,
            'customer': None,
            'department': None,
            'source': None
        }
    
    if 'email_error' not in st.session_state:
        st.session_state.email_error = None
    
    if 'email' not in st.session_state:
        st.session_state.email = ""
    
    # Custom header with inline styling
    logo_col, header_col = st.columns([0.1, 0.9])
    with logo_col:
        st.image("UHC.png", width=45)
    with header_col:
        st.markdown('<h2 class="main-header">Financial Tagging Services</h2>', unsafe_allow_html=True)
    
    # Load the mapping file
    mapping_df = load_mapping_file()
    if mapping_df is None:
        return
    
    # Create container with custom border
    st.markdown("""
    <div style="border: 1px solid #d8dbe0; border-radius: 5px; padding: 10px; margin-bottom: 20px;">
    """, unsafe_allow_html=True)
    
    # File upload section with direct styling
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<p style="color: #002677; font-weight: bold;">Upload MASTER COSGP PS LOOKUP</p>', unsafe_allow_html=True)
        master_file = st.file_uploader("Upload Master Lookup file", type=["xlsx", "xls"], key="master", label_visibility="collapsed")
    
    with col2:
        st.markdown('<p style="color: #002677; font-weight: bold;">Upload COSMOS9 CL PS LOOKUP</p>', unsafe_allow_html=True)
        cosmos_file = st.file_uploader("Upload COSMOS Lookup file", type=["xlsx", "xls"], key="cosmos", label_visibility="collapsed")
    
    with col3:
        st.markdown('<p style="color: #002677; font-weight: bold;">Upload COSMOS SOURCE</p>', unsafe_allow_html=True)
        source_file = st.file_uploader("Upload Source Excel file", type=["xlsx", "xls"], key="source", label_visibility="collapsed")
    
    # Close the container div
    st.markdown("""</div>""", unsafe_allow_html=True)
    
    # Email notification section
    st.markdown("""
    <div style="border: 1px solid #d8dbe0; border-radius: 5px; padding: 10px; margin-bottom: 20px;">
    """, unsafe_allow_html=True)
    
    st.markdown('<p style="color: #002677; font-weight: bold;">Email Notification</p>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 14px; color: #666;">Enter your email address to receive notifications when processing is complete.</p>', unsafe_allow_html=True)
    
    email = st.text_input("Email Address", value=st.session_state.email, key="email_input")
    
    # Display email validation error if it exists
    if st.session_state.email_error:
        st.error(st.session_state.email_error)
    
    st.markdown("""</div>""", unsafe_allow_html=True)
    
    # Process files and display summary if any file is uploaded
    file_summary_data = []
    error_messages = []
    special_tabs_identified = False
    
    # Process Master Lookup if uploaded
    if master_file:
        try:
            if not validate_file_extension(master_file):
                error_messages.append("Only Excel files (.xlsx, .xls) are allowed for Master Lookup.")
            else:
                xls = pd.ExcelFile(master_file)
                for sheet_name in xls.sheet_names:
                    df_mas = pd.read_excel(master_file, sheet_name=sheet_name)
                    st.session_state.file_data['master'] = df_mas
                    
                    required_columns = get_required_columns_from_mapping(mapping_df, 'Master')
                    valid, missing = validate_required_columns(df_mas, required_columns)
                    
                    if not valid:
                        error_messages.append(f"Master file is missing required columns: {', '.join(missing)}")
                    
                    file_summary_data.append({
                        "File Name": master_file.name,
                        "Tab Name": sheet_name,
                        "Row Count": len(df_mas),
                        "Column Count": len(df_mas.columns)
                    })
        except Exception as e:
            error_messages.append(f"Error reading Master Lookup: {str(e)}")
    
    # Process COSMOS Lookup if uploaded
    if cosmos_file:
        try:
            if not validate_file_extension(cosmos_file):
                error_messages.append("Only Excel files (.xlsx, .xls) are allowed for COSMOS Lookup.")
            else:
                # Reset file pointer before reading
                cosmos_file.seek(0)
                
                # Identify special tabs
                account_tab, customer_tab, department_tab = identify_special_tabs(cosmos_file)
                
                if not all([account_tab, customer_tab, department_tab]):
                    error_messages.append("COSMOS9 Lookup file doesn't contain all required tabs.")
                else:
                    special_tabs_identified = True
                    
                    # Reset file pointer and read data
                    cosmos_file.seek(0)
                    xls = pd.ExcelFile(cosmos_file)
                    
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(cosmos_file, sheet_name=sheet_name)
                        tab_type = ""
                        
                        if sheet_name == account_tab:
                            tab_type = " (Account)"
                            st.session_state.file_data['account'] = df
                            
                            required_columns = get_required_columns_from_mapping(mapping_df, 'Account')
                            valid, missing = validate_required_columns(df, required_columns)
                            
                            if not valid:
                                error_messages.append(f"Account tab is missing required columns: {', '.join(missing)}")
                                
                        elif sheet_name == customer_tab:
                            tab_type = " (Customer)"
                            st.session_state.file_data['customer'] = df
                            
                            required_columns = get_required_columns_from_mapping(mapping_df, 'Customer')
                            valid, missing = validate_required_columns(df, required_columns)
                            
                            if not valid:
                                error_messages.append(f"Customer tab is missing required columns: {', '.join(missing)}")
                                
                        elif sheet_name == department_tab:
                            tab_type = " (Department)"
                            st.session_state.file_data['department'] = df
                            
                            required_columns = get_required_columns_from_mapping(mapping_df, 'Department')
                            valid, missing = validate_required_columns(df, required_columns)
                            
                            if not valid:
                                error_messages.append(f"Department tab is missing required columns: {', '.join(missing)}")
                        
                        file_summary_data.append({
                            "File Name": cosmos_file.name,
                            "Tab Name": f"{sheet_name}{tab_type}",
                            "Row Count": len(df),
                            "Column Count": len(df.columns)
                        })
        except Exception as e:
            error_messages.append(f"Error reading COSMOS Lookup: {str(e)}")
    
    # Process Source Excel if uploaded
    if source_file:
        try:
            if not validate_file_extension(source_file):
                error_messages.append("Only Excel files (.xlsx, .xls) are allowed for Source file.")
            else:
                xls = pd.ExcelFile(source_file)
                for sheet_name in xls.sheet_names:
                    df_src = pd.read_excel(source_file, sheet_name=sheet_name)
                    st.session_state.file_data['source'] = df_src
                    
                    required_columns = get_required_columns_from_mapping(mapping_df, 'Target')
                    valid, missing = validate_required_columns(df_src, required_columns)
                    
                    if not valid:
                        error_messages.append(f"Source file is missing required columns: {', '.join(missing)}")
                    
                    file_summary_data.append({
                        "File Name": source_file.name,
                        "Tab Name": sheet_name,
                        "Row Count": len(df_src),
                        "Column Count": len(df_src.columns)
                    })
        except Exception as e:
            error_messages.append(f"Error reading Source Excel: {str(e)}")
    
    # Display file summary if we have data
    if file_summary_data:
        st.markdown('<h3 class="section-header">File Summary</h3>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(file_summary_data), hide_index=True)
    
    # Display any errors
    for error in error_messages:
        st.error(error)
    
    # Check for special characters if all files are present and valid
    if (master_file and cosmos_file and source_file and 
        special_tabs_identified and 
        not error_messages):
        
        # Get dataframes from session state
        df_mas = st.session_state.file_data['master']
        df_acc = st.session_state.file_data['account']
        df_cus = st.session_state.file_data['customer']
        df_dep = st.session_state.file_data['department']
        df_src = st.session_state.file_data['source']
        
        # Get list of columns to check
        master_cols = [col for col in mapping_df['Master'].dropna().tolist() if col in df_mas.columns]
        source_cols = [col for col in mapping_df['Target'].dropna().tolist() if col in df_src.columns]
        customer_cols = [col for col in mapping_df['Customer'].dropna().tolist() if col in df_cus.columns]
        account_cols = [col for col in mapping_df['Account'].dropna().tolist() if col in df_acc.columns]
        department_cols = [col for col in mapping_df['Department'].dropna().tolist() if col in df_dep.columns]
        
        # Check for special characters
        special_char_errors = False
        
        # Master file check
        invalid_cells = check_special_characters(df_mas, master_cols)
        if invalid_cells:
            special_char_errors = True
            st.error("Master file contains invalid special characters:")
            for idx, col, value, chars in invalid_cells[:5]:
                st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
        
        # Source file check
        if not special_char_errors:
            invalid_cells = check_special_characters(df_src, source_cols)
            if invalid_cells:
                special_char_errors = True
                st.error("Source file contains invalid special characters:")
                for idx, col, value, chars in invalid_cells[:5]:
                    st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
        
        # Customer file check
        if not special_char_errors:
            invalid_cells = check_special_characters(df_cus, customer_cols)
            if invalid_cells:
                special_char_errors = True
                st.error("Customer file contains invalid special characters:")
                for idx, col, value, chars in invalid_cells[:5]:
                    st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
        
        # Account file check
        if not special_char_errors:
            invalid_cells = check_special_characters(df_acc, account_cols)
            if invalid_cells:
                special_char_errors = True
                st.error("Account file contains invalid special characters:")
                for idx, col, value, chars in invalid_cells[:5]:
                    st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
        
        # Department file check
        if not special_char_errors:
            invalid_cells = check_special_characters(df_dep, department_cols)
            if invalid_cells:
                special_char_errors = True
                st.error("Department file contains invalid special characters:")
                for idx, col, value, chars in invalid_cells[:5]:
                    st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
        
        # Display processing section if no special character errors
        if not special_char_errors:
            st.markdown('<h3 class="section-header">Process Files</h3>', unsafe_allow_html=True)
            
            if not st.session_state.job_submitted:
                st.info('Files uploaded successfully!')
                
                # Validate email before processing
                email_valid = True
                if not email:
                    st.session_state.email_error = "Email address is required."
                    email_valid = False
                elif not validate_email(email):
                    st.session_state.email_error = "Please enter a valid email address."
                    email_valid = False
                else:
                    st.session_state.email_error = None
                    st.session_state.email = email
                
                if email_valid:
                    # Center the button using columns
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col2:
                        # Custom styled button using markdown
                        if st.button("Process Files", key="process_btn"):
                            with st.spinner("Processing files..."):
                                # Simulate processing
                                success = process_files(
                                    master_file, 
                                    cosmos_file, 
                                    source_file,
                                    account_tab,
                                    customer_tab,
                                    department_tab,
                                    email
                                )
                                
                                if success:
                                    st.session_state.job_submitted = True
            else:
                st.warning('Job already submitted, please start a new session to rerun.')
            
            # Show success message if job was submitted
            if st.session_state.job_submitted:
                st.success("Job submitted successfully!")
                st.info(f"You will be notified via email at {email} when processing is complete.")
    
    # Footer with direct styling
    st.markdown("""
    <div class="footer">
        © 2025 UnitedHealthcare Services, Inc. All rights reserved.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
