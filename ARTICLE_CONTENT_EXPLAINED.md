# What Content Does the AI Review to Write Articles?

## Short Answer
**The AI reviews ONE DOCUMENT at a time**, not all case events or full case history.

For each document, it receives:
1. **Case Overview** - Brief case summary (first 2,000 chars from `cases.summarize`)
2. **Event Details** - Event date & description for this specific document
3. **Document Text** - The actual PDF content (up to ~10,000 chars)

---

## Detailed Breakdown

### Input #1: Case Overview (Context)
```sql
SELECT c.summarize FROM cases c WHERE c.id = ?
```

- **Purpose:** Provides background context about the case
- **Size:** First 2,000 characters only
- **Content:** High-level case summary (what's this case about?)
- **Example:** "Celebrity defamation lawsuit filed by Actor X against Tabloid Y over 2023 article claiming drug use..."

### Input #2: Event Information
```sql
SELECT 
    e.event_description,
    e.event_date
FROM case_events e
WHERE e.id = p.fk_case_event
```

- **Purpose:** What happened on this specific date
- **Size:** First 500 characters
- **Content:** Event description (e.g., "Motion for Summary Judgment")
- **Example:** "Motion Filed - Defendant seeks summary judgment"

### Input #3: Document Text (The Main Content)
```python
# From documents table
SELECT p.ocr_text FROM documents p WHERE p.doc_uid = ?

# OR extracted from PDF if ocr_text is empty
pdf_to_text(pdf_path)  # Uses PyPDF2 or Tesseract OCR
```

- **Purpose:** The actual content to analyze
- **Size:** Up to 10,000 characters (with smart truncation)
- **Content:** The full text of the PDF document
- **Truncation Strategy:** 
  - If over 10,000 chars: Keep first 8,000 + last 2,000 (preserves beginning and end)

---

## The AI Prompt Structure

```
SYSTEM: You are a senior legal journalist...

### CASE OVERVIEW
The following is a high-level case summary to help you contextualize the document:

[First 2,000 chars from cases.summarize]

### EVENT
Date: 2025-10-12
Description: Motion for Summary Judgment

### DOCUMENT TEXT
[Up to 10,000 chars from the PDF]

--- END OF DOCUMENT ---
```

---

## What It Does NOT Review

❌ **All case events** - Only reviews the ONE document being processed  
❌ **Full case history** - Only gets brief overview (2,000 chars)  
❌ **Other documents** - Each document analyzed independently  
❌ **Previous articles** - No memory of past summaries  

---

## Article Evolution Logic

### First Document of the Day
```
9:00 AM: Motion filed
AI Input:
  - Case overview: "Celebrity defamation case..."
  - Event: "Motion for Summary Judgment"
  - Document: [Motion text]
  
Result: Creates NEW article
  - story_headline: "Celebrity Lawsuit Takes Major Turn"
  - version: 1
  - articleStatus: Pending
```

### Second Document Same Day
```
2:00 PM: Opposition filed (same case, same day)
AI Input:
  - Case overview: "Celebrity defamation case..."
  - Event: "Opposition to Motion"
  - Document: [Opposition text]
  
Result: UPDATES EXISTING article
  - story_headline: "Celebrity Lawsuit Explodes With New Evidence"
  - version: 2 (incremented!)
  - articleStatus: Pending (still evolving)
```

**Key Point:** Each document gets its own AI analysis with fresh context, but they update the SAME article for that case/day.

---

## Database Flow

### Query for Case Context
```sql
-- Get case overview for context
SELECT 
    c.summarize,                          -- Case background
    e.event_description,                   -- What happened
    e.event_date,                          -- When it happened
    p.ocr_text,                            -- Document content
    p.fk_case                              -- Case ID
FROM docketwatch.dbo.documents p
LEFT JOIN docketwatch.dbo.case_events e ON e.id = p.fk_case_event
JOIN docketwatch.dbo.cases c ON c.id = p.fk_case
WHERE p.doc_uid = ?
```

### After AI Analysis
```python
# Parse AI response
parsed = {
    'story_headline': "Celebrity Lawsuit Takes Major Turn",
    'story_sub_head': "Summary judgment motion filed",
    'story_body': "In a dramatic development...",
    'event_summary': "Plaintiff filed motion...",
    'is_newsworthy': True,
    'key_details': [...],
    'whats_next': "Defendant has 30 days..."
}

# Save to documents table (legacy)
UPDATE documents SET 
    story_headline = ?,
    story_body = ?,
    ...
WHERE doc_uid = ?

# Save to articles table (new - Phase 4)
EXEC upsert_article_for_event
    @fk_case = ?,
    @article_date = TODAY,
    @story_headline = ?,
    @story_body = ?,
    ...
```

---

## Size Limits & Truncation

### Case Overview
```python
case_summary = (case_summary or "")[:2000]  # Max 2,000 chars
```

### Event Description
```python
event_desc = (event_desc or "")[:500]  # Max 500 chars
```

### Document Text
```python
body_text = f"Date: {event_date}\nDescription: {event_desc}\n\n{pdf_text}"

if len(body_text) > 10000:
    # Keep beginning and end
    body_text = body_text[:8000] + "\n...\n" + body_text[-2000:]
```

### Total AI Input
```python
full_prompt = RULES.replace("{CASE_OVERVIEW}", case_summary)
                   .replace("{PDF_BODY}", body_text)

# Final limit
alt_model.generate_content(full_prompt[:16000])  # Max ~16,000 chars
```

---

## Example: Real Processing Flow

### Document 1: Complaint Filed
```
Input:
  Case Overview: "John Doe vs. Jane Smith defamation case filed 2024..."
  Event: "Complaint Filed" (2025-10-15)
  Document: [25-page complaint with allegations]

AI Output:
  Headline: "Celebrity Files $10M Defamation Lawsuit"
  Body: "Actor John Doe filed a lawsuit today..."
  
Database:
  ✓ Documents table updated
  ✓ Article created (version 1, Pending)
```

### Document 2: Answer Filed (Same Day)
```
Input:
  Case Overview: "John Doe vs. Jane Smith defamation case filed 2024..."
  Event: "Answer Filed" (2025-10-15)  ← Same day!
  Document: [Answer with affirmative defenses]

AI Output:
  Headline: "Defendant Fires Back in Celebrity Defamation Case"
  Body: "Jane Smith filed a scorching response today..."
  
Database:
  ✓ Documents table updated (new row)
  ✓ Article UPDATED (version 2, still Pending) ← Same article!
```

---

## Key Insights

### ✅ What Makes This Work
1. **Fresh AI analysis** per document (not cached)
2. **Case context** helps AI understand significance
3. **Single article** per case per day (evolves with new info)
4. **Version tracking** shows article evolution
5. **Independent processing** (each document stands alone)

### 🎯 Design Philosophy
- **Document-centric:** Focus on what THIS document says
- **Context-aware:** Brief case overview provides perspective
- **Evolving story:** Multiple docs update same article
- **Journalist-focused:** Written for reporters, not lawyers

### 📊 Performance Trade-offs
- **Pro:** Fast processing (each doc analyzed separately)
- **Pro:** Fresh perspective (AI doesn't carry forward biases)
- **Con:** No memory of previous analysis
- **Con:** May repeat information across versions

---

## Summary Table

| Input | Source | Size Limit | Purpose |
|-------|--------|-----------|---------|
| Case Overview | `cases.summarize` | 2,000 chars | Background context |
| Event Description | `case_events.event_description` | 500 chars | What happened |
| Event Date | `case_events.event_date` | 10 chars | When it happened |
| Document Text | `documents.ocr_text` or PDF | ~10,000 chars | Main content to analyze |
| **Total AI Input** | Combined prompt | ~16,000 chars | Full context for analysis |

---

## Bottom Line

**The AI reviews:**
- ✅ One document at a time
- ✅ Brief case overview for context
- ✅ Event details (what/when)
- ✅ Full document text (up to 10K chars)

**The AI does NOT review:**
- ❌ All case events
- ❌ Full case history
- ❌ Other documents
- ❌ Previous articles

**Result:** Each document gets fresh AI analysis, but updates the same evolving article for that case/day.
