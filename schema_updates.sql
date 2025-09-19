-- SQL Schema Updates for Structured AI Summaries
-- Run these commands to add the new fields and table

-- Add new columns to documents table
ALTER TABLE docketwatch.dbo.documents ADD 
    event_summary NVARCHAR(500),
    newsworthiness NVARCHAR(10), -- 'Yes' or 'No'
    newsworthiness_reason NVARCHAR(200),
    story_headline NVARCHAR(200),
    story_sub_head NVARCHAR(300),
    story_body NVARCHAR(MAX),
    whats_next NVARCHAR(1000);

-- Create new table for key details (many-to-one relationship)
CREATE TABLE docketwatch.dbo.document_key_details (
    id INT IDENTITY(1,1) PRIMARY KEY,
    fk_document_uid UNIQUEIDENTIFIER NOT NULL,
    key_title NVARCHAR(100) NOT NULL,
    key_detail NVARCHAR(500) NOT NULL,
    sort_order INT DEFAULT 1,
    created_at DATETIME DEFAULT GETDATE(),
    CONSTRAINT FK_document_key_details_documents 
        FOREIGN KEY (fk_document_uid) 
        REFERENCES documents(doc_uid)
);

-- Create index for better performance
CREATE INDEX IX_document_key_details_doc_uid 
    ON docketwatch.dbo.document_key_details(fk_document_uid);

-- Sample query to retrieve structured summary data
/*
SELECT 
    d.doc_uid,
    d.event_summary,
    d.newsworthiness,
    d.newsworthiness_reason,
    d.story_headline,
    d.story_sub_head,
    d.story_body,
    d.whats_next,
    kd.key_title,
    kd.key_detail,
    kd.sort_order
FROM docketwatch.dbo.documents d
LEFT JOIN docketwatch.dbo.document_key_details kd ON d.doc_uid = kd.fk_document_uid
WHERE d.doc_uid = 'BDA392F6-A9EA-4EDC-9602-B55BB2A0A55D'
ORDER BY kd.sort_order;
*/