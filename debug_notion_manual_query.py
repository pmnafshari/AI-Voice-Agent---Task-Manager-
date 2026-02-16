
import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

notion = Client(auth=os.getenv("NOTION_API_KEY"))
NOTION_DB_ID = os.getenv("NOTION_DB_ID")

print(f"Testing manual query for DB: {NOTION_DB_ID}")

# Format UUID if needed
if len(NOTION_DB_ID) == 32 and "-" not in NOTION_DB_ID:
    NOTION_DB_ID = f"{NOTION_DB_ID[:8]}-{NOTION_DB_ID[8:12]}-{NOTION_DB_ID[12:16]}-{NOTION_DB_ID[16:20]}-{NOTION_DB_ID[20:]}"
    print(f"Formatted DB ID: {NOTION_DB_ID}")

try:
    print("Attempting retrieve...")
    db = notion.databases.retrieve(NOTION_DB_ID)
    print(f"Retrieved object type: {db.get('object', 'unknown')}")
    
    # Test generic request
    print("Testing users endpoint...")
    users = notion.request(path="users", method="GET")
    print(f"Users endpoint success, found {len(users.get('results', []))} users.")

    query_payload = {
        "filter": {
            "and": [
                {"property": "Status", "select": {"does_not_equal": "Done"}}
            ]
        }
    }
    
    print("Attempting request...")
    response = notion.request(
        path=f"databases/{NOTION_DB_ID}/query",
        method="POST",
        body=query_payload
    )
    
    print("Success!")
    print(f"Results count: {len(response.get('results', []))}")
    
except Exception as e:
    print(f"Error: {e}")
