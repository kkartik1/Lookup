import streamlit as st
import pandas as pd
import re
import os
from datetime import datetime
import tempfile
import io
import time

def load_mapping_file():
    """Load the mapping CSV file that should be present at deployment site"""
    try:
        # In production, use the actual path where the mapping file is stored
        mapping_df = pd.read_csv("FTS_Mapping.csv")
        mas_map_df = mapping_df[['Type','Length','Target','Master']]
        acc_map_df = mapping_df[['Type','Length','Target','Account']]
        acc_map_df.columns = ['Type','Length','Target','Master']
        cus_map_df = mapping_df[['Type','Length','Target','Customer']]
        cus_map_df.columns = ['Type','Length','Target','Master']
        dep_map_df = mapping_df[['Type','Length','Target','Department']]
        dep_map_df.columns = ['Type','Length','Target','Master']
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

def check_dates_match(duplicates, master_row, source_row):
    # Check the date condition 
    if len(duplicates) > 1:
        pattern_fr = master_row[duplicates.iloc[0]['Master']]
        if pd.isna(master_row[duplicates.iloc[1]['Master']]) or master_row[duplicates.iloc[1]['Master']] == 'nan':
            pattern_to = ''
        else:
            pattern_to = master_row[duplicates.iloc[1]['Master']]
        value_dt = source_row[duplicates.iloc[0]['Target']]
        if not (parse_match_dates(str(pattern_fr), str(pattern_to), str(value_dt))):
            print('Date: Failed', pattern_fr, pattern_to, value_dt)
            return False
        print('Date: Passed', pattern_fr, pattern_to, value_dt)
        return True 
    else:
        return False
    
def format_number(x, ln):
    x = str(x).strip()
    if pd.isna(x) or x == '' or x == '0':
        return x
    else:
        return str(int(x)).zfill(ln)
    
def pad_with_zeros(in_df, df_len):
    # Convert 'account_number' to a fixed 6-character string with leading zeros
    for _, len_row in df_len.iterrows():
        in_df[len_row['Target']] = in_df[len_row['Target']].apply(lambda x: format_number(x, len_row['Length']))
    return in_df

def check_match_files(in_mappings, master_col, source_col, master_row, source_row):
   # Check all IN type mappings for a match
   for _, mapping_row in in_mappings.iterrows():
       master_column = mapping_row['Master']
       source_column = mapping_row['Target']
       
       # Skip if columns don't exist in the dataframes
       if master_column not in master_col or source_column not in source_col:
           continue      
       master_value = master_row[master_column]
       source_value = source_row[source_column]
       # Regular pattern matching
       if not parse_match_pattern(master_value, source_value):
           print(master_column +': Failed', master_value, source_value)
           return False
       else:
           print(master_column +': Passed', master_value, source_value)
   return True
   

    
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
    # Filter the mapping for "Length" types (for updating)
    len_mappings = mapping_df[~mapping_df['Length'].isna()][['Length', 'Target']]
    len_mappings['Length'] = len_mappings.Length.astype(int)
    # Create a copy of the Master dataframe to modify
    result_df = source_df.copy().astype(str)
    source_copy_df = source_df.copy().astype(str)
    master_copy_df = master_df.copy().astype(str)
    # Process each row in the Source dataframe
    count = 0
    for source_idx, source_row in source_copy_df.iterrows():
        match_found = False
        # For each source row, check if it matches current master row
        for idx, master_row in master_copy_df.iterrows():
            all_conditions_met = True
            # check for dates matching
            if not check_dates_match(duplicates, master_row, source_row):
                all_conditions_met = False
                continue
            print('Date Check Passed')
            # Check all matching conditions
            if not check_match_files(in_mappings, master_df.columns, source_df.columns, master_row, source_row):
                all_conditions_met = False
                continue
            print('All check passed for record')    
            if all_conditions_met:
                match_found = True  
                # Update the result dataframe with OUT mappings
                for _, out_row in out_mappings.iterrows():
                    target_column = out_row['Target']
                    master_column = out_row['Master']
                    if master_column in master_df.columns and target_column in result_df.columns:
                        result_df.at[source_idx, target_column] = master_row[master_column]
                    # Remove the matched row from the source dataframe
                source_copy_df = source_copy_df.drop(source_idx)
                master_copy_df = master_copy_df.drop(idx)
                break
        if match_found:
            count = count + 1
    total = len(master_df)
    st.warning(f"Out of total {total} rules, from {sheet} matches found for {count} rule(s).")
    result_df = pad_with_zeros(result_df, len_mappings)
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
                    cosmos_dfs[sheet] = pd.read_excel(cosmos_file, sheet_name=sheet).astype(str)
                    st.write(f"Loaded {sheet} with {len(cosmos_dfs[sheet])} rows")
    
    if master_file and source_file and cosmos_file and selected_sheets:
        #try:
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
            lst_tabs = []
            tabs = st.tabs(selected_sheets)
            for i, sheet_name in enumerate(selected_sheets):
                lst_tabs.append(sheet_name)
                with tabs[i]:
                    st.write(f"{sheet_name}:")
                    st.write(f"Total rows: {len(cosmos_dfs[sheet_name])}")
            
            # Process button
            if st.button("Process Files"):
                with st.spinner("Processing files..."):
                    start_time = time.time()  # Start timer
                    result_df = process_files(master_df, source_df, mas_map_df, 'Master Lookup')
                    result_df2 = process_files(cosmos_dfs[lst_tabs[0]], result_df, acc_map_df, 'Account Lookup')
                    result_df3 = process_files(cosmos_dfs[lst_tabs[1]], result_df2, cus_map_df, 'Customer Lookup')
                    result_df4 = process_files(cosmos_dfs[lst_tabs[2]], result_df3, dep_map_df, 'Department Lookup')
                    end_time = time.time()  # End timer
                st.success("Processing complete!")
                elapsed_time = end_time - start_time  # Total time in seconds
                st.success(f"Processing time: {elapsed_time:.2f} seconds")
                
                # Display results
                st.subheader("Results")
                st.write("Updated Source Data:")
                st.dataframe(result_df4)
               
                # Download buttons for results
                # Create a buffer
                output = io.BytesIO()
                # Write the DataFrame into the buffer as Excel
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    result_df4.to_excel(writer, index=False, sheet_name='Sheet1')
                    workbook  = writer.book
                    worksheet = writer.sheets['Sheet1']
                    text_format = workbook.add_format({'num_format': '@'})  # '@' means TEXT format
                    worksheet.set_column('A:H', None, text_format)  # Apply to first column (A)
                
                # Get the Excel bytes
                excel_bytes = output.getvalue()
                
                # Streamlit download button
                st.download_button(
                    label="Download Updated Source Data (Excel)",
                    data=excel_bytes,
                    file_name="updated_source_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                        
        #except Exception as e:
            #st.error(f"Error processing files: {str(e)}")

if __name__ == "__main__":
    main()
