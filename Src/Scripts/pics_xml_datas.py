import re
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import CellFormat, Color, format_cell_range, TextFormat

# === SETTINGS ===
HTML_FILES = ['allclusters.html', 'index.html']
CREDS_FILE = 'credentials.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/11VFIumfm5xpB8YhKtGi8esbJ8KlHrRJ-WbQj4I6deyA/edit#gid=0'

SECTIONS = {
    'Server/Client PICS': ('h3', '_role'),
    'Features': ('h4', '_features'),
    'Attributes': ('h4', '_attributes'),
    'Manual Controllable': ('h4', '_manual_controllable'),
    'Commands Received': ('h4', '_commands_received'),
    'Commands Generated': ('h4', '_commands_generated'),
    'Events': ('h4', '_events'),
    'PIXIT Definition': ('h2', '_pixit_definition')
}

def extract_section_tables(soup, html_file):
    data_by_section = {key: {'header': [], 'rows': []} for key in SECTIONS}
    cluster_name = None

    ref_doc = html_file

    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        if tag.name == 'h1':
            strong = tag.find('strong')
            if strong:
                cluster_name = strong.get_text(strip=True)

        for section_name, (tag_type, id_prefix) in SECTIONS.items():
            if tag.name == tag_type and tag.get('id', '').startswith(id_prefix):
                table = tag.find_next('table')
                if not table:
                    continue

                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue

                section_heading_text = tag.get_text(strip=True)

                header_cells = rows[0].find_all(['th', 'td'])[:3]
                header = ["Cluster Name", header_cells[0].get_text(strip=True), "PICS name", "Reference"]
                if len(header_cells) > 1:
                    header += [cell.get_text(strip=True) for cell in header_cells[1:] if cell != header_cells[0]]
                data_by_section[section_name]['header'] = header

                reference = f"{section_heading_text} - {ref_doc}"

                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])[:3]
                    if not cells:
                        continue

                    # Extract main PICS and PICS name from first column
                    pics_cell = cells[0].get_text(strip=True)
                    pics_main = re.sub(r'\(.*?\)', '', pics_cell).strip()
                    pics_name_match = re.search(r'\((.*?)\)', pics_cell)
                    pics_name = pics_name_match.group(1).strip() if pics_name_match else ''

                    remaining_values = [cell.get_text(strip=True) for cell in cells[1:]]
                    row_data = [cluster_name, pics_main, pics_name, reference] + remaining_values
                    data_by_section[section_name]['rows'].append(row_data)

    return data_by_section

def clean_pics_name(pics_name):
    return re.sub(r'\(.*?\)', '', pics_name).strip()

def connect_to_google_sheet(sheet_url, creds_file):
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_url(sheet_url)

def update_google_sheet(spreadsheet, section_name, data):
    try:
        worksheet = spreadsheet.worksheet(section_name)
        worksheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=section_name, rows="1000", cols="10")

    rows = [data['header']] + data['rows']
    worksheet.update('A1', rows)

    format_cell_range(worksheet, 'A1:{}1'.format(chr(65 + len(data['header']) - 1)), CellFormat(
        backgroundColor=Color(0.85, 0.92, 0.98),
        textFormat=TextFormat(bold=True),
        horizontalAlignment='CENTER'
    ))

def main():
    all_data = {section: {'header': [], 'rows': []} for section in SECTIONS}

    for html_file in HTML_FILES:
        with open(html_file, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')
            section_data = extract_section_tables(soup, html_file)

            for section in SECTIONS:
                if section_data[section]['rows']:
                    all_data[section]['header'] = section_data[section]['header']
                    all_data[section]['rows'].extend(section_data[section]['rows'])

    spreadsheet = connect_to_google_sheet(SHEET_URL, CREDS_FILE)

    for section_name, data in all_data.items():
        if data['rows']:
            update_google_sheet(spreadsheet, section_name, data)
            print(f"✅ Uploaded {len(data['rows'])} rows to sheet: {section_name}")

if __name__ == '__main__':
    main()
