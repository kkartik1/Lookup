import getpass
from datetime import datetime
import os
import platform
import pandas as pd
import numpy as np
import streamlit as st
import smtplib
import sys
from dateutil import parser
import polars as pl

from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import COMMASPACE, formatdate
from email import encoders
MailUSER = getpass.getuser()
MailHOST = platform.uname()[1]
MailFROM = 'fts_tagging@rn000116071.uhc.com' 
MailSERVER = "mailo2.uhc.com"

def SendMail(email,MailSUBJECT, MailTEXT="", MailFILES=[]):
    MailTO = [email] 
    if type(MailTO) != list:
        MailTO = [MailTO]
    if type(MailFILES) != list:
        MailFILES = [MailFILES]

    msg = MIMEMultipart('related')
    msg['From'] = MailFROM
    msg['To'] = COMMASPACE.join(MailTO)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = MailSUBJECT

    # Create the body with HTML
    msgAlternative = MIMEMultipart('alternative')
    msg.attach(MIMEText(MailTEXT, "html"))
    msgText = MIMEText(MailTEXT, 'plain')
    msgAlternative.attach(msgText)
    # Attach image with Content-ID
    with open("UHC.png", 'rb') as img_file:
        img = MIMEImage(img_file.read())
        img.add_header('Content-ID', '<UHC.png>')
        img.add_header('Content-Disposition', 'inline', filename="UHC.png")
        msg.attach(img)

    # Attach files
    for file in MailFILES:
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(file, "rb").read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % file)
        msg.attach(part)

    smtp = smtplib.SMTP(MailSERVER)
    smtp.sendmail(MailFROM, MailTO, msg.as_string())
    smtp.close()

    print("Email sent successfully!")

def column_name_formatting(df):
    df.columns = [col.replace('-', '_') for col in df.columns]
    return df

def extract_master_string(df):
    df_name = [name for name in globals() if globals()[name] is df][0]
    extracted_string = df_name.split('_')[1].capitalize()
    return extracted_string

def process_map_columns(df, column_name,df_map):
    # Print the length of the needed master column
    mapped_list = [x for x in df_map[column_name].values.tolist() if pd.notna(x) and x != 'nan']
    df_mapped = df[mapped_list]
    return df_mapped

def explode_range(row, dy_col, static_col):
    exploded_data = []
    for col in dy_col:
        row[col] = str(row[col]).replace('(', '').replace(')', '')
        if '-' in str(row[col]):
            start_str, end_str = row[col].split('-')
            start, end = int(start_str), int(end_str)
            original_length = len(start_str)
            exploded_values = [str(i).zfill(original_length) for i in range(start, end + 1)]
        elif '/' in str(row[col]):
            exploded_values = row[col].split('/')
        else:
            exploded_values = [row[col]]

        for value in exploded_values:
            new_row = row.copy()
            new_row[col] = value
            exploded_data.append(new_row)
    return pl.DataFrame(exploded_data)

def recursive_explode(df, dy_col, static_col):
    df = pl.DataFrame(df)
    for i, col in enumerate(dy_col):
        current_dy_col = [col]
        current_static_col = dy_col[:i] + dy_col[i+1:] + static_col
        exploded_dfs = [explode_range(row, current_dy_col, current_static_col) for row in df.iter_rows(named=True)]

        # Ensure schema consistency, casting Null types to Utf8
        schema = exploded_dfs[0].schema
        exploded_dfs = [
            df.with_columns([
                pl.col(col).cast(schema[col] if schema[col] != pl.Null else pl.Utf8)
                for col in schema
            ])
            for df in exploded_dfs
        ]

        df = pl.concat(exploded_dfs)
    return df.to_pandas()

def merged_df(df, master, key_columns, mapping, col):
    import pandas as pd
    import polars as pl

    fin = df.copy()
    index_col_name = col
    fin[index_col_name] = None  # Initialize the new column

    # Ensure date columns are in datetime format
    fin['GL_IDB_A_DT'] = pd.to_datetime(fin['GL_IDB_A_DT'], errors='coerce')
    master['START_DATE_ACTIVE'] = pd.to_datetime(master['START_DATE_ACTIVE'], errors='coerce')
    master['END_DATE_ACTIVE'] = pd.to_datetime(master['END_DATE_ACTIVE'], errors='coerce')

    # Convert to Polars DataFrames
    fin_pl = pl.DataFrame(fin).with_columns([
        pl.col("GL_IDB_A_DT").cast(pl.Datetime("ns"))
    ])
    master_pl = pl.DataFrame(master)

    for master_row in master_pl.iter_rows(named=True):
        mask = pl.Series([True] * len(fin_pl))

        # Apply key column filters
        for col in key_columns:
            val = master_row[col]
            if val != '<ANY>' and val!= 'None':
                if isinstance(val, str) and '%' in val:
                    mask &= fin_pl[col].str.contains(val.replace('%', ''), literal=False).fill_null(False)
                elif isinstance(val, str) and val.startswith('NOT '):
                    exclude = val.split(' ', 1)[1]
                    mask &= ~fin_pl[col].str.contains(exclude, literal=False).fill_null(False)
                else:
                    # Try numeric comparison if both values are numeric strings
                    try:
                        val_int = int(val.lstrip('0') or '0')
                        mask &= fin_pl[col].cast(pl.Int64).fill_null(-1) == val_int
                    except:
                        mask &= fin_pl[col] == val

        # Apply mapping and date filters
        for master_col, target_col in mapping.items():
            if pd.notna(master_row[master_col]):
                mask_target = (
                    mask &
                    (fin_pl[target_col] == '0') &
                    pl.lit(master_row['ENABLED_FLAG'] == 'Y')
                )

                # Apply date filters only if dates are not null
                if pd.notna(master_row['END_DATE_ACTIVE']):
                    mask_target &= fin_pl['GL_IDB_A_DT'] <= pl.lit(master_row['END_DATE_ACTIVE'])
                if pd.notna(master_row['START_DATE_ACTIVE']):
                    mask_target &= fin_pl['GL_IDB_A_DT'] >= pl.lit(master_row['START_DATE_ACTIVE'])

                fin_pl = fin_pl.with_columns([
                    pl.when(mask_target).then(pl.lit(master_row[master_col])).otherwise(fin_pl[target_col]).alias(target_col),
                    pl.when(mask_target).then(pl.lit(master_row[index_col_name])).otherwise(fin_pl[index_col_name]).alias(index_col_name)
                ])

    return fin_pl.to_pandas()

def main(df_target,df_master,df_account,df_customer,df_department,df_map,email):
    start_time = datetime.now()
    print('Start time:',start_time)
    df_target.columns = [col.replace('_ORIG', '') for col in df_target.columns]

    df_dict = {'Target': df_target,'Master': df_master,'Account': df_account,'Customer': df_customer,'Department': df_department}
    for key, df in df_dict.items():
        df = column_name_formatting(pd.DataFrame(df))
        df = process_map_columns(df, key, df_map)
        df.columns = df.columns.str.upper()
        df_dict[key] = df                              

    # Update the original DataFrames from the dictionary
    df_target = df_dict['Target']
    df_master = df_dict['Master']
    df_account = df_dict['Account']
    df_customer = df_dict['Customer']
    df_department = df_dict['Department']
    df_target = df_target.loc[:, ~df_target.columns.duplicated()]

    # Now df_target and all other dataframes in df_list have the filtered data
    print ("Reading dfs!")
    print("Target df!",df_target.shape) #(50000, 17)
    print("Master df!",df_master.shape)
    print("Account df!",df_account.shape)
    print("Customer df!",df_customer.shape)
    print("Department df!",df_department.shape)

    # Function to convert values to strings representing integers
    def convert_to_str(value):
        try:
            return str(int(value))
        except ValueError:
            return value  

    df_account['ASO_CLM_FLG'] = df_account['ASO_CLM_FLG'].apply(convert_to_str)

    df_master['START_DATE_ACTIVE'] = df_master['START_DATE_ACTIVE'].apply(lambda x: parser.parse(x).date() if pd.notnull(x) and x != '' else None)
    df_account['START_DATE_ACTIVE'] = df_account['START_DATE_ACTIVE'].apply(lambda x: parser.parse(x).date() if pd.notnull(x) and x != '' else None)
    df_customer['START_DATE_ACTIVE'] = df_customer['START_DATE_ACTIVE'].apply(lambda x: parser.parse(x).date() if pd.notnull(x) and x != '' else None)
    df_department['START_DATE_ACTIVE'] = df_department['START_DATE_ACTIVE'].apply(lambda x: parser.parse(x).date() if pd.notnull(x) and x != '' else None)

    df_master['END_DATE_ACTIVE'] = df_master['END_DATE_ACTIVE'].apply(lambda x: parser.parse(x).date() if pd.notnull(x) and x != '' else None)
    df_account['END_DATE_ACTIVE'] = df_account['END_DATE_ACTIVE'].apply(lambda x: parser.parse(x).date() if pd.notnull(x) and x != '' else None)
    df_customer['END_DATE_ACTIVE'] = df_customer['END_DATE_ACTIVE'].apply(lambda x: parser.parse(x).date() if pd.notnull(x) and x != '' else None)
    df_department['END_DATE_ACTIVE'] = df_department['END_DATE_ACTIVE'].apply(lambda x: parser.parse(x).date() if pd.notnull(x) and x != '' else None)
    df_target['GL_IDB_A_DT'] = df_target['GL_IDB_A_DT'].apply(lambda x: parser.parse(x).date() if pd.notnull(x) and x != '' else None)

    master_dy_col = [item for item in df_map['Master'].dropna().tolist() if item not in ['LOOKUP_CODE','START_DATE_ACTIVE', 'END_DATE_ACTIVE']]
    master_static_col = ['LOOKUP_CODE','START_DATE_ACTIVE','END_DATE_ACTIVE']
    print("Exploding master df")
    df_master_fin = recursive_explode(df_master, master_dy_col, master_static_col)
    
    account_dy_col = [item for item in df_map['Account'].dropna().tolist() if item not in ['LOOKUP_CODE','START_DATE_ACTIVE', 'END_DATE_ACTIVE']]
    account_static_col = ['LOOKUP_CODE','START_DATE_ACTIVE','END_DATE_ACTIVE']
    print("Exploding account df")
    df_account_fin = recursive_explode(df_account, account_dy_col, account_static_col)
    
    customer_dy_col = [item for item in df_map['Customer'].dropna().tolist() if item not in ['LOOKUP_CODE','START_DATE_ACTIVE', 'END_DATE_ACTIVE']]
    customer_static_col = ['LOOKUP_CODE','START_DATE_ACTIVE','END_DATE_ACTIVE']
    print("Exploding customer df")
    df_customer_fin = recursive_explode(df_customer, customer_dy_col, customer_static_col)
    
    department_dy_col = [item for item in df_map['Department'].dropna().tolist() if item not in ['LOOKUP_CODE','START_DATE_ACTIVE', 'END_DATE_ACTIVE']]
    department_static_col = ['LOOKUP_CODE','START_DATE_ACTIVE','END_DATE_ACTIVE']
    print("Exploding department df")
    df_department_fin = recursive_explode(df_department, department_dy_col, department_static_col)
    
    df_target_fin = df_target.copy()
    print("Records after exploding!")
    print("Target df!",df_target_fin.shape)
    print("Master df!",df_master_fin.shape)
    print("Account df!",df_account_fin.shape)
    print("Customer df!",df_customer_fin.shape)
    print("Department df!",df_department_fin.shape)
    explode_time = datetime.now()
    print ('Time taken in exploding dfs: ',int((explode_time-start_time).total_seconds())/60,' mins')
    
    df_target_fin.columns = [col.replace('COSMOS_', '') for col in df_target_fin.columns]
    df_target_fin.rename(columns={'PRVDR_NTWRK_NBR':'PRVDR_NTWRK_CD'}, inplace=True)
    df_target_fin.rename(columns={'ASO_CLAIM_FLAG':'ASO_CLM_FLG'}, inplace=True)

    df_department_fin.columns = [col.replace('COSMOS_', '') for col in df_department_fin.columns]
    df_department_fin.rename(columns={'FNC_PRCD': 'FNC_PRDCT'}, inplace=True)

    df_master_fin.rename(columns={'LOOKUP_CODE': 'LOOKUP_CODE_MASTER'}, inplace=True)
    df_account_fin.rename(columns={'LOOKUP_CODE': 'LOOKUP_CODE_ACCOUNT'}, inplace=True)
    df_customer_fin.rename(columns={'LOOKUP_CODE': 'LOOKUP_CODE_CUST'}, inplace=True)
    df_department_fin.rename(columns={'LOOKUP_CODE': 'LOOKUP_CODE_DEPT'}, inplace=True)

    key_col_master = [item for item in df_master_fin.columns if item not in df_map.query("Type =='OUT'")['Master'].dropna().tolist() + ['LOOKUP_CODE_MASTER','ENABLED_FLAG', 'START_DATE_ACTIVE', 'END_DATE_ACTIVE']] #['DIV', 'LGL_ENTY','GRP_POL_NBR','FNC_PRDCT', 'DATA_TYP_CD'] 
    key_col_account = [item for item in df_account_fin.columns if item not in df_map.query("Type =='OUT'")['Account'].dropna().tolist() + ['LOOKUP_CODE_ACCOUNT','ENABLED_FLAG', 'START_DATE_ACTIVE', 'END_DATE_ACTIVE']] #['DIV', 'LGL_ENTY','GRP_POL_NBR','DATA_TYP_CD','SRVC_TYP_CD'] 
    key_col_customer = [item for item in df_customer_fin.columns if item not in df_map.query("Type =='OUT'")['Customer'].dropna().tolist() + ['LOOKUP_CODE_CUST','ENABLED_FLAG', 'START_DATE_ACTIVE', 'END_DATE_ACTIVE']]# ['DIV', 'LGL_ENTY','GRP_POL_NBR','FNC_PRDCT'] 
    key_col_department = [item for item in df_department_fin.columns if item not in df_map.query("Type =='OUT'")['Department'].dropna().tolist() + ['LOOKUP_CODE_DEPT','ENABLED_FLAG', 'START_DATE_ACTIVE', 'END_DATE_ACTIVE']]# ['DIV', 'LGL_ENTY','GRP_POL_NBR','FNC_PRDCT'] 

    def replace_nan_like_values(df, columns, replacement='<ANY>'):
        for col in columns:
            df[col] = df[col].apply(
                lambda x: replacement if (pd.isna(x) or (isinstance(x, str) and x.strip().lower() == 'nan')) else x
            )
        return df

    df_master_fin = replace_nan_like_values(df_master_fin, key_col_master)
    df_account_fin = replace_nan_like_values(df_account_fin, key_col_account)
    df_customer_fin = replace_nan_like_values(df_customer_fin, key_col_customer)
    df_department_fin = replace_nan_like_values(df_department_fin, key_col_department)

    print("Target df!",df_target_fin.shape) 
    print("Master df!",df_master_fin.shape)
    print("Account df!",df_account_fin.shape)
    print("Customer df!",df_customer_fin.shape)
    print("Department df!",df_department_fin.shape)

    ps9_master_mapping = {
        'COSMOS_BU' : 'PS9_GL_LEG_ENTY_A_CD',
        'COSMOS_LOC' : 'PS9_GL_LOC_A_NBR',
        'COSMOS_PROD' : 'PS9_GL_PRDCT_A_CD',
        'COSMOS_OU' : 'PS9_GL_SEG_A_CD'}
    ps9_account_mapping = {'GL_ACCT_A_NBR' : 'PS9_GL_ACCT_A_NBR'}
    ps9_department_mapping = {'GL_DEPT_A' : 'PS9_GL_DEPT_A_CD'}
    ps9_customer_mapping = {'GL_CUST_A' : 'PS9_GL_CUST_A_NBR'}
    df_fin = df_target_fin.copy()

    print("Merging dfs!")
    df_fin = merged_df(df_fin,df_master_fin,key_col_master,ps9_master_mapping,'LOOKUP_CODE_MASTER')
    print("Master df merged!",df_fin.shape)
    df_fin = merged_df(df_fin,df_department_fin,key_col_department,ps9_department_mapping,'LOOKUP_CODE_DEPT')
    print("Department df merged!",df_fin.shape)
    df_fin = merged_df(df_fin,df_account_fin,key_col_account,ps9_account_mapping,'LOOKUP_CODE_ACCOUNT')
    print("Account df merged!",df_fin.shape)
    df_fin = merged_df(df_fin,df_customer_fin,key_col_customer,ps9_customer_mapping,'LOOKUP_CODE_CUST')
    print("Customer df merged!",df_fin.shape)
    columns_to_replace = ['PS9_GL_ACCT_A_NBR', 'PS9_GL_CUST_A_NBR', 'PS9_GL_DEPT_A_CD', 'PS9_GL_LEG_ENTY_A_CD', 'PS9_GL_LOC_A_NBR', 'PS9_GL_PRDCT_A_CD', 'PS9_GL_SEG_A_CD']

    merge_time = datetime.now()
    print ('Time taken in merging dfs: ',int((merge_time-explode_time).total_seconds())/60,' mins')
    
    df_fin[columns_to_replace] = df_fin[columns_to_replace].replace({'nan': 'DDD', '0': 'DDD', None: 'DDD', 'None': 'DDD', np.nan: 'DDD'}).infer_objects(copy=False)
    master_count = len(df_fin[(df_fin['PS9_GL_LEG_ENTY_A_CD'] == 'DDD') & (df_fin['PS9_GL_LOC_A_NBR'] == 'DDD') & (df_fin['PS9_GL_PRDCT_A_CD'] == 'DDD') & (df_fin['PS9_GL_SEG_A_CD'] == 'DDD')])
    account_count = len(df_fin[(df_fin['PS9_GL_ACCT_A_NBR'] == 'DDD')])
    department_count = len(df_fin[(df_fin['PS9_GL_DEPT_A_CD'] == 'DDD')])
    department_count_unmatched = len(df_fin[(df_fin['PS9_GL_DEPT_A_CD'] == 'DDD') & (df_fin['DATA_TYP_CD'] == 'INTC')])
    customer_count = len(df_fin[(df_fin['PS9_GL_CUST_A_NBR'] == 'DDD')])
    df_fin = df_fin.replace(['nan',None,'None',np.nan], '').infer_objects(copy=False)
    df_fin = df_fin.astype(str)
    fts_final_dataset = 'COSMOS_DETAIL_TAGGED_'+str(datetime.today().strftime('%Y%m%d_%H%M%S'))+'.xlsx'
    df_fin.to_excel('tagged/'+fts_final_dataset, index=False)
    print("Final dataset downloaded!")

    mail_body = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tagged Summary</title>
        <style>
            table {{
                width: 80%;
                border-collapse: collapse;
                font-size: 14px;
            }}
            table, th, td {{
                border: 1px solid black;
            }}
            th, td {{
                padding: 10px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            p {{
                font-size: 14px;
                margin: 0;
            }}
            .small-table {{
                width: 50%;
                font-size: 12px;
                margin-top: 20px;
            }}
            .small-table th, .small-table td {{
                padding: 5px;
            }}
        </style>
    </head>
    <body>
        <table style="border: none; margin-bottom: 20px; border-spacing: 0; border-collapse: collapse;" cellpadding="0" cellspacing="0">
            <tr>
                <td style="border: none; vertical-align: middle; padding: 0; font-size: 0;">
                    <img src="cid:UHC.png" alt="Logo" width="35" height="50" style="vertical-align: middle;">
                </td>
                <td style="border: none; vertical-align: middle; padding: 0; margin-left: 0;">
                    <span style="font-size: 20px; font-weight: bold; margin-left: -5px; display: inline-block;">Tagged Summary</span>
                </td>
            </tr>
        </table>
        <table>
            <tr>
                <th>Lookup info</th>
                <th>Matched</th>
                <th>Not Matched</th>
            </tr>
            <tr>
                <td>Master Lookup</td>
                <td>{len(df_target)-master_count}</td>
                <td>{master_count}</td>
            </tr>
            <tr>
                <td>Account Lookup</td>
                <td>{len(df_target)-account_count}</td>
                <td>{account_count}</td>
            </tr>
            <tr>
                <td>Department Lookup</td>
                <td>{len(df_target)-department_count}</td>
                <td>{department_count_unmatched}</td>
            </tr>
            <tr>
                <td>Customer Lookup</td>
                <td>{len(df_target)-customer_count}</td>
                <td>{customer_count}</td>
            </tr>
        </table>

        <p>‘Printed DDD’ in case if value is not matched with the look up file.</p>
        <p>Rules in Source dataset: {len(df_target)} </p> 
        <p>Rules in Master dataset: {len(df_master)}</p>
        <p>Rules in Account dataset: {len(df_account)}</p>
        <p>Rules in Customer dataset: {len(df_customer)}</p>
        <p>Rules in Department dataset: {len(df_department)}</p>
        <p>The complete results are attached as an Excel file named {fts_final_dataset}.</p>
        <p>Thank you</p>
    </body>
    </html>
    '''

    SendMail(email,'FTS GL Tagging Report', mail_body, ['tagged/'+fts_final_dataset])
    end_time = datetime.now()
    print('End time:',end_time)
    print ('Time taken E2E: ',int((end_time-start_time).total_seconds())/60,' mins')

if __name__ == "__main__":
    main(df_target,df_master,df_account,df_customer,df_department,df_map,email)
