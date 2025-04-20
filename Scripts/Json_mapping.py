import gspread
import json

# Authenticate with your service account
gc = gspread.service_account(filename='credentials.json')

# Open the first Google Sheet (Test Case data with Steps PICS)
sheet1_url = 'https://docs.google.com/spreadsheets/d/11VFIumfm5xpB8YhKtGi8esbJ8KlHrRJ-WbQj4I6deyA/edit?gid=922332307#gid=922332307'
sheet1 = gc.open_by_url(sheet1_url)
worksheet1 = sheet1.worksheet('TestCases_2025-04-20_21-59-37')  # Replace with actual tab name

# Open the second Google Sheet (Certification status)
sheet2_url = 'https://docs.google.com/spreadsheets/d/13Pgom27-yQ-Wyvuh4wTeBEr_R2SEt9evhJGiUVnc4p0/edit?gid=0#gid=0'
sheet2 = gc.open_by_url(sheet2_url)
worksheet2 = sheet2.worksheet('Sheet1')  # Replace with actual tab name

# Fetch data from both sheets
data_1 = worksheet1.get_all_records()
data_2 = worksheet2.get_all_records()

# Clean and deduplicate comma-separated PICS fields
def clean_pics_data(pics_str):
    seen = set()
    cleaned = []
    for p in pics_str.split(','):
        item = p.strip()
        if item and item not in seen:
            seen.add(item)
            cleaned.append(item)
    return cleaned


# Generate the JSON structure
def generate_json(data_1, data_2):
    result = {}

    for row in data_1:
        tc_id = row['Test Case ID']
        cluster_name = row['Cluster Name']
        tc_description = row['Test Case Description']
        pics_data = row.get('High-Level PICS', '')
        steps_pics_data = row.get('Steps PICS', '')

        print(f" {tc_id} - Steps PICS: '{steps_pics_data}'")

        # Clean both fields
        cleaned_pics = clean_pics_data(pics_data)
        cleaned_steps_pics = clean_pics_data(steps_pics_data)

        # Match TC ID in second sheet to get Certification Status
        certification_status = next(
            (item['Certification Status'] for item in data_2 if item['Test Case ID'] == tc_id),
            'Not Executable'
        )

        result[tc_id] = {
            "PICS": cleaned_pics,
            "stepsPICS": cleaned_steps_pics,
            "tcDescription": tc_description,
            "clusterName": cluster_name,
            "notes": "",
            "CertificationStatus": certification_status,
            "cert": "true" if certification_status == "Executable" else "false"
        }

    return result

# Generate JSON and write to file
json_data = generate_json(data_1, data_2)

with open('Matter_PICS__TC_Mapping_V_40_1_5.json', 'w') as f:
    json.dump(json_data, f, indent=4)

print("✅ JSON file generated successfully.")
