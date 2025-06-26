import streamlit as st
import requests
import datetime
import google.generativeai as genai
import os
from dotenv import load_dotenv
import pandas as pd

# 環境変数読み込み
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash")

# CSV読み込み（エンコーディング対策）
try:
    politicians_df = pd.read_csv("politicians.csv", encoding="utf-8")
except UnicodeDecodeError:
    politicians_df = pd.read_csv("politicians.csv", encoding="shift_jis")

# 整形
def normalize_name(name):
    return name.replace("　", "").replace(" ", "") if name else ""

politicians_df["name"] = politicians_df["name"].apply(normalize_name)

# 主要政党順指定
main_party_order = ["自由民主党", "立憲民主党", "国民民主党", "日本維新の会", "公明党", "共産党", "れいわ新選組", "社民党", "無所属"]
def party_sort_key(p):
    return main_party_order.index(p) if p in main_party_order else 999

party_names = sorted(politicians_df["party"].dropna().unique(), key=party_sort_key)
politician_names = sorted(politicians_df["name"].unique())

# UIヘッダー
st.title("💡 国会議員の発言分析 by 生成AI")
st.markdown("議事録から該当発言をAIで分析し、政治家や政党の思想傾向を可視化します。")

# 検索条件
st.markdown("### 🎯 検索条件を設定")

selected_party = st.selectbox("🏛️ 政党を選択", ["指定しない"] + party_names)

# 政党に応じて議員候補を絞る
if selected_party != "指定しない":
    filtered_df = politicians_df[politicians_df["party"] == selected_party]
    filtered_names = sorted(filtered_df["name"].unique())
else:
    filtered_names = politician_names

selected_politician_input = st.selectbox(
    "👤 国会議員を選択または入力（例：河野太郎）",
    ["指定しない"] + filtered_names,
    index=0
)

# 自動政党補完
if selected_politician_input != "指定しない":
    matched_row = politicians_df[politicians_df["name"] == normalize_name(selected_politician_input)]
    if not matched_row.empty:
        detected_party = matched_row["party"].values[0]
        if selected_party == "指定しない":
            st.info(f"🧾 所属政党を自動補完：**{detected_party}**")
            selected_party = detected_party

keyword = st.text_input("🗝️ キーワードを入力（例：消費税）")

# 日付指定
today = datetime.date.today()
five_years_ago = today.replace(year=today.year - 5)
from_date = st.date_input("開始日", value=five_years_ago)
to_date = st.date_input("終了日", value=today)

if st.button("📡 検索して分析"):
    st.info("検索中...")

    speaker = normalize_name(selected_politician_input)

    if speaker != "指定しない":
        speakers_to_search = [speaker]
    elif selected_party != "指定しない":
        party_members = politicians_df[politicians_df["party"] == selected_party]
        influential_members = party_members[party_members["position"].notna()] if "position" in party_members else party_members
        if influential_members.empty:
            influential_members = party_members
        speakers_to_search = influential_members["name"].tolist()[:5]
    else:
        st.warning("議員または政党を選択してください。")
        st.stop()

    all_speeches = []
    base_url = "https://kokkai.ndl.go.jp/api/speech"

    for name in speakers_to_search:
        params = {
            "speaker": name,
            "any": keyword,
            "from": from_date.strftime("%Y-%m-%d"),
            "until": to_date.strftime("%Y-%m-%d"),
            "recordPacking": "json",
            "maximumRecords": 5,
            "startRecord": 1,
        }

        with st.spinner(f"{name} の発言を取得中..."):
            try:
                response = requests.get(base_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    speeches = data.get("speechRecord", [])
                    all_speeches.extend(speeches)
            except Exception as e:
                st.error(f"{name} のデータ取得中にエラー: {e}")

    if not all_speeches:
        st.warning("該当する発言が見つかりませんでした。")
        st.stop()

    combined_text = "\n\n".join([f"{s['speaker']}（{s['date']}）: {s['speech']}" for s in all_speeches])
    prompt = f"以下は日本の国会での発言の抜粋です。この政治家たち（政党: {selected_party if selected_party != '指定しない' else '不明'}）が「{keyword}」に関してどのような思想や立場を持っているかを、200字以内で簡潔にまとめてください：\n\n{combined_text}"

    with st.spinner("生成AIで分析中..."):
        result = model.generate_content(prompt)
        ai_summary = result.text
        st.subheader("🧠 生成AIによる分析結果")
        st.write(ai_summary)

    st.subheader("📚 根拠となる発言抜粋")
    for s in all_speeches:
        highlighted = s["speech"].replace(keyword, f"**:orange[{keyword}]**")
        meeting_name = s.get("nameOfMeeting") or s.get("meeting") or "不明"
        speaker_name = normalize_name(s["speaker"])
        house = politicians_df.loc[politicians_df["name"] == speaker_name, "house"].values
        house_str = house[0] if len(house) > 0 else "所属院不明"

        st.markdown(f"**{s['speaker']}（{s['date']}／{house_str}）**")
        st.markdown(f"会議名：{meeting_name}")
        st.markdown(f"> {highlighted}")
        st.markdown(f"[🔗 会議録を見る]({s['meetingURL']})")
        st.markdown("---")
