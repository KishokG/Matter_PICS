from bs4 import BeautifulSoup
import re

def extract_steps_pics_for_cluster(html_file, target_cluster):
    results = []

    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    all_h1_tags = soup.find_all("h1")
    for h1 in all_h1_tags:
        strong_tag = h1.find("strong")
        if strong_tag:
            cluster_name = strong_tag.text.strip()
            print(f"Found cluster: {cluster_name}")

            if cluster_name != target_cluster:
                continue

            print(f"Matched target cluster: {cluster_name}")

            # Now within target cluster, look for test cases
            for sibling in h1.find_all_next():
                if sibling.name == "h1":
                    break  # Next cluster reached

                if sibling.name == "h4":
                    print(f"Found h4: {sibling.get_text(strip=True)}")

                if sibling.name == "h5" and sibling.get("id", "").startswith("_test_procedure"):
                    print(f"Found Test Procedure section under cluster {cluster_name}")
                    table = sibling.find_next("table")
                    if table:
                        for row in table.find_all("tr"):
                            cells = row.find_all("td")
                            if len(cells) >= 3:
                                raw_pics = cells[2].get_text(separator=",", strip=True)
                                print(f"Raw PICS: {raw_pics}")

                                # Refined regex to capture !(PICS) and (PICS)
                                pics_matches = re.findall(r'(!?\([A-Za-z0-9\.\-\_]+(?:\.[A-Za-z0-9\.\-\_]+)*\))', raw_pics)

                                # Debug print to show matches found
                                print(f"Matches found: {pics_matches}")

                                # Store the result (cluster name and steps pics)
                                results.append([cluster_name, ", ".join(pics_matches)])

    return results
