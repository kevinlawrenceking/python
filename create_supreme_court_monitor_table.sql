-- Create table for Supreme Court monitor status dashboard
-- Run this in SQL Server Management Studio

USE docketwatch;
GO

-- Drop table if it exists (for testing)
-- DROP TABLE IF EXISTS dbo.supreme_court_monitor_status;

CREATE TABLE dbo.supreme_court_monitor_status (
    id INT IDENTITY(1,1) PRIMARY KEY,
    case_number VARCHAR(20) NOT NULL UNIQUE,
    case_name VARCHAR(500),
    status VARCHAR(20) NOT NULL, -- 'OK', 'ALERT', 'ERROR'
    message VARCHAR(1000),
    last_check DATETIME2 NOT NULL,
    proceedings_count INT DEFAULT 0,
    last_proceeding_date VARCHAR(50),
    created_date DATETIME2 DEFAULT GETDATE()
);

-- Create index for faster lookups
CREATE INDEX IX_supreme_court_monitor_status_case_number ON dbo.supreme_court_monitor_status(case_number);
CREATE INDEX IX_supreme_court_monitor_status_last_check ON dbo.supreme_court_monitor_status(last_check);

-- Insert initial record for Maxwell case
INSERT INTO dbo.supreme_court_monitor_status 
(case_number, case_name, status, message, last_check, proceedings_count)
VALUES 
('24-1073', 'Ghislaine Maxwell, Petitioner v. United States', 'PENDING', 'Waiting for first monitor run', GETDATE(), 0);

SELECT * FROM dbo.supreme_court_monitor_status;
