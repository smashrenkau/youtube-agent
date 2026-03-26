"""Notionにlong動画・short動画の構造を作成するセットアップスクリプト。

使い方:
    python scripts/setup_long_short_notion.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from notion_client import Client
from config.settings import get_settings

RENKAU_PAGE_ID = "32eb35e4-1872-8173-b035-c9c973deecf2"

# 既存の8ページ（long動画に移動する）
EXISTING_PAGES = [
    "32eb35e4-1872-819f-9af5-f73e6b57c38c",  # チャンネル戦略
    "32eb35e4-1872-8131-b3e4-d9350f4a62cb",  # マーケティング軸・刺さるメッセージ
    "32eb35e4-1872-8162-83fe-d2a97e1a641d",  # YouTube検索キーワードリスト
    "32eb35e4-1872-819b-8415-c17ff134f51c",  # 台本スタイルガイド
    "32eb35e4-1872-819d-b59d-e66b18dd25e1",  # 品質基準
    "32eb35e4-1872-812c-beba-c1485ad5f8ba",  # スライド仕様書
    "32fb35e4-1872-811b-ae18-c2cfb7b5d373",  # マーケティング戦略
    "32eb35e4-1872-81bc-b5ab-f1cd51cca66a",  # 生成物
]

# ショート動画のナレッジページ内容
SHORT_PAGES = {
    "チャンネル戦略": """# チャンネル戦略

## チャンネルコンセプト
「お金の問題を抱えた人が、今日から生活を立て直すための情報チャンネル」

## ターゲット視聴者
- 携帯・クレジットカードの審査に落ちた人
- 過去に自己破産・任意整理をした人
- ブラックリストに載っていて困っている人
- 収入が不安定でクレカを持てない人
- 生活に必要な家電・スマホをどうしても確保したい人

## 動画フォーマット
- YouTube Shorts（縦型 9:16）
- 長さ：45秒以内
- 字幕あり
- 冒頭1〜2秒で視聴者を引き込む

## トーン＆マナー
- 「あなたの状況は恥ずかしくない」という共感ファースト
- 超シンプル・超ダイレクトに伝える
- 専門用語なし
- 1本1メッセージに絞る
""",
    "マーケティング軸・刺さるメッセージ": """# 刺さるメッセージ・必須訴求ポイント（ショート版）

## Renkauとは
クレジットカード不要・信用情報照会なしで、新品の家電・スマホをレンタルできるサービス。
月額料金を払い続けることで、2年後に実質的に自分のものになる。

## ショートで使うメッセージ（自然に入る場合のみ）

### 借入枠を守れる
- レンタルは「借入」ではないので総量規制の対象外
- キャッシングの枠を残せる

### クレカ・信用情報不要
- クレジットカードなしでOK
- 信用情報（CIC）を照会しない

### 2年で自分のものになる
- ずっと払い続けるだけでなく、所有権が移転する

## 注意
ショートでは1本に1メッセージだけ使う。詰め込まない。
""",
    "YouTube検索キーワードリスト": """# YouTube検索キーワードリスト（ショート版）

## メインキーワード
- 審査落ち ショート
- ブラックリスト 解決
- クレカなし 生活
- 家電 借りる
- スマホ 審査なし

## 動画テーマ例
- 「審査落ちた人へ」
- 「ブラックでも○○できる方法」
- 「クレカなしで家電を手に入れる方法」
- 「知らないと損する制度」
""",
    "台本スタイルガイド": """# 台本スタイルガイド（ショート版）

## 全体構成（45秒以内）
1. **フック（5〜8秒）**：最初の一言で視聴者を止める
2. **本題（30秒）**：解決策を1〜2点だけ、シンプルに
3. **CTA（5〜7秒）**：チャンネル登録or詳細は概要欄へ

## 文字数
- 目安：150〜200文字（±10%）
- 読み上げ速度：1文字＝約0.2〜0.25秒

## 文体ルール
- 話し言葉（「〜なんです」「〜ですよ」）
- 一文10〜15文字以内
- 難しい言葉は使わない
- 「あなた」に語りかける

## フックの例
- 「審査落ちた？実は解決策あります。」
- 「ブラックでも家電が持てる方法、知ってますか？」
- 「クレカなしでスマホを手に入れる方法。」

## Renkauの紹介
- 自然に入る場合だけ紹介する（無理に入れない）
- エンディングで「詳しくは概要欄のRenkauをチェック」程度でOK

## 禁止事項
- 不安を過度に煽る表現
- 「絶対」「必ず」などの断言
- 法的にグレーな表現

## 構成例
フック：「審査落ちてスマホが持てない？」
本題：「実は、信用情報を見ない方法があります。レンタルサービスなら、クレカなし・ブラックリストOKで新品スマホが使えます。」
CTA：「詳しくは概要欄のリンクをチェック！チャンネル登録もお願いします。」
""",
    "品質基準": """# 品質基準（ショート版）

## タイトルの品質基準
- 検索されやすいキーワードを含む
- 20文字以内（ショートは短く）
- 数字・具体性・共感のいずれかを含む
- ターゲットが「自分のことだ」と思える

## 台本の品質基準（15点満点）
- 冒頭5秒で視聴者を止めるフックがある（5点）
- 150〜200文字の範囲に収まっている（3点）
- 解決策が1〜2点に絞られている（4点）
- CTAが明確である（3点）

合格基準：12点以上
""",
    "マーケティング戦略": """# マーケティング戦略（ショート版）

## 主要マーケティング軸

### 軸1：「審査落ち・ブラックでも大丈夫」共感軸
- 最初の1〜2秒でターゲットを引き込む
- 「あなたのことだ」と感じさせる

### 軸2：「今すぐ解決できる」即効性軸
- 問題→解決策を15秒以内に見せる
- ハードルを最大限下げる

### 軸3：「知らないと損」情報格差軸
- 「こんな方法があるの？」という発見感
- シェアしたくなる情報設計

## SEO・検索意図
- 「審査落ち」「ブラックリスト」「クレカなし」などの困り事キーワード
- ショートのタイトルは短く・直接的に
""",
}


def _text(content: str) -> dict:
    return {"type": "text", "text": {"content": content[:2000]}}


def md_to_blocks(text: str) -> list[dict]:
    """マークダウンテキストをNotionブロックのリストに変換する（簡易版）。"""
    blocks = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.startswith("# "):
            key = "heading_1"
            blocks.append({"object": "block", "type": key, key: {"rich_text": [_text(stripped[2:])]}})
        elif stripped.startswith("## "):
            key = "heading_2"
            blocks.append({"object": "block", "type": key, key: {"rich_text": [_text(stripped[3:])]}})
        elif stripped.startswith("### "):
            key = "heading_3"
            blocks.append({"object": "block", "type": key, key: {"rich_text": [_text(stripped[4:])]}})
        elif stripped.startswith("- "):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [_text(stripped[2:])]},
            })
        elif stripped == "":
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}})
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [_text(stripped)]}})
    return blocks


def append_blocks(client: Client, page_id: str, blocks: list[dict]) -> None:
    for i in range(0, len(blocks), 95):
        client.blocks.children.append(block_id=page_id, children=blocks[i:i + 95])


def main() -> None:
    settings = get_settings()
    client = Client(auth=settings.notion_api_key.get_secret_value())

    print("=== Notion Long/Short 構造セットアップ開始 ===\n")

    # ── 1. Renkau配下に「long動画」ページを作成 ──
    print("[1] 「long動画」ページを作成中...")
    long_page = client.pages.create(
        parent={"type": "page_id", "page_id": RENKAU_PAGE_ID},
        properties={"title": {"title": [_text("long動画")]}},
        children=[],
    )
    long_page_id = long_page["id"]
    print(f"    → 作成完了: {long_page_id}")

    # ── 2. 既存8ページをlong動画に移動 ──
    print("\n[2] 既存ページをlong動画に移動中...")
    for page_id in EXISTING_PAGES:
        try:
            client.pages.update(
                page_id=page_id,
                parent={"type": "page_id", "page_id": long_page_id},
            )
            print(f"    → 移動完了: {page_id}")
        except Exception as e:
            print(f"    [WARN] 移動失敗 {page_id}: {e}")

    # ── 3. Renkau配下に「short動画」ページを作成 ──
    print("\n[3] 「short動画」ページを作成中...")
    short_page = client.pages.create(
        parent={"type": "page_id", "page_id": RENKAU_PAGE_ID},
        properties={"title": {"title": [_text("short動画")]}},
        children=[],
    )
    short_page_id = short_page["id"]
    print(f"    → 作成完了: {short_page_id}")

    # ── 4. short動画配下にナレッジページを作成 ──
    print("\n[4] short動画配下にナレッジページを作成中...")
    for title, content in SHORT_PAGES.items():
        blocks = md_to_blocks(content)
        page = client.pages.create(
            parent={"type": "page_id", "page_id": short_page_id},
            properties={"title": {"title": [_text(title)]}},
            children=blocks[:95],
        )
        if len(blocks) > 95:
            append_blocks(client, page["id"], blocks[95:])
        print(f"    → 作成完了: 「{title}」 ({page['id']})")

    # ── 5. short動画配下に「生成物」ページを作成 ──
    print("\n[5] short動画配下に「生成物」ページを作成中...")
    storage_page = client.pages.create(
        parent={"type": "page_id", "page_id": short_page_id},
        properties={"title": {"title": [_text("生成物")]}},
        children=[{
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [_text("タイトル・台本が自動保存されます。")]}
        }],
    )
    print(f"    → 作成完了: {storage_page['id']}")

    print("\n=== セットアップ完了 ===")
    print(f"\n.envに以下を追記してください:")
    print(f"NOTION_RENKAU_LONG_PAGE_ID={long_page_id.replace('-', '')}")
    print(f"NOTION_RENKAU_SHORT_PAGE_ID={short_page_id.replace('-', '')}")


if __name__ == "__main__":
    main()
