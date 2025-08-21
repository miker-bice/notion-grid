from datetime import datetime
from flask import Flask, render_template, request
from helpers.notion import get_data_from_notion_db
from helpers.utils import extract_db_id_from_url
import json
import os

app = Flask(__name__, template_folder="templates")

# get the env vars
NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN")
NOTION_DB_URL = os.getenv("NOTION_DB_URL")
TEMPLATE_FILE_NAME = "template.html"
OUTPUT_FILE = "index.html"
CONTENT_TYPES = ["moiraphilyn", "moira.creates"]

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
    

def fetch_items(content_type="moiraphilyn"):
    # fetch the pinned posts
    pinned_payload = {
        "filter": {
            "and": [
                {"property": "Pinned", "checkbox": {"equals": True}},
                {"property": "Name", "title": {"contains": str(content_type)}}
            ]
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
        "filter": {
            "and": [
                {"property": "Pinned", "checkbox": {"equals": False}},
                {"property": "Name", "title": {"contains": str(content_type)}}
            ]
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
        result_prop = result.get("properties", {})

        pinned = result_prop.get("Pinned", {}).get("checkbox", None)
        publish_date_str = (
            result_prop.get("Publish Date", {}).get("date", {}).get("start", None)
        )

        last_edited_str = result.get("last_edited_time", None)

        name = None
        if result_prop.get("Name", {}).get("title"):
            name = result_prop["Name"]["title"][0]["text"]["content"]

        attachment_name = None
        attachment_url = None
        if result_prop.get("Attachment", {}).get("files"):
            file_entry = result_prop["Attachment"]["files"][0]
            attachment_name = file_entry.get("name")
            attachment_url = file_entry.get("file", {}).get("url")

        post_content_type = result_prop.get("Content Type", {}).get("select")

        if post_content_type:
            post_content_type = post_content_type.get("name")
        else:
            post_content_type = None

        formatted_publish_date = None
        if publish_date_str:
            try:
                formatted_publish_date = format_date(publish_date_str)
            except Exception:
                formatted_publish_date = publish_date_str

        parsed_last_edited_date = None
        if last_edited_str:
            try:
                parsed_last_edited_date = datetime.fromisoformat(last_edited_str.replace("Z", "+00:00"))
            except Exception:
                parsed_last_edited_date = last_edited_str

        # TODO: make logic to identify the file upload and link attachment in result_prop["Attachment"]["files"]

        items.append({
            "name": name,
            "publish_date": formatted_publish_date,
            "attachment_name": attachment_name,
            "attachment_url": attachment_url,
            "content_type": post_content_type,
            "pinned": pinned,
            "last_edited": parsed_last_edited_date
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
    items = fetch_items(content_type="moiraphilyn")
    return render_template(TEMPLATE_FILE_NAME, items=items, types=CONTENT_TYPES, current_filter="moiraphilyn")


@app.route("/refresh", methods=["POST"])
def refresh_data():
    selected_content_type = request.form.get("type_filter", "moiraphilyn")
    items = fetch_items(content_type=selected_content_type.lower())
    return render_template(TEMPLATE_FILE_NAME, items=items, types=CONTENT_TYPES, current_filter=selected_content_type)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
