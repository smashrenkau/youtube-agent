"""content/renkau/ のmdファイルをNotionナレッジDBに同期するスクリプト。

使い方:
    python scripts/update_notion_knowledge.py
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from notion_client import Client
from config.settings import get_settings

CONTENT_DIR = Path(__file__).parent.parent / "content" / "renkau"

# mdファイルのファイル名 → Notionページタイトルの対応
TITLE_MAP = {
    "script_style.md": "台本スタイルガイド",
    "key_messages.md": "マーケティング軸・刺さるメッセージ",
    "channel_strategy.md": "チャンネル戦略",
    "marketing_strategy.md": "マーケティング戦略",
    "quality_criteria.md": "品質基準",
}

# Notionページタイトル → page_id（searchで確認済み）
PAGE_ID_MAP = {
    "台本スタイルガイド": "32eb35e4-1872-819b-8415-c17ff134f51c",
    "マーケティング軸・刺さるメッセージ": "32eb35e4-1872-8131-b3e4-d9350f4a62cb",
    "チャンネル戦略": "32eb35e4-1872-819f-9af5-f73e6b57c38c",
    "品質基準": "32eb35e4-1872-819d-b59d-e66b18dd25e1",
    # マーケティング戦略はNotionに未存在 → Renkauページ配下に新規作成
}

RENKAU_PAGE_ID = "32eb35e4-1872-8173-b035-c9c973deecf2"  # 親ページ


def md_to_blocks(text: str) -> list[dict]:
    """マークダウンテキストをNotionブロックのリストに変換する（簡易版）。"""
    blocks = []
    for line in text.splitlines():
        stripped = line.rstrip()

        if stripped.startswith("# "):
            blocks.append(_heading(1, stripped[2:]))
        elif stripped.startswith("## "):
            blocks.append(_heading(2, stripped[3:]))
        elif stripped.startswith("### "):
            blocks.append(_heading(3, stripped[4:]))
        elif stripped.startswith("- "):
            blocks.append(_bullet(stripped[2:]))
        elif stripped.startswith("**") and stripped.endswith("**"):
            blocks.append(_paragraph(stripped.replace("**", "")))
        elif stripped == "":
            blocks.append(_paragraph(""))
        else:
            blocks.append(_paragraph(stripped))

    return blocks


def _heading(level: int, text: str) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": [_text(text)]}}


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [_text(text)]},
    }


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [_text(text)] if text else []},
    }


def _text(content: str) -> dict:
    return {"type": "text", "text": {"content": content[:2000]}}


def get_existing_pages(client: Client, database_id: str) -> dict[str, str]:
    """データベース内の全ページをタイトル→page_idのdictで返す。"""
    pages = {}
    cursor = None
    while True:
        body: dict = {}
        if cursor:
            body["start_cursor"] = cursor
        response = client.request(
            path=f"databases/{database_id}/query",
            method="POST",
            body=body,
        )
        for page in response.get("results", []):
            if page.get("object") != "page":
                continue
            for prop in page.get("properties", {}).values():
                if prop["type"] == "title":
                    title = "".join(rt["plain_text"] for rt in prop.get("title", []))
                    pages[title] = page["id"].replace("-", "")
                    break
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return pages


def clear_page_blocks(client: Client, page_id: str) -> None:
    """ページ内の既存ブロックをすべて削除する。"""
    cursor = None
    while True:
        kwargs: dict = {"block_id": page_id}
        if cursor:
            kwargs["start_cursor"] = cursor
        response = client.blocks.children.list(**kwargs)
        for block in response["results"]:
            client.blocks.delete(block_id=block["id"])
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")


def append_blocks(client: Client, page_id: str, blocks: list[dict]) -> None:
    """ブロックを100件ずつ分割してページに追加する。"""
    for i in range(0, len(blocks), 95):
        client.blocks.children.append(block_id=page_id, children=blocks[i:i + 95])


def main() -> None:
    settings = get_settings()
    client = Client(auth=settings.notion_api_key.get_secret_value())

    print("Notionナレッジページを更新中...")

    for filename, title in TITLE_MAP.items():
        md_path = CONTENT_DIR / filename
        if not md_path.exists():
            print(f"  [SKIP] {filename} が存在しません")
            continue

        content = md_path.read_text(encoding="utf-8")
        blocks = md_to_blocks(content)

        if title in PAGE_ID_MAP:
            page_id = PAGE_ID_MAP[title]
            print(f"  [UPDATE] 「{title}」を更新中...")
            clear_page_blocks(client, page_id)
            append_blocks(client, page_id, blocks)
            print(f"    → 更新完了（{len(blocks)}ブロック）")
        else:
            print(f"  [CREATE] 「{title}」を新規作成中（Renkauページ配下）...")
            page = client.pages.create(
                parent={"type": "page_id", "page_id": RENKAU_PAGE_ID},
                properties={"title": {"title": [_text(title)]}},
                children=blocks[:95],
            )
            page_id = page["id"]
            if len(blocks) > 95:
                append_blocks(client, page_id, blocks[95:])
            print(f"    → 作成完了（{len(blocks)}ブロック）page_id={page_id}")

    print("\n✓ Notion同期完了")


if __name__ == "__main__":
    main()
