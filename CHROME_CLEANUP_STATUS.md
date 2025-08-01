# DocketWatch Scripts - Chrome Cleanup and Error Notification Status

## SUMMARY OF REQUIREMENTS

### Every Script Needs:
1. **Chrome Cleanup Pattern** (for scripts using Selenium):
   ```python
   driver = None
   try:
       driver = webdriver.Chrome(...)
       # ... script logic ...
   finally:
       if driver:
           try:
               driver.quit()
           except Exception as cleanup_error:
               error_notifier.log_chrome_error(f"Cleanup failed: {cleanup_error}")
   ```

2. **Error Notification System**:
   ```python
   from error_notification_system import create_error_notifier
   error_notifier = create_error_notifier(script_name)
   
   # Top-level exception handler
   except Exception as e:
       error_notifier.log_critical_error(f"Script failed: {e}")
       raise
   ```

---

## SCRIPT STATUS

### ✅ COMPLETED (Chrome + Error Notifications)
- `docketwatch_case_events.py` - ✅ Full implementation
- `docketwatch_map_unfiled_scraper.py` - ✅ Full implementation (Chrome cleanup + Error notifications + Database logging)
- `docketwatch_map_scraper.py` - ✅ Chrome cleanup done
- `script_template_with_error_handling.py` - ✅ Template created

### 🔄 PARTIAL (Chrome cleanup done, needs error notifications)
- None currently

### ❌ NEEDS IMPLEMENTATION

#### High Priority (Selenium scripts):
- `docketwatch_broward_scraper.py`
- `docketwatch_la_scraper.py` 
- `docketwatch_nyc_scraper.py`
- `docketwatch_nycsc_scraper.py`
- `docketwatch_ny_scraper_new.py`
- `docketwatch_orange_FL_scraper.py`
- `pacer_single.py`
- `pacer_api.py`
- `capture_pdf_viewer.py`
- `capture_pdf_with_table.py`

#### Medium Priority (Critical operations):
- `batch_case_summarizer.py`
- `pacer_case_event_pdf_summarizer.py`
- `map_case_summarizer.py` - ✅ Has some error handling
- `supreme_court_monitor.py` - ✅ Has logging, needs email notifications
- `case_processing.py`
- `batch_generate_map_summaries.py`

#### Lower Priority (Data processing):
- `extract_pacer_pdf_metadata_loop.py`
- `extract_pacer_pdf_file_loop.py`
- `pdf_email_loop.py`
- `summarize_case_event_ai.py`

---

## IMPLEMENTATION STEPS

### For Each Script:

1. **Add Error Notification Import**:
   ```python
   from error_notification_system import create_error_notifier
   script_name = os.path.splitext(os.path.basename(__file__))[0]
   error_notifier = create_error_notifier(script_name)
   ```

2. **Wrap Script in Try/Catch**:
   ```python
   try:
       # ... existing script logic ...
   except Exception as e:
       error_notifier.log_critical_error(f"Script failed: {e}")
       raise
   ```

3. **For Selenium Scripts - Add Chrome Cleanup**:
   ```python
   driver = None
   try:
       driver = webdriver.Chrome(...)
       # ... script logic ...
   finally:
       if driver:
           try:
               driver.quit()
           except Exception as cleanup_error:
               error_notifier.log_chrome_error(f"Cleanup failed: {cleanup_error}")
   ```

4. **Add Specific Error Handling**:
   - Database errors: `error_notifier.log_database_error()`
   - Authentication errors: `error_notifier.log_authentication_error()`
   - PDF errors: `error_notifier.log_pdf_error()`
   - Chrome errors: `error_notifier.log_chrome_error()`

---

## TESTING CHECKLIST

For each updated script:
- [ ] Chrome processes close properly on success
- [ ] Chrome processes close properly on failure  
- [ ] Error emails are sent for critical failures
- [ ] Errors are logged to database
- [ ] Script still exits with proper error codes
- [ ] No temp Chrome profile directories left behind

---

## DATABASE SETUP REQUIRED

1. **Run SQL script**: `create_error_notifications_table.sql`
2. **Verify SMTP config** in `docketwatch.dbo.utilities` table
3. **Test email notifications** with test script

---

## NEXT IMMEDIATE ACTIONS

1. Complete `docketwatch_map_unfiled_scraper.py` error notifications
2. Fix highest priority Selenium scripts
3. Test email notification system 
4. Deploy SQL table creation script
5. Update remaining scripts using template

---

## PRIORITY ORDER

1. **CRITICAL**: Scripts that run frequently and use Chrome
2. **HIGH**: Scripts that process important data or send emails  
3. **MEDIUM**: Batch processing scripts
4. **LOW**: Utility and test scripts
