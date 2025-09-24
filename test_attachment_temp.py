#!/usr/bin/env python3
import pyodbc
import subprocess
import sys

def test_pdf_attachment_with_temp_reset():
    """Temporarily reset emailed flag to test PDF attachment, then restore."""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        event_id = 'ECBEE0BE-9665-42CA-8804-AD61B0548671'
        case_id = 107756
        
        print("🧪 Testing PDF attachment with temporary flag reset")
        print("=" * 50)
        
        # 1. Store current emailed status
        cursor.execute("SELECT emailed FROM docketwatch.dbo.case_events WHERE id = ?", (event_id,))
        original_status = cursor.fetchone()
        
        if not original_status:
            print("❌ Event not found")
            return False
        
        original_emailed = original_status[0]
        print(f"📋 Current emailed status: {original_emailed}")
        
        # 2. Temporarily set emailed = 0
        cursor.execute("UPDATE docketwatch.dbo.case_events SET emailed = 0 WHERE id = ?", (event_id,))
        conn.commit()
        print("✅ Temporarily set emailed = 0")
        
        # 3. Run the alert script
        print(f"🚀 Running alert script for case {case_id}...")
        try:
            result = subprocess.run([
                sys.executable, 
                "docketwatch_case_events_alert_plus2.py", 
                str(case_id)
            ], capture_output=True, text=True, cwd="u:/docketwatch/python")
            
            print(f"Script return code: {result.returncode}")
            if result.stdout:
                print("STDOUT:", result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
                
        except Exception as e:
            print(f"❌ Error running script: {e}")
        
        # 4. Restore original emailed status
        cursor.execute("UPDATE docketwatch.dbo.case_events SET emailed = ? WHERE id = ?", (original_emailed, event_id))
        conn.commit()
        print(f"✅ Restored original emailed status: {original_emailed}")
        
        cursor.close()
        conn.close()
        
        print("✅ Test completed")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_pdf_attachment_with_temp_reset()