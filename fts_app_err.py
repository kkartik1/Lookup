import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io
import time
import os

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


def check_special_characters(df):
    """Check for special characters in all columns except allowed ones"""
    allowed_chars = ['%', '-', '/', ')', '(', '>', '<']
    allowed_pattern = r'^[a-zA-Z0-9\s' + ''.join([re.escape(c) for c in allowed_chars]) + ']*$'
    
    invalid_cells = []
    
    for col in df.columns:
        for idx, value in df[col].astype(str).items():
            if not re.match(allowed_pattern, value):
                invalid_chars = [c for c in value if c not in allowed_chars and not c.isalnum() and not c.isspace()]
                if invalid_chars:
                    invalid_cells.append((idx, col, value, ''.join(set(invalid_chars))))
    
    return invalid_cells


def get_file_metadata(file):
    """Extract file metadata including creation time"""
    try:
        # Get file name
        filename = file.name
        
        # Get current date and time as upload time
        upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return {
            'filename': filename,
            'upload_time': upload_time
        }
    except Exception as e:
        st.error(f"Error extracting file metadata: {str(e)}")
        return {}


def parse_match_dates(pattern_fr, pattern_to, value_dt):
    """Parse and compare dates based on provided patterns"""
    date_format = '%m/%d/%Y'
    try:
        date_fr = datetime.strptime(pattern_fr, date_format)
        value_date = datetime.strptime(value_dt, date_format)
        
        if not pattern_to:
            return date_fr <= value_date
        
        date_to = datetime.strptime(pattern_to, date_format)
        return date_fr <= value_date <= date_to
    except ValueError:
        # Not valid dates, proceed with mismatch
        return False


def check_dates_match(duplicates, master_row, source_row):
    """Check if dates match according to specified conditions"""
    if len(duplicates) > 1:
        pattern_fr = master_row[duplicates.iloc[0]['Master']]
        
        pattern_to = ''
        if not pd.isna(master_row[duplicates.iloc[1]['Master']]) and master_row[duplicates.iloc[1]['Master']] != 'nan':
            pattern_to = master_row[duplicates.iloc[1]['Master']]
            
        value_dt = source_row[duplicates.iloc[0]['Target']]
        
        match_result = parse_match_dates(str(pattern_fr), str(pattern_to), str(value_dt))
        print(f"Date: {'Passed' if match_result else 'Failed'}", pattern_fr, pattern_to, value_dt)
        return match_result
    return False


def format_number(x, ln):
    """Format a number with leading zeros to match specified length"""
    x = str(x).strip()
    if pd.isna(x) or x == '' or x == '0':
        return x
    return str(int(x)).zfill(ln)



def pad_with_zeros(in_df, df_len):
    """Pad numeric fields with zeros based on specified lengths"""
    result_df = in_df.copy()
    for _, len_row in df_len.iterrows():
        if len_row['Target'] in result_df.columns:  # Check if column exists
            result_df[len_row['Target']] = result_df[len_row['Target']].apply(
                lambda x: format_number(x, int(len_row['Length']))
            )
    return result_df


def parse_match_pattern(pattern, value):
    """Parse and evaluate various matching patterns based on guidelines"""
    # Check if pattern is None or value is None
    if pattern is None or value is None:
        return False
    
    # Convert both to strings for comparison
    pattern = str(pattern).strip()
    value = str(value).strip()
    
    # Handle <ANY> pattern - match everything
    if pattern == "<ANY>":
        return True
    
    # Handle CLP% pattern (starts with CLP)
    if pattern.endswith('%'):
        prefix = pattern[:-1]
        return value.startswith(prefix)
    
    # Handle 000001019/000001020 pattern (either/or)
    if '/' in pattern:
        options = pattern.split('/')
        if all(isinstance(x, int) for x in options):
            options = [int(item) for item in options if item.isdigit()]
        if value.isdigit():
            value = int(value)
        return value in options
    
    # Handle (0097003-0097005) pattern (range)
    range_match = re.match(r'\((\w+)-(\w+)\)', pattern)
    if range_match:
        start, end = range_match.groups()
        # Check if it's a numeric range
        if start.isdigit() and end.isdigit():
            try:
                value_int = int(value)
                return int(start) <= value_int <= int(end)
            except ValueError:
                pass
        # Otherwise treat as string range
        return start <= value <= end
    
    # Simple numeric or string equality
    if value.isdigit() and pattern.isdigit():
        try:
            return int(pattern) == int(value)
        except ValueError:
            return pattern == value
    
    return pattern == value


def check_match_files(in_mappings, master_col, source_col, master_row, source_row):
    """Check all IN type mappings for a match"""
    for _, mapping_row in in_mappings.iterrows():
        if 'Master' not in mapping_row or 'Target' not in mapping_row:
            continue
            
        master_column = mapping_row['Master']
        source_column = mapping_row['Target']
        
        # Skip if columns don't exist in the dataframes
        if master_column not in master_col or source_column not in source_col:
            continue
            
        master_value = master_row[master_column]
        source_value = source_row[source_column]
        
        # Regular pattern matching
        match_result = parse_match_pattern(master_value, source_value)
        
        if not match_result:
            return False
            
    return True


def process_rule_files(master_df, in_mappings, source_row, source_col):
    """Process rules against master files"""
    # Handle empty mappings
    if in_mappings.empty:
        return False, None, master_df
        
    # Check if columns exist
    if 'Target' not in in_mappings.columns:
        return False, None, master_df
        
    # Remove all rows with duplicates mappings e.g. date
    duplicates = in_mappings[in_mappings.Target.duplicated(keep=False)]
    filtered_mappings = in_mappings[~in_mappings['Target'].duplicated(keep=False)].reset_index(drop=True)
    
    master_copy_df = master_df.copy().astype(str)
    
    for idx, master_row in master_copy_df.iterrows():
        # Check for dates matching
        date_match = True
        if not duplicates.empty:
            date_match = check_dates_match(duplicates, master_row, source_row)
            
        if not date_match:
            continue
            
        # Check all matching conditions
        if not check_match_files(filtered_mappings, master_df.columns, source_col, master_row, source_row):
            continue
            
        # Found a match
        remaining_df = master_copy_df.drop(idx)
        return True, master_row, remaining_df
        
    return False, None, master_copy_df


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


def process_files(master_df, acc_df, cus_df, dep_df, source_df, mapping_df):
    """Process the Excel files based on mapping guidelines"""
    # Create a copy of the Source dataframe to modify
    result_df = source_df.copy().astype(str)
    source_copy_df = source_df.copy().astype(str)
    
    # Track match counts for each type
    match_counts = {
        'Master': 0,
        'Account': 0,
        'Customer': 0,
        'Department': 0
    }
    
    # Store total counts for each lookup
    total_counts = {
        'Master': len(master_df),
        'Account': len(acc_df),
        'Customer': len(cus_df),
        'Department': len(dep_df)
    }
    
    # Store dataframes in a dictionary for easier access
    dfs = {
        'Master': master_df,
        'Account': acc_df,
        'Customer': cus_df,
        'Department': dep_df
    }
    
    # Process each row in the source dataframe
    for source_idx, source_row in source_copy_df.iterrows():
        row_updated = False
        
        # Process each lookup type (Master, Account, Customer, Department)
        for lookup_type, lookup_df in dfs.items():
            in_mappings, out_mappings, len_mappings = get_mapping(mapping_df, lookup_type)
            
            # Skip if no mappings found
            if in_mappings.empty:
                continue
                
            # Check if the source row matches any rule in the current lookup
            all_conditions_met, master_row, filtered_df = process_rule_files(
                lookup_df, in_mappings, source_row, source_df.columns
            )
            
            # Update the dataframe with the filtered results
            dfs[lookup_type] = filtered_df
            
            if all_conditions_met and master_row is not None:
                # Update the result dataframe with OUT mappings
                for _, out_row in out_mappings.iterrows():
                    if 'Target' not in out_row or 'Master' not in out_row:
                        continue
                        
                    target_column = out_row['Target']
                    master_column = out_row['Master']
                    
                    if (master_column in master_row.index and 
                        target_column in result_df.columns):
                        result_df.at[source_idx, target_column] = master_row[master_column]
                
                # Increment match count for this lookup type
                match_counts[lookup_type] += 1
                row_updated = True
        
        # Remove the source row if it was updated by any lookup
        if row_updated:
            source_copy_df = source_copy_df.drop(source_idx)
    
    # Display match counts
    for lookup_type, count in match_counts.items():
        st.info(
            f"Out of total {total_counts[lookup_type]} rules, from {lookup_type} Lookup "
            f"matches found for {count} rule(s)."
        )
    
    # Format result numbers with leading zeros
    _, _, len_mappings = get_mapping(mapping_df, 'Master')
    if not len_mappings.empty:
        result_df = pad_with_zeros(result_df, len_mappings)
    
    return result_df


def create_file_summary(file_metadata, df):
    """Create a summary for the uploaded file"""
    summary = {
        'filename': file_metadata.get('filename', 'Unknown'),
        'upload_time': file_metadata.get('upload_time', 'Unknown'),
        'records': len(df),
        'columns': len(df.columns),
        'column_names': list(df.columns)
    }
    
    # Add assigned role if available
    if 'assigned_role' in file_metadata:
        summary['assigned_role'] = file_metadata['assigned_role']
        
    return summary


def main():
    st.title("Financial Tagging Services")
    
    st.write("""This application maps data between Master Lookup files and Source Excel file.""")
    
    # Load the mapping file
    mapping_df = load_mapping_file()
    if mapping_df is None:
        return
    
    # File uploaders in three columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        master_file = st.file_uploader("Upload Master Lookup Excel", type=['xlsx', 'xls'])
    
    with col2:
        cosmos_file = st.file_uploader("Upload COSMOS Lookup Excel", type=['xlsx', 'xls'])
    
    with col3:
        source_file = st.file_uploader("Upload Source Excel", type=['xlsx', 'xls'])
    
    # Variables to store validation status
    validation_passed = False
    file_summaries = {}
    cosmos_dfs = {}
    selected_sheets = []
    
    # Validate files and extract metadata if all files are uploaded
    if master_file and cosmos_file and source_file:
        # Validate file extensions
        if not (validate_file_extension(master_file) and 
                validate_file_extension(cosmos_file) and 
                validate_file_extension(source_file)):
            st.error("Only Excel files (.xlsx, .xls) are allowed.")
            return
        
        try:
            # Read Excel files
            master_df = pd.read_excel(master_file).astype(str)
            source_df = pd.read_excel(source_file).astype(str)
            
            # Extract metadata for files
            master_metadata = get_file_metadata(master_file)
            source_metadata = get_file_metadata(source_file)
            cosmos_metadata = get_file_metadata(cosmos_file)
            
            # Create file summaries
            file_summaries['Master'] = create_file_summary(master_metadata, master_df)
            file_summaries['Source'] = create_file_summary(source_metadata, source_df)
            
            # Get required columns for validation
            required_master_columns = get_required_columns_from_mapping(mapping_df, 'Master')
            required_source_columns = get_required_columns_from_mapping(mapping_df, 'Target')
            
            # Validate required columns in Master file
            master_valid, master_missing = validate_required_columns(master_df, required_master_columns)
            if not master_valid:
                st.error(f"Master file is missing required columns: {', '.join(master_missing)}")
                return
            
            # Validate required columns in Source file
            source_valid, source_missing = validate_required_columns(source_df, required_source_columns)
            if not source_valid:
                st.error(f"Source file is missing required columns: {', '.join(source_missing)}")
                return
            
            # Check for special characters in all files
            master_invalid_cells = check_special_characters(master_df)
            source_invalid_cells = check_special_characters(source_df)
            
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
            
            st.subheader("Files Loaded Successfully")
            
                            # COSMOS sheet selection (shown only after COSMOS file is uploaded and validated)
            # Read all sheet names from COSMOS file
            with pd.ExcelFile(cosmos_file) as xls:
                sheet_names = xls.sheet_names
                
                st.write("Select sheets from COSMOS excel and assign them to lookup types:")
                
                cosmos_sheets_expander = st.expander("COSMOS Sheets Selection", expanded=True)
                with cosmos_sheets_expander:
                    # Max tabs warning
                    st.warning("Please select exactly three sheets and assign each one to Account, Customer, and Department")
                    
                    # Create selection options for each lookup type
                    st.subheader("Sheet Assignments")
                    
                    # Create multiselect to select sheets
                    selected_sheets = st.multiselect(
                        "Select exactly three sheets from COSMOS file:",
                        options=sheet_names,
                        default=sheet_names[:min(3, len(sheet_names))]
                    )
                    
                    # If sheets are selected, show assignment options
                    sheet_assignments = {"Account": None, "Customer": None, "Department": None}
                    
                    if selected_sheets:
                        st.subheader("Assign sheets to lookup types")
                        st.write("Each sheet must be assigned to exactly one lookup type")
                        
                        # Create three columns for the three lookup types
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.markdown("**Account**")
                            sheet_assignments["Account"] = st.selectbox(
                                "Select sheet for Account lookup:",
                                options=[""] + selected_sheets,
                                index=0 if len(selected_sheets) < 1 else 1
                            )
                            
                        with col2:
                            st.markdown("**Customer**")
                            sheet_assignments["Customer"] = st.selectbox(
                                "Select sheet for Customer lookup:",
                                options=[""] + selected_sheets,
                                index=0 if len(selected_sheets) < 2 else 2
                            )
                            
                        with col3:
                            st.markdown("**Department**")
                            sheet_assignments["Department"] = st.selectbox(
                                "Select sheet for Department lookup:",
                                options=[""] + selected_sheets,
                                index=0 if len(selected_sheets) < 3 else 3
                            )
                
                # Validate selections
                if selected_sheets:
                    # Check if we have exactly 3 sheets
                    if len(selected_sheets) != 3:
                        st.warning(f"You have selected {len(selected_sheets)} sheets. Please select exactly 3 sheets.")
                    
                    # Check if all lookup types have been assigned
                    missing_assignments = [lookup_type for lookup_type, sheet in sheet_assignments.items() if not sheet]
                    if missing_assignments:
                        st.warning(f"Missing assignments for: {', '.join(missing_assignments)}")
                    
                    # Check for duplicate assignments
                    assigned_sheets = [sheet for sheet in sheet_assignments.values() if sheet]
                    if len(assigned_sheets) != len(set(assigned_sheets)):
                        st.error("Each sheet must be assigned to exactly one lookup type.")
                
                # Load selected sheets into dataframes
                if selected_sheets and not missing_assignments and len(assigned_sheets) == len(set(assigned_sheets)):
                    cosmos_dfs_temp = {}
                    cosmos_summaries = {}
                    
                    # Map assigned sheets to their roles
                    sheet_role_mapping = {}
                    for role, sheet in sheet_assignments.items():
                        if sheet:
                            sheet_role_mapping[sheet] = role
                            
                    for sheet in selected_sheets:
                        if sheet not in sheet_role_mapping:
                            continue  # Skip sheets that haven't been assigned a role
                            
                        sheet_df = pd.read_excel(cosmos_file, sheet_name=sheet).astype(str)
                        role = sheet_role_mapping[sheet]
                        
                        # Store the dataframe with its role name as the key
                        cosmos_dfs_temp[role] = sheet_df
                        
                        # Get required columns for this sheet
                        if sheet_role_mapping[sheet] in mapping_df.columns:
                            required_sheet_columns = []
                            sheet_mappings = mapping_df[mapping_df['Type'] == 'IN'][sheet_role_mapping[sheet]].dropna()
                            if not sheet_mappings.empty:
                                required_sheet_columns = sheet_mappings.unique().tolist()
                            
                            if required_sheet_columns:
                                sheet_valid, sheet_missing = validate_required_columns(sheet_df, required_sheet_columns)
                                
                                if not sheet_valid:
                                    st.error(f"COSMOS '{sheet}' sheet (assigned to {role}) is missing required columns: {', '.join(sheet_missing)}")
                                    return  # Skip this sheet but continue with others
                        
                        # Check for special characters
                        sheet_invalid_cells = check_special_characters(sheet_df)
                        if sheet_invalid_cells:
                            st.error(f"COSMOS '{sheet}' sheet (assigned to {role}) contains invalid special characters:")
                            for idx, col, value, chars in sheet_invalid_cells[:5]:  # Show first 5
                                st.error(f"Row {idx+1}, Column '{col}': '{value}' contains invalid chars: '{chars}'")
                            return  # Skip this sheet but continue with others
                        
                        # Create sheet summary
                        sheet_metadata = cosmos_metadata.copy()
                        sheet_metadata['sheet_name'] = sheet
                        sheet_metadata['assigned_role'] = role
                        cosmos_summaries[sheet] = create_file_summary(sheet_metadata, sheet_df)
                    
                    # If all validations pass, update the cosmos_dfs
                    cosmos_dfs = cosmos_dfs_temp
                    file_summaries['COSMOS'] = cosmos_summaries
                    
                    # Set validation_passed to True only if we have 3 roles assigned (Account, Customer, Department)
                    required_roles = {"Account", "Customer", "Department"}
                    validation_passed = set(cosmos_dfs.keys()) == required_roles
                    
                    if not validation_passed and cosmos_dfs:
                        missing_roles = required_roles - set(cosmos_dfs.keys())
                        if missing_roles:
                            st.warning(f"Missing assignments for: {', '.join(missing_roles)}")
                        else:
                            st.warning("Not all selected sheets passed validation. Please select valid sheets.")
                else:
                    st.error("Please select at least one sheet from the COSMOS file.")
        
        except Exception as e:
            st.error(f"Error processing files: {str(e)}")
            import traceback
            st.error(traceback.format_exc())
            return
    
    # Display summaries if validation passed
    if validation_passed:
        st.subheader("Upload Summary")
        
        summary_expander = st.expander("View Upload Summary", expanded=True)
        with summary_expander:
            # Master file summary
            st.markdown("### Master Lookup File")
            master_summary = file_summaries['Master']
            st.write(f"**Filename:** {master_summary['filename']}")
            st.write(f"**Upload Time:** {master_summary['upload_time']}")
            st.write(f"**Records:** {master_summary['records']}")
            st.write(f"**Columns:** {master_summary['columns']}")
            
            # COSMOS file summaries
            st.markdown("### COSMOS Lookup Sheets")
            for sheet, summary in file_summaries['COSMOS'].items():
                role = summary.get('assigned_role', 'Unknown Role')
                st.markdown(f"#### {sheet} Sheet (Assigned as {role})")
                st.write(f"**Filename:** {summary['filename']}")
                st.write(f"**Upload Time:** {summary['upload_time']}")
                st.write(f"**Records:** {summary['records']}")
                st.write(f"**Columns:** {summary['columns']}")
            
            # Source file summary
            st.markdown("### Source File")
            source_summary = file_summaries['Source']
            st.write(f"**Filename:** {source_summary['filename']}")
            st.write(f"**Upload Time:** {source_summary['upload_time']}")
            st.write(f"**Records:** {source_summary['records']}")
            st.write(f"**Columns:** {source_summary['columns']}")
        
        # Process button - only show if validation passed
        if st.button("Process Files"):
            # Check if we have all required roles assigned
            required_roles = {"Account", "Customer", "Department"}
            if set(cosmos_dfs.keys()) != required_roles:
                missing_roles = required_roles - set(cosmos_dfs.keys())
                st.error(f"Please assign sheets to all required roles. Missing: {', '.join(missing_roles)}")
                return
                
            with st.spinner("Processing files..."):
                try:
                    start_time = time.time()  # Start timer
                    
                    # Extract the dataframes directly using role names as keys
                    acc_df = cosmos_dfs.get("Account", pd.DataFrame())
                    cus_df = cosmos_dfs.get("Customer", pd.DataFrame()) 
                    dep_df = cosmos_dfs.get("Department", pd.DataFrame())
                    
                    result_df = process_files(
                        pd.read_excel(master_file).astype(str), 
                        acc_df, 
                        cus_df, 
                        dep_df, 
                        pd.read_excel(source_file).astype(str), 
                        mapping_df
                    )
                    
                    end_time = time.time()  # End timer
                    
                    st.success("Processing complete!")
                    elapsed_time = end_time - start_time  # Total time in seconds
                    st.success(f"Processing time: {elapsed_time:.2f} seconds")
                    
                    # Display results
                    st.subheader("Results")
                    st.write("Updated Source Data:")
                    st.dataframe(result_df)
                   
                    # Create Excel output with text formatting
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        result_df.to_excel(writer, index=False, sheet_name='Sheet1')
                        workbook = writer.book
                        worksheet = writer.sheets['Sheet1']
                        text_format = workbook.add_format({'num_format': '@'})  # '@' means TEXT format
                        worksheet.set_column('A:Z', None, text_format)  # Apply to all columns
                    
                    # Streamlit download button
                    st.download_button(
                        label="Download Updated Source Data (Excel)",
                        data=output.getvalue(),
                        file_name="updated_source_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Error during processing: {str(e)}")
                    import traceback
                    st.error(traceback.format_exc())


if __name__ == "__main__":
    main()