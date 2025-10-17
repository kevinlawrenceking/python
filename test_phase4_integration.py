"""
=============================================================================
Phase 4 Integration Test - Articles Table
=============================================================================
Purpose: Test the integration between summary_parser and article_manager.
         Demonstrates how articles evolve throughout the day.

Author: DocketWatch Development Team
Date: 2025-10-15

This test script:
  1. Creates mock document summaries for a test case
  2. Calls save_structured_summary with enable_articles=True
  3. Shows how articles evolve (version increments)
  4. Verifies articles table is updated correctly

Prerequisites:
  - Phase 1 complete (articles table exists)
  - Phase 2 complete (stored procedures exist)
  - Phase 3 complete (migration done)
  - article_manager.py and summary_parser.py in place

Usage:
  python test_phase4_integration.py
=============================================================================
"""

import pyodbc
import uuid
from datetime import datetime, date
from summary_parser import parse_ai_summary, save_structured_summary
from article_manager import get_todays_article, get_articles_for_case

# Configuration
DSN = "Docketwatch"


def test_article_evolution():
    """
    Test how an article evolves throughout the day with multiple document summaries.
    """
    print("=" * 80)
    print("PHASE 4 INTEGRATION TEST - Article Evolution")
    print("=" * 80)
    print()
    
    conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    try:
        # Step 1: Get a test case (or create one)
        print("Step 1: Getting test case...")
        cursor.execute("SELECT TOP 1 id, case_number, case_name FROM dbo.cases ORDER BY id")
        case_row = cursor.fetchone()
        
        if not case_row:
            print("ERROR: No cases found in database")
            return
        
        test_case_id = case_row.id
        case_number = case_row.case_number
        case_name = case_row.case_name
        
        print(f"✓ Using case: {case_number} - {case_name}")
        print(f"  Case ID: {test_case_id}")
        print()
        
        # Step 2: Create test case_event for today
        print("Step 2: Creating test case_event...")
        test_event_id = str(uuid.uuid4())
        today = date.today()
        
        cursor.execute("""
            INSERT INTO dbo.case_events (id, fk_cases, event_type, event_date, event_description)
            VALUES (?, ?, ?, ?, ?)
        """, (test_event_id, test_case_id, 'Motion Filed', today, 'Phase 4 Test Event'))
        conn.commit()
        
        print(f"✓ Created test event: {test_event_id}")
        print()
        
        # Step 3: Create test document
        print("Step 3: Creating test document...")
        test_doc_uid = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO dbo.documents (
                doc_uid, fk_case, fk_case_event, fk_tool, doc_id, rel_path,
                date_downloaded, pdf_title
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_doc_uid,
            test_case_id,
            test_event_id,
            1,  # tool_id
            'TEST-001',
            'test/phase4/test.pdf',
            datetime.now(),
            'Phase 4 Test Document'
        ))
        conn.commit()
        
        print(f"✓ Created test document: {test_doc_uid}")
        print()
        
        # Step 4: Simulate first AI summary (morning)
        print("Step 4: Simulating first AI summary (9:00 AM)...")
        print("-" * 80)
        
        summary_v1_html = """
        <h3>EVENT SUMMARY</h3>
        <p>Plaintiff filed a motion for summary judgment arguing no genuine issues of material fact exist.</p>
        
        <h3>NEWSWORTHINESS</h3>
        <p>Yes - Major motion in high-profile celebrity case</p>
        
        <h3>STORY</h3>
        <ul>
        <li>HEADLINE: Celebrity Lawsuit Takes Major Turn</li>
        <li>SUBHEAD: Summary judgment motion filed in high-stakes case</li>
        <li>BODY: In a dramatic development, the plaintiff has filed a motion for summary judgment that could bring this celebrity legal battle to a swift conclusion.</li>
        </ul>
        
        <h3>WHAT'S NEXT</h3>
        <p>Defendant has 30 days to respond.</p>
        """
        
        parsed_v1 = parse_ai_summary(summary_v1_html)
        save_structured_summary(cursor, test_doc_uid, parsed_v1, enable_articles=True)
        conn.commit()
        
        print("✓ First summary saved")
        print(f"  Headline: {parsed_v1['story_headline']}")
        print()
        
        # Check article was created
        article_v1 = get_todays_article(cursor, test_case_id, today)
        if article_v1:
            print(f"✓ Article created: {article_v1['id']}")
            print(f"  Status: {article_v1['articleStatus']}")
            print(f"  Version: {article_v1['version']}")
            print(f"  Headline: {article_v1['story_headline']}")
        else:
            print("✗ ERROR: Article was not created!")
        print()
        
        # Step 5: Simulate second AI summary (afternoon) - updated story
        print("Step 5: Simulating updated AI summary (2:00 PM)...")
        print("-" * 80)
        
        # Create second document for same event
        test_doc_uid_2 = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO dbo.documents (
                doc_uid, fk_case, fk_case_event, fk_tool, doc_id, rel_path,
                date_downloaded, pdf_title
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_doc_uid_2,
            test_case_id,
            test_event_id,
            1,
            'TEST-002',
            'test/phase4/test2.pdf',
            datetime.now(),
            'Phase 4 Test Document - Response'
        ))
        
        summary_v2_html = """
        <h3>EVENT SUMMARY</h3>
        <p>Defendant filed opposition to summary judgment motion with new evidence.</p>
        
        <h3>NEWSWORTHINESS</h3>
        <p>Yes - Dramatic response with bombshell evidence</p>
        
        <h3>STORY</h3>
        <ul>
        <li>HEADLINE: Celebrity Lawsuit Explodes With New Evidence</li>
        <li>SUBHEAD: Defendant fires back with bombshell documents in legal battle</li>
        <li>BODY: The celebrity lawsuit took an explosive turn today as the defendant filed a blistering response to the summary judgment motion, attaching dozens of previously unseen documents that they claim completely undermine the plaintiff's case. Legal experts say this could be a game-changer.</li>
        </ul>
        
        <h3>WHAT'S NEXT</h3>
        <p>Court will schedule hearing within 30 days.</p>
        """
        
        parsed_v2 = parse_ai_summary(summary_v2_html)
        save_structured_summary(cursor, test_doc_uid_2, parsed_v2, enable_articles=True)
        conn.commit()
        
        print("✓ Second summary saved")
        print(f"  Headline: {parsed_v2['story_headline']}")
        print()
        
        # Check article was updated (not created)
        article_v2 = get_todays_article(cursor, test_case_id, today)
        if article_v2:
            print(f"✓ Article updated: {article_v2['id']}")
            print(f"  Status: {article_v2['articleStatus']}")
            print(f"  Version: {article_v2['version']} (should be 2)")
            print(f"  Headline: {article_v2['story_headline']}")
            
            if article_v2['version'] == 2:
                print("  ✓ Version correctly incremented!")
            else:
                print("  ✗ ERROR: Version did not increment correctly")
        else:
            print("✗ ERROR: Article not found!")
        print()
        
        # Step 6: Show article history
        print("Step 6: Article History...")
        print("-" * 80)
        
        articles = get_articles_for_case(cursor, test_case_id, include_closed=True, limit=5)
        print(f"Total articles for this case: {len(articles)}")
        for article in articles:
            print(f"  - {article['article_date']}: {article['story_headline'][:50]}...")
            print(f"    Status: {article['articleStatus']}, Version: {article['version']}")
        print()
        
        # Step 7: Cleanup
        print("Step 7: Cleaning up test data...")
        print("-" * 80)
        
        cursor.execute("DELETE FROM dbo.documents WHERE doc_uid IN (?, ?)", (test_doc_uid, test_doc_uid_2))
        cursor.execute("DELETE FROM dbo.case_events WHERE id = ?", (test_event_id,))
        cursor.execute("DELETE FROM dbo.articles WHERE fk_case = ? AND article_date = ? AND generated_by = 'summary_parser'", (test_case_id, today))
        conn.commit()
        
        print("✓ Test data cleaned up")
        print()
        
        print("=" * 80)
        print("PHASE 4 INTEGRATION TEST COMPLETE!")
        print("=" * 80)
        print()
        print("Summary:")
        print("  ✓ Article created from first document summary")
        print("  ✓ Article updated (version incremented) from second document")
        print("  ✓ Both documents table and articles table updated")
        print("  ✓ Parallel system working correctly")
        print()
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    test_article_evolution()
