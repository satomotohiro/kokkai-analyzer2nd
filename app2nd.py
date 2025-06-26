import streamlit as st
import pandas as pd
import requests
import datetime
import os
import google.generativeai as genai
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash")

# CSV読み込み
politicians_df = pd.read_csv("politicians.csv", encoding="utf-8")
politicians_df["name"] = politicians_df["name"].str.replace("　", "")  # 全角スペース除去
politician_names = sorted(politicians_df["name"].unique())

# 主要政党順（必要に応じて調整可）
main_parties_order = ["自由民主党", "立憲民主党", "日本維新の会", "公明党", "国民民主党", "共産党", "れいわ新選組", "社民党", "無所属"]
party_names = sorted(politicians_df["party"].dropna().unique(), key=lambda x: main_parties_order.index(x) if x in main_parties_order else 999)

# タイトル
st.title("💡 国会議員の発言分析 by 生成AI")
st.markdown("議事録から該当発言をAIで分析し、政治家や政党の思想傾向を可視化します。")

# 入力UI
st.markdown("### 🎯 検索条件を設定")

# 政党を先に選択
selected_party = st.selectbox("🏛️ 政党を選択", ["（指定しない）"] + party_names)

# 政党に応じた議員リストを動的にフィルタ
if selected_party != "（指定しない）":
    filtered_names = sorted(politicians_df[politicians_df["party"] == selected_party]["name"].unique())
else:
    filtered_names = politician_names

selected_politician = st.selectbox("👤 国会議員を選択", ["（指定しない）"] + filtered_names)
manual_input = st.text_input("または名前を直接入力（例：大石あきこ）")

# 議員名が入力されたら政党を自動入力（上書きはしない）
auto_party = ""
if manual_input:
    matched = politicians_df[politicians_df["name"].str.replace("　", "") == manual_input]
    if not matched.empty:
        auto_party = matched["party"].values[0]
        if selected_party == "（指定しない）":
            selected_party = auto_party
            st.info(f"🧾 議員の所属政党を自動補完：**{auto_party}**")

# キーワード
keyword = st.text_input("🗝️ キーワードを入力（例：防衛）")

# 日付
today = datetime.date.today()
five_years_ago = today.replace(year=today.year - 5)
from_date = st.date_input("開始日", value=five_years_ago)
to_date = st.date_input("終了日", value=today)

# 実行ボタン
if st.button("📡 検索して分析"):
    st.info("検索中...")

    # 最終的な検索議員名
    speaker = manual_input if manual_input else (selected_politician if selected_politician != "（指定しない）" else None)

    # APIパラメータ
    params = {
        "speaker": speaker,
        "party": selected_party if speaker is None and selected_party != "（指定しない）" else None,
        "any": keyword,
        "from": from_date.strftime("%Y-%m-%d"),
        "until": to_date.strftime("%Y-%m-%d"),
        "recordPacking": "json",
        "maximumRecords": 10,
        "startRecord": 1,
    }

    try:
        with st.spinner("国会議事録を検索中..."):
            response = requests.get("https://kokkai.ndl.go.jp/api/speech", params={k: v for k, v in params.items() if v})
            st.markdown(f"🔗 API送信URL： `{response.url}`")

            if response.status_code != 200:
                st.error(f"❌ APIリクエスト失敗: {response.status_code}")
            else:
                data = response.json()
                speeches = data.get("speechRecord", [])

                if not speeches:
                    st.warning("指定した条件に一致する発言が見つかりませんでした。")
                else:
                    combined_text = "\n\n".join([f"{s['speaker']}（{s['date']}）: {s['speech']}" for s in speeches])

                    prompt = (
                        f"以下は日本の国会での発言の抜粋です。この政治家や政党が「{keyword}」に関してどのような思想や立場を持っているかを"
                        f"200字以内で簡潔にまとめてください：\n\n{combined_text[:8000]}"
                    )

                    with st.spinner("生成AIで分析中..."):
                        result = model.generate_content(prompt)
                        st.subheader("💡 生成AIによる分析結果")
                        st.write(result.text)

                    st.subheader("📚 根拠となる発言抜粋")
                    for s in speeches:
                        speaker_name = s.get("speaker", "不明")
                        chamber = s.get("speakerPosition", "所属院不明")
                        highlighted = s["speech"].replace(keyword, f"<span style='background-color: #fff3cd'>{keyword}</span>")
                        st.markdown(f"**{speaker_name}（{chamber} / {s['date']}）**", unsafe_allow_html=True)
                        st.markdown(f"会議名：{s.get('meeting', '不明')}")
                        st.markdown(f"> {highlighted}", unsafe_allow_html=True)
                        st.markdown(f"[🔗 会議録を見る]({s['meetingURL']})")
                        st.markdown("---")
    except Exception as e:
        st.error(f"❌ エラーが発生しました: {e}")
