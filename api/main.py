from fastapi import FastAPI, Request
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_REPO_DATABASE_ID = os.getenv("NOTION_REPO_DATABASE_ID")
NOTION_TASK_DATABASE_ID = os.getenv("NOTION_TASK_DATABASE_ID")
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")

@app.get("/")
def read_root():
    return {"message": "Notion-GitHub Sync API is running"}

@app.post("/api/github/repository_webhook")
async def github_repository_webhook(request: Request):
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event")

    if event_type == "repository" and payload.get("action") == "created":
        repo_name = payload["repository"]["name"]
        repo_url = payload["repository"]["html_url"]

        notion_headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

        notion_data = {
            "parent": {"database_id": NOTION_REPO_DATABASE_ID},
            "properties": {
                "リポジトリ名": {"title": [{"text": {"content": repo_name}}]},
                "URL": {"url": repo_url},
                "ステータス": {"select": {"name": "Active"}}
            }
        }

        notion_response = requests.post("https://api.notion.com/v1/pages", headers=notion_headers, json=notion_data)

        if notion_response.status_code == 200:
            print(f"✅ Notion にリポジトリ {repo_name} を追加しました")
        else:
            print(f"⚠️ Notion API Error: {notion_response.status_code} - {notion_response.text}")

    return {"message": "Webhook received"}

@app.post("/api/sync_notion_to_github")
def sync_notion_to_github():
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28"
    }

    notion_url = f"https://api.notion.com/v1/databases/{NOTION_TASK_DATABASE_ID}/query"
    response = requests.post(notion_url, headers=headers)

    if response.status_code != 200:
        print(f"⚠️ Notion API Error: {response.status_code} - {response.text}")
        return {"error": "Notion API failed"}

    notion_tasks = response.json().get("results", [])

    for task in notion_tasks:
        title = task["properties"]["タイトル"]["title"][0]["text"]["content"]
        github_issue_id = task["properties"].get("GithubIssueID", {}).get("rich_text", [{}])[0].get("text", {}).get("content")
        repository_name = task["properties"]["リポジトリ"]["relation"][0]["id"] if "リポジトリ" in task["properties"] else None

        if not github_issue_id and repository_name:
            github_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{repository_name}/issues"
            issue_data = {"title": title, "body": "Created from Notion"}
            github_headers = {
                "Authorization": f"Bearer {GITHUB_API_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }

            github_response = requests.post(github_url, json=issue_data, headers=github_headers)

            if github_response.status_code == 201:
                issue_number = github_response.json()["number"]
                notion_page_id = task["id"]
                update_data = {
                    "properties": {
                        "GithubIssueID": {"rich_text": [{"text": {"content": str(issue_number)}}]}
                    }
                }
                requests.patch(f"https://api.notion.com/v1/pages/{notion_page_id}", headers=headers, json=update_data)

    return {"message": "Notion tasks synced to GitHub"}
