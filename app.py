"""YouTube コンテンツ生成 Streamlit アプリ。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from ui.content_folder import ContentFolder

st.set_page_config(
    page_title="YouTube コンテンツ生成",
    page_icon="🎬",
    layout="wide",
)

# ──────────────────────────────────────────
# セッション状態の初期化
# ──────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "titles": [],
        "scripts": {},          # title -> script str
        "slides": {},           # title -> list[dict]
        "title_page_ids": {},   # title -> Notion page_id
        "generating_titles": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ──────────────────────────────────────────
# サイドバー：設定フェーズ
# ──────────────────────────────────────────
with st.sidebar:
    st.title("設定")

    folders = ContentFolder.list_all()
    if not folders:
        st.error("content/ フォルダが見つかりません。")
        st.stop()

    folder_map = {f.display_name: f for f in folders}
    selected_name = st.selectbox("コンテンツフォルダ", list(folder_map.keys()))
    selected_folder = folder_map[selected_name]
    st.caption(selected_folder.description)

    num_titles = st.selectbox("タイトル候補数", [5, 10, 20], index=0)

    st.divider()

    if st.button("タイトル生成", type="primary", use_container_width=True):
        st.session_state.titles = []
        st.session_state.scripts = {}
        st.session_state.slides = {}
        st.session_state.title_page_ids = {}
        st.session_state.generating_titles = True

    st.divider()
    st.markdown("**📁 フォルダを追加するには**")
    st.markdown(
        "Notionの「YouTube コンテンツ管理」ページに\n"
        "新しい子ページを追加してください。\n\n"
        "**手順：**\n"
        "1. 下のリンクを開く\n"
        "2. ページ内で `+` を押して子ページを追加\n"
        "3. ページ名 = フォルダ名になります\n"
        "4. 子ページ内に「チャンネル戦略」「マーケティング軸・刺さるメッセージ」"
        "「YouTube検索キーワードリスト」「台本スタイルガイド」「品質基準」の"
        "5ページを作成してください"
    )
    st.link_button(
        "Notionで管理する →",
        "https://notion.so/32eb35e4187281809a92d780769614fc",
        use_container_width=True,
    )

# ──────────────────────────────────────────
# メイン：タイトル生成
# ──────────────────────────────────────────
st.title("YouTube コンテンツ生成")

if st.session_state.generating_titles:
    with st.spinner(f"タイトルを {num_titles} 本生成中..."):
        from ui.generators import generate_titles, save_titles_to_notion
        titles = generate_titles(selected_folder, num_titles)
        st.session_state.titles = titles

        # Notionに自動保存
        page_ids = save_titles_to_notion(titles)
        st.session_state.title_page_ids = page_ids
        st.session_state.generating_titles = False

    st.toast(f"✅ タイトル {len(titles)} 件をNotionに保存しました", icon="✅")

# ──────────────────────────────────────────
# タイトル一覧 + チェックボックス
# ──────────────────────────────────────────
if st.session_state.titles:
    st.header("タイトル候補")

    selected_titles = []
    for i, title in enumerate(st.session_state.titles):
        checked = st.checkbox(title, key=f"title_check_{i}")
        if checked:
            selected_titles.append(title)

    st.divider()

    if selected_titles:
        if st.button(f"台本生成（{len(selected_titles)}本）", type="primary"):
            from ui.generators import generate_script, save_script_to_notion
            for title in selected_titles:
                if title not in st.session_state.scripts:
                    with st.spinner(f"台本生成中: {title}"):
                        script = generate_script(title, selected_folder)
                        st.session_state.scripts[title] = script

                        # Notionに自動保存
                        save_script_to_notion(title, script, st.session_state.title_page_ids)

            st.toast(f"✅ 台本 {len(selected_titles)} 件をNotionに保存しました", icon="✅")
    else:
        st.info("台本を作成したいタイトルにチェックを入れてください。")

# ──────────────────────────────────────────
# 台本一覧 + スライド作成ボタン
# ──────────────────────────────────────────
if st.session_state.scripts:
    st.header("台本")

    for title, script in st.session_state.scripts.items():
        with st.expander(f"📝 {title}", expanded=True):
            edited_script = st.text_area(
                "台本（編集可能）",
                value=script,
                height=300,
                key=f"script_area_{title}",
            )
            st.session_state.scripts[title] = edited_script

            col1, col2 = st.columns([1, 4])
            with col1:
                slide_btn = st.button(
                    "スライド作成",
                    key=f"slide_btn_{title}",
                    type="secondary",
                )

            if slide_btn:
                with st.spinner(f"スライド生成中（約8分）... {title}"):
                    from ui.generators import generate_slides, save_slides_to_notion
                    slides = generate_slides(edited_script, title, folder=selected_folder)
                    st.session_state.slides[title] = slides

                    # Notionに自動保存
                    save_slides_to_notion(title, slides, st.session_state.title_page_ids)

                st.toast(f"✅ スライドをNotionに保存しました", icon="✅")

            # スライドプレビュー
            if title in st.session_state.slides:
                slides = st.session_state.slides[title]
                st.subheader(f"スライドプレビュー（{len(slides)}枚）")
                cols = st.columns(4)
                for i, slide in enumerate(slides):
                    png_path = slide.get("png_path", "")
                    if Path(png_path).exists():
                        with cols[i % 4]:
                            st.image(
                                png_path,
                                caption=f"{slide['slide_num']}. {slide['title']}",
                                use_container_width=True,
                            )

# ──────────────────────────────────────────
# 初期メッセージ
# ──────────────────────────────────────────
if not st.session_state.titles and not st.session_state.generating_titles:
    st.info("← 左のサイドバーでフォルダとタイトル数を選択して「タイトル生成」を押してください。")
