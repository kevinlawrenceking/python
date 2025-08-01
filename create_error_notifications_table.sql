-- Create error notification system table
-- This table stores critical errors that need immediate email notification

USE docketwatch;
GO

-- Drop table if it exists (for testing/development)
IF OBJECT_ID('dbo.error_notifications', 'U') IS NOT NULL
    DROP TABLE dbo.error_notifications;
GO

CREATE TABLE dbo.error_notifications (
    id INT IDENTITY(1,1) PRIMARY KEY,
    script_name VARCHAR(255) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message NTEXT NOT NULL,
    error_timestamp DATETIME2 DEFAULT GETDATE(),
    stack_trace NTEXT NULL,
    fk_task_run INT NULL,
    fk_case INT NULL,
    email_sent BIT DEFAULT 0,
    email_sent_timestamp DATETIME2 NULL,
    severity VARCHAR(20) DEFAULT 'ERROR', -- ERROR, CRITICAL, WARNING
    environment VARCHAR(50) DEFAULT 'PRODUCTION',
    resolved BIT DEFAULT 0,
    resolved_timestamp DATETIME2 NULL,
    resolved_by VARCHAR(100) NULL,
    additional_context NTEXT NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE()
);

-- Create indexes for performance
CREATE INDEX IX_error_notifications_script_timestamp ON dbo.error_notifications (script_name, error_timestamp DESC);
CREATE INDEX IX_error_notifications_email_sent ON dbo.error_notifications (email_sent, severity);
CREATE INDEX IX_error_notifications_resolved ON dbo.error_notifications (resolved, error_timestamp DESC);

-- Insert some test data
INSERT INTO dbo.error_notifications (script_name, error_type, error_message, severity)
VALUES 
    ('test_script.py', 'Database Connection', 'Failed to connect to database', 'CRITICAL'),
    ('docketwatch_case_events.py', 'Chrome Driver', 'ChromeDriver failed to start', 'ERROR'),
    ('pacer_scraper.py', 'Authentication', 'Login credentials invalid', 'ERROR');

-- Grant permissions (adjust as needed for your environment)
GRANT SELECT, INSERT, UPDATE ON dbo.error_notifications TO [docketwatch_user];

SELECT 'Error notifications table created successfully' as Status;
