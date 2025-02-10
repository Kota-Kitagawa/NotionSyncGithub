from fastapi import FastAPI, Request
import os
import requests
from dotenv import load_dotenv
from datetime import datetime


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

@app.post("/api/github/webhook")
async def github_webhook(request: Request):
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event")

    if event_type == "issues":
        issue = payload["issue"]
        action = payload["action"]
        issue_number = issue["number"]
        issue_state = issue["state"]
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        notion_url = f"https://api.notion.com/v1/databases/{NOTION_TASK_DATABASE_ID}/query"
        headers = {"Authorization": f"Bearer {NOTION_API_KEY}", "Notion-Version": "2022-06-28"}
        response = requests.post(notion_url, headers=headers)

        notion_tasks = response.json().get("results", [])
        for task in notion_tasks:
            if str(issue_number) == task["properties"]["GithubIssueID"]["rich_text"][0]["text"]["content"]:
                notion_page_id = task["id"]
                previous_history = task["properties"].get("更新履歴", {}).get("rich_text", [])

                new_history = f"{updated_at}: Issue {issue_number} {issue_state.capitalize()} に変更"
                updated_history = [{"text": {"content": new_history}}] + previous_history

                update_data = {
                    "properties": {
                        "ステータス": {"select": {"name": "完了" if issue_state == "closed" else "In Progress"}},
                        "更新履歴": {"rich_text": updated_history}
                    }
                }
                requests.patch(f"https://api.notion.com/v1/pages/{notion_page_id}", headers=headers, json=update_data)

    return {"message": "Webhook received"}


def handler(req):
    return app
