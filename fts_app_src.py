import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io
import time


def load_mapping_file():
    """Load the mapping CSV file that should be present at deployment site"""
    try:
        # In production, use the actual path where the mapping file is stored
        return pd.read_csv("FTS_Mapping.csv")
    except FileNotFoundError:
        st.error("Mapping file (FTS_Mapping.csv) not found. Please place it in the application directory.")
        return None


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
        result_df[len_row['Target']] = result_df[len_row['Target']].apply(
            lambda x: format_number(x, len_row['Length'])
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
        if all(opt.isdigit() for opt in options):
            options = [int(item) for item in options]
            return int(value) if value.isdigit() else value in options
        return value in options
    
    # Handle (0097003-0097005) pattern (range)
    range_match = re.match(r'\((\w+)-(\w+)\)', pattern)
    if range_match:
        start, end = range_match.groups()
        # Check if it's a numeric range
        if start.isdigit() and end.isdigit() and value.isdigit():
            return int(start) <= int(value) <= int(end)
        # Otherwise treat as string range
        return start <= value <= end
    
    # Simple numeric or string equality
    if value.isdigit() and pattern.isdigit():
        return int(pattern) == int(value)
    
    return pattern == value


def check_match_files(in_mappings, master_col, source_col, master_row, source_row):
    """Check all IN type mappings for a match"""
    for _, mapping_row in in_mappings.iterrows():
        master_column = mapping_row['Master']
        source_column = mapping_row['Target']
        
        # Skip if columns don't exist in the dataframes
        if master_column not in master_col or source_column not in source_col:
            continue
            
        master_value = master_row[master_column]
        source_value = source_row[source_column]
        
        # Regular pattern matching
        match_result = parse_match_pattern(master_value, source_value)
        print(f"{master_column}: {'Passed' if match_result else 'Failed'}", master_value, source_value)
        
        if not match_result:
            return False
            
    return True


def process_rule_files(master_df, in_mappings, source_row, source_col):
    """Process rules against master files"""
    # Remove all rows with duplicates mappings e.g. date
    duplicates = in_mappings[in_mappings.Target.duplicated(keep=False)]
    filtered_mappings = in_mappings[~in_mappings['Target'].duplicated(keep=False)].reset_index(drop=True)
    
    master_copy_df = master_df.copy().astype(str)
    
    for idx, master_row in master_copy_df.iterrows():
        # Check for dates matching
        if not check_dates_match(duplicates, master_row, source_row):
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
    if sheet == 'Master':
        mapping_df = map_df[['Type', 'Length', 'Target', 'Master']]
    else:
        column_name = sheet
        mapping_df = map_df[['Type', 'Length', 'Target', column_name]]
        mapping_df.columns = ['Type', 'Length', 'Target', 'Master']
    
    # Filter the mapping for "IN" types (for matching)
    in_mappings = mapping_df[mapping_df['Type'] == 'IN']
    
    # Filter the mapping for "OUT" types (for updating)
    out_mappings = mapping_df[mapping_df['Type'] == 'OUT']
    
    # Filter the mapping for "Length" types (for updating)
    len_mappings = mapping_df[~mapping_df['Length'].isna()][['Length', 'Target']]
    len_mappings['Length'] = len_mappings.Length.astype(int)
    
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
        for lookup_type in dfs.keys():
            in_mappings, out_mappings, len_mappings = get_mapping(mapping_df, lookup_type)
            
            # Check if the source row matches any rule in the current lookup
            all_conditions_met, master_row, filtered_df = process_rule_files(
                dfs[lookup_type], in_mappings, source_row, source_df.columns
            )
            
            # Update the dataframe with the filtered results
            dfs[lookup_type] = filtered_df
            
            if all_conditions_met:
                # Update the result dataframe with OUT mappings
                for _, out_row in out_mappings.iterrows():
                    target_column = out_row['Target']
                    master_column = out_row['Master']
                    
                    if (master_column in dfs[lookup_type].columns and 
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
        st.warning(
            f"Out of total {total_counts[lookup_type]} rules, from {lookup_type} Lookup "
            f"matches found for {count} rule(s)."
        )
    
    # Format result numbers with leading zeros
    _, _, len_mappings = get_mapping(mapping_df, 'Master')
    result_df = pad_with_zeros(result_df, len_mappings)
    
    return result_df


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
    
    # COSMOS sheet selection (shown only after COSMOS file is uploaded)
    cosmos_dfs = {}
    selected_sheets = []
    
    if cosmos_file:
        # Read all sheet names from COSMOS file
        with pd.ExcelFile(cosmos_file) as xls:
            sheet_names = xls.sheet_names
            
            st.write("Select sheets from COSMOS excel to use for lookup:")
            
            # Create checkboxes for selecting sheets
            selected_sheets = []
            for sheet in sheet_names:
                if st.checkbox(f"Use {sheet}", value=True):
                    selected_sheets.append(sheet)
            
            # Load selected sheets into dataframes
            if selected_sheets:
                for sheet in selected_sheets:
                    cosmos_dfs[sheet] = pd.read_excel(cosmos_file, sheet_name=sheet).astype(str)
                    st.write(f"Loaded {sheet} with {len(cosmos_dfs[sheet])} rows")
    
    if master_file and source_file and cosmos_file and selected_sheets:
        try:
            # Read Excel files
            master_df = pd.read_excel(master_file).astype(str)
            source_df = pd.read_excel(source_file).astype(str)
            
            st.subheader("Files Loaded Successfully")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"Total rows (Master Lookup): {len(master_df)}")
            
            with col2:
                st.write(f"Total rows (Source Lookup): {len(source_df)}")
            
            # Show COSMOS data previews
            if selected_sheets:
                tabs = st.tabs(selected_sheets)
                for i, sheet_name in enumerate(selected_sheets):
                    with tabs[i]:
                        st.write(f"{sheet_name}:")
                        st.write(f"Total rows: {len(cosmos_dfs[sheet_name])}")
            
            # Process button
            if st.button("Process Files"):
                with st.spinner("Processing files..."):
                    start_time = time.time()  # Start timer
                    
                    # Ensure we have at least 3 sheets for the 3 required dataframes
                    if len(selected_sheets) < 3:
                        st.error("Please select at least 3 sheets from the COSMOS file.")
                        return
                        
                    result_df = process_files(
                        master_df, 
                        cosmos_dfs[selected_sheets[0]], 
                        cosmos_dfs[selected_sheets[1]], 
                        cosmos_dfs[selected_sheets[2]], 
                        source_df, 
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
            st.error(f"Error processing files: {str(e)}")


if __name__ == "__main__":
    main()
