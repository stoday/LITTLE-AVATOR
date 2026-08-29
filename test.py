import json
import os
import uuid

import requests
from dotenv import load_dotenv


load_dotenv()

BEARER_TOKEN = os.environ.get("BEARER_TOKEN")
USER_OID = os.environ.get("USER_OID")
TENANT_ID = os.environ.get("TENANT_ID")
THREAD_ID = f"19:{USER_OID}_8e0bf425-413f-42e2-93cc-c7ff2bbd9ae2@unq.gbl.spaces"

url = f"https://substrate.office.com/AllFiles/api/users('OID:{USER_OID}@{TENANT_ID}')/AllShared"
params = {
    "ThreadId": THREAD_ID,
    "ItemTypes": ["File", "Link"],
    "PageSize": 100,
}

req_id = str(uuid.uuid4())
headers = {
    "authorization": f"Bearer {BEARER_TOKEN}",
    "scenariotag": "TeamsSharedInChat",
    "x-anchormailbox": f"Oid:{USER_OID}@{TENANT_ID}",
    "Referer": "https://teams.cloud.microsoft/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
    "accept": "application/json",
    "client-request-id": req_id,
    "clientrequestid": req_id,
    "content-type": "application/json;charset=UTF-8",
}


def parse_file_items(payload):
    """Convert an AllShared response into readable file metadata."""
    items = payload.get("Items", payload.get("value", []))
    files = []

    for item in items:
        if item.get("ItemType") != "File":
            continue

        file_data = item.get("FileData") or {}
        if not file_data:
            continue

        files.append(
            {
                "name": file_data.get("FileName"),
                "extension": file_data.get("FileExtension"),
                "file_id": file_data.get("ImmutableId"),
                "web_url": file_data.get("WebUrl"),
                "file_url": file_data.get("FileUrl"),
                "preview_url": file_data.get("PreviewUrl") or None,
                "shared_by": item.get("SharedByDisplayName"),
                "shared_by_email": item.get("SharedBySmtp"),
                "shared_at": item.get("SharedDateTime"),
                "last_modified_at": item.get("LastModifiedDateTime"),
                "teams_message_id": item.get("TeamsMessageId"),
                "thread_id": item.get("ThreadId"),
            }
        )

    return files


def main():
    required_settings = {
        "BEARER_TOKEN": BEARER_TOKEN,
        "USER_OID": USER_OID,
        "TENANT_ID": TENANT_ID,
    }
    missing = [name for name, value in required_settings.items() if not value]
    if missing:
        raise RuntimeError(f"Set these values in .env: {', '.join(missing)}")

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()

    files = parse_file_items(response.json())
    print(f"Retrieved {len(files)} file items.")
    print(json.dumps(files, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
