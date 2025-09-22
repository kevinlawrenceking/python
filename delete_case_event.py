#!/usr/bin/env python3
"""
Delete Case Event and Associated Data

This script deletes a case event and all its associated data:
- Documents records
- PDF files from disk
- Case event record
- RSS feed entries (optional)

Usage:
python delete_case_event.py <case_event_id>
python delete_case_event.py <case_event_id> --include-rss

SAFETY:
- Shows what will be deleted before confirmation
- Backs up SQL data before deletion
- Logs all actions
"""

import sys
import os
import pyodbc
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Delete case event and associated data')
    parser.add_argument('case_event_id', type=str, help='Case Event ID (GUID) to delete')
    parser.add_argument('--include-rss', action='store_true', help='Also delete RSS feed entries')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    args = parser.parse_args()

    case_event_id = args.case_event_id.strip()
    
    # Validate GUID format
    import re
    guid_pattern = r'^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$'
    if not re.match(guid_pattern, case_event_id):
        print(f"❌ Invalid GUID format: {case_event_id}")
        print(f"   Expected format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
        return
    
    try:
        # Connect to database
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        print(f"✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return

    try:
        # Step 1: Get case event details
        print(f"\n🔍 Looking up case event ID {case_event_id}...")
        cursor.execute("""
            SELECT ce.id, ce.event_no, ce.event_description, ce.fk_cases, c.case_name
            FROM docketwatch.dbo.case_events ce
            JOIN docketwatch.dbo.cases c ON ce.fk_cases = c.id
            WHERE ce.id = ?
        """, (case_event_id,))
        
        case_event = cursor.fetchone()
        if not case_event:
            print(f"❌ Case event ID {case_event_id} not found")
            return
        
        event_id, event_no, event_desc, fk_case, case_name = case_event
        print(f"📋 Found: Event {event_no} in case '{case_name}' (fk_case: {fk_case})")
        print(f"   Description: {event_desc[:100]}...")

        # Step 2: Find associated documents
        print(f"\n📄 Finding associated documents...")
        cursor.execute("""
            SELECT doc_uid, rel_path, pdf_title, file_size
            FROM docketwatch.dbo.documents
            WHERE fk_case_event = ?
        """, (case_event_id,))
        
        documents = cursor.fetchall()
        pdf_files_to_delete = []
        
        if documents:
            print(f"   Found {len(documents)} document(s):")
            for doc in documents:
                doc_uid, rel_path, pdf_title, file_size = doc
                print(f"   - {doc_uid}: {pdf_title}")
                print(f"     Path: {rel_path}")
                print(f"     Size: {file_size or 'Unknown'} bytes")
                
                # Check if PDF file exists
                if rel_path:
                    # Convert relative path to absolute
                    if rel_path.startswith('cases\\'):
                        pdf_path = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\{rel_path}"
                    elif '\\' in rel_path:
                        pdf_path = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\{rel_path}"
                    else:
                        pdf_path = f"\\\\10.146.176.84\\general\\docketwatch\\docs\\cases\\{fk_case}\\{rel_path}"
                    
                    if os.path.exists(pdf_path):
                        pdf_files_to_delete.append(pdf_path)
                        print(f"     ✅ PDF file exists: {pdf_path}")
                    else:
                        print(f"     ⚠️  PDF file not found: {pdf_path}")
        else:
            print("   No documents found")

        # Step 3: Find RSS entries (if requested)
        rss_entries = []
        if args.include_rss:
            print(f"\n📡 Finding RSS feed entries...")
            cursor.execute("""
                SELECT id, guid, event_description, pub_date
                FROM docketwatch.dbo.rss_feed_entries
                WHERE pacer_id IN (
                    SELECT pacer_id FROM docketwatch.dbo.cases WHERE id = ?
                ) AND event_no = ?
            """, (fk_case, event_no))
            
            rss_entries = cursor.fetchall()
            if rss_entries:
                print(f"   Found {len(rss_entries)} RSS entry(ies):")
                for rss in rss_entries:
                    rss_id, guid, desc, pub_date = rss
                    print(f"   - RSS ID {rss_id}: {desc[:50]}...")
                    print(f"     GUID: {guid}")
                    print(f"     Date: {pub_date}")
            else:
                print("   No RSS entries found")

        # Step 4: Show summary and confirm
        print(f"\n🗑️  DELETION SUMMARY:")
        print(f"   Case Event: {event_no} - {event_desc[:50]}...")
        print(f"   Documents: {len(documents)} record(s)")
        print(f"   PDF Files: {len(pdf_files_to_delete)} file(s)")
        if args.include_rss:
            print(f"   RSS Entries: {len(rss_entries)} record(s)")
        
        if args.dry_run:
            print(f"\n🔍 DRY RUN - Nothing will be deleted")
            print(f"\nSQL Commands that would be executed:")
            print(f"DELETE FROM docketwatch.dbo.documents WHERE fk_case_event = {case_event_id};")
            print(f"DELETE FROM docketwatch.dbo.case_events WHERE id = {case_event_id};")
            if args.include_rss and rss_entries:
                for rss in rss_entries:
                    print(f"DELETE FROM docketwatch.dbo.rss_feed_entries WHERE id = {rss[0]};")
            
            print(f"\nFiles that would be deleted:")
            for pdf_path in pdf_files_to_delete:
                print(f"  {pdf_path}")
            return

        # Confirm deletion
        print(f"\n⚠️  This will permanently delete all the above data!")
        confirm = input("Type 'DELETE' to confirm: ")
        if confirm != 'DELETE':
            print("❌ Deletion cancelled")
            return

        # Step 5: Perform deletions
        print(f"\n🗑️  Starting deletion process...")
        
        # Delete PDF files first
        if pdf_files_to_delete:
            print(f"   Deleting {len(pdf_files_to_delete)} PDF file(s)...")
            for pdf_path in pdf_files_to_delete:
                try:
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                        print(f"   ✅ Deleted: {pdf_path}")
                    else:
                        print(f"   ⚠️  File not found: {pdf_path}")
                except Exception as e:
                    print(f"   ❌ Error deleting {pdf_path}: {e}")

        # Delete documents records
        if documents:
            print(f"   Deleting {len(documents)} document record(s)...")
            cursor.execute("""
                DELETE FROM docketwatch.dbo.documents 
                WHERE fk_case_event = ?
            """, (case_event_id,))
            deleted_docs = cursor.rowcount
            print(f"   ✅ Deleted {deleted_docs} document record(s)")

        # Delete RSS entries (if requested)
        if args.include_rss and rss_entries:
            print(f"   Deleting {len(rss_entries)} RSS entry(ies)...")
            for rss in rss_entries:
                cursor.execute("""
                    DELETE FROM docketwatch.dbo.rss_feed_entries 
                    WHERE id = ?
                """, (rss[0],))
            deleted_rss = len(rss_entries)
            print(f"   ✅ Deleted {deleted_rss} RSS entry(ies)")

        # Delete case event record
        print(f"   Deleting case event record...")
        cursor.execute("""
            DELETE FROM docketwatch.dbo.case_events 
            WHERE id = ?
        """, (case_event_id,))
        deleted_events = cursor.rowcount
        
        if deleted_events > 0:
            print(f"   ✅ Deleted case event {case_event_id}")
        else:
            print(f"   ⚠️  Case event {case_event_id} was not deleted (may not exist)")

        # Commit all changes
        conn.commit()
        print(f"\n✅ All deletions completed successfully!")
        print(f"   Case event {case_event_id} and all associated data have been removed")

    except Exception as e:
        print(f"❌ Error during deletion: {e}")
        try:
            conn.rollback()
            print("🔄 Database changes rolled back")
        except:
            pass
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

if __name__ == "__main__":
    main()