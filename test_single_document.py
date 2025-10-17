"""
Quick test script to process a single document and create an article.
Usage: python test_single_document.py <doc_uid>
"""
import sys
import pyodbc
from summarize_document_event import process_single_pdf

def test_document(doc_uid):
    """Test processing a single document and verify article creation."""
    
    print("=" * 80)
    print(f"TESTING DOCUMENT: {doc_uid}")
    print("=" * 80)
    print()
    
    # Get document info
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            d.doc_uid,
            d.pdf_title,
            d.fk_case,
            d.fk_case_event,
            c.case_name,
            c.case_number
        FROM dbo.documents d
        LEFT JOIN dbo.cases c ON c.id = d.fk_case
        WHERE d.doc_uid = ?
    """, (doc_uid,))
    
    row = cursor.fetchone()
    if not row:
        print(f"❌ Document {doc_uid} not found!")
        return
    
    print(f"Document Title: {row.pdf_title}")
    print(f"Case: {row.case_name} ({row.case_number})")
    print(f"Case ID: {row.fk_case}")
    print(f"Event ID: {row.fk_case_event}")
    print()
    
    case_id = row.fk_case
    event_id = row.fk_case_event
    
    # Check for existing articles today
    print("Checking for existing articles today...")
    cursor.execute("""
        SELECT id, version, story_headline, articleStatus
        FROM dbo.articles
        WHERE fk_case = ? 
        AND article_date = CAST(GETDATE() AS DATE)
        AND articleStatus = 'Pending'
    """, (case_id,))
    
    existing = cursor.fetchone()
    if existing:
        print(f"✓ Found existing Pending article (version {existing.version})")
        print(f"  Current headline: {existing.story_headline}")
        print(f"  Will update this article (increment version)")
    else:
        print("✓ No existing Pending article found")
        print("  Will create new article")
    print()
    
    cursor.close()
    conn.close()
    
    # Process the document
    print("-" * 80)
    print("PROCESSING DOCUMENT...")
    print("-" * 80)
    print()
    
    try:
        process_single_pdf(doc_uid)
        print()
        print("✓ Document processed successfully!")
        print()
    except Exception as e:
        print(f"❌ Error processing document: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check results
    print("-" * 80)
    print("VERIFYING RESULTS...")
    print("-" * 80)
    print()
    
    conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
    cursor = conn.cursor()
    
    # Check documents table (legacy)
    print("1. Documents Table (legacy):")
    cursor.execute("""
        SELECT 
            story_headline,
            story_sub_head,
            LEFT(story_body, 100) as story_preview,
            ai_processed_at
        FROM dbo.documents
        WHERE doc_uid = ?
    """, (doc_uid,))
    
    doc_row = cursor.fetchone()
    if doc_row and doc_row.story_headline:
        print(f"   ✓ Headline: {doc_row.story_headline}")
        print(f"   ✓ Subhead: {doc_row.story_sub_head}")
        print(f"   ✓ Body preview: {doc_row.story_preview}...")
        print(f"   ✓ Processed: {doc_row.ai_processed_at}")
    else:
        print("   ⚠️ No story fields in documents table")
    print()
    
    # Check articles table (new)
    print("2. Articles Table (new - Phase 4):")
    cursor.execute("""
        SELECT 
            id,
            version,
            story_headline,
            story_sub_head,
            LEFT(story_body, 100) as story_preview,
            articleStatus,
            created_at,
            updated_at
        FROM dbo.articles
        WHERE fk_case = ? 
        AND article_date = CAST(GETDATE() AS DATE)
        ORDER BY updated_at DESC
    """, (case_id,))
    
    article_row = cursor.fetchone()
    if article_row:
        print(f"   ✓ Article ID: {article_row.id}")
        print(f"   ✓ Version: {article_row.version}")
        print(f"   ✓ Status: {article_row.articleStatus}")
        print(f"   ✓ Headline: {article_row.story_headline}")
        print(f"   ✓ Subhead: {article_row.story_sub_head}")
        print(f"   ✓ Body preview: {article_row.story_preview}...")
        print(f"   ✓ Created: {article_row.created_at}")
        print(f"   ✓ Updated: {article_row.updated_at}")
    else:
        print("   ❌ No article found! Article creation may have failed.")
    print()
    
    # Check case_events linking
    if event_id:
        print("3. Case Event Linking:")
        cursor.execute("""
            SELECT fk_article
            FROM dbo.case_events
            WHERE id = ?
        """, (event_id,))
        
        event_row = cursor.fetchone()
        if event_row and event_row.fk_article:
            print(f"   ✓ Case event linked to article: {event_row.fk_article}")
        else:
            print("   ⚠️ Case event not linked to article (fk_article is NULL)")
        print()
    
    cursor.close()
    conn.close()
    
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_single_document.py <doc_uid>")
        print()
        print("Available documents:")
        
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 5 doc_uid, pdf_title 
            FROM dbo.documents 
            WHERE summary_ai IS NULL 
            ORDER BY date_downloaded DESC
        """)
        for i, row in enumerate(cursor.fetchall(), 1):
            print(f"{i}. {row.doc_uid} - {row.pdf_title}")
        
        cursor.close()
        conn.close()
        sys.exit(1)
    
    doc_uid = sys.argv[1]
    test_document(doc_uid)
