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
        mapping_df = pd.read_csv("FTS_Mapping.csv")
        
        # Create mapping dataframes for each type
        mapping_types = {
            'Master': 'Master',
            'Account': 'Account',
            'Customer': 'Customer',
            'Department': 'Department'
        }
        
        result_dfs = {}
        for key, column in mapping_types.items():
            df = mapping_df[['Type', 'Length', 'Target', column]]
            if key != 'Master':
                df.columns = ['Type', 'Length', 'Target', 'Master']
            result_dfs[key] = df
            
        return result_dfs
    except FileNotFoundError:
        st.error("Mapping file (FTS_Mapping.csv) not found. Please place it in the application directory.")
        return None


def parse_match_dates(pattern_fr, pattern_to, value_dt):
    """Parse and compare dates based on the patterns"""
    date_format = '%m/%d/%Y'
    
    try:
        date_fr = datetime.strptime(pattern_fr, date_format)
        value_date = datetime.strptime(value_dt, date_format)
        
        if pattern_to == '':
            return date_fr <= value_date
            
        date_to = datetime.strptime(pattern_to, date_format)
        return date_fr <= value_date <= date_to
    except ValueError:
        # Not valid dates, proceed with mismatch
        return False


def check_dates_match(duplicates, master_row, source_row):
    """Check if dates match according to the conditions"""
    if len(duplicates) > 1:
        pattern_fr = master_row[duplicates.iloc[0]['Master']]
        
        # Check if the second value is valid
        second_value = master_row[duplicates.iloc[1]['Master']]
        pattern_to = '' if pd.isna(second_value) or second_value == 'nan' else second_value
        
        value_dt = source_row[duplicates.iloc[0]['Target']]
        
        result = parse_match_dates(str(pattern_fr), str(pattern_to), str(value_dt))
        print('Date:', 'Passed' if result else 'Failed', pattern_fr, pattern_to, value_dt)
        return result
    return False


def format_number(x, ln):
    """Format a number with leading zeros to specified length"""
    x = str(x).strip()
    if pd.isna(x) or x == '' or x == '0':
        return x
    return str(int(x)).zfill(ln)


def pad_with_zeros(in_df, df_len):
    """Pad numeric fields with zeros based on length specifications"""
    for _, len_row in df_len.iterrows():
        in_df[len_row['Target']] = in_df[len_row['Target']].apply(
            lambda x: format_number(x, len_row['Length'])
        )
    return in_df


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
            options = [int(item) for item in options if item.isdigit()]
            if value.isdigit():
                value = int(value)
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
        
    # Simple equality comparison
    if value.isdigit() and pattern.isdigit():
        return int(pattern) == int(value)
    
    return pattern == value


def check_match_files(in_mappings, master_cols, source_cols, master_row, source_row):
    """Check all IN type mappings for a match"""
    for _, mapping_row in in_mappings.iterrows():
        master_column = mapping_row['Master']
        source_column = mapping_row['Target']
        
        # Skip if columns don't exist in the dataframes
        if master_column not in master_cols or source_column not in source_cols:
            continue
            
        master_value = master_row[master_column]
        source_value = source_row[source_column]
        
        # Regular pattern matching
        if not parse_match_pattern(master_value, source_value):
            print(f"{master_column}: Failed", master_value, source_value)
            return False
        
        print(f"{master_column}: Passed", master_value, source_value)
    
    return True


def get_mapping_components(mapping_df):
    """Extract the different mapping components from the mapping dataframe"""
    # Filter the mapping for "IN" types (for matching)
    in_mappings = mapping_df[mapping_df['Type'] == 'IN']
    
    # Identify duplicated target columns (like dates)
    duplicates = in_mappings[in_mappings.Target.duplicated(keep=False)]
    
    # Remove the duplicates from the regular in_mappings
    unique_in_mappings = in_mappings[~in_mappings['Target'].duplicated(keep=False)].reset_index(drop=True)
    
    # Filter the mapping for "OUT" types (for updating)
    out_mappings = mapping_df[mapping_df['Type'] == 'OUT']
    
    # Filter the mapping for "Length" types (for updating)
    len_mappings = mapping_df[~mapping_df['Length'].isna()][['Length', 'Target']]
    len_mappings['Length'] = len_mappings.Length.astype(int)
    
    return unique_in_mappings, duplicates, out_mappings, len_mappings


def process_files(master_df, source_df, mapping_df, sheet):
    """Process files based on mapping rules"""
    # Get the different mapping components
    in_mappings, duplicates, out_mappings, len_mappings = get_mapping_components(mapping_df)
    
    # Create copies of dataframes for processing
    result_df = source_df.copy().astype(str)
    source_copy_df = source_df.copy().astype(str)
    master_copy_df = master_df.copy().astype(str)
    
    # Process each row in the source dataframe
    count = 0
    processed_indices = set()  # Track processed source indices
    
    for source_idx, source_row in source_copy_df.iterrows():
        if source_idx in processed_indices:
            continue
            
        match_found = False
        
        # For each source row, check if it matches any master row
        for idx, master_row in master_copy_df.iterrows():
            # Check date matching conditions
            if len(duplicates) > 0 and not check_dates_match(duplicates, master_row, source_row):
                continue
                
            print('Date Check Passed')
            
            # Check all other matching conditions
            if not check_match_files(in_mappings, master_df.columns, source_df.columns, master_row, source_row):
                continue
                
            print('All check passed for record')
            
            # All conditions met - we have a match
            match_found = True
            
            # Update the result dataframe with OUT mappings
            for _, out_row in out_mappings.iterrows():
                target_column = out_row['Target']
                master_column = out_row['Master']
                
                if master_column in master_df.columns and target_column in result_df.columns:
                    result_df.at[source_idx, target_column] = master_row[master_column]
            
            # Mark source row as processed
            processed_indices.add(source_idx)
            
            # Remove the matched master row to avoid reusing
            master_copy_df = master_copy_df.drop(idx)
            break
            
        if match_found:
            count += 1
    
    # Report statistics
    total = len(master_df)
    st.warning(f"Out of total {total} rules, from {sheet} matches found for {count} rule(s).")
    
    # Format numbers with leading zeros
    result_df = pad_with_zeros(result_df, len_mappings)
    
    return result_df


def main():
    st.title("Financial Tagging Services")
    
    st.write("""This application maps data between Master Lookup files and Source Excel file.""")
    
    # Load the mapping file
    mapping_dfs = load_mapping_file()
    if mapping_dfs is None:
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
    
    if master_file and source_file and cosmos_file and len(selected_sheets) >= 3:
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
            tabs = st.tabs(selected_sheets)
            for i, sheet_name in enumerate(selected_sheets):
                with tabs[i]:
                    st.write(f"{sheet_name}:")
                    st.write(f"Total rows: {len(cosmos_dfs[sheet_name])}")
            
            # Process button
            if st.button("Process Files"):
                with st.spinner("Processing files..."):
                    start_time = time.time()  # Start timer
                    
                    # Process files sequentially with each mapping
                    result_df = process_files(
                        master_df, 
                        source_df, 
                        mapping_dfs['Master'], 
                        'Master Lookup'
                    )
                    
                    result_df = process_files(
                        cosmos_dfs[selected_sheets[0]], 
                        result_df, 
                        mapping_dfs['Account'], 
                        'Account Lookup'
                    )
                    
                    result_df = process_files(
                        cosmos_dfs[selected_sheets[1]], 
                        result_df, 
                        mapping_dfs['Customer'], 
                        'Customer Lookup'
                    )
                    
                    result_df = process_files(
                        cosmos_dfs[selected_sheets[2]], 
                        result_df, 
                        mapping_dfs['Department'], 
                        'Department Lookup'
                    )
                    
                    end_time = time.time()  # End timer
                    
                st.success("Processing complete!")
                elapsed_time = end_time - start_time  # Total time in seconds
                st.success(f"Processing time: {elapsed_time:.2f} seconds")
                
                # Display results
                st.subheader("Results")
                st.write("Updated Source Data:")
                st.dataframe(result_df)
               
                # Create Excel output
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
    elif master_file and source_file and cosmos_file:
        st.error("Please select at least 3 sheets from the COSMOS file.")


if __name__ == "__main__":
    main()
