"""content/renkau/ のmdファイルをNotionナレッジDBに同期するスクリプト。

使い方:
    python scripts/update_notion_knowledge.py --type long   # long動画のナレッジを更新
    python scripts/update_notion_knowledge.py --type short  # short動画のナレッジを更新
    python scripts/update_notion_knowledge.py               # 両方更新（デフォルト）
"""
import argparse
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from notion_client import Client
from config.settings import get_settings

CONTENT_BASE = Path(__file__).parent.parent / "content" / "renkau"

# long動画: mdファイル名 → Notionページタイトルの対応
LONG_TITLE_MAP = {
    "script_style.md": "台本スタイルガイド",
    "key_messages.md": "マーケティング軸・刺さるメッセージ",
    "channel_strategy.md": "チャンネル戦略",
    "marketing_strategy.md": "マーケティング戦略",
    "quality_criteria.md": "品質基準",
}

# long動画: Notionページタイトル → page_id
LONG_PAGE_ID_MAP = {
    "台本スタイルガイド": "32fb35e4-1872-8128-93c1-c6f35306a773",
    "マーケティング軸・刺さるメッセージ": "32fb35e4-1872-8102-a48c-ce64ef1a3a7a",
    "チャンネル戦略": "32fb35e4-1872-81b2-b8dc-ec536418b97c",
    "マーケティング戦略": "32fb35e4-1872-8161-b262-fcbc9262da1f",
    "品質基準": "32fb35e4-1872-815b-ba67-ee60f23ea39a",
}

# long動画の親ページID（long動画フォルダ）
LONG_PARENT_PAGE_ID = "32fb35e4-1872-815a-a111-d9ea170d2b92"

# short動画: mdファイル名 → Notionページタイトルの対応
SHORT_TITLE_MAP = {
    "script_style.md": "台本スタイルガイド",
    "key_messages.md": "マーケティング軸・刺さるメッセージ",
    "channel_strategy.md": "チャンネル戦略",
    "marketing_strategy.md": "マーケティング戦略",
    "quality_criteria.md": "品質基準",
}

# short動画: Notionページタイトル → page_id
SHORT_PAGE_ID_MAP = {
    "チャンネル戦略": "32fb35e4-1872-8105-b861-eb4e6aff1fb5",
    "マーケティング軸・刺さるメッセージ": "32fb35e4-1872-81b5-9348-ff6cc8bbb6bc",
    "台本スタイルガイド": "32fb35e4-1872-811b-abb6-f89d538a4303",
    "品質基準": "32fb35e4-1872-81b7-8ca1-ca6a5c564056",
    "マーケティング戦略": "32fb35e4-1872-81d8-92f6-f8b022f96d42",
}

# short動画の親ページID（short動画フォルダ）
SHORT_PARENT_PAGE_ID = "32fb35e4-1872-8114-a415-f816e463e6d3"


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


def sync_pages(
    client: Client,
    content_dir: Path,
    title_map: dict[str, str],
    page_id_map: dict[str, str],
    parent_page_id: str,
    label: str,
) -> None:
    """指定ディレクトリのmdファイルをNotionに同期する。"""
    print(f"\n--- {label} ---")
    for filename, title in title_map.items():
        md_path = content_dir / filename
        if not md_path.exists():
            print(f"  [SKIP] {filename} が存在しません")
            continue

        content = md_path.read_text(encoding="utf-8")
        blocks = md_to_blocks(content)

        if title in page_id_map:
            page_id = page_id_map[title]
            print(f"  [UPDATE] 「{title}」を更新中...")
            clear_page_blocks(client, page_id)
            append_blocks(client, page_id, blocks)
            print(f"    → 更新完了（{len(blocks)}ブロック）")
        else:
            print(f"  [CREATE] 「{title}」を新規作成中（{label}フォルダ配下）...")
            page = client.pages.create(
                parent={"type": "page_id", "page_id": parent_page_id},
                properties={"title": {"title": [_text(title)]}},
                children=blocks[:95],
            )
            page_id = page["id"]
            if len(blocks) > 95:
                append_blocks(client, page_id, blocks[95:])
            print(f"    → 作成完了（{len(blocks)}ブロック）page_id={page_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Notionナレッジページを同期する")
    parser.add_argument("--type", choices=["long", "short", "both"], default="both",
                        help="更新する動画タイプ（long/short/both）")
    args = parser.parse_args()

    settings = get_settings()
    client = Client(auth=settings.notion_api_key.get_secret_value())

    print("Notionナレッジページを更新中...")

    if args.type in ("long", "both"):
        sync_pages(
            client=client,
            content_dir=CONTENT_BASE / "long",
            title_map=LONG_TITLE_MAP,
            page_id_map=LONG_PAGE_ID_MAP,
            parent_page_id=LONG_PARENT_PAGE_ID,
            label="long動画",
        )

    if args.type in ("short", "both"):
        sync_pages(
            client=client,
            content_dir=CONTENT_BASE / "short",
            title_map=SHORT_TITLE_MAP,
            page_id_map=SHORT_PAGE_ID_MAP,
            parent_page_id=SHORT_PARENT_PAGE_ID,
            label="short動画",
        )

    print("\n✓ Notion同期完了")


if __name__ == "__main__":
    main()
