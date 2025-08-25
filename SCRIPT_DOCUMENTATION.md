# DocketWatch Python Scripts Documentation & Organization Plan

## 📋 Current State Analysis

### Production Scripts (Scheduled via ColdFusion)
These files beginning with `docketwatch_` are in production and run via ColdFusion scheduler:

#### Court Scrapers
- `docketwatch_case_events.py` - Core case events scraper
- `docketwatch_broward_scraper.py` - Broward County scraper
- `docketwatch_nyc_scraper.py` - NYC courts scraper
- `docketwatch_ny_scraper_new.py` - New York state courts
- `docketwatch_la_scraper.py` - Los Angeles courts
- `docketwatch_hearings_la.py` - LA hearings specific
- `docketwatch_map_scraper.py` - MAP court system
- `docketwatch_map_scraper_new.py` - Updated MAP scraper
- `docketwatch_map_unfiled_scraper.py` - MAP unfiled cases

#### PACER System
- `docketwatch_pacer_scraper_v2.py` - Main PACER scraper
- `docketwatch_pacer_scraper_hearing_final.py` - PACER hearings
- `docketwatch_pacer_scraper_single.py` - Single case PACER
- `docketwatch_pacer_find_scraper.py` - PACER case finder

#### Specialized Tasks
- `docketwatch_celebrity_wikidata.py` - Celebrity data integration
- `docketwatch_celebrity_insert.py` - Celebrity case matching
- `docketwatch_legal_name_finder.py` - Legal name matching
- `docketwatch_monitoredContent.py` - Content monitoring
- `docketwatch_case_updates_alerts.py` - Alert system

### Supporting Scripts
- `scraper_base.py` - **CORE** Common functions library
- `process_pacer_event_pdf.py` - PDF processing for PACER events
- `run_event_pdf_batch.py` - Batch PDF processor

### Utility Scripts (Need Review)
- `pdf_fetcher.py` - PDF downloading
- `pacer_single.py` - Individual PACER processing
- `map_case_summarizer.py` - MAP case AI summarization
- `send_case_update_alerts.py` - Email alerts
- Various test files (`test*.py`)

## 🎯 Recommended Refactoring Plan

### Phase 1: Create Modular Components

#### 1.1 PDF Operations Module (`pdf_operations.py`)
Extract from `scraper_base.py`:
```python
# Functions to extract:
- download_pending_documents_for_event()
- perform_ocr_for_documents()
- is_valid_pdf()
- preprocess_image()
- clean_ocr_text()

# New functions to add:
- download_pdf_from_url()
- batch_download_pdfs()
- validate_pdf_integrity()
- extract_pdf_metadata()
```

#### 1.2 Case Event Management (`case_event_manager.py`)
Extract from `scraper_base.py`:
```python
# Functions to extract:
- insert_new_case_events()
- create_case_update_if_needed()
- update_case_records()
- mark_case_found()
- mark_case_not_found()

# New functions to add:
- merge_duplicate_events()
- archive_old_events()
- validate_event_data()
```

#### 1.3 AI Summarization (`ai_summarizer.py`)
Extract from `scraper_base.py`:
```python
# Functions to extract:
- generate_ai_summary_for_documents()
- summarize_case_update_old()
- clean_ocr_text()

# New functions to add:
- summarize_single_document()
- batch_summarize_events()
- generate_case_timeline()
- extract_key_entities()
```

#### 1.4 Document Management (`document_manager.py`)
```python
# New comprehensive module for:
- insert_documents_for_event()
- update_document_metadata()
- organize_document_files()
- cleanup_orphaned_documents()
- generate_document_reports()
```

#### 1.5 Alert System (`alert_system.py`)
Extract from `scraper_base.py`:
```python
# Functions to extract:
- send_case_update_alert()
- send_not_found_email()

# New functions to add:
- send_error_alerts()
- send_summary_reports()
- manage_subscription_preferences()
```

### Phase 2: Core Base Library (`scraper_core.py`)
Keep essential shared functions:
```python
# Database operations
- get_db_cursor()
- log_message()
- setup_logging()

# Common utilities
- get_task_context_by_tool_id()
- get_tool_selectors()
- perform_tool_login()

# Court-specific
- extract_court_and_type()
- extract_case_name_from_html()
- solve_recaptcha_2captcha()
```

### Phase 3: Workflow Orchestration

#### 3.1 Main Workflow Manager (`workflow_manager.py`)
```python
class DocketWatchWorkflow:
    def __init__(self, case_event_id):
        self.case_event_id = case_event_id
        
    def process_full_workflow(self):
        """Complete workflow: scrape → download → OCR → summarize → alert"""
        # 1. Download PDFs
        # 2. Perform OCR
        # 3. Generate AI summaries
        # 4. Create case updates
        # 5. Send alerts if storyworthy
        
    def process_pdf_only(self):
        """Just PDF download and metadata"""
        
    def process_summarization_only(self):
        """Just AI summarization workflow"""
```

#### 3.2 Batch Processor (`batch_processor.py`)
```python
class BatchProcessor:
    def process_pending_pdfs(self, limit=100):
        """Batch process all pending PDF downloads"""
        
    def process_pending_ocr(self, limit=50):
        """Batch OCR for documents missing text"""
        
    def process_pending_summaries(self, limit=25):
        """Batch AI summarization"""
```

## 🧹 Cleanup Tasks

### Files to Remove/Archive
- `test*.py` files (archive to `/archive/` folder)
- Duplicate versions (`*_backup.py`, `*_old.py`)
- Single-use diagnostic scripts

### Files to Consolidate
- Multiple PACER scrapers → unified `pacer_scraper.py`
- Multiple MAP scrapers → unified `map_scraper.py`
- Test/debug scripts → single `debug_tools.py`

### Files to Update
- Update all production scripts to use new modular imports
- Standardize error handling and logging
- Add configuration management

## 🔄 Migration Plan

### Week 1: Analysis & Setup
1. Create new modular files
2. Extract functions from `scraper_base.py`
3. Test new modules independently

### Week 2: Production Scripts Update
1. Update `docketwatch_*` files to use new modules
2. Test each production script
3. Deploy to staging environment

### Week 3: Batch Processing
1. Implement new workflow manager
2. Update batch processing scripts
3. Test end-to-end workflows

### Week 4: Cleanup & Documentation
1. Archive old files
2. Update documentation
3. Deploy to production

## 📊 New Architecture Overview

```
docketwatch/python/
├── core/
│   ├── scraper_core.py          # Essential shared functions
│   ├── pdf_operations.py        # PDF download, OCR, validation
│   ├── case_event_manager.py    # Case/event CRUD operations
│   ├── ai_summarizer.py         # AI/ML summarization
│   ├── document_manager.py      # Document lifecycle management
│   └── alert_system.py          # Notifications and alerts
├── workflows/
│   ├── workflow_manager.py      # Orchestrates complete workflows
│   └── batch_processor.py       # Handles batch operations
├── scrapers/
│   ├── pacer_scraper.py         # Unified PACER scraping
│   ├── map_scraper.py           # Unified MAP scraping
│   ├── court_scrapers/          # Individual court scrapers
│   └── specialty_scrapers/      # Celebrity, monitoring, etc.
├── production/
│   └── docketwatch_*.py         # ColdFusion scheduled scripts
├── utilities/
│   ├── debug_tools.py           # Debugging utilities
│   ├── migration_tools.py       # Data migration helpers
│   └── maintenance.py           # Cleanup and maintenance
└── archive/
    └── old_scripts/             # Deprecated files
```

## 🎯 Immediate Action Items

1. **Create `core/` directory** and start extracting modular components
2. **Audit all `docketwatch_*` files** to identify dependencies
3. **Create test cases** for new modular components
4. **Set up staging environment** for testing new architecture
5. **Document all workflows** currently implemented

## 💡 Benefits of New Architecture

- **Maintainability**: Clear separation of concerns
- **Reusability**: Functions can be used across multiple scripts
- **Testing**: Individual components can be unit tested
- **Debugging**: Easier to isolate issues
- **Scalability**: New court systems can be added easily
- **Documentation**: Clear purpose for each module

Would you like me to start implementing any of these components?
