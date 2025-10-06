#!/usr/bin/env python3
"""
Backfill PACER case_events.event_url when NULL.

Strategy (ordered):
1. If the event has related document(s) (documents.fk_case_event) with a non-null pdf_url, use the most recent pdf_url.
2. Else, derive a base court URL from another event in the same case that already has an event_url (truncate at '.gov').
   - If found, set event_url to that base (acts as placeholder rather than leaving NULL).
3. Else, skip and report.

Features:
- Dry run mode (default) prints intended updates without committing.
- --commit flag applies changes.
- Summary report at end.
- Minimal logging to stdout. Can be adapted to use scraper_base.log_message if desired.

Usage:
  python backfill_event_urls.py            # dry run
  python backfill_event_urls.py --commit   # apply updates

Assumptions:
- DSN named 'Docketwatch' is configured.
- documents.pdf_url is a valid replacement for event_url when present.
- Acceptable to store base court URL (e.g. https://ecf.cacd.uscourts.gov) if no direct event-specific URL is recoverable.

Enhancements (future):
- Attempt reconstruction of specific docket entry URL patterns if rules become available.
- Log to task_runs/task_runs_log for auditing.
"""
import sys
import re
import pyodbc
from datetime import datetime

# Optional flags:
#   --commit      Actually write changes
#   --verify      After each update, re-select the row to confirm persisted
#   --limit=N     Only process first N targets (for testing)
#   --show-sql    Print the UPDATE statement parameters

DSN = "Docketwatch"

RAW_ARGS = [a.strip() for a in sys.argv[1:]]
USE_COMMIT = any(a.lower() == "--commit" for a in RAW_ARGS)
VERIFY = any(a.lower() == "--verify" for a in RAW_ARGS)
SHOW_SQL = any(a.lower() == "--show-sql" for a in RAW_ARGS)
LIMIT = None
for a in RAW_ARGS:
    if a.lower().startswith("--limit="):
        try:
            LIMIT = int(a.split("=",1)[1])
        except ValueError:
            pass

def connect():
    conn = pyodbc.connect(f"DSN={DSN};TrustServerCertificate=yes;")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
    conn.setencoding(encoding='utf-8')
    return conn, conn.cursor()

BASE_TRUNC_RE = re.compile(r"^(.*?\.gov)")  # capture up through first .gov

def extract_base(url: str) -> str | None:
    if not url:
        return None
    m = BASE_TRUNC_RE.search(url)
    return m.group(1) if m else None

def preload_case_bases(cur):
    """Return mapping case_id -> base_url derived from any non-null event_url in that case."""
    cur.execute("""
        SELECT fk_cases, event_url
        FROM docketwatch.dbo.case_events
        WHERE event_url IS NOT NULL
    """)
    bases = {}
    for case_id, evt_url in cur.fetchall():
        if case_id in bases:
            continue
        base = extract_base(evt_url)
        if base:
            bases[case_id] = base
    return bases

def fetch_targets(cur):
    cur.execute("""
        SELECT e.id, e.fk_cases, e.event_no
        FROM docketwatch.dbo.case_events e
        INNER JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id
        WHERE e.event_url IS NULL AND c.fk_tool = 2
        ORDER BY e.id
    """)
    return cur.fetchall()

def find_doc_url(cur, event_id):
    cur.execute("""
        SELECT TOP 1 pdf_url
        FROM docketwatch.dbo.documents
        WHERE fk_case_event = ? AND pdf_url IS NOT NULL
        ORDER BY date_downloaded DESC
    """, (event_id,))
    row = cur.fetchone()
    return row.pdf_url if row else None

def find_case_doc_url(cur, case_id):
    """Fallback: any document for the case (not just tied to event) to harvest a pdf_url base."""
    cur.execute("""
        SELECT TOP 1 pdf_url
        FROM docketwatch.dbo.documents
        WHERE fk_case = ? AND pdf_url IS NOT NULL
        ORDER BY date_downloaded DESC
    """, (case_id,))
    row = cur.fetchone()
    return row.pdf_url if row else None

def find_case_pacer_base(cur, case_id):
    """Attempt to derive base from court pacer_url via cases -> courts join (best effort)."""
    try:
        cur.execute("""
            SELECT TOP 1 crt.pacer_url
            FROM docketwatch.dbo.cases c
            JOIN docketwatch.dbo.courts crt ON c.fk_court = crt.id
            WHERE c.id = ? AND crt.pacer_url IS NOT NULL
        """, (case_id,))
        row = cur.fetchone()
        if row and row.pacer_url:
            return extract_base(row.pacer_url)
    except Exception:
        return None
    return None


def count_nulls(cur):
    cur.execute("""SELECT COUNT(*) FROM docketwatch.dbo.case_events e INNER JOIN docketwatch.dbo.cases c ON e.fk_cases = c.id WHERE e.event_url IS NULL AND c.fk_tool = 2""")
    return cur.fetchone()[0]

def main():
    conn, cur = connect()
    print(f"Started backfill at {datetime.now():%Y-%m-%d %H:%M:%S} (commit={USE_COMMIT}, verify={VERIFY}, limit={LIMIT})")

    before_nulls = count_nulls(cur)
    print(f"Initial NULL event_url count: {before_nulls}")

    case_bases = preload_case_bases(cur)
    targets = fetch_targets(cur)
    print(f"Found {len(targets)} case_events with NULL event_url.")

    updated = 0
    doc_based = 0
    base_based = 0
    skipped = 0

    processed = 0
    for event_id, case_id, event_no in targets:
        if LIMIT is not None and processed >= LIMIT:
            print(f"Limit {LIMIT} reached, stopping early.")
            break
        doc_url = find_doc_url(cur, event_id)
        if doc_url:
            new_url = doc_url.strip()
            source = "doc"
        else:
            base = case_bases.get(case_id)
            if base:
                new_url = base
                source = "base"
            else:
                # Additional fallbacks
                case_doc = find_case_doc_url(cur, case_id)
                if case_doc:
                    new_url = case_doc.strip()
                    source = "case_doc"
                else:
                    pacer_base = find_case_pacer_base(cur, case_id)
                    if pacer_base:
                        new_url = pacer_base
                        source = "pacer_base"
                    else:
                        skipped += 1
                        print(f"SKIP event_id={event_id} case_id={case_id} event_no={event_no} (no doc_url, no base, no case_doc, no pacer_base)")
                        continue

        # Skip if the derived URL is blank after stripping
        if not new_url:
            skipped += 1
            print(f"SKIP event_id={event_id} case_id={case_id} event_no={event_no} (derived empty URL)")
            continue

        print(f"UPDATE event_id={event_id} case_id={case_id} event_no={event_no} source={source} -> {new_url}")
        if USE_COMMIT:
            cur.execute("""
                UPDATE docketwatch.dbo.case_events
                SET event_url = ?
                WHERE id = ? AND event_url IS NULL
            """, (new_url, event_id))
            if cur.rowcount == 0:
                print(f"NOTE: No update applied (rowcount=0) for event_id={event_id} (maybe already set concurrently)")
            elif SHOW_SQL:
                print(f"  Applied UPDATE rowcount={cur.rowcount}")
            if VERIFY:
                cur.execute("SELECT event_url FROM docketwatch.dbo.case_events WHERE id = ?", (event_id,))
                v = cur.fetchone()
                persisted = v and v[0]
                print(f"  VERIFY event_id={event_id} stored_event_url={persisted}")
        updated += 1
        if source in ("doc", "case_doc"):
            doc_based += 1
        else:  # base, pacer_base
            base_based += 1
        processed += 1

    if USE_COMMIT and updated:
        conn.commit()
        after_nulls = count_nulls(cur)
        print(f"Post-commit NULL event_url count: {after_nulls} (delta={before_nulls - after_nulls})")
    else:
        after_nulls = count_nulls(cur)
        print(f"(Dry run) NULL event_url count still: {after_nulls}")

    print("\nSummary:")
    print(f"  Updated: {updated}")
    print(f"    From documents: {doc_based}")
    print(f"    From base court URL: {base_based}")
    print(f"  Skipped (no data): {skipped}")
    print(f"  Mode: {'COMMIT' if USE_COMMIT else 'DRY RUN'}")
    if USE_COMMIT:
        print(f"  NULL count before/after: {before_nulls} -> {after_nulls}")

    cur.close(); conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
