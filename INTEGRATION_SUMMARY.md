# DocketWatch Pipeline Integration Summary

## Overview
This document summarizes the integration of PDF downloading into the unfiled record scraping process to ensure users only see unfiled records after their PDFs are available.

## Problem Solved
**Before**: Unfiled records appeared in the system immediately after scraping, but PDFs were downloaded in a separate process that ran every 5 minutes. This caused user confusion as they could see records but couldn't access the associated documents.

**After**: Each unfiled record is only saved to the database AFTER its PDF has been successfully downloaded and the document record created.

## Changes Made

### 1. Modified `docketwatch_map_unfiled_scraper.py`

#### Added PDF Download Function
- `download_pdf_for_case()`: Handles PDF downloading using the existing Node.js pipeline
- Downloads PDF using `download_map_filing.js` and `combine_images_to_pdf.py`
- Creates case_event and document records immediately after successful PDF download
- Returns True only if PDF is saved and document records are created

#### Integrated Processing Loop
- **Before**: Insert case → Commit → Run separate PDF download later
- **After**: Insert case → Download PDF → Commit only if PDF succeeds → Rollback if PDF fails

#### Transaction Management
- Uses database transactions to ensure atomicity
- Case insertion is rolled back if PDF download fails
- Document records are created inline with case insertion

#### Removed Separate Post-Processing
- No longer calls `docketwatch_process.py` separately
- PDF downloading and document creation now happen inline
- Party extraction can still be run separately if needed

### 2. Dependencies
- Added import for `insert_documents_for_event` from `scraper_base`
- Utilizes existing PDF download infrastructure:
  - `download_map_filing.js` (Node.js/Puppeteer)
  - `combine_images_to_pdf.py` (Image to PDF conversion)

## Benefits

### User Experience
- **Immediate PDF Availability**: Users see unfiled records only when PDFs are ready
- **Reduced Confusion**: No more "record exists but PDF missing" scenarios
- **Faster Access**: PDFs are available as soon as records appear

### System Reliability
- **Atomic Operations**: Database and file system stay in sync
- **Better Error Handling**: Failed PDF downloads don't create orphaned records
- **Reduced Complexity**: Single process instead of coordinated multiple processes

### Performance
- **Reduced Polling**: No need for separate download loop checking for missing PDFs
- **Resource Efficiency**: Single login session used for both scraping and PDF download
- **Transaction Safety**: Database rollback prevents inconsistent states

## Process Flow

### Integrated Workflow
1. **Login** → Get authentication cookie
2. **Fetch Unfiled Records** → API call to get recent filings
3. **For Each New Record**:
   - Check if case already exists
   - If new case:
     a. Insert case record (not committed)
     b. Download PDF using Node.js pipeline
     c. Create case_event and document records
     d. **Commit transaction only if PDF succeeds**
     e. **Rollback if PDF fails**
4. **Complete** → All visible records have PDFs available

### Error Handling
- **PDF Download Timeout**: 5-minute timeout per PDF
- **File System Errors**: Verify PDF exists before committing
- **Node.js Failures**: Check return codes and error output
- **Database Rollback**: Automatic cleanup of failed insertions

## Configuration

### Environment Variables (Node.js)
- `FILE_NAME`: PDF filename without extension
- `KEY`: Empty for unfiled cases
- `END`: Empty for unfiled cases  
- `COOKIE`: Authentication cookie from login
- `COURT_CASE_NUMBER`: Court case number
- `FK_CASE`: Database case ID
- `IS_UNFILED`: "true" for unfiled cases

### File Paths
- **PDF Storage**: `\\10.146.176.84\general\docketwatch\docs\cases\{case_id}\E{court_case_number}.pdf`
- **Temp Images**: `u:\docketwatch\python\temp_pages\`
- **Scripts**: Node.js and Python scripts in same directory

## Backward Compatibility

### Existing Infrastructure
- All existing PDF download components remain unchanged
- `download_map_filing.js` works exactly as before
- `combine_images_to_pdf.py` unchanged
- Database schema unchanged

### Migration Path
- Current separate download process can be disabled
- `run_map_download_loop.py` no longer needed for unfiled cases
- Filed cases (with court case numbers) can still use separate download if needed

## Future Improvements

### Potential Enhancements
1. **Parallel PDF Downloads**: Process multiple PDFs simultaneously (with rate limiting)
2. **Retry Logic**: Automatic retry for failed PDF downloads
3. **Progress Tracking**: Real-time status updates for long-running downloads
4. **Selective Processing**: Option to process only specific case types
5. **Performance Metrics**: Track download success rates and timing

### Monitoring
- Enhanced logging for PDF download success/failure rates
- Alert on consecutive PDF download failures
- Track processing time per unfiled record
- Monitor disk space for PDF storage

## Testing Recommendations

### Integration Testing
1. **Happy Path**: Verify new unfiled records appear with PDFs
2. **PDF Failure**: Confirm failed PDF downloads don't create database records
3. **Database Rollback**: Test transaction rollback on various failure scenarios
4. **Performance**: Monitor processing time with multiple records
5. **Error Recovery**: Test behavior after Node.js crashes or timeouts

### Monitoring Points
- Case insertion success rate
- PDF download success rate  
- Average processing time per record
- Database transaction rollback frequency
- File system errors

## Technical Notes

### Transaction Scope
- Database transaction includes: case insertion + case_event creation + document records
- File system operations (PDF creation) are outside transaction scope
- Verification of PDF existence happens before transaction commit

### Error Scenarios Handled
- Node.js script failures
- PDF file not created
- Document record creation failures
- Database constraint violations
- Network timeouts
- File system permission errors

### Performance Considerations
- PDF downloads are serial (one at a time)
- Each record requires: API call + PDF download + database operations
- Processing time depends on PDF complexity and network speed
- Memory usage managed by Node.js script cleanup

This integration significantly improves the user experience by ensuring data consistency between the database and file system, eliminating the confusion of records without available PDFs.
