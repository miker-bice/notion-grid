import re

def extract_db_id_from_url(notion_url: str) -> str:
    """
    Extracts the unique database UUID from a Notion share URL.
    Works whether UUID is hyphenated or not.
    Example:
    https://www.notion.so/user/1234567890abcdef1234567890abcdef?v=abcd1234
    → returns '1234567890abcdef1234567890abcdef'
    """
    # Match 32 hex chars possibly separated by hyphens
    match = re.search(r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", notion_url)
    if match:
        db_id = match.group(1)
        # Remove hyphens if present to make it API-ready
        return db_id.replace("-", "")
    raise ValueError("No valid Notion database ID found in URL")