import re
import json
import datetime
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import CellFormat, Color, format_cell_range, TextFormat
from extract_pics import extract_steps_pics_for_cluster

# === SETTINGS ===
USE_EXISTING_TAB = False
EXISTING_TAB_NAME = "TestCases"
HTML_FILES = ['allclusters.html', 'index.html']
ENABLE_FALLBACK_PICS = True
FALLBACK_PICS_FILE = "fallback_pics.json"
USE_EXTERNAL_FUNCTION_FOR_STEPS_PICS = False  # Set to False to disable using the external function

def extract_test_cases_and_pics(html_files, fallback_pics_dict):
    all_results = []
    special_clusters = ['Device Discovery Test Plan']  # Add more clusters as needed

    for html_file in html_files:
        with open(html_file, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')

        results = []
        current_cluster = ""
        special_pics_cache = dict(extract_steps_pics_for_cluster(html_file, None))

        for tag in soup.find_all(['h1', 'h4']):
            if tag.name == 'h1':
                strong = tag.find('strong')
                new_cluster = strong.get_text(strip=True) if strong else tag.get_text(strip=True)
                new_cluster = re.sub(r'\s*(Test\s*Plan|Tests?)\s*$', '', new_cluster, flags=re.IGNORECASE).strip()
                if new_cluster != current_cluster:
                    current_cluster = new_cluster
                    #print(f"🔄 New cluster: {current_cluster}")

            if tag.name == 'h4':
                tag_id = tag.get('id', '')
                if any(tag_id.startswith(prefix) for prefix in ['_features', '_attributes', '_manual_controllable',
                                                                '_commands_received', '_commands_generated',
                                                                '_events']):
                    continue

                text = tag.get_text(strip=True)
                match = re.search(r'\[TC-([^\]]+)\]\s*(.+)', text)
                if match:
                    tc_id = f'TC-{match.group(1)}'
                    tc_desc = match.group(2)

                    # High-Level PICS
                    h5 = tag.find_next(lambda tag: tag.name == "h5" and tag.get("id", "").startswith("_pics"))
                    high_pics = []
                    if h5:
                        ulist = h5.find_next("div", class_="ulist")
                        if ulist:
                            lines = ulist.get_text(separator="\n").splitlines()
                            pics_flat = []
                            for line in lines:
                                line = re.sub(r'\([^)]*\)', '', line).strip()
                                parts = re.split(r'(?=!)', line)
                                pics_flat.extend([p.strip() for p in parts if p.strip()])
                            high_pics = pics_flat

                    # Steps PICS
                    steps_pics = []

                    if current_cluster in special_clusters:
                        if USE_EXTERNAL_FUNCTION_FOR_STEPS_PICS:
                            # Use the external function if the flag is True
                            steps_pics = special_pics_cache.get(current_cluster, "").split(", ")
                        else:
                            # Use the original steps pics extraction logic for these clusters if the flag is False
                            h5_proc = tag.find_next(
                                lambda tag: tag.name == "h5" and tag.get("id", "").startswith("_test_procedure"))
                            if h5_proc:
                                table = h5_proc.find_next("table")
                                if table:
                                    rows = table.find_all("tr")
                                    if rows:
                                        headers = [th.get_text(strip=True).upper() for th in
                                                   rows[0].find_all(["td", "th"])]
                                        pics_idx = next((i for i, h in enumerate(headers) if "PICS" in h), -1)
                                        if pics_idx != -1:
                                            for row in rows[1:]:
                                                cells = row.find_all(["td", "th"])
                                                if len(cells) > pics_idx:
                                                    cell_text = cells[pics_idx].get_text(separator="\n").strip()
                                                    matches = re.findall(r'(!?[A-Z0-9]+\.[\w\-\.]+)', cell_text)
                                                    steps_pics.extend(matches)

                                # Fallback if no table
                                if not steps_pics:
                                    sib = h5_proc.find_next_sibling()
                                    while sib:
                                        if sib.name == "p":
                                            matches = re.findall(r'(!?[A-Z0-9]+\.[\w\-\.]+)', sib.get_text())
                                            steps_pics.extend(matches)
                                        if sib.name in ["h1", "h2", "h3", "h4", "h5"]:
                                            break
                                        sib = sib.find_next_sibling()

                    else:
                        # For other clusters, use the original logic without external function
                        h5_proc = tag.find_next(
                            lambda tag: tag.name == "h5" and tag.get("id", "").startswith("_test_procedure"))
                        if h5_proc:
                            table = h5_proc.find_next("table")
                            if table:
                                rows = table.find_all("tr")
                                if rows:
                                    headers = [th.get_text(strip=True).upper() for th in rows[0].find_all(["td", "th"])]
                                    pics_idx = next((i for i, h in enumerate(headers) if "PICS" in h), -1)
                                    if pics_idx != -1:
                                        for row in rows[1:]:
                                            cells = row.find_all(["td", "th"])
                                            if len(cells) > pics_idx:
                                                cell_text = cells[pics_idx].get_text(separator="\n").strip()
                                                matches = re.findall(r'(!?[A-Z0-9]+\.[\w\-\.]+)', cell_text)
                                                steps_pics.extend(matches)

                            # Fallback if no table
                            if not steps_pics:
                                sib = h5_proc.find_next_sibling()
                                while sib:
                                    if sib.name == "p":
                                        matches = re.findall(r'(!?[A-Z0-9]+\.[\w\-\.]+)', sib.get_text())
                                        steps_pics.extend(matches)
                                    if sib.name in ["h1", "h2", "h3", "h4", "h5"]:
                                        break
                                    sib = sib.find_next_sibling()

                    # Always append fallback PICS
                    fallback = fallback_pics_dict.get(tc_id, [])
                    all_steps_pics = list(dict.fromkeys(steps_pics + fallback))

                    # Append the results for this test case
                    results.append((current_cluster, tc_id, tc_desc, ", ".join(high_pics), ", ".join(all_steps_pics)))

        all_results.extend(results)
        print(f"✅ Extracted {len(results)} test cases from {html_file}")
    return all_results

def connect_to_sheet(sheet_url, creds_json='credentials.json'):
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(creds_json, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(sheet_url)

    if USE_EXISTING_TAB:
        try:
            worksheet = spreadsheet.worksheet(EXISTING_TAB_NAME)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=EXISTING_TAB_NAME, rows="1000", cols="5")
    else:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        worksheet = spreadsheet.add_worksheet(title=f"TestCases_{timestamp}", rows="1000", cols="5")
    return worksheet

def update_sheet_with_test_cases(sheet, test_case_data):
    header = [["Cluster Name", "Test Case ID", "Test Case Description", "High-Level PICS", "Steps PICS"]]
    sheet.update(range_name= 'A1', values= header + test_case_data)
    format_cell_range(sheet, 'A1:E1', CellFormat(
        backgroundColor=Color(0.8, 0.9, 1),
        textFormat=TextFormat(bold=True),
        horizontalAlignment='CENTER'
    ))

if __name__ == '__main__':
    sheet_url = 'https://docs.google.com/spreadsheets/d/11VFIumfm5xpB8YhKtGi8esbJ8KlHrRJ-WbQj4I6deyA/edit#gid=0'
    creds_file = 'credentials.json'

    fallback_pics_dict = {}
    if ENABLE_FALLBACK_PICS:
        try:
            with open(FALLBACK_PICS_FILE, 'r') as f:
                fallback_pics_dict = json.load(f)
                print("✅ Fallback PICS loaded.")
        except FileNotFoundError:
            print("⚠️ Fallback PICS file not found. Continuing without it.")
    else:
        print("ℹ️ Fallback PICS disabled.")

    test_data = extract_test_cases_and_pics(HTML_FILES, fallback_pics_dict)
    sheet = connect_to_sheet(sheet_url, creds_file)
    update_sheet_with_test_cases(sheet, test_data)
    print(f"✅ Uploaded {len(test_data)} test cases to tab: {sheet.title}")
