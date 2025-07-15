import re
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.utils import rowcol_to_a1


# -------- Helper Functions --------

def load_json(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


def setup_gspread(credentials_file, scope, spreadsheet_url):
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    spreadsheet_id = spreadsheet_url.split("/d/")[1].split("/")[0]
    return client.open_by_key(spreadsheet_id)


def create_sc_variable_set(sheet):
    return {row['Variable'].strip() for row in sheet.get_all_records()}


def create_features_map(sheet):
    features = {}
    for row in sheet.get_all_records():
        pics_name = row.get("PICS name", "").strip()
        variable = row.get("Variable", "").strip()
        if pics_name and variable:
            if pics_name not in features:
                features[pics_name] = []
            features[pics_name].append(variable)
    return features


def find_matching_feature_variable(prefix, pics_name, features_map):
    candidates = features_map.get(pics_name, [])
    for var in candidates:
        if var.startswith(prefix + "."):
            return var
    return ""


def find_all_matching_feature_variables(prefix, feature_names, features_data):
    results = []
    for feature in feature_names:
        for row in features_data:
            if row.get("PICS name", "").strip() == feature.strip():
                variable = row.get("Variable", "").strip()
                if not prefix or variable.startswith(prefix + "."):
                    results.append(variable)
    return results


import re


def clean_and_map_expression(expression, features_data, variable_context):
    # Step 1: Remove labels in parentheses (e.g., (PIR), (US), etc.)
    expression = re.sub(r"\([^)]+\)", "", expression)

    # Step 2: Tokenize the expression respecting logical operators and brackets
    tokens = re.findall(r'!?\w+(?:\.\w+)*|[&|()!]', expression)

    result = []
    for token in tokens:
        # Handle logical operators and parentheses as is
        if token in ['&', '|', '(', ')']:
            result.append(token)
        elif token.startswith("!"):
            # Handle negated variables like !OCC.S.F01(PIR)
            base = token[1:]
            mapped = [
                row.get("Variable", "").strip()
                for row in features_data
                if row.get("PICS name", "").strip() == base
            ]
            prefix = variable_context.split('.')[0:2]  # e.g., ['OCC', 'S']
            filtered = [m for m in mapped if m.startswith('.'.join(prefix))]
            result.append("!" + (filtered[0] if filtered else base))
        else:
            # Handle regular variables like OCC.S.F01
            mapped = [
                row.get("Variable", "").strip()
                for row in features_data
                if row.get("PICS name", "").strip() == token
            ]
            prefix = variable_context.split('.')[0:2]
            filtered = [m for m in mapped if m.startswith('.'.join(prefix))]
            result.append(filtered[0] if filtered else token)

    # Return the cleaned and mapped expression as a string
    return ' '.join(result)


def process_row(mo_val, rules, sc_variables, features_map, features_data, variable_context):
    original_val = mo_val.strip()
    mo_val = original_val  # preserve full string initially

    # Step 0a: Handle features in brackets (e.g., EEM.S: (IMPE & CUME))
    if rules.get("remove_suffix_in_brackets", False):
        bracket_match = re.search(r"\((.*?)\)", mo_val)
        if bracket_match and ":" in mo_val:
            suffix_content = bracket_match.group(1)
            features = [f.strip() for f in re.split(r"&|\|", suffix_content)]
            prefix = mo_val.split(":")[0].strip()
            matched_vars = find_all_matching_feature_variables(prefix, features, features_data)
            if matched_vars:
                sep = " & " if "&" in suffix_content else " | "
                return [sep.join(matched_vars)]
        # Remove the parentheses and their content
        mo_val = re.sub(r"\(.*?\)", "", mo_val).strip()

    # Step 0b: Handle cases like [MACCNT], MACCNT, or [PIN | RID]
    if "|" in mo_val:
        # Remove outer brackets if present
        parts = re.sub(r"^\[|\]$", "", mo_val).split("|")
        features = [p.strip().strip("[]") for p in parts]
        matched_vars = find_all_matching_feature_variables("", features, features_data)
        if matched_vars and len(matched_vars) == len(features):
            return [" | ".join(f"{v}" for v in matched_vars)]

    # Step 0c: Handle single feature in brackets or without (e.g., [MACCNT], MACCNT)
    cleaned_feature = mo_val.strip("[]").strip(".").strip()
    for row in features_data:
        if row.get("PICS name", "").strip() == cleaned_feature:
            variable = row.get("Variable", "").strip()
            if original_val.startswith("[") and original_val.endswith("]"):
                return [f"[{variable}]"]
            return [variable]

    # Step 0d: Handle full PICS variable with (XXX): M/O → [PICSID]
    match_full_var_with_paren = re.match(r"^([A-Z]+\.\w+\.F\d+)\(.*?\):\s*[MO]$", mo_val)
    if match_full_var_with_paren:
        var_id = match_full_var_with_paren.group(1)
        return [f"[{var_id}]"]

    # Step 1: Direct value M or O
    if mo_val in rules["direct_values"]:
        return [mo_val]

    # Step 2: Server/Client and Feature Mapping Handling
    if ":" in mo_val:
        try:
            prefix, value = [x.strip() for x in mo_val.split(":", 1)]

            # Server/Client direct value handling
            if rules["server_client_prefix_handling"] and prefix in sc_variables and value in rules["direct_values"]:
                return [value]

            # Feature Mapping Handling
            if rules["feature_mapping_handling"]:
                matched_variable = find_matching_feature_variable(prefix, value, features_map)
                if matched_variable:
                    return [matched_variable]

            return [""]
        except Exception as e:
            print(f"⚠️ Error processing row '{mo_val}': {e}")
            return [""]

    # Step 3: Handle expressions with parentheses and logical operators
    # Clean and map expression if it contains logical structures or brackets
    if "[" in mo_val:
        # Process the full expression with logical operators and parentheses
        return [clean_and_map_expression(mo_val, features_data, variable_context)]

    # Step 4: Reduced prefix match
    parts = mo_val.split(".")
    if len(parts) >= 2:
        reduced_prefix = ".".join(parts[:2])
        if reduced_prefix in sc_variables:
            print(f"✅ Matched reduced prefix: {reduced_prefix}, keeping full value: {mo_val}")
            return [mo_val]

    print(f"❌ No match for: {original_val}")
    return [""]


# -------- Main Code --------

# Load configuration and credentials
rules = load_json("conformance_rules.json")
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
spreadsheet_url = "https://docs.google.com/spreadsheets/d/11VFIumfm5xpB8YhKtGi8esbJ8KlHrRJ-WbQj4I6deyA/edit#gid=0"
spreadsheet = setup_gspread("credentials.json", scope, spreadsheet_url)

# Load lookup maps
sc_variables = create_sc_variable_set(spreadsheet.worksheet("Server/Client PICS"))
features_sheet = spreadsheet.worksheet("Features")
features_map = create_features_map(features_sheet)
features_data = features_sheet.get_all_records()  # ✅ Cache once

# Sheets to process
sheets_to_process = [
    "Server/Client PICS", "Attributes", "Manual Controllable",
    "Commands Received", "Commands Generated", "Events", "PIXIT Definition"
]

# Process each sheet
for sheet_name in sheets_to_process:
    sheet = spreadsheet.worksheet(sheet_name)
    data = sheet.get_all_records()
    num_rows = len(data)
    sheet.batch_clear([f"G2:G{num_rows + 1}"])

    conformance_values = []
    for row in data:
        mo_val = row.get(rules["column_mapping"]["mandatory_optional_column"], "")
        variable_context = row.get("Variable", "")
        conformance_values.append(
            process_row(mo_val, rules, sc_variables, features_map, features_data, variable_context)
        )

    cell_range = rowcol_to_a1(2, 7) + f":{rowcol_to_a1(1 + num_rows, 7)}"
    sheet.update(range_name= cell_range, values= conformance_values)

print("✅ Column G (Conformance) updated with bracketed feature mapping support.")
