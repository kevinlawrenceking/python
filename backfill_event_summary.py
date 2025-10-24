"""
Backfill event_summary and structured fields for documents processed after Oct 17, 2025 10:35am
when the parser was broken due to BeautifulSoup prettify() whitespace issues.

This script:
1. Finds documents with summary_ai_html but empty event_summary since Oct 17 10:35
2. Re-parses the existing HTML using the fixed parser
3. Updates documents table with structured fields
4. Inserts key details into document_key_details table
5. Creates articles for newsworthy stories

Usage:
    python backfill_event_summary.py [--limit N] [--all]
"""

import sys
import argparse
import pyodbc
from datetime import datetime
from summary_parser import parse_ai_summary, save_structured_summary
from scraper_base import log_message, setup_logging
import traceback


def get_cursor():
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
    conn.setencoding(encoding="utf-8")
    return conn, conn.cursor()


def backfill_documents(limit=None, show_all=False):
    """
    Backfill event_summary and structured fields for documents.
    
    Args:
        limit: Maximum number of documents to process (None for all)
        show_all: If True, process all documents regardless of date
    """
    setup_logging("u:/docketwatch/python/logs/backfill_event_summary.log")
    conn, cur = get_cursor()
    
    try:
        # Build query based on parameters
        if show_all:
            query = """
                SELECT doc_uid, summary_ai_html
                FROM docketwatch.dbo.documents
                WHERE ocr_text IS NOT NULL
                  AND event_summary IS NULL
                  AND pdf_type = 'Docket'
                  AND summary_ai_html IS NOT NULL
                ORDER BY date_downloaded DESC
            """
        else:
            query = """
                SELECT doc_uid, summary_ai_html
                FROM docketwatch.dbo.documents
                WHERE ocr_text IS NOT NULL
                  AND event_summary IS NULL
                  AND pdf_type = 'Docket'
                  AND summary_ai_html IS NOT NULL
                  AND ai_processed_at >= '2025-10-17 10:35:00'
                ORDER BY date_downloaded DESC
            """
        
        if limit:
            query = query.replace("SELECT ", f"SELECT TOP {limit} ")
        
        log_message(cur, None, "INFO", f"Starting backfill - limit={limit}, show_all={show_all}")
        cur.execute(query)
        rows = cur.fetchall()
        
        total = len(rows)
        log_message(cur, None, "INFO", f"Found {total} documents to backfill")
        print(f"Found {total} documents to backfill")
        
        success_count = 0
        error_count = 0
        
        for idx, row in enumerate(rows, 1):
            doc_uid = str(row.doc_uid)
            summary_html = row.summary_ai_html
            
            try:
                # Parse the existing HTML
                parsed_summary = parse_ai_summary(summary_html)
                
                # Check if we got any data
                if not parsed_summary.get('event_summary'):
                    log_message(cur, None, "WARNING", f"[{idx}/{total}] {doc_uid}: No event_summary extracted")
                    error_count += 1
                    continue
                
                # Save structured summary (this updates documents table and inserts key details)
                save_structured_summary(cur, doc_uid, parsed_summary, enable_articles=True)
                conn.commit()
                
                success_count += 1
                event_summary_preview = parsed_summary['event_summary'][:60] + "..." if len(parsed_summary['event_summary']) > 60 else parsed_summary['event_summary']
                log_message(cur, None, "INFO", f"[{idx}/{total}] {doc_uid}: SUCCESS - {event_summary_preview}")
                print(f"[{idx}/{total}] {doc_uid}: ✓ {event_summary_preview}")
                
            except Exception as e:
                error_count += 1
                tb = traceback.format_exc()
                log_message(cur, None, "ERROR", f"[{idx}/{total}] {doc_uid}: FAILED - {e}\n{tb}")
                print(f"[{idx}/{total}] {doc_uid}: ✗ {e}")
                conn.rollback()
                continue
        
        log_message(cur, None, "INFO", f"Backfill complete: {success_count} success, {error_count} errors out of {total} total")
        print(f"\nBackfill complete:")
        print(f"  Success: {success_count}")
        print(f"  Errors:  {error_count}")
        print(f"  Total:   {total}")
        
    except Exception as e:
        tb = traceback.format_exc()
        log_message(cur, None, "ERROR", f"Fatal error in backfill: {e}\n{tb}")
        print(f"Fatal error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill event_summary and structured fields for documents"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of documents to process"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all documents with empty event_summary (not just since Oct 17)"
    )
    
    args = parser.parse_args()
    
    if not args.limit and not args.all:
        # Default: process documents since Oct 17 10:35am
        print("Backfilling documents since Oct 17, 2025 10:35am")
        print("Use --limit N to process only N documents")
        print("Use --all to process all documents regardless of date")
        print()
    
    backfill_documents(limit=args.limit, show_all=args.all)


if __name__ == "__main__":
    main()
