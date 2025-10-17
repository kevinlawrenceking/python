# Articles Project Implementation Plan

## Overview
Move story fields from `dbo.documents` to new `dbo.articles` table to create one evolving daily article per case, rather than story fields scattered across multiple documents.

## Current State Analysis

### Documents Table Story Fields
Currently, these fields exist in `dbo.documents`:
- `story_headline` (NVARCHAR(MAX))
- `story_sub_head` (NVARCHAR(300))
- `story_body` (NVARCHAR(MAX))
- `event_summary` (NVARCHAR(MAX))
- `newsworthiness` (NVARCHAR(10))
- `newsworthiness_reason` (NVARCHAR(MAX))
- `whats_next` (NVARCHAR(1000))

### Key Python Scripts That Write Story Fields
1. **`summary_parser.py`** - Parses AI summaries and writes to documents table
2. **`docketwatch_case_events_alert_plus2.py`** - Reads story fields for email generation
3. **`scraper_base.py`** - Contains `generate_ai_summary_for_documents_older()` function

### Key Python Scripts That Read Story Fields
1. **`docketwatch_case_events_alert_plus2.py`** - Reads for email display
2. **`test_final_email_format.py`** - Test script for email formatting
3. **`generate_mock_email.py`** - Mock data generator

---

## Implementation Steps

### PHASE 1: Database Schema (Non-Breaking)
**Goal**: Create new tables/columns without affecting existing system

#### Step 1.1: Create Articles Table
```sql
-- File: u:\docketwatch\sql\01_create_articles_table.sql
-- Creates the new articles table with all required fields
-- Run this first
```

**SQL Content**: From articles_project.txt DDL section

**Verification**:
```sql
SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'articles'
SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'articles'
```

#### Step 1.2: Add fk_article to case_events
```sql
-- File: u:\docketwatch\sql\02_add_fk_article_to_case_events.sql
-- Adds the linking column to case_events
```

**SQL Content**: From articles_project.txt DDL section (case_events part)

**Verification**:
```sql
SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'case_events' AND COLUMN_NAME = 'fk_article'
```

---

### PHASE 2: Stored Procedures
**Goal**: Create the article lifecycle management procedures

#### Step 2.1: Create upsert_article_for_event
```sql
-- File: u:\docketwatch\sql\03_create_upsert_article_proc.sql
```

**Key Behavior**:
- Finds or creates ONE Pending article per case per day
- Updates existing Pending article (increments version)
- Links case_event to the article
- Returns @article_id OUTPUT parameter

**Test Script**:
```sql
-- Test creating first article
DECLARE @article_id UNIQUEIDENTIFIER
EXEC dbo.upsert_article_for_event 
    @fk_case = 123,
    @event_id = '...guid...',
    @event_date = '2025-10-13',
    @story_headline = 'Test Headline',
    @story_body = 'Test Body',
    @generated_by = 'test',
    @article_id = @article_id OUTPUT
SELECT @article_id, * FROM dbo.articles WHERE id = @article_id
```

#### Step 2.2: Create complete_article
```sql
-- File: u:\docketwatch\sql\04_create_complete_article_proc.sql
```

**Test Script**:
```sql
EXEC dbo.complete_article @article_id = '...guid...', @username = 'test_user'
SELECT * FROM dbo.articles WHERE id = '...guid...'
-- Should show articleStatus = 'Completed'
```

---

### PHASE 3: Data Migration (Backfill)
**Goal**: Migrate existing story data from documents to articles

#### Step 3.1: Dry Run Migration
```sql
-- File: u:\docketwatch\sql\05_migrate_articles_DRY_RUN.sql
```

**Content**: Migration SQL wrapped in transaction with ROLLBACK
```sql
BEGIN TRANSACTION
-- Run migration CTE queries
SELECT COUNT(*) AS articles_that_would_be_created FROM ...
ROLLBACK
```

**Verification Queries**:
```sql
-- How many documents have story content?
SELECT COUNT(*) FROM dbo.documents 
WHERE story_body IS NOT NULL OR story_headline IS NOT NULL

-- How many unique case/date combinations?
SELECT COUNT(*) FROM (
    SELECT DISTINCT fk_case, CAST(date_downloaded AS DATE)
    FROM dbo.documents
    WHERE story_body IS NOT NULL
) x

-- Sample of what would be migrated
SELECT TOP 10 
    fk_case, 
    CAST(date_downloaded AS DATE) as article_date,
    story_headline,
    LEFT(story_body, 100) as body_preview
FROM dbo.documents
WHERE story_body IS NOT NULL
ORDER BY date_downloaded DESC
```

#### Step 3.2: Execute Real Migration
```sql
-- File: u:\docketwatch\sql\06_migrate_articles_LIVE.sql
```

**Content**: Same as dry run but with COMMIT

**Post-Migration Verification**:
```sql
-- Count migrated articles
SELECT COUNT(*) FROM dbo.articles WHERE generated_by = 'migration'

-- Verify linkages
SELECT COUNT(*) FROM dbo.case_events WHERE fk_article IS NOT NULL

-- Sample migrated data
SELECT TOP 10 * FROM dbo.articles ORDER BY created_at DESC
```

---

### PHASE 4: Python Code Changes (Parallel System)
**Goal**: Update Python to write to articles table while keeping documents writes

#### Step 4.1: Create Article Helper Module
```python
# File: u:\docketwatch\python\article_manager.py
```

**Functions to create**:
```python
def upsert_article_for_event(cursor, fk_case, event_id, event_date, 
                              story_headline=None, story_sub_head=None,
                              story_body=None, ai_model=None, 
                              ai_tokens_input=None, ai_tokens_output=None,
                              ai_cost=None, generated_by='pipeline'):
    """
    Call the stored procedure to upsert an article for a case event.
    Returns the article_id (GUID).
    """
    # Call stored proc
    # Return article_id

def get_todays_article(cursor, fk_case, article_date=None):
    """Get the current pending article for a case on given date"""
    # Query for Pending article
    # Return article data dict

def complete_article(cursor, article_id, username=None):
    """Mark an article as Completed"""
    # Call stored proc
```

#### Step 4.2: Update summary_parser.py
```python
# Changes to summary_parser.py

# BEFORE: Only updates documents table
def save_structured_summary(cursor, doc_uid, parsed_summary):
    cursor.execute("""
        UPDATE docketwatch.dbo.documents 
        SET story_headline = ?, story_body = ?, ...
        WHERE doc_uid = ?
    """, ...)

# AFTER: Updates documents table AND creates/updates article
import article_manager

def save_structured_summary(cursor, doc_uid, parsed_summary):
    # DEPRECATED: Keep for backward compatibility during transition
    cursor.execute("""
        UPDATE docketwatch.dbo.documents 
        SET story_headline = ?, story_body = ?, ...
        WHERE doc_uid = ?
    """, ...)
    
    # NEW: Also upsert to articles table
    # Get the case_event and case info for this document
    cursor.execute("""
        SELECT d.fk_case, d.fk_case_event, 
               COALESCE(e.event_date, CAST(GETDATE() AS DATE)) as event_date
        FROM dbo.documents d
        LEFT JOIN dbo.case_events e ON d.fk_case_event = e.id
        WHERE d.doc_uid = ?
    """, doc_uid)
    row = cursor.fetchone()
    
    if row and row.fk_case and row.fk_case_event:
        article_id = article_manager.upsert_article_for_event(
            cursor=cursor,
            fk_case=row.fk_case,
            event_id=row.fk_case_event,
            event_date=row.event_date,
            story_headline=parsed_summary.get('story_headline'),
            story_sub_head=parsed_summary.get('story_sub_head'),
            story_body=parsed_summary.get('story_body'),
            generated_by='ai_summary_parser'
        )
        logger.info(f"Upserted article {article_id} for document {doc_uid}")
```

#### Step 4.3: Update Email Generator
```python
# Changes to docketwatch_case_events_alert_plus2.py

# Option A: Continue reading from documents (no change needed)
# Option B: Read from articles table instead

def get_todays_article_for_email(cursor, case_id):
    """Get today's article for this case"""
    cursor.execute("""
        SELECT TOP 1 
            id, story_headline, story_sub_head, story_body,
            articleStatus, version, updated_at
        FROM dbo.articles
        WHERE fk_case = ?
          AND article_date = CAST(GETDATE() AS DATE)
          AND articleStatus IN ('Pending', 'Completed')
        ORDER BY updated_at DESC
    """, case_id)
    return cursor.fetchone()
```

---

### PHASE 5: Midnight Lifecycle Job
**Goal**: Auto-close Pending articles at midnight

#### Step 5.1: Create SQL Agent Job
```sql
-- File: u:\docketwatch\sql\07_create_midnight_close_job.sql

USE msdb;
GO

EXEC dbo.sp_add_job
    @job_name = N'DocketWatch_Close_Pending_Articles',
    @enabled = 1,
    @description = N'Close yesterday Pending articles to Closed status';

EXEC dbo.sp_add_jobstep
    @job_name = N'DocketWatch_Close_Pending_Articles',
    @step_name = N'Close Pending Articles',
    @subsystem = N'TSQL',
    @command = N'
        UPDATE docketwatch.dbo.articles
        SET articleStatus = ''Closed'',
            updated_at = GETDATE()
        WHERE articleStatus = ''Pending''
          AND article_date < CAST(GETDATE() AS DATE);
    ',
    @database_name = N'docketwatch',
    @retry_attempts = 3,
    @retry_interval = 5;

EXEC dbo.sp_add_jobschedule
    @job_name = N'DocketWatch_Close_Pending_Articles',
    @name = N'Daily at 12:05 AM',
    @freq_type = 4, -- Daily
    @freq_interval = 1,
    @active_start_time = 000500; -- 12:05 AM

EXEC dbo.sp_add_jobserver
    @job_name = N'DocketWatch_Close_Pending_Articles';
GO
```

**Alternative: Python Scheduler**
```python
# File: u:\docketwatch\python\close_pending_articles.py
# Schedule via Windows Task Scheduler or cron
```

---

### PHASE 6: ColdFusion UI (New Tab)
**Goal**: Add Articles tab to case details page

#### Step 6.1: Create articles_tab.cfm
```cfm
<!-- File: u:\docketwatch\court-beta\includes\articles_tab.cfm -->

<cfquery name="Q_articles" datasource="Reach">
    SELECT 
        id, article_date, articleStatus,
        story_headline, story_sub_head, LEFT(story_body, 200) as body_preview,
        version, updated_at, generated_by, is_published
    FROM docket watch.dbo.articles
    WHERE fk_case = <cfqueryparam value="#URL.id#" cfsqltype="cf_sql_integer">
    ORDER BY article_date DESC, version DESC
</cfquery>

<!-- Display pending article first -->
<!-- Display historical articles -->
<!-- Buttons for Complete, Edit, Publish -->
```

#### Step 6.2: Add to case_details.cfm
```cfm
<!-- Add new tab -->
<li><a href="##articles">Articles (#Q_articles.recordCount#)</a></li>

<!-- Add tab content -->
<div id="articles">
    <cfinclude template="includes/articles_tab.cfm">
</div>
```

---

### PHASE 7: Testing & Validation

#### Test 7.1: Unit Tests (SQL)
```sql
-- File: u:\docketwatch\sql\08_test_articles_system.sql

-- Test 1: Create first article for a case/date
-- Test 2: Update same article (version increment)
-- Test 3: Complete article
-- Test 4: Create new Pending after Complete
-- Test 5: Unique constraint blocks duplicate Pending
-- Test 6: Midnight close logic
-- Test 7: Event linkage
```

#### Test 7.2: Integration Tests (Python)
```python
# File: u:\docketwatch\python\test_articles_system.py

def test_article_creation():
    """Test creating an article via Python"""
    
def test_article_evolution():
    """Test updating same article multiple times"""
    
def test_complete_workflow():
    """Test full workflow: create, update, complete, new"""
```

---

## Rollout Strategy

### Week 1: Database Setup (Non-Breaking)
- [x] ✅ Phase 1: Create tables - COMPLETED 2025-10-15
- [x] ✅ Phase 2: Create stored procedures - READY TO EXECUTE
- [x] ✅ Phase 3: Create migration scripts - READY TO EXECUTE
- [ ] Execute Phase 2 stored procedures
- [ ] Execute Phase 3 migration (analyze → dry run → live)
- [ ] Verify with test data
- [ ] No impact to production (Phase 3 marks historical as Closed)

### Week 2: Migration & Parallel System
- [ ] Run Phase 3 migration (dry run first)
- [ ] Deploy Phase 4 Python changes (writes to both tables)
- [ ] Monitor logs for any issues
- [ ] Documents table still has story fields

### Week 3: UI & Lifecycle
- [ ] Deploy Phase 6 CF changes (new tab)
- [ ] Set up Phase 5 midnight job
- [ ] User acceptance testing
- [ ] Both systems running in parallel

### Week 4+: Transition & Deprecation
- [ ] Monitor articles table for 1-2 weeks
- [ ] Verify all new stories go to articles
- [ ] Add deprecation comments to document writes
- [ ] Plan eventual removal of documents.story_* columns

---

## Monitoring & Validation

### Daily Checks
```sql
-- New articles created today
SELECT COUNT(*) FROM dbo.articles 
WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)

-- Pending articles (should auto-close at midnight)
SELECT COUNT(*) FROM dbo.articles 
WHERE articleStatus = 'Pending' AND article_date < CAST(GETDATE() AS DATE)
-- Should be 0 after midnight job runs

-- Events without article links
SELECT COUNT(*) FROM dbo.case_events 
WHERE fk_article IS NULL 
  AND CAST(created_at AS DATE) >= '2025-10-13' -- after go-live date
```

### Error Scenarios to Monitor
1. Duplicate Pending articles (unique constraint violations)
2. Events not getting linked to articles
3. Articles not closing at midnight
4. Migration data quality issues

---

## Rollback Plan

### If Issues Found in Week 2-3
```sql
-- Remove article linkages
UPDATE dbo.case_events SET fk_article = NULL

-- Delete migration data
DELETE FROM dbo.articles WHERE generated_by = 'migration'

-- Delete new articles
DELETE FROM dbo.articles WHERE generated_by <> 'migration'

-- Revert Python code
-- Documents table still has all story fields, no data loss
```

### If Issues Found After Week 4
- Articles table has become source of truth
- Cannot easily rollback
- Fix forward instead

---

## Success Criteria

- [ ] No duplicate Pending articles per case per date
- [ ] All new case events create/update articles
- [ ] Midnight job successfully closes Pending articles
- [ ] UI displays evolving articles correctly
- [ ] Email system works with either data source
- [ ] Migration preserves all historical story content
- [ ] Performance is acceptable (article queries fast)
- [ ] No data loss from documents table

---

## Next Steps - YOUR DECISION POINTS

1. **Review this plan** - Does this match your vision?
2. **Timeline** - What's your preferred rollout schedule?
3. **Testing** - Do you want me to create test scripts first?
4. **Start Point** - Should we begin with Phase 1 (create tables)?
5. **Dependencies** - Any other systems/scripts I should know about?

Let me know which phase you'd like to tackle first, and I'll help you implement it step by step!
