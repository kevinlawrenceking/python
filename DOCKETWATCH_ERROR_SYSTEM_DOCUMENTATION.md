# DocketWatch Error Notification & Chrome Cleanup System Documentation

## Overview

We've implemented a comprehensive error notification and Chrome cleanup system for all DocketWatch automation scripts. This ensures reliable operation, immediate error awareness, and proper resource cleanup.

## System Components

### 1. Error Notification System (`error_notification_system.py`)

**Purpose**: Centralized error logging and email notification system

**Features**:
- Logs all errors to `docketwatch.dbo.error_notifications` table
- Sends email notifications for critical errors
- Prevents duplicate notifications
- Tracks error resolution status
- Provides contextual error information

**Database Schema**:
```sql
-- Table: docketwatch.dbo.error_notifications
CREATE TABLE error_notifications (
    id INT IDENTITY(1,1) PRIMARY KEY,
    script_name NVARCHAR(255) NOT NULL,
    error_type NVARCHAR(100) NOT NULL,
    error_message NVARCHAR(MAX) NOT NULL,
    severity NVARCHAR(20) NOT NULL DEFAULT 'ERROR',
    fk_task_run INT NULL,
    additional_context NVARCHAR(MAX) NULL,
    stack_trace NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
    resolved_at DATETIME2 NULL,
    email_sent BIT NOT NULL DEFAULT 0,
    email_sent_at DATETIME2 NULL
);
```

### 2. SMTP Configuration

**Settings** (matches existing `scraper_base.py`):
- **Server**: `mx0a-00195501.pphosted.com`
- **Port**: `25`
- **Authentication**: None required
- **TLS**: Not used
- **From Address**: `it@tmz.com`
- **To Address**: `kevin@tmz.com`

### 3. Chrome Cleanup Pattern

**Purpose**: Ensures Chrome/ChromeDriver processes are always properly closed

**Implementation**:
```python
driver = None
try:
    driver = webdriver.Chrome(service=service, options=chrome_options)
    # ... script logic ...
finally:
    if driver:
        try:
            driver.quit()
            log_message(cursor, fk_task_run, "INFO", "ChromeDriver properly closed.")
        except Exception as cleanup_error:
            error_msg = f"Error during driver cleanup: {str(cleanup_error)}"
            log_message(cursor, fk_task_run, "ERROR", error_msg)
            error_notifier.log_chrome_error(error_msg, fk_task_run=fk_task_run)
```

## Implementation Guide

### Step 1: Add Error Notification System

Add to script imports:
```python
from error_notification_system import create_error_notifier

# Initialize (near top of script)
script_filename = os.path.splitext(os.path.basename(__file__))[0]
error_notifier = create_error_notifier(script_filename)
```

### Step 2: Wrap Script in Error Handling

```python
try:
    # === Main script logic here ===
    
    # Database connections
    try:
        conn = pyodbc.connect("DSN=Docketwatch;TrustServerCertificate=yes;")
        cursor = conn.cursor()
    except Exception as e:
        error_msg = f"Database connection failed: {e}"
        error_notifier.log_database_error(error_msg)
        raise
    
    # Chrome operations
    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        # ... Chrome automation ...
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as cleanup_error:
                error_notifier.log_chrome_error(f"Cleanup failed: {cleanup_error}")
    
    # Database operations
    try:
        cursor.execute("...")
        conn.commit()
    except Exception as db_error:
        error_notifier.log_database_error(f"Database operation failed: {db_error}")
    
    # Cleanup
    try:
        cursor.close()
        conn.close()
    except Exception as cleanup_error:
        error_notifier.log_database_error(f"Database cleanup failed: {cleanup_error}")

except Exception as e:
    # Top-level error handler
    error_msg = f"Critical script failure: {str(e)}"
    try:
        log_message(cursor, fk_task_run, "ERROR", error_msg)
    except:
        pass
    
    error_notifier.log_critical_error(
        error_msg, 
        fk_task_run=fk_task_run,
        additional_context="Script failed at top level"
    )
    raise
```

### Step 3: Error Notification Methods

**Available Methods**:
```python
# Database errors
error_notifier.log_database_error(error_message, fk_task_run=None)

# Chrome/Selenium errors  
error_notifier.log_chrome_error(error_message, fk_task_run=None)

# General errors
error_notifier.log_error(error_type, error_message, severity="ERROR", fk_task_run=None)

# Critical errors (always send email)
error_notifier.log_critical_error(error_message, fk_task_run=None)
```

**Parameters**:
- `error_message`: Descriptive error message
- `error_type`: Category of error (e.g., "Database Error", "Chrome Error")
- `severity`: ERROR, WARNING, CRITICAL
- `fk_task_run`: Task run ID for context
- `additional_context`: Extra debugging information
- `send_email`: Boolean to control email sending (default: True for CRITICAL)

## Error Types and Handling

### 1. Database Errors
```python
try:
    cursor.execute("SELECT * FROM table")
except Exception as e:
    error_notifier.log_database_error(f"Query failed: {e}", fk_task_run=fk_task_run)
```

### 2. Chrome/Selenium Errors
```python
try:
    driver.get(url)
except Exception as e:
    error_notifier.log_chrome_error(f"Navigation failed: {e}", fk_task_run=fk_task_run)
```

### 3. API Errors
```python
try:
    response = requests.get(api_url)
    if response.status_code != 200:
        error_notifier.log_error(
            "API Request Failed", 
            f"HTTP {response.status_code}: {api_url}",
            fk_task_run=fk_task_run
        )
except Exception as e:
    error_notifier.log_error("API Exception", str(e), fk_task_run=fk_task_run)
```

### 4. Critical System Errors
```python
try:
    # Critical operation
    pass
except Exception as e:
    error_notifier.log_critical_error(
        f"Critical failure in {operation_name}: {e}",
        fk_task_run=fk_task_run,
        additional_context="System may be unstable"
    )
```

## Script Status Tracking

### Completed Scripts ✅
- `docketwatch_case_events.py` - Full implementation
- `docketwatch_map_unfiled_scraper.py` - Full implementation  
- `docketwatch_map_scraper.py` - Full implementation

### High Priority (Chrome/Selenium scripts)
- `docketwatch_la_scraper.py`
- `docketwatch_nyc_scraper.py`
- `docketwatch_nycsc_scraper.py`
- `docketwatch_broward_scraper.py`

### Medium Priority (Other automation)
- `docketwatch_case_events_alert_plus.py`
- `docketwatch_celebrity_insert.py`
- `docketwatch_legal_name_finder.py`
- `docketwatch_hearings_la.py`

## Monitoring and Administration

### Database Queries for Monitoring

**Recent Errors**:
```sql
SELECT TOP 50 
    script_name,
    error_type,
    error_message,
    severity,
    created_at,
    resolved_at,
    email_sent
FROM docketwatch.dbo.error_notifications 
ORDER BY created_at DESC
```

**Error Summary by Script**:
```sql
SELECT 
    script_name,
    COUNT(*) as total_errors,
    COUNT(CASE WHEN severity = 'CRITICAL' THEN 1 END) as critical_errors,
    MAX(created_at) as last_error
FROM docketwatch.dbo.error_notifications 
WHERE created_at >= DATEADD(day, -7, GETDATE())
GROUP BY script_name
ORDER BY total_errors DESC
```

**Unresolved Critical Errors**:
```sql
SELECT 
    script_name,
    error_type,
    error_message,
    created_at,
    additional_context
FROM docketwatch.dbo.error_notifications 
WHERE severity = 'CRITICAL' 
    AND resolved_at IS NULL
ORDER BY created_at DESC
```

### ColdFusion Integration Points

**For Admin Dashboard**:
1. **Error Log Table**: Query `docketwatch.dbo.error_notifications`
2. **Real-time Monitoring**: Filter by `created_at >= DATEADD(hour, -1, GETDATE())`
3. **Error Resolution**: Update `resolved_at` when issues are fixed
4. **Email Status**: Track `email_sent` and `email_sent_at`

**Useful Filters**:
- By script: `WHERE script_name = ?`
- By severity: `WHERE severity IN ('CRITICAL', 'ERROR')`
- By date range: `WHERE created_at BETWEEN ? AND ?`
- Unresolved: `WHERE resolved_at IS NULL`

## Best Practices

### 1. Error Context
Always provide meaningful context:
```python
error_notifier.log_error(
    "PDF Download Failed",
    f"Failed to download PDF for case {case_id}",
    additional_context=f"URL: {pdf_url}, Attempt: {attempt_num}"
)
```

### 2. Granular Error Handling
Handle specific error types separately:
```python
try:
    # Database operation
except pyodbc.Error as db_error:
    error_notifier.log_database_error(str(db_error))
except requests.RequestException as api_error:
    error_notifier.log_error("API Error", str(api_error))
except Exception as general_error:
    error_notifier.log_error("General Error", str(general_error))
```

### 3. Chrome Cleanup
Always use try/finally for Chrome cleanup:
```python
driver = None
try:
    driver = webdriver.Chrome(...)
    # ... operations ...
finally:
    if driver:
        try:
            driver.quit()
        except Exception as e:
            error_notifier.log_chrome_error(f"Cleanup failed: {e}")
```

### 4. Email Throttling
The system automatically prevents duplicate email notifications for the same error type within a time window.

## Deployment Notes

1. **Dependencies**: Ensure `error_notification_system.py` is in the Python path
2. **Database**: Run the table creation script once
3. **SMTP**: Uses existing TMZ email infrastructure
4. **Permissions**: Scripts need database INSERT permissions for error_notifications table
5. **Monitoring**: Set up ColdFusion admin page to query error_notifications table

## Benefits

1. **Immediate Awareness**: Email notifications for critical failures
2. **Centralized Logging**: All errors in one database table
3. **Historical Tracking**: Full error history with timestamps
4. **Resource Cleanup**: Guaranteed Chrome process cleanup
5. **Debugging Context**: Rich error context and stack traces
6. **No Duplicates**: Built-in duplicate prevention
7. **Resolution Tracking**: Mark errors as resolved

This system ensures robust, monitored, and maintainable automation scripts with immediate error visibility and proper resource management.
