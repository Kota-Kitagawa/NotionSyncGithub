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
    print("✅ GitHub Webhook received")

    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event")

    print(f"🔹 受信したイベントタイプ: {event_type}")
    print(f"🔹 ペイロード: {payload}")

    notion_headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    # ✅ リポジトリ作成イベント
    if event_type == "repository":
        action = payload.get("action")

        if action == "created":
            repo_name = payload["repository"]["name"]
            repo_url = payload["repository"]["html_url"]

            print(f"📡 Notion に送信するリポジトリ情報: {repo_name}, {repo_url}")

            notion_data = {
                "parent": {"database_id": NOTION_REPO_DATABASE_ID},
                "properties": {
                    "リポジトリ名": {"title": [{"text": {"content": repo_name}}]},
                    "URL": {"url": repo_url},
                    "ステータス": {"rich_text": [{"text": {"content": "Active"}}]}
                }
            }

            notion_response = requests.post("https://api.notion.com/v1/pages", headers=notion_headers, json=notion_data)

            print(f"🔹 Notion API のレスポンス: {notion_response.status_code}, {notion_response.text}")

            if notion_response.status_code == 200:
                print(f"✅ Notion にリポジトリ {repo_name} を追加しました")
            else:
                print(f"⚠️ Notion API Error: {notion_response.status_code} - {notion_response.text}")

        elif action == "deleted":
            repo_name = payload["repository"]["name"]
            print(f"🗑️ リポジトリ削除イベント: {repo_name}")

            # Notion から削除する処理
            notion_query_url = f"https://api.notion.com/v1/databases/{NOTION_REPO_DATABASE_ID}/query"
            query_payload = {
                "filter": {
                    "property": "リポジトリ名",
                    "title": {"equals": repo_name}
                }
            }

            notion_query_response = requests.post(notion_query_url, headers=notion_headers, json=query_payload)

            if notion_query_response.status_code == 200:
                results = notion_query_response.json().get("results", [])
                for page in results:
                    page_id = page["id"]
                    delete_url = f"https://api.notion.com/v1/pages/{page_id}"
                    delete_response = requests.delete(delete_url, headers=notion_headers)
                    print(f"🗑️ Notion からリポジトリ {repo_name} を削除: {delete_response.status_code}")

            else:
                print(f"⚠️ Notion API クエリエラー: {notion_query_response.status_code} - {notion_query_response.text}")

        return {"message": "Webhook processed"}

    # ✅ Issue 作成イベントの処理
    elif event_type == "issues":
        if payload.get("action") != "opened":
            print("⚠️ action が opened ではないのでスキップ")
            return {"message": "Webhook received but ignored"}

        issue_title = payload["issue"]["title"]
        issue_body = payload["issue"]["body"]
        issue_url = payload["issue"]["html_url"]
        repo_name = payload["repository"]["name"]

        print(f"📡 Notion に送信する Issue 情報: {issue_title}, {issue_url}")

        notion_data = {
            "parent": {"database_id": NOTION_TASK_DATABASE_ID},
            "properties": {
                "タイトル名": {"title": [{"text": {"content": issue_title}}]},
                "本文": {"rich_text": [{"text": {"content": issue_body or ''}}]},
                "URL": {"url": issue_url},
                "リポジトリ": {"rich_text": [{"text": {"content": repo_name}}]},
                "ステータス": {"rich_text": [{"text": {"content": "Open"}}]}
            }
        }

        notion_response = requests.post("https://api.notion.com/v1/pages", headers=notion_headers, json=notion_data)

        print(f"🔹 Notion API のレスポンス: {notion_response.status_code}, {notion_response.text}")

        if notion_response.status_code == 200:
            print(f"✅ Notion に Issue {issue_title} を追加しました")
        else:
            print(f"⚠️ Notion API Error: {notion_response.status_code} - {notion_response.text}")

        return {"message": "Issue added to Notion"}

    else:
        print(f"⚠️ {event_type} イベントは処理対象外のためスキップ")
        return {"message": "Webhook received but ignored"}
