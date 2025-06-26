import streamlit as st
import pandas as pd
import requests
import datetime
import os
import google.generativeai as genai
from dotenv import load_dotenv

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

# 主要政党優先の表示順
major_parties = ["自由民主党", "立憲民主党", "日本維新の会", "公明党", "国民民主党", "共産党", "れいわ新選組"]
all_parties = sorted(politicians_df["party"].dropna().unique())
sorted_parties = major_parties + [p for p in all_parties if p not in major_parties]

# --- UI ---
st.title("🎤 国会議員の発言分析")

st.markdown("### 🎯 検索条件を設定")

# 政党選択を先に
selected_party = st.selectbox("🏛️ 政党を選択", ["指定しない"] + sorted_parties)

# 議員入力（フリガナ対応）
user_input = st.text_input("👤 議員名（漢字またはよみ）")

# 議員候補フィルター（政党指定ありなら絞る）
filtered_df = politicians_df.copy()
if selected_party != "指定しない":
    filtered_df = filtered_df[filtered_df["party"] == selected_party]

if user_input:
    filtered_df = filtered_df[
        filtered_df["name"].str.contains(user_input) | filtered_df["yomi"].str.contains(user_input)
    ]

politician_candidates = sorted(filtered_df["name"].unique())
selected_politician = st.selectbox("一致する議員候補", ["指定しない"] + politician_candidates)

# 日付範囲
today = datetime.date.today()
five_years_ago = today.replace(year=today.year - 5)
from_date = st.date_input("開始日", value=five_years_ago)
to_date = st.date_input("終了日", value=today)

# キーワード
keyword = st.text_input("🗝️ キーワードを入力（例：消費税）")

# --- 検索ボタン ---
if st.button("📡 検索して分析"):

    if selected_politician != "指定しない":
        speakers = [selected_politician]
    elif selected_party != "指定しない":
        party_members = politicians_df[politicians_df["party"] == selected_party]
        top_members = party_members.head(5)
        speakers = top_members["name"].tolist()
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

    # --- Gemini 要約 ---
    combined_text = "\n\n".join(
        [f"{s['speaker']}（{s['date']}）: {s['speech']}" for s in all_speeches]
    )
    prompt = (
        f"以下は国会議員の発言です。「{keyword}」に対する見解を200字以内で要約してください：\n\n{combined_text}"
    )

    with st.spinner("🧠 要約生成中..."):
        result = model.generate_content(prompt)
        st.subheader("📝 生成AIによる要約")
        st.write(result.text)

    # --- 結果表示 ---
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
