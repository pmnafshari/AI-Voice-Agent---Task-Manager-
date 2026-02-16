
import os
from dotenv import load_dotenv
from notion_client import Client
import inspect

load_dotenv()

try:
    notion = Client(auth=os.getenv("NOTION_API_KEY"))
    print(f"Type of notion.databases: {type(notion.databases)}")
    print(f"Dir of notion.databases: {dir(notion.databases)}")
    
    # Check if query exists
    if hasattr(notion.databases, 'query'):
        print("query method exists!")
    else:
        print("query method DOES NOT exist!")

except Exception as e:
    print(f"Error: {e}")
