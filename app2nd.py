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

# 国会議員データ読み込み
try:
    politicians_df = pd.read_csv("politicians.csv", encoding="utf-8")
except UnicodeDecodeError:
    politicians_df = pd.read_csv("politicians.csv", encoding="shift_jis")

politician_names = sorted(politicians_df["name"].unique())
party_names = sorted(politicians_df["party"].dropna().unique())

# ヘッダー
st.title("🧠 国会議員の発言分析 by 生成AI")
st.markdown("議事録から該当発言をAIで分析し、政治家や政党の思想傾向を可視化します。")

# 入力欄
st.markdown("### 🎯 検索条件を設定")
col1, col2 = st.columns(2)
with col1:
    selected_politician = st.selectbox("👤 国会議員を選択", [""] + politician_names)
    manual_input = st.text_input("または名前を直接入力（例：河野太郎）")
with col2:
    selected_party = st.selectbox("🏛️ 政党を選択", [""] + party_names)
    keyword = st.text_input("🗝️ キーワードを入力（例：防衛）")

# 日付指定
today = datetime.date.today()
five_years_ago = today.replace(year=today.year - 5)
from_date = st.date_input("開始日", value=five_years_ago)
to_date = st.date_input("終了日", value=today)

# 実行ボタン
if st.button("📡 検索して分析"):
    st.info("検索中...")
    speaker = manual_input if manual_input else selected_politician

    # 検索対象議員のリスト
    if speaker:
        speakers_to_search = [speaker]
    elif selected_party:
        party_members = politicians_df[politicians_df["party"] == selected_party]
        if "position" in party_members.columns:
            influential_members = party_members[party_members["position"].notna()]
            if influential_members.empty:
                influential_members = party_members
        else:
            influential_members = party_members
        speakers_to_search = influential_members["name"].tolist()[:5]
    else:
        st.warning("議員または政党を選択してください。")
        st.stop()

    # 発言収集
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

    # ✅ 政党フィルタ（安全に処理）
    filtered_speeches = []
    if selected_party:
        for s in all_speeches:
            speaker_group = s.get("speakerGroup", "")
            party = s.get("party", "")
            if selected_party in speaker_group or selected_party in party:
                filtered_speeches.append(s)
    else:
        filtered_speeches = all_speeches

    if not filtered_speeches:
        st.warning("指定した政党に一致する発言が見つかりませんでした。")
        st.stop()

    # 発言を結合
    combined_text = "\n\n".join(
        [f"{s['speaker']}（{s['date']}）: {s['speech']}" for s in filtered_speeches]
    )

    # プロンプト生成とAI解析
    prompt = (
        f"以下は日本の国会での発言の抜粋です。この政治家たち（政党: {selected_party if selected_party else '不明'}）が「{keyword}」に関して"
        f"どのような思想や立場を持っているかを、200字以内で簡潔にまとめてください：\n\n{combined_text}"
    )

    with st.spinner("生成AIで分析中..."):
        result = model.generate_content(prompt)
        ai_summary = result.text
        st.subheader("🧠 生成AIによる分析結果")
        st.write(ai_summary)

    # 発言を表示
    st.subheader("📚 根拠となる発言抜粋")
    for s in filtered_speeches:
        highlighted = s["speech"].replace(keyword, f"**:orange[{keyword}]**")
        st.markdown(f"**{s['speaker']}（{s['date']}）**")
        st.markdown(f"会議名：{s.get('meeting', '不明')}")
        st.markdown(f"> {highlighted}")
        st.markdown(f"[🔗 会議録を見る]({s['meetingURL']})")
        st.markdown("---")
