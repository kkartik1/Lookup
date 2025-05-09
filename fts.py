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
    
    for col in cols:
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

def get_mapping(map_df, sheet):
    """Get mappings for specific sheet type"""
    # Check if the sheet exists in the mapping dataframe
    if sheet != 'Master' and sheet not in map_df.columns:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
    if sheet == 'Master':
        mapping_df = map_df[['Type', 'Length', 'Target', 'Master']]
    else:
        column_name = sheet
        if column_name not in map_df.columns:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            
        mapping_df = map_df[['Type', 'Length', 'Target', column_name]]
        mapping_df.columns = ['Type', 'Length', 'Target', 'Master']
    
    # Filter the mapping for "IN" types (for matching)
    in_mappings = mapping_df[mapping_df['Type'] == 'IN']
    
    # Filter the mapping for "OUT" types (for updating)
    out_mappings = mapping_df[mapping_df['Type'] == 'OUT']
    
    # Filter the mapping for "Length" types (for updating)
    len_mappings = pd.DataFrame()
    if 'Length' in mapping_df.columns:
        len_mappings = mapping_df[mapping_df['Length'].notna()][['Length', 'Target']]
        # Convert length to integer safely
        len_mappings['Length'] = len_mappings['Length'].apply(lambda x: int(float(x)) if pd.notna(x) else 0)
    
    return in_mappings, out_mappings, len_mappings

# Function to process the files (placeholder for actual processing)
def process_files(master_lookup, cosmos_lookup, source_file, account_tab, customer_tab, department_tab):
    # This is a placeholder function that would normally perform processing
    # In a real application, this would process the data and submit a job
    return True

def main():
    # Set page configuration
    st.set_page_config(
        page_title="Financial Tagging Services | UHC",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Load the UHC style CSS
    load_css("uhc_style.css")

    colx, coly = st.columns([0.05, 0.95])
    with colx:
        with st.container():
            # Display logo
            st.image("UHC.png", width=45)  # Adjust width as needed

    with coly:
        with st.container():  # Rest of your app
            st.markdown('<h2 class="main-header">Financial Tagging Services</h3>', unsafe_allow_html=True)
    
    # Load the mapping file
    mapping_df = load_mapping_file()
    if mapping_df is None:
        return
    
    # Create a layout with three columns for file uploads
    col1, col2, col3 = st.columns(3)
    
    # File upload widgets in each column with UHC styled containers
    with col1:
        with st.container():
            st.markdown('<strong style="color: var(--uhc-blue);">MASTER COSGP PS LOOKUP</strong>', unsafe_allow_html=True)
            master_file = st.file_uploader("Upload Master Lookup file", type=["xlsx", "xls"], key="master", label_visibility="collapsed")
    with col2:
        with st.container():
            st.markdown('<strong style="color: var(--uhc-blue);">COSMOS9 CL PS LOOKUP</strong>', unsafe_allow_html=True)
            cosmos_file = st.file_uploader("Upload COSMOS Lookup file", type=["xlsx", "xls"], key="cosmos", label_visibility="collapsed")        
    with col3:
        with st.container():
            st.markdown('<strong style="color: var(--uhc-blue);">COSMOS SOURCE</strong>', unsafe_allow_html=True)
            source_file = st.file_uploader("Upload Source Excel file", type=["xlsx", "xls"], key="source", label_visibility="collapsed")
            
    # Initialize session state variables if they don't exist
    if 'account_tab' not in st.session_state:
        st.session_state.account_tab = None
    if 'customer_tab' not in st.session_state:
        st.session_state.customer_tab = None
    if 'department_tab' not in st.session_state:
        st.session_state.department_tab = None
    if 'job_submitted' not in st.session_state:
        st.session_state.job_submitted = False

    #create compact layout with two columns
    cola, colb = st.columns(2)
    with cola:    
        # File summary section
        if master_file or cosmos_file or source_file:
            st.markdown('<h3 class="section-header">File Summary</h3>', unsafe_allow_html=True)
            
            summary_data = []
            
            # Process Master Lookup if uploaded
            if master_file:
                try:
                    if not validate_file_extension(master_file):
                        st.error("Only Excel files (.xlsx, .xls) are allowed.")
                        return
                    xls = pd.ExcelFile(master_file)
                    for sheet_name in xls.sheet_names:
                        df_mas = pd.read_excel(master_file, sheet_name=sheet_name)
                        required_master_columns = get_required_columns_from_mapping(mapping_df, 'Master')
                        # Validate required columns in Master file
                        master_valid, master_missing = validate_required_columns(df_mas, required_master_columns)
                        if not master_valid:
                            st.error(f"Master file is missing required columns: {', '.join(master_missing)}")
                            return
                        summary_data.append({
                            "File Name": master_file.name,
                            "Tab Name": sheet_name,
                            "Row Count": len(df_mas),
                            "Column Count": len(df_mas.columns)
                        })
                except Exception as e:
                    st.error(f"Error reading Master Lookup: {e}")
            
            # Process COSMOS Lookup if uploaded and identify special tabs
            if cosmos_file:
                try:
                    if not validate_file_extension(cosmos_file):
                        st.error("Only Excel files (.xlsx, .xls) are allowed.")
                        return
                    # Reset file pointer
                    cosmos_file.seek(0)
                    
                    # Identify special tabs
                    account_tab, customer_tab, department_tab = identify_special_tabs(cosmos_file)
                    st.session_state.account_tab = account_tab
                    st.session_state.customer_tab = customer_tab
                    st.session_state.department_tab = department_tab
                    if not account_tab or not customer_tab or not department_tab:
                        st.error("COSMOS9 Lookup file doesn't contain the required tabs.")
                        return
                    # Reset file pointer again before reading
                    cosmos_file.seek(0)
                    xls = pd.ExcelFile(cosmos_file)
                    
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(cosmos_file, sheet_name=sheet_name)
                        tab_type = ""
                        if sheet_name == account_tab:
                            tab_type = " (Account)"
                            df_acc = df
                            required_account_columns = get_required_columns_from_mapping(mapping_df, 'Account')
                            # Validate required columns in Account file
                            account_valid, account_missing = validate_required_columns(df_acc, required_account_columns)
                            if not account_valid:
                                st.error(f"Account file is missing required columns: {', '.join(account_missing)}")
                                return
                        elif sheet_name == customer_tab:
                            tab_type = " (Customer)"
                            df_cus = df
                            required_customer_columns = get_required_columns_from_mapping(mapping_df, 'Customer')
                            # Validate required columns in Customer file
                            customer_valid, customer_missing = validate_required_columns(df_cus, required_customer_columns)
                            if not customer_valid:
                                st.error(f"Customer file is missing required columns: {', '.join(customer_missing)}")
                                return
                        elif sheet_name == department_tab:
                            tab_type = " (Department)"
                            df_dep = df
                            required_department_columns = get_required_columns_from_mapping(mapping_df, 'Department')
                            # Validate required columns in Department file
                            department_valid, department_missing = validate_required_columns(df_dep, required_department_columns)
                            if not department_valid:
                                st.error(f"Department file is missing required columns: {', '.join(department_missing)}")
                                return
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
                    if not validate_file_extension(source_file):
                        st.error("Only Excel files (.xlsx, .xls) are allowed.")
                        return    
                    xls = pd.ExcelFile(source_file)
                    for sheet_name in xls.sheet_names:
                        df_src = pd.read_excel(source_file, sheet_name=sheet_name)
                        required_source_columns = get_required_columns_from_mapping(mapping_df, 'Target')
                        # Validate required columns in Source file
                        source_valid, source_missing = validate_required_columns(df_src, required_source_columns)
                        if not source_valid:
                            st.error(f"Source file is missing required columns: {', '.join(source_missing)}")
                            return
                        summary_data.append({
                            "File Name": source_file.name,
                            "Tab Name": sheet_name,
                            "Row Count": len(df_src),
                            "Column Count": len(df_src.columns)
                        })
                except Exception as e:
                    st.error(f"Error reading Source Excel: {e}")
            # Get required columns for validation
            
            # Display summary table with UHC styling
            if summary_data:
                df_summary = pd.DataFrame(summary_data)
                
                # Apply UHC styling to dataframe
                st.dataframe(df_summary, 
                    hide_index=True
                )
    with colb:
        # Validate files and extract metadata if all files are uploaded
        if master_file and cosmos_file and source_file:
            
            try:
                # Check for special characters in all files
                master_invalid_cells = check_special_characters(df_mas, mapping_df['Master'].dropna().tolist())
                source_invalid_cells = check_special_characters(df_src, mapping_df['Target'].dropna().tolist())
                customer_invalid_cells = check_special_characters(df_cus, mapping_df['Customer'].dropna().tolist())
                account_invalid_cells = check_special_characters(df_acc, mapping_df['Account'].dropna().tolist())
                department_invalid_cells = check_special_characters(df_dep, mapping_df['Department'].dropna().tolist())
                
                if master_invalid_cells:
                    st.error("Master file contains invalid special characters:")
                    for idx, col, value, chars in master_invalid_cells[:5]:  # Show first 5
                        st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
                    return
                
                if source_invalid_cells:
                    st.error("Source file contains invalid special characters:")
                    for idx, col, value, chars in source_invalid_cells[:5]:  # Show first 5
                        st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
                    return  
                
                if customer_invalid_cells:
                    st.error("Customer file contains invalid special characters:")
                    for idx, col, value, chars in customer_invalid_cells[:5]:  # Show first 5
                        st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
                    return
                
                if account_invalid_cells:
                    st.error("Account file contains invalid special characters:")
                    for idx, col, value, chars in account_invalid_cells[:5]:  # Show first 5
                        st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
                    return  
        
                if department_invalid_cells:
                    st.error("Department file contains invalid special characters:")
                    for idx, col, value, chars in department_invalid_cells[:5]:  # Show first 5
                        st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
                    return  
        
       
                st.markdown('<h3 class="section-header">Process Files</h3>', unsafe_allow_html=True)
            
                if not st.session_state.job_submitted:
                    # Use standard Streamlit warning with UHC styling
                    st.info('Files uploaded successfully!')
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col2:
                        if st.button("Process Files"):
                            with st.spinner("Processing files..."):
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
                                    # No rerun - will update on next interaction
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
    # Updated footer with UHC styling
    st.markdown("""
    <div style="background-color: #002677; padding: 0.8rem; color: white; border-radius: 4px; margin-top: 2rem; font-size: 0.8rem; text-align: center;">
        © 2025 UnitedHealthcare Services, Inc. All rights reserved.
    </div>
    """, unsafe_allow_html=True)
    
if __name__ == "__main__":
    main()
