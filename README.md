The lookup application implements all the requirements as specified below:

User Interface: A Streamlit app that accepts three Excel files as input - Master Lookup, COSMOS Lookup and Source Excel.
Mapping Logic: Uses the FTS_Mapping.csv file to determine how to match and update records.
Matching Guidelines: Implements all the specified matching patterns:
CLP% for prefix matching
<ANY> for accepting everything
000001019/000001020 for OR conditions
(0097003-0097005) for range matching
Date handling in mm/dd/yyyy format


Processing Flow:
Uses "IN" type mappings to identify matching criteria
Processes the Master Excel sequentially
Matches Source Excel records based on the mapping rules
Updates Master data using "OUT" mappings when matches are found
Removes matched records from the Source data
Repeats until all Master rows are processed

Results and Downloads: Provides the updated Master file and the remaining unmatched Source records for download.

To use this application:
Deploy it in a location where the FTS_Mapping.csv file is accessible
Upload your Master Lookup, COSMOS Lookup and Source Excel files
Select multiple tabs from the COSMOS excel you want to process 
Click "Process Files" to run the mapping operation
Download the results
