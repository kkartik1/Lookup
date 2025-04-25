import streamlit as st
import pandas as pd
import re
import os
from datetime import datetime
import tempfile


def load_mapping_file():
    """Load the mapping CSV file that should be present at deployment site"""
    try:
        # In production, use the actual path where the mapping file is stored
        mapping_df = pd.read_csv("FTS_Mapping.csv")
        mas_map_df = mapping_df[['Type','Target','Master']]
        acc_map_df = mapping_df[['Type','Target','Account']]
        acc_map_df.columns = ['Type','Target','Master']
        cus_map_df = mapping_df[['Type','Target','Customer']]
        cus_map_df.columns = ['Type','Target','Master']
        dep_map_df = mapping_df[['Type','Target','Department']]
        dep_map_df.columns = ['Type','Target','Master']
        return mas_map_df, acc_map_df, cus_map_df, dep_map_df 
    except FileNotFoundError:
        st.error("Mapping file (FTS_Mapping.csv) not found. Please place it in the application directory.")
        return None
    
def parse_match_dates(pattern_fr, pattern_to, value_dt):
    if pattern_to=='':
        try:
            date_fr = datetime.strptime(pattern_fr, '%m/%d/%Y')
            value_date = datetime.strptime(value_dt, '%m/%d/%Y')
            return date_fr <= value_date
        #except ValueError:
        except ValueError:
            # Not valid dates, proceed with mismatch
            return False
    try:
        date_fr = datetime.strptime(pattern_fr, '%m/%d/%Y')
        date_to = datetime.strptime(pattern_to, '%m/%d/%Y')
        value_date = datetime.strptime(value_dt, '%m/%d/%Y')
        return date_fr <= value_date <= date_to
    except ValueError:
        # Not valid dates, proceed with mismatch
        return False

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
        if start.isdigit() and end.isdigit() and value.isdigit():
            return int(start) <= int(value) <= int(end)
        # Otherwise treat as string range
        return start <= value <= end
    if value.isdigit() and pattern.isdigit():
        return int(pattern) == int(value)
    else:
        return pattern == value

def process_files(master_df, source_df, mapping_df, sheet):
    """Process the Excel files based on mapping guidelines"""
    # Filter the mapping for "IN" types (for matching)
    in_mappings = mapping_df[mapping_df['Type'] == 'IN']
    # Remove all rows with duplicates mappings e.g. date
    duplicates = in_mappings[in_mappings.Target.duplicated(keep=False)]
    in_mappings = in_mappings[~in_mappings['Target'].duplicated(keep=False)].reset_index(drop=True)
    # Filter the mapping for "OUT" types (for updating)
    out_mappings = mapping_df[mapping_df['Type'] == 'OUT']
    count = 0
    # Create a copy of the Master dataframe to modify
    result_df = source_df.copy()
    source_copy_df = source_df.copy()
    # Process each row in the Master dataframe
    for idx, master_row in master_df.iterrows():
        match_found = False
        
        # For each source row, check if it matches current master row
        for source_idx, source_row in source_copy_df.iterrows():
            all_conditions_met = True
            # Check the date condition 
            if len(duplicates) > 1:
                pattern_fr = master_row[duplicates.iloc[0]['Master']]
                if pd.isna(master_row[duplicates.iloc[1]['Master']]):
                    pattern_to = ''
                else:
                    pattern_to = master_row[duplicates.iloc[1]['Master']]
                value_dt = source_row[duplicates.iloc[0]['Target']]
                if not (parse_match_dates(str(pattern_fr), str(pattern_to), str(value_dt))):
                    all_conditions_met = False
                    print('Date: Failed', pattern_fr, value_dt)
                    break
                print('Date: Passed', pattern_fr, value_dt)
            # Check all IN type mappings for a match
            for _, mapping_row in in_mappings.iterrows():
                master_column = mapping_row['Master']
                source_column = mapping_row['Target']
                
                # Skip if columns don't exist in the dataframes
                if master_column not in master_df.columns or source_column not in source_df.columns:
                    continue
                
                master_value = master_row[master_column]
                source_value = source_row[source_column]
                # Regular pattern matching
                if not parse_match_pattern(master_value, source_value):
                    all_conditions_met = False
                    print(master_column +': Failed', master_value, source_value)
                    break
                else:
                    print(master_column +': Passed', master_value, source_value)
            
            if all_conditions_met:
                match_found = True               
                # Update the result dataframe with OUT mappings
                for _, out_row in out_mappings.iterrows():
                    target_column = out_row['Target']
                    master_column = out_row['Master']
                    if master_column in master_df.columns and target_column in result_df.columns:
                        result_df.at[idx, target_column] = master_row[master_column]
                
                    # Remove the matched row from the source dataframe
                source_copy_df = source_copy_df.drop(source_idx)
                break
        
        if not match_found:
            count = count + 1
    total = len(master_df)
    match = total - count
    st.warning(f"Out of total {total} rules, from {sheet} matches found for {match} rule(s).")
    return result_df

def main():
    st.title("Financial Tagging Services")
    
    st.write(""" This application maps data between Master Lookup files and Source Excel file. """)
    
    # Load the mapping file
    mas_map_df, acc_map_df, cus_map_df, dep_map_df = load_mapping_file()
    if mas_map_df is None or acc_map_df is None or cus_map_df is None or dep_map_df is None:
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
                    cosmos_dfs[sheet] = pd.read_excel(cosmos_file, sheet_name=sheet)
                    st.write(f"Loaded {sheet} with {len(cosmos_dfs[sheet])} rows")
    
    if master_file and source_file and cosmos_file and selected_sheets:
        try:
            # Read Excel files
            master_df = pd.read_excel(master_file)
            source_df = pd.read_excel(source_file)
            
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
                    result_df = process_files(master_df, source_df, mas_map_df, 'Master Lookup')
                    result_df2 = process_files(cosmos_dfs['ACCOUNT'], result_df, acc_map_df, 'Account Lookup')
                    result_df3 = process_files(cosmos_dfs['CUST'], result_df2, cus_map_df, 'Customer Lookup')
                    result_df4 = process_files(cosmos_dfs['DEP'], result_df3, dep_map_df, 'Department Lookup')
                st.success("Processing complete!")
                
                # Display results
                st.subheader("Results")
                st.write("Updated Master Data:")
                st.dataframe(result_df4)
               
                # Download buttons for results
                result_csv = result_df4.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Updated Master Data",
                    data=result_csv,
                    file_name="updated_master_data.csv",
                    mime="text/csv"
                )
                        
        except Exception as e:
            st.error(f"Error processing files: {str(e)}")

if __name__ == "__main__":
    main()
