import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import io

def send_html_email(data_df, to_email, subject, from_email, attachment_df=None, attachment_name=None, smtp_server='smtp.example.com', smtp_port=587, username=None, password=None):
    """
    Send an HTML email with a body containing data from a DataFrame and an optional DataFrame attachment.
    
    Parameters:
    -----------
    data_df : pandas.DataFrame
        DataFrame containing the data to be displayed in the email body.
        Expected columns: 'Filename', 'Tab', '#Rules', '#Matches', '#Mismatches'
    to_email : str
        Recipient's email address
    subject : str
        Email subject
    from_email : str
        Sender's email address
    attachment_df : pandas.DataFrame, optional
        DataFrame to be attached to the email
    attachment_name : str, optional
        Name of the attachment file (e.g., 'data.csv')
    smtp_server : str
        SMTP server address
    smtp_port : int
        SMTP server port
    username : str, optional
        SMTP authentication username
    password : str, optional
        SMTP authentication password
    """
    # Create message container
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    
    # Create HTML version of the message
    html = """
    <html>
    <head>
        <style>
            table {
                border-collapse: collapse;
                width: 100%;
            }
            th, td {
                border: 1px solid #dddddd;
                text-align: left;
                padding: 8px;
            }
            th {
                background-color: #f2f2f2;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
        </style>
    </head>
    <body>
        <p>Please find the summary of rules processing below:</p>
        <table>
            <tr>
                <th>Filename</th>
                <th>Tab</th>
                <th>#Rules</th>
                <th>#Matches</th>
                <th>#Mismatches</th>
            </tr>
    """
    
    # Add rows from DataFrame
    for _, row in data_df.iterrows():
        html += f"""
            <tr>
                <td>{row['Filename']}</td>
                <td>{row['Tab']}</td>
                <td>{row['#Rules']}</td>
                <td>{row['#Matches']}</td>
                <td>{row['#Mismatches']}</td>
            </tr>
        """
    
    html += """
        </table>
        <p>For more details, please see the attached file.</p>
    </body>
    </html>
    """
    
    # Attach HTML part
    msg.attach(MIMEText(html, 'html'))
    
    # Attach DataFrame if provided
    if attachment_df is not None and attachment_name is not None:
        if attachment_name.endswith('.csv'):
            # Convert DataFrame to CSV
            csv_data = attachment_df.to_csv(index=False)
            attachment = MIMEApplication(csv_data, Name=attachment_name)
        elif attachment_name.endswith('.xlsx'):
            # Convert DataFrame to Excel
            excel_buffer = io.BytesIO()
            attachment_df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)
            attachment = MIMEApplication(excel_buffer.read(), Name=attachment_name)
        else:
            # Default to CSV if extension is not recognized
            csv_data = attachment_df.to_csv(index=False)
            attachment = MIMEApplication(csv_data, Name=f"{attachment_name}.csv")
        
        # Add header with attachment name
        attachment['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
        msg.attach(attachment)
    
    # Send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.ehlo()
        server.starttls()
        
        # Login if credentials are provided
        if username and password:
            server.login(username, password)
        
        server.sendmail(from_email, to_email, msg.as_string())
        server.close()
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False


# Example usage
if __name__ == "__main__":
    # Sample data for the email body
    data = {
        'Filename': ['MASTER COSGP PS LOOKUP', 'COSMOS9 CL PS LOOKUP'],
        'Tab': ['COSGPLOC', 'COSMOS CL_ACCOUNT_A'],
        '#Rules': [43055, 1219],
        '#Matches': [41025, 1103],
        '#Mismatches': [2030, 116]
    }
    
    email_data_df = pd.DataFrame(data)
    
    # Sample attachment data
    attachment_data = {
        'Filename': ['MASTER COSGP PS LOOKUP', 'COSMOS9 CL PS LOOKUP'],
        'Tab': ['COSGPLOC', 'COSMOS CL_ACCOUNT_A'],
        'Rule ID': ['R001', 'R002'],
        'Rule Description': ['Check account match', 'Validate customer ID'],
        'Status': ['Match', 'Mismatch'],
        'Details': ['Account numbers match', 'Customer ID not found']
    }
    
    attachment_df = pd.DataFrame(attachment_data)
    
    # Send the email
    send_html_email(
        data_df=email_data_df,
        to_email='recipient@example.com',
        subject='Rule Processing Summary Report',
        from_email='sender@example.com',
        attachment_df=attachment_df,
        attachment_name='rule_details.xlsx',
        smtp_server='smtp.example.com',
        smtp_port=587,
        username='your_username',
        password='your_password'
    )