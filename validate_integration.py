"""
Validation script to check the DocketWatch integration results.
This script verifies that unfiled records have associated PDFs and document records.
"""

import pyodbc
import os
from datetime import datetime, timedelta

def validate_integration(days_back=1):
    """
    Validate that recent unfiled records have associated PDFs and document records.
    """
    
    try:
        # Connect to database
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        
        # Get cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        print(f"Validating integration for records created since: {cutoff_date}")
        print("=" * 60)
        
        # Query for recent unfiled cases
        cursor.execute("""
            SELECT 
                c.id,
                c.courtCaseNumber,
                c.case_name,
                c.created_at,
                COUNT(d.id) as document_count
            FROM docketwatch.dbo.cases c
            LEFT JOIN docketwatch.dbo.case_events ce ON c.id = ce.fk_cases
            LEFT JOIN docketwatch.dbo.documents d ON ce.id = d.fk_case_events
            WHERE c.case_number = 'Unfiled'
              AND c.created_at >= ?
              AND c.status <> 'Removed'
            GROUP BY c.id, c.courtCaseNumber, c.case_name, c.created_at
            ORDER BY c.created_at DESC
        """, (cutoff_date,))
        
        cases = cursor.fetchall()
        
        if not cases:
            print("✓ No recent unfiled cases found.")
            return True
        
        print(f"Found {len(cases)} recent unfiled cases:")
        print()
        
        all_valid = True
        pdf_missing_count = 0
        doc_missing_count = 0
        
        for case in cases:
            case_id, court_case_number, case_name, created_at, document_count = case
            
            # Check if PDF exists
            expected_pdf_path = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{case_id}\\E{court_case_number}.pdf"
            pdf_exists = os.path.exists(expected_pdf_path)
            
            # Status indicators
            pdf_status = "✓" if pdf_exists else "✗"
            doc_status = "✓" if document_count > 0 else "✗"
            
            print(f"Case {case_id}: {case_name[:50]}...")
            print(f"  Court #: {court_case_number}")
            print(f"  Created: {created_at}")
            print(f"  PDF: {pdf_status} {'EXISTS' if pdf_exists else 'MISSING'}")
            print(f"  Docs: {doc_status} {document_count} record(s)")
            
            if not pdf_exists:
                pdf_missing_count += 1
                all_valid = False
                print(f"  ⚠ Expected PDF not found: {expected_pdf_path}")
            
            if document_count == 0:
                doc_missing_count += 1
                all_valid = False
                print(f"  ⚠ No document records found")
            
            print()
        
        # Summary
        print("=" * 60)
        print("VALIDATION SUMMARY:")
        print(f"Total cases checked: {len(cases)}")
        print(f"Cases with PDFs: {len(cases) - pdf_missing_count}")
        print(f"Cases with document records: {len(cases) - doc_missing_count}")
        
        if all_valid:
            print("✓ ALL VALIDATIONS PASSED")
            print("  Integration is working correctly!")
        else:
            print("✗ VALIDATION ISSUES FOUND")
            if pdf_missing_count > 0:
                print(f"  {pdf_missing_count} cases missing PDFs")
            if doc_missing_count > 0:
                print(f"  {doc_missing_count} cases missing document records")
        
        cursor.close()
        conn.close()
        
        return all_valid
        
    except Exception as e:
        print(f"✗ Validation failed: {e}")
        return False

def check_orphaned_cases():
    """
    Check for cases that exist but don't have PDFs (potential orphans from failed integrations).
    """
    
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        
        print("Checking for orphaned cases (cases without PDFs)...")
        
        # Get unfiled cases without document records
        cursor.execute("""
            SELECT c.id, c.courtCaseNumber, c.case_name, c.created_at
            FROM docketwatch.dbo.cases c
            WHERE c.case_number = 'Unfiled'
              AND c.status <> 'Removed'
              AND c.id NOT IN (
                  SELECT DISTINCT ce.fk_cases 
                  FROM docketwatch.dbo.case_events ce
                  INNER JOIN docketwatch.dbo.documents d ON ce.id = d.fk_case_events
                  WHERE ce.fk_cases IS NOT NULL
              )
            ORDER BY c.created_at DESC
        """)
        
        orphans = cursor.fetchall()
        
        if not orphans:
            print("✓ No orphaned cases found.")
        else:
            print(f"⚠ Found {len(orphans)} potentially orphaned cases:")
            for case in orphans[:10]:  # Show first 10
                case_id, court_case_number, case_name, created_at = case
                print(f"  Case {case_id}: {case_name[:40]}... (Created: {created_at})")
            
            if len(orphans) > 10:
                print(f"  ... and {len(orphans) - 10} more")
        
        cursor.close()
        conn.close()
        
        return len(orphans) == 0
        
    except Exception as e:
        print(f"✗ Orphan check failed: {e}")
        return False

if __name__ == "__main__":
    print("DocketWatch Integration Validation")
    print("=" * 40)
    
    # Validate recent integration results
    integration_valid = validate_integration(days_back=2)
    
    print()
    
    # Check for orphaned cases
    no_orphans = check_orphaned_cases()
    
    print()
    print("=" * 40)
    if integration_valid and no_orphans:
        print("✓ OVERALL VALIDATION PASSED")
        print("Integration is working correctly!")
    else:
        print("✗ VALIDATION ISSUES DETECTED")
        print("Please review the issues above.")
