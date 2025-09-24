#!/usr/bin/env python3
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def test_email_with_pdf():
    """Test sending an email with PDF attachment."""
    
    # Email settings
    FROM_EMAIL = "it@tmz.com"
    TO_EMAIL = "Kevin.King@tmz.com"
    SMTP_SERVER = "mx0a-00195501.pphosted.com"
    SMTP_PORT = 25
    
    # PDF file to attach
    pdf_path = r"\\10.146.176.84\general\docketwatch\docs\cases\107756\E127138256058.pdf"
    
    print(f"Testing PDF attachment: {pdf_path}")
    
    # Check if file exists
    if not os.path.exists(pdf_path):
        print(f"❌ PDF file does not exist: {pdf_path}")
        return False
    
    file_size = os.path.getsize(pdf_path)
    print(f"✅ PDF file exists, size: {file_size:,} bytes")
    
    try:
        # Create message
        msg = MIMEMultipart("mixed")
        msg["Subject"] = "Test PDF Attachment - Case 107756"
        msg["From"] = FROM_EMAIL
        msg["To"] = TO_EMAIL
        
        # Add HTML body
        body = """
        <html><body>
            <h2>Test PDF Attachment</h2>
            <p>This is a test email to verify PDF attachment functionality.</p>
            <p>The PDF should be attached to this email.</p>
        </body></html>
        """
        
        html_part = MIMEMultipart("alternative")
        html_part.attach(MIMEText(body, "html", "utf-8"))
        msg.attach(html_part)
        
        # Add PDF attachment
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
            print(f"✅ Read PDF content: {len(pdf_content):,} bytes")
            
            pdf_attachment = MIMEApplication(pdf_content, _subtype='pdf')
            pdf_attachment.add_header('Content-Disposition', 'attachment', filename='E127138256058.pdf')
            msg.attach(pdf_attachment)
        
        print("✅ PDF attachment added to email")
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            print(f"✅ Connected to SMTP server: {SMTP_SERVER}:{SMTP_PORT}")
            server.sendmail(FROM_EMAIL, [TO_EMAIL], msg.as_string())
            print("✅ Email sent successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_email_with_pdf()