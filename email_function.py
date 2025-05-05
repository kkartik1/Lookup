import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_excel_processing_email(results_df, recipient_email, subject="Excel Processing Results"):
    """
    Send an HTML email with Excel processing results
    
    Parameters:
    -----------
    results_df : pandas.DataFrame
        DataFrame containing processing results with columns:
        Filename, Tab, #Rules, #Matches, #Mismatches
    recipient_email : str
        Email address of the recipient
    subject : str, optional
        Subject line for the email (default: "Excel Processing Results")
        
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
        </div>
        
        <div class="footer">
          <p>This is an automated email from the Excel Processing Tool.</p>
          <p>Please do not reply to this email.</p>
        </div>
    </body>
    </html>
    """
    
    # Attach HTML parts to message
    msg.attach(MIMEText(html, 'html'))
    
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

# Send email with results
send_excel_processing_email(
    results_df=df,
    recipient_email="user@example.com",
    subject="Excel Processing Results - Job #12345"
)
"""
