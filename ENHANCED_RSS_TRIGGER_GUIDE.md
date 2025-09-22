# Enhanced RSS Trigger - User Guide

## Overview

The Enhanced RSS Trigger (`docketwatch_rss_trigger_enhanced.py`) extends the basic RSS monitoring functionality with automatic PDF download and AI-powered document summarization.

## Features

### 🔍 **RSS Monitoring** (from original)
- Monitors court RSS feeds for new docket entries
- Tracks PACER cases automatically
- Creates case_events records in database
- Duplicate detection prevents reprocessing

### 📄 **PDF Download** (NEW)
- Automatically downloads PDFs for new case events
- Uses existing PACER login infrastructure
- Handles "Cannot redisplay" errors automatically
- Saves PDFs to organized directory structure

### 🧠 **AI Summarization** (NEW)
- Generates AI-powered summaries of downloaded documents
- Uses existing Gemini API integration
- Processes OCR text to create readable summaries
- Updates database with summary results

### 📧 **Enhanced Email Alerts** (NEW)
- Includes PDF summaries in email notifications
- Lists downloaded document paths
- Maintains backward compatibility with existing alerts

## Usage

### Basic Usage
```bash
python docketwatch_rss_trigger_enhanced.py
```

### Configuration

Edit `rss_trigger_enhanced.config` to customize behavior:

```ini
[FEATURES]
ENABLE_PDF_DOWNLOAD = True      # Enable/disable PDF download
ENABLE_SUMMARIZATION = True     # Enable/disable AI summarization
ENHANCED_EMAIL_ALERTS = True    # Enhanced email with summaries

[PROCESSING]
PDF_DOWNLOAD_TIMEOUT = 300      # PDF download timeout (seconds)
SUMMARIZATION_TIMEOUT = 120     # Summarization timeout (seconds)
```

### Testing

Test the enhanced functionality:
```bash
python test_enhanced_rss_trigger_clean.py
```

Test with a specific case event:
```bash
python test_enhanced_rss_trigger_clean.py [case_event_id]
```

## Workflow

1. **RSS Monitoring**: Scans RSS feeds for new docket entries
2. **Event Creation**: Creates case_events record if new
3. **PDF Download**: Downloads associated PDFs using PACER processor
4. **Document Processing**: Extracts metadata and saves documents
5. **AI Summarization**: Generates summaries for downloaded documents
6. **Enhanced Alerts**: Sends email with summaries and document info

## Error Handling

- **PDF Download Failures**: Logged as warnings, don't stop processing
- **Summarization Failures**: Gracefully handled, basic email still sent
- **Email Failures**: Non-fatal, logged for review
- **Database Errors**: Proper rollback and error notification

## Database Updates

The enhanced script updates these tables:
- `rss_feed_entries` - RSS feed items
- `case_events` - New docket events
- `documents` - Downloaded PDF metadata
- `task_runs_log` - Processing logs

## Performance

- **Runtime**: ~15-30 minutes depending on new events
- **Safe Scheduling**: Every 15-30 minutes
- **Timeout Protection**: PDF/summarization have timeouts
- **Resource Usage**: Minimal when no new events

## Dependencies

Required Python packages:
- `requests` - HTTP requests
- `beautifulsoup4` - XML/HTML parsing
- `pyodbc` - Database connectivity
- `selenium` - PACER web automation (for PDF download)

Required scripts:
- `combined_pacer_pdf_vprocessor.py` - PDF download processor
- `summarize_document_event.py` - AI summarization
- `scraper_base.py` - Common utilities
- `error_notification_system.py` - Error handling

## Monitoring

### Logs
- Main log: `logs/docketwatch_rss_trigger_enhanced.log`
- Database logs: `task_runs_log` table
- Error notifications: Automatic email alerts

### Key Metrics
- New RSS events detected
- PDFs successfully downloaded
- Documents summarized
- Email alerts sent

## Troubleshooting

### Common Issues

1. **PDF Download Fails**
   - Check PACER credentials in database
   - Verify Chrome WebDriver path
   - Check network connectivity to PACER

2. **Summarization Fails**
   - Verify Gemini API key in database
   - Check document OCR text availability
   - Review summarization timeout settings

3. **Email Fails**
   - Verify SMTP server settings
   - Check recipient email addresses
   - Review email content for formatting issues

### Diagnostic Commands
```bash
# Test database connection
python -c "import pyodbc; conn = pyodbc.connect('DSN=Docketwatch;TrustServerCertificate=yes;'); print('✅ DB OK')"

# Test enhanced script import
python -c "import docketwatch_rss_trigger_enhanced; print('✅ Script OK')"

# Run comprehensive test
python test_enhanced_rss_trigger_clean.py
```

## Migration from Basic RSS Trigger

To switch from the basic RSS trigger:

1. **Backup**: Keep `docketwatch_rss_trigger.py` as fallback
2. **Schedule**: Replace in task scheduler with enhanced version
3. **Monitor**: Watch first few runs for issues
4. **Fallback**: Can revert to basic version anytime

The enhanced version is fully backward compatible with existing database schema and email systems.

## Support

For issues or questions:
1. Check logs for specific error messages
2. Run test script for diagnostics
3. Review database for processing status
4. Contact system administrator if needed