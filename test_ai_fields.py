#!/usr/bin/env python3
import pyodbc

def test_ai_summary_fields():
    """Test if the new AI summary fields exist in the database."""
    
    try:
        # Connect to database
        conn = pyodbc.connect('DSN=Docketwatch')
        cursor = conn.cursor()
        
        print("🔍 Testing AI summary fields in documents table")
        print("=" * 50)
        
        # Check if the new columns exist
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'documents' 
            AND COLUMN_NAME IN ('event_summary', 'newsworthiness', 'newsworthiness_reason', 
                                'story_headline', 'story_sub_head', 'story_body', 'whats_next')
            ORDER BY COLUMN_NAME
        """)
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        expected_columns = [
            'event_summary', 'newsworthiness', 'newsworthiness_reason', 
            'story_headline', 'story_sub_head', 'story_body', 'whats_next'
        ]
        
        print("📋 Column existence check:")
        for col in expected_columns:
            if col in existing_columns:
                print(f"   ✅ {col}")
            else:
                print(f"   ❌ {col} - NOT FOUND")
        
        print(f"\n📊 Found {len(existing_columns)} of {len(expected_columns)} expected columns")
        
        # Test query with available columns
        if existing_columns:
            print("\n🧪 Testing query with available columns...")
            
            # Build dynamic query with only existing columns
            select_fields = ["d.doc_id", "d.pdf_title"]
            for col in existing_columns:
                select_fields.append(f"d.{col}")
            
            query = f"""
                SELECT TOP 1 {', '.join(select_fields)}
                FROM docketwatch.dbo.documents d
                WHERE d.doc_id IS NOT NULL
                ORDER BY d.doc_uid DESC
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            if result:
                print("✅ Query executed successfully")
                print(f"   Sample doc_id: {result[0]}")
                print(f"   Sample pdf_title: {result[1]}")
                
                # Show sample values for AI fields
                for i, col in enumerate(existing_columns):
                    value = result[i + 2]  # Skip doc_id and pdf_title
                    if value:
                        display_value = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                        print(f"   {col}: {display_value}")
                    else:
                        print(f"   {col}: (null)")
            else:
                print("❌ No documents found")
        
        cursor.close()
        conn.close()
        
        return len(existing_columns) == len(expected_columns)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ai_summary_fields()
    if success:
        print("\n✅ All AI summary fields are available!")
    else:
        print("\n⚠️  Some AI summary fields may be missing from the database schema.")