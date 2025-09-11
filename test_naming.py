#!/usr/bin/env python3
"""Test RSS trigger document naming conventions"""

import sys
import os
import re
from urllib.parse import urlparse, parse_qs

# Test the extract_doc_id_from_url function
def extract_doc_id_from_url(url: str):
    if not url:
        return None
    qs = parse_qs(urlparse(url).query)
    for key in ("doc1", "document_id", "DLS_id", "docid"):
        if key in qs and qs[key]:
            return qs[key][0]
    
    # Also try regex patterns for doc1 URLs
    patterns = [
        r'doc1/(\d+)',
        r'document_id=(\d+)', 
        r'DLS_id=(\d+)',
        r'de_seq_num=(\d+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# Test various PACER URL formats
test_urls = [
    "https://ecf.cacd.uscourts.gov/doc1/12345678",
    "https://ecf.nysd.uscourts.gov/cgi-bin/show_case_doc?de_seq_num=142&caseid=1:23-cv-01234",
    "https://ecf.flsd.uscourts.gov/doc1/803396024",
    "https://example.com/document_id=987654",
    "https://example.com/DLS_id=555666",
    "https://invalid.url/no_doc_id"
]

print("Testing document ID extraction:")
for url in test_urls:
    doc_id = extract_doc_id_from_url(url)
    filename = f"E{doc_id}.pdf" if doc_id else "No doc_id found"
    rel_path = f"cases\\216895\\{filename}" if doc_id else "N/A"
    print(f"URL: {url}")
    print(f"  doc_id: {doc_id}")
    print(f"  filename: {filename}")
    print(f"  rel_path: {rel_path}")
    print()

# Test event number fallback
print("Testing event number fallback:")
for event_no in [142, 1, 999]:
    doc_id = f"{event_no:08d}"
    filename = f"E{doc_id}.pdf"
    rel_path = f"cases\\107799\\{filename}"
    print(f"Event No: {event_no}")
    print(f"  doc_id: {doc_id}")
    print(f"  filename: {filename}")
    print(f"  rel_path: {rel_path}")
    print()
