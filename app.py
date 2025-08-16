from datetime import datetime
from flask import Flask, render_template
from jinja2 import Environment, FileSystemLoader
from helpers.notion import get_data_from_notion_db
from helpers.utils import extract_db_id_from_url
import json
import os

app = Flask(__name__, template_folder="templates")

# get the env vars
NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN")
NOTION_DB_URL = os.getenv("NOTION_DB_URL")
sample = os.getenv("SAMPLE_STRING")
TEMPLATE_FILE_NAME = "template.html"
OUTPUT_FILE = "index.html"

try:
    NOTION_FETCH_LIMIT = min(int(os.getenv("NOTION_FETCH_LIMIT", 30)), 90)
except ValueError:
    NOTION_FETCH_LIMIT = 30


if not NOTION_API_TOKEN or not NOTION_DB_URL:
    raise SystemError("Please set NOTION_API_TOKEN and NOTION_DB_URL to you environment variables")

processed_notion_db_url = extract_db_id_from_url(notion_url=NOTION_DB_URL)

headers = {
    "Authorization": f"Bearer {NOTION_API_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-type": "application/json"
}

@app.template_filter("format_date")
def format_date(value, format="%m-%d-%Y"):
    try:
        date_obj = datetime.fromisoformat(value)
        return date_obj.strftime(format)
    except Exception:
        return value 
    

def fetch_items():
    # fetch the pinned posts
    pinned_payload = {
        # "page_size": NOTION_FETCH_LIMIT,
        "filter": {
            "property": "Pinned",
            "checkbox": {
                "equals": True
            }
        },
        "sorts": [{"property": "Publish Date", "direction": "descending"}]
    }
    pinned_response = get_data_from_notion_db(db_url=processed_notion_db_url, headers=headers, payload=pinned_payload)

    if pinned_response.status_code != 200:
        error_details = {"message": pinned_response.status_code, "details": pinned_response.text}
        print(f"ERROR FETCHING PINNED RESULTS: {error_details}")
        raise SystemExit(error_details)

    pinned_results = pinned_response.json()["results"]

    # fetch latest non-pinned posts
    non_pinned_payload = {
        "page_size": NOTION_FETCH_LIMIT,
        "filter": {
            "property": "Pinned",
            "checkbox": {
                "equals": False
            }
        },
        "sorts": [{"property": "Publish Date", "direction": "descending"}]
    }
    non_pinned_response = get_data_from_notion_db(db_url=processed_notion_db_url, headers=headers, payload=non_pinned_payload)

    if non_pinned_response.status_code != 200:
        error_details = {"message": non_pinned_response.status_code, "details": non_pinned_response.text}
        print(f"ERROR FETCHING NON PINNED RESULTS: {error_details}")
        raise SystemExit(error_details)

    non_pinned_results = non_pinned_response.json()["results"]

    # combine
    db_results = pinned_results + non_pinned_results

    print(json.dumps(db_results))

    items = []
    for result in db_results:
        result_prop = result["properties"]
        required_properties = ["Name", "Publish Date", "Attachment", "Content Type", "Pinned"]
        
        # check if the required_properties exist
        for property in required_properties:
            if property not in result_prop:
                raise KeyError(f"Missing required property: {property} in Notion database item: {json.dumps(result, indent=2)}")
            
        # checking for nested properties
        if "checkbox" not in result_prop["Pinned"]:
            raise KeyError(f"'Pinned' property missing 'checkbox' key in: {json.dumps(result, indent=2)}")
        if not result_prop["Publish Date"]["date"] or "start" not in result_prop["Publish Date"]["date"]:
            raise KeyError(f"'Publish Date' property missing 'date.start' in: {json.dumps(result, indent=2)}")
        if not result_prop["Name"]["title"]:
            raise KeyError(f"'Name' property missing 'title' in: {json.dumps(result, indent=2)}")
        if not result_prop["Attachment"]["files"]:
            raise KeyError(f"'Attachment' property missing 'files' in: {json.dumps(result, indent=2)}")
        if "name" not in result_prop["Content Type"]["select"]:
            raise KeyError(f"'Content Type' property missing 'select.name' in: {json.dumps(result, indent=2)}")
        
        pinned = result_prop["Pinned"]["checkbox"]
        publish_date_str = result_prop["Publish Date"]["date"]["start"]
        last_edited_str = result["last_edited_time"]

        # attachment when using external link
        # result_prop["Attachment"]["files"][0]["external"]["url"]

        # TODO: make logic to identify the file upload and link attachment in result_prop["Attachment"]["files"]

        items.append({
            "name": result_prop["Name"]["title"][0]["text"]["content"],
            "publish_date": format_date(publish_date_str),
            "attachment_name": result_prop["Attachment"]["files"][0]["name"],
            "attachment_url": result_prop["Attachment"]["files"][0]["file"]["url"],
            "content_type": result_prop["Content Type"]["select"]["name"],
            "pinned": pinned,
            "last_edited": datetime.fromisoformat(last_edited_str.replace("Z", "+00:00"))
        })

    pinned_items = [item for item in items if item["pinned"]]
    non_pinned_items = [item for item in items if not item["pinned"]]

    # sort the pinned items
    # the pinned_items should remain on top, and pinned_items are sorted by descending order
    pinned_items.sort(key=lambda x: x["last_edited"], reverse=True)
    non_pinned_items.sort(key=lambda x: x["publish_date"], reverse=True)

    return pinned_items + non_pinned_items


@app.route("/")
def index():
    items = fetch_items()
    return render_template(TEMPLATE_FILE_NAME, items=items)


@app.route("/refresh")
def refresh_data():
    items = fetch_items()
    return render_template(TEMPLATE_FILE_NAME, items=items)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
