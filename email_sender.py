import smtplib
import pandas as pd
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def send_excel_processing_email(results_df, recipient_email, subject="Excel Processing Results", attach_excel=True, excel_filename="results.xlsx"):
    """
    Send an HTML email with Excel processing results and an optional Excel attachment
    
    Parameters:
    -----------
    results_df : pandas.DataFrame
        DataFrame containing processing results with columns:
        Filename, Tab, #Rules, #Matches, #Mismatches
    recipient_email : str
        Email address of the recipient
    subject : str, optional
        Subject line for the email (default: "Excel Processing Results")
    attach_excel : bool, optional
        Whether to attach the DataFrame as an Excel file (default: True)
    excel_filename : str, optional
        Name of the Excel file attachment (default: "results.xlsx")
        
    Returns:
    --------
    bool
        True if email was sent successfully, False otherwise
    """
    # Create message container
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = "excel_processor@example.com"  # Replace with actual sender email
    msg['To'] = recipient_email
    
    # Create HTML table from DataFrame
    html_table = results_df.to_html(index=False, classes='table table-striped')
    
    # Create the HTML email body
    html = f"""
    <html>
    <head>
        <style>
            .table {{
                border-collapse: collapse;
                width: 100%;
                font-family: Arial, sans-serif;
                margin-bottom: 20px;
            }}
            .table-striped tr:nth-child(even) {{
                background-color: #f2f2f2;
            }}
            .table th, .table td {{
                text-align: left;
                padding: 12px 8px;
                border: 1px solid #ddd;
            }}
            .table th {{
                background-color: #4472C4;
                color: white;
                font-weight: bold;
            }}
            .summary {{
                margin-top: 20px;
                margin-bottom: 20px;
                font-size: 14px;
            }}
            .header {{
                color: #333;
                font-family: Arial, sans-serif;
            }}
            .footer {{
                margin-top: 30px;
                font-size: 12px;
                color: #777;
                border-top: 1px solid #ddd;
                padding-top: 10px;
            }}
        </style>
    </head>
    <body>
        <h2 class="header">Excel Processing Results</h2>
        
        <div class="summary">
          <p>The Excel files have been processed. Below are the results:</p>
        </div>
        
        {html_table}
        
        <div class="summary">
          <p>Total Rules: {results_df['#Rules'].sum()}</p>
          <p>Total Matches: {results_df['#Matches'].sum()}</p>
          <p>Total Mismatches: {results_df['#Mismatches'].sum()}</p>
          <p>Match Rate: {(results_df['#Matches'].sum() / results_df['#Rules'].sum() * 100):.2f}%</p>
          {f"<p>The complete results are attached as an Excel file named '{excel_filename}'.</p>" if attach_excel else ""}
        </div>
        
        <div class="footer">
          <p>This is an automated email from the Excel Processing Tool.</p>
          <p>Please do not reply to this email.</p>
        </div>
    </body>
    </html>
    """
    
    # Attach HTML part to message
    msg.attach(MIMEText(html, 'html'))
    
    # Attach Excel file if requested
    if attach_excel:
        # Convert DataFrame to Excel bytes
        excel_buffer = io.BytesIO()
        results_df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        # Create attachment
        attachment = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        attachment.set_payload(excel_buffer.read())
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', f'attachment; filename="{excel_filename}"')
        
        # Add attachment to message
        msg.attach(attachment)
    
    try:
        # Configure SMTP server
        # Note: In a production environment, you would use your actual SMTP settings
        server = smtplib.SMTP('smtp.example.com', 587)
        server.starttls()
        server.login('username', 'password')  # Replace with actual credentials
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


# Example usage:
"""
import pandas as pd

# Create sample dataframe with results
data = [
    {
        "Filename": "MASTER COSGP PS LOOKUP",
        "Tab": "COSGP_LOC",
        "#Rules": 43055,
        "#Matches": 41025,
        "#Mismatches": 2030
    },
    {
        "Filename": "COSMOS9 CL PS LOOKUP",
        "Tab": "COSMOS_ CL_ACCOUNT_A",
        "#Rules": 1219,
        "#Matches": 1103,
        "#Mismatches": 116
    }
]

df = pd.DataFrame(data)

# Send email with results and Excel attachment
send_excel_processing_email(
    results_df=df,
    recipient_email="user@example.com",
    subject="Excel Processing Results - Job #12345",
    attach_excel=True,
    excel_filename="processing_results.xlsx"
)
"""