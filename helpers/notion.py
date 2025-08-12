import requests


def get_data_from_notion_db(db_url, headers, payload):
    '''
    fetch data from notion
    '''
    url = f"https://api.notion.com/v1/databases/{db_url}/query"

    response = requests.post(url=url, headers=headers, json=payload)

    return response