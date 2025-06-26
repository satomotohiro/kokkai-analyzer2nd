import streamlit as st
import pandas as pd
import requests
import datetime
import os
import google.generativeai as genai
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib

# --- APIキーの設定 ---
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash")

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

st.markdown("### 🎯 検索条件を設定")

# 政党選択を先に
selected_party = st.selectbox("🏛️ 政党を選択（議員数順）", ["指定しない"] + sorted_parties)

# --- 議員名入力と候補絞り込み（selectbox使用） ---
filtered_df = politicians_df.copy()
if selected_party != "指定しない":
    filtered_df = filtered_df[filtered_df["party"] == selected_party]

# 全候補リスト（政党指定ありならその政党の議員のみ）
all_candidates = filtered_df[["name", "yomi"]].drop_duplicates()

# フリガナ付き表示（ユーザー向け）
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

# キーワード
keyword = st.text_input("🗝️ キーワードを入力（例：消費税）")

# --- 検索ボタン ---
if st.button("📡 検索して分析"):

    if selected_politician and selected_politician != "指定しない":
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

    all_speeches = []
    for speaker in speakers:
        params = {
            "speaker": speaker,
            "any": keyword,
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
                all_speeches.extend(data.get("speechRecord", []))
        except Exception as e:
            st.error(f"{speaker} のデータ取得エラー: {e}")

    if not all_speeches:
        st.warning("該当する発言が見つかりませんでした。")
        st.stop()

    combined_text = "\n\n".join(
        [f"{s['speaker']}（{s['date']}）: {s['speech']}" for s in all_speeches]
    )

    # --- 要約プロンプト構築 ---
    if selected_politician != "指定しない":
        prompt = f"""
以下は日本の国会における{selected_politician}の発言記録です。
まず、各発言が「質問」か「答弁（政策説明）」かを内部的に判別してください（出力には含めないでください）。
そのうえで「{keyword}」に関して、{selected_politician}がどのような立場や政策的考えを持っているかを、文脈を踏まえて**200字以内**で要約してください。
出力は次のように始めてください：
「{selected_politician}は〜」
"""
    else:
        prompt = f"""
以下は日本の国会における{selected_party}に所属する議員の発言記録です。
まず、各発言が「質問」か「答弁（政策説明）」かを内部的に判別してください（出力には含めないでください）。
そのうえで「{keyword}」に関して、{selected_party}がどのような政策的立場・思想を持っているかを、答弁内容を重視して**200字以内**で要約してください。
出力は次のように始めてください：
「{selected_party}は〜」
"""

    with st.spinner("🧠 要約生成中..."):
        result = model.generate_content(prompt + "\n\n" + combined_text)
        st.subheader("📝 生成AIによる要約")
        st.write(result.text)

        # --- 賛否スコア表示 ---
        st.markdown("### 📊 賛否スコア表示（仮）")
        score = st.slider("AIが推定した賛否スコア（デモ用）", -1.0, 1.0, 0.0, 0.1)

        def show_sentiment_bar(score):
            fig, ax = plt.subplots(figsize=(5, 0.4))
            cmap = matplotlib.colors.LinearSegmentedColormap.from_list("sentiment", ["red", "gray", "green"])
            norm_score = (score + 1) / 2
            ax.barh([0], [norm_score], color=cmap(norm_score), height=0.5)
            ax.set_xlim(0, 1)
            ax.set_yticks([])
            ax.set_xticks([0, 0.5, 1])
            ax.set_xticklabels(["反対", "中立", "賛成"])
            ax.set_title("立場スコア（-1=反対、+1=賛成）", fontsize=10)
            st.pyplot(fig)

        show_sentiment_bar(score)

    st.subheader("📚 発言の詳細")
    for s in all_speeches:
        highlighted = s["speech"].replace(keyword, f"**:orange[{keyword}]**")
        meeting_name = s.get("nameOfMeeting") or s.get("meeting") or "会議名不明"
        speaker_name = normalize(s["speaker"])
        house_info = politicians_df[politicians_df["name"] == speaker_name]["house"]
        house = house_info.values[0] if len(house_info) else "所属院不明"

        st.markdown(f"**{s['speaker']}（{s['date']}／{house}）**")
        st.markdown(f"会議名：{meeting_name}")
        st.markdown(f"> {highlighted}")
        st.markdown(f"[🔗 会議録を見る]({s.get('meetingURL', '#')})")
        st.markdown("---")
