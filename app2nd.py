import streamlit as st
import pandas as pd
import requests
import datetime
import os
import google.generativeai as genai
from dotenv import load_dotenv
import re

# --- 複数キーワードのハイライト用関数 ---
def highlight_keywords_multi(text, keywords):
    if not keywords:
        return text
    for kw in keywords:
        pattern = re.compile(re.escape(kw), flags=re.IGNORECASE)
        text = pattern.sub(
            f'<span style="background: repeating-linear-gradient(45deg, yellow, yellow 4px, transparent 4px, transparent 8px);">{kw}</span>',
            text
        )
    return text

# --- APIキーの設定 ---
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ✅ 修正版：現行API対応
model = genai.GenerativeModel("gemini-2.5-flash")

# --- CSV読み込み ---
csv_path = "politicians.csv"
try:
    politicians_df = pd.read_csv(csv_path, encoding="utf-8")
except UnicodeDecodeError:
    politicians_df = pd.read_csv(csv_path, encoding="shift_jis")

# --- 整形 ---
def normalize(name):
    return str(name).replace("　", "").replace(" ", "")

politicians_df["name"] = politicians_df["name"].apply(normalize)
politicians_df["yomi"] = politicians_df["yomi"].apply(normalize)

# 政党を議員数の多い順に並べ替え
party_counts = politicians_df["party"].value_counts()
sorted_parties = party_counts.index.tolist()

# --- UI ---
st.title("🎤 国会議員の発言分析")
st.markdown("「議員名＋キーワード」または「政党名＋キーワード」で、国会議事録を検索し、発言内容からキーワードに関する議員や政党の考え方をAIが要約します。要約の根拠となる発言は、要約の下部に表示され、リンクから国会議事録検索システムに移動できます。")
st.markdown("本サイトの生成AIは、gemini-1.5-flashを使用しています。無料枠の上限があるため、上限に達している際は時間を空けて使ってください。本サイトが皆さんの投票の参考になれば幸いです。")
st.markdown("### 🎯 検索条件を設定")

# 政党選択を先に
selected_party = st.selectbox("🏛️ 政党を選択（議員数順）", ["指定しない"] + sorted_parties)

# --- 議員名入力と候補絞り込み（selectbox使用） ---
filtered_df = politicians_df.copy()
if selected_party != "指定しない":
    filtered_df = filtered_df[filtered_df["party"] == selected_party]

all_candidates = filtered_df[["name", "yomi"]].drop_duplicates()
display_candidates = [
    f"{row['name']}（{row['yomi']}）" for _, row in all_candidates.iterrows()
]
selected_display = st.selectbox(
    "👤 議員を選択（漢字またはよみで検索可能）",
    ["指定しない"] + display_candidates,
    index=0
)

if selected_display == "指定しない":
    selected_politician = "指定しない"
else:
    selected_politician = selected_display.split("（")[0]

# 日付範囲
today = datetime.date.today()
five_years_ago = today.replace(year=today.year - 5)
from_date = st.date_input("開始日", value=five_years_ago)
to_date = st.date_input("終了日", value=today)

# --- 最大3つのキーワード欄（ボタンクリックで補完） ---
st.markdown("💡 よく使われる政治キーワード例：")
example_keywords = ["消費税", "子育て支援", "外交", "原発", "防衛費", "教育無償化", "年金", "経済安全保障"]

# セッションステートに入力履歴を保持（リセット用）
if st.button("🔄 キーワードをリセット"):
    st.session_state.kw1 = ""
    st.session_state.kw2 = ""
    st.session_state.kw3 = ""

if "kw1" not in st.session_state:
    st.session_state.kw1 = ""
if "kw2" not in st.session_state:
    st.session_state.kw2 = ""
if "kw3" not in st.session_state:
    st.session_state.kw3 = ""

clicked_keywords = []
cols = st.columns(4)
for i, kw in enumerate(example_keywords):
    if cols[i % 4].button(kw):
        clicked_keywords.append(kw)

# 自動入力（最初の空欄に割り当て）
for kw in clicked_keywords:
    if not st.session_state.kw1:
        st.session_state.kw1 = kw
    elif not st.session_state.kw2:
        st.session_state.kw2 = kw
    elif not st.session_state.kw3:
        st.session_state.kw3 = kw

keyword1 = st.text_input("🗝️ キーワード1", st.session_state.kw1)
keyword2 = st.text_input("🗝️ キーワード2", st.session_state.kw2)
keyword3 = st.text_input("🗝️ キーワード3", st.session_state.kw3)
keywords = [kw.strip() for kw in [keyword1, keyword2, keyword3] if kw.strip()]

# --- 検索ボタン ---
if st.button("📡 検索して分析"):

    with st.spinner("💬 要約準備中..."):

        all_speeches = []
        seen_ids = set()

        if selected_politician != "指定しない":
            speakers = [selected_politician]
        elif selected_party != "指定しない":
            party_members = politicians_df[politicians_df["party"] == selected_party]
            if "position" in party_members.columns:
                influential_members = party_members[party_members["position"].notna()]
                if influential_members.empty:
                    influential_members = party_members
            else:
                influential_members = party_members
            speakers = influential_members["name"].head(5).tolist()
        else:
            st.warning("議員または政党を選択してください。")
            st.stop()

        for kw in keywords:
            for speaker in speakers:
                params = {
                    "speaker": speaker,
                    "any": kw,
                    "from": from_date.strftime("%Y-%m-%d"),
                    "until": to_date.strftime("%Y-%m-%d"),
                    "recordPacking": "json",
                    "maximumRecords": 5,
                    "startRecord": 1,
                }
                try:
                    response = requests.get("https://kokkai.ndl.go.jp/api/speech", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        speeches = data.get("speechRecord", [])
                        for s in speeches:
                            uid = s.get("speechID")
                            if uid and uid not in seen_ids:
                                all_speeches.append(s)
                                seen_ids.add(uid)
                except Exception as e:
                    st.error(f"{speaker} のキーワード「{kw}」検索でエラー: {e}")

        if not all_speeches:
            st.warning("該当する発言が見つかりませんでした。")
            st.stop()

        gemini_input_speeches = all_speeches[:10]
        combined_text = "\n\n".join(
            [f"{s['speaker']}（{s['date']}）: {s['speech']}" for s in gemini_input_speeches]
        )

        if selected_politician != "指定しない":
            prompt = f"""
            以下は日本の国会における{selected_politician}の発言記録です。:\n\n{combined_text}

            まず、各発言が「質問」か「答弁（政策説明）」かを内部的に判別してください（出力には含めないでください）。

            次に、以下2つの出力をそれぞれ順番に提供してください：
            ・「{'、'.join(keywords)}」に関して{selected_politician}が述べた内容を要約し、20字以内の見出しとして出力してください（出力例：「防衛費の増額を支持」などとしてください。出力時の書き出しに「見出し：」のような表記は不要です。）。
            ・そのうえで「{'、'.join(keywords)}」に関して、{selected_politician}がどのような立場や政策的考えを持っているかを、文脈を踏まえて**200字以内**で要約してください。（出力は「{selected_politician}は〜」で始めてください）。
            """
        else:
            prompt = f"""
            以下は日本の国会における{selected_party}に所属する議員の発言記録です。:\n\n{combined_text}

            まず、各発言が「質問」か「答弁（政策説明）」かを内部的に判別してください（出力には含めないでください）。

            次に、以下2つの出力をそれぞれ順番に提供してください：
            ・「{'、'.join(keywords)}」に関して{selected_party}の立場を要約し、20字以内の見出しとして出力してください（出力例：「消費税減税に慎重姿勢」などとしてください。出力時の書き出しに「見出し：」のような表記は不要です。）。
            ・そのうえで「{'、'.join(keywords)}」に関して、{selected_party}がどのような政策的立場・思想を持っているかを、文脈を踏まえて**200字以内**で要約してください。（出力は「{selected_party}は〜」で始めてください）。
            """

        try:
            result = model.generate_content(prompt)
            summary = result.text
        except Exception as e:
            if "ResourceExhausted" in str(e) or "quota" in str(e).lower():
                st.error("🚫 現在、生成AIの利用上限に達している可能性があります。時間をおいて再度お試しください。")
            else:
                st.error(f"⚠️ 要約生成中に予期しないエラーが発生しました: {e}")
            st.stop()

        st.subheader("📝 生成AIによる要約")
        st.write(summary)

        st.subheader("📚 発言の詳細")
        for s in all_speeches:
            meeting_name = s.get("nameOfMeeting") or s.get("meeting") or "会議名不明"
            speaker_name = normalize(s["speaker"])
            house_info = politicians_df[politicians_df["name"] == speaker_name]["house"]
            house = house_info.values[0] if len(house_info) else "所属院不明"

            st.markdown(f"**{s['speaker']}（{s['date']}／{house}）**")
            st.markdown(f"会議名：{meeting_name}")

            highlighted = highlight_keywords_multi(s["speech"], keywords)
            st.markdown(f"> {highlighted}", unsafe_allow_html=True)

            st.markdown(f"[🔗 会議録を見る]({s.get('meetingURL', '#')})")
            st.markdown("---")


