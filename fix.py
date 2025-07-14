from bs4 import BeautifulSoup
import csv

def extract_case_data_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    rows = soup.find_all('tr')
    results = []

    for row in rows:
        a_tag = row.find('a', href=True)
        if a_tag:
            case_number = a_tag.get_text(strip=True)
            href = a_tag['href']
            results.append((case_number, href))

    return results

# Use raw strings to avoid escape sequence issues
input_file_path = r'u:\docketwatch\python\fix.txt'
output_file_path = r'u:\docketwatch\python\case_data.csv'

# Read the input HTML
with open(input_file_path, 'r', encoding='utf-8') as file:
    html_data = file.read()

# Extract data
case_data = extract_case_data_from_html(html_data)

# Write to CSV
with open(output_file_path, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['Case Number', 'Href'])  # Header row
    writer.writerows(case_data)

print(f"Saved {len(case_data)} rows to {output_file_path}")
