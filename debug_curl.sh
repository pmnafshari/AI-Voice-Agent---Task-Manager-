#!/bin/bash
source .env

# Format ID
DB_ID=$NOTION_DB_ID
if [[ $DB_ID != *-* ]]; then
  DB_ID="${DB_ID:0:8}-${DB_ID:8:4}-${DB_ID:12:4}-${DB_ID:16:4}-${DB_ID:20}"
fi

echo "Testing curl for DB: $DB_ID"

curl 'https://api.notion.com/v1/databases/'$DB_ID'/query' \
  -H 'Authorization: Bearer '"$NOTION_API_KEY"'' \
  -H 'Notion-Version: 2022-06-28' \
  -H "Content-Type: application/json" \
  --data '{
    "filter": {
        "and": [
            {"property": "Status", "select": {"does_not_equal": "Done"}}
        ]
    }
}'
