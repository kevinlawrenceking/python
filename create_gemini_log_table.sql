-- Create table to log Gemini API calls and token usage
CREATE TABLE docketwatch.dbo.gemini_api_log (
    id INT IDENTITY(1,1) PRIMARY KEY,
    call_timestamp DATETIME2 DEFAULT GETDATE(),
    script_name NVARCHAR(100) NOT NULL,
    model_name NVARCHAR(50) NOT NULL,
    fk_asset INT NULL,  -- Link to asset being processed (if applicable)
    prompt_length INT NULL,  -- Length of prompt in characters
    response_length INT NULL,  -- Length of response in characters
    input_tokens INT NULL,  -- Tokens used for input (if available from API)
    output_tokens INT NULL,  -- Tokens used for output (if available from API)
    total_tokens INT NULL,  -- Total tokens used
    temperature DECIMAL(3,2) NULL,
    max_tokens INT NULL,
    success BIT NOT NULL DEFAULT 1,  -- 1 for success, 0 for failure
    error_message NVARCHAR(500) NULL,
    processing_time_ms INT NULL,  -- Time taken for API call in milliseconds
    cost_estimate DECIMAL(10,6) NULL,  -- Estimated cost in dollars (if calculated)
    created_by NVARCHAR(100) DEFAULT SYSTEM_USER
);

-- Create index for performance
CREATE INDEX IX_gemini_api_log_timestamp ON docketwatch.dbo.gemini_api_log(call_timestamp);
CREATE INDEX IX_gemini_api_log_script ON docketwatch.dbo.gemini_api_log(script_name);
CREATE INDEX IX_gemini_api_log_asset ON docketwatch.dbo.gemini_api_log(fk_asset);

-- Create a view for daily usage summary
CREATE VIEW v_gemini_daily_usage AS
SELECT 
    CAST(call_timestamp AS DATE) as call_date,
    script_name,
    model_name,
    COUNT(*) as total_calls,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_calls,
    AVG(processing_time_ms) as avg_processing_time_ms,
    SUM(ISNULL(input_tokens, 0)) as total_input_tokens,
    SUM(ISNULL(output_tokens, 0)) as total_output_tokens,
    SUM(ISNULL(total_tokens, 0)) as total_tokens_used,
    SUM(ISNULL(cost_estimate, 0)) as estimated_daily_cost
FROM docketwatch.dbo.gemini_api_log
GROUP BY CAST(call_timestamp AS DATE), script_name, model_name;
