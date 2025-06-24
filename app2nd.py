import streamlit as st
import requests
import datetime
import google.generativeai as genai
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# 環境変数読み込み
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("models/gemini-1.5-flash")

# 国会議員データ取得
@st.cache_data(ttl=86400)
def get_current_politicians():
    urls = [
        ("衆議院", "https://ja.wikipedia.org/wiki/日本の衆議院議員一覧"),
        ("参議院", "https://ja.wikipedia.org/wiki/日本の参議院議員一覧")
    ]
    politicians = []
    for house, url in urls:
        res = requests.get(url)
        soup = BeautifulSoup(res.content, "html.parser")
        tables = soup.select("table.wikitable")
        for table in tables:
            for row in table.select("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    name = cols[0].text.strip().split('（')[0]
                    party = cols[1].text.strip().split('（')[0]
                    if name:
                        politicians.append({"name": name, "party": party, "house": house})
    return politicians

# データ取得
politicians = get_current_politicians()
politician_names = sorted({p["name"] for p in politicians})
party_names = sorted({p["party"] for p in politicians})

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

# 日付
today = datetime.date.today()
five_years_ago = today.replace(year=today.year - 5)
from_date = st.date_input("開始日", value=five_years_ago)
to_date = st.date_input("終了日", value=today)

# ボタン
if st.button("📡 検索して分析"):
    st.info("検索中...")
    speaker = manual_input if manual_input else selected_politician
    base_url = "https://kokkai.ndl.go.jp/api/speech"
    params = {
        "speaker": speaker,
        "party": selected_party if not speaker else None,
        "any": keyword,
        "from": from_date.strftime("%Y-%m-%d"),
        "until": to_date.strftime("%Y-%m-%d"),
        "recordPacking": "json",
        "maximumRecords": 10,
        "startRecord": 1,
    }

    with st.spinner("国会議事録を検索中..."):
        try:
            response = requests.get(base_url, params={k: v for k, v in params.items() if v})
            st.markdown(f"🔗 API送信URL： `{response.url}`")

            if response.status_code == 200:
                data = response.json()
                if data["numberOfRecords"] == 0:
                    st.warning("該当する発言が見つかりませんでした。")
                else:
                    speeches = data.get("speechRecord", [])
                    combined_text = "\n\n".join(
                        [f"{s['speaker']}（{s['date']}）: {s['speech']}" for s in speeches]
                    )

                    prompt = (
                        f"以下は日本の国会での発言の抜粋です。この政治家や政党が「{keyword}」に関してどのような思想や立場を持っているかを"
                        f"200字以内で簡潔にまとめてください：\n\n{combined_text}"
                    )

                    with st.spinner("生成AIで分析中..."):
                        result = model.generate_content(prompt)
                        ai_summary = result.text
                        st.subheader("🧠 生成AIによる分析結果")
                        st.write(ai_summary)

                        st.subheader("📚 根拠となる発言抜粋")
                        for s in speeches:
                            highlighted = s["speech"].replace(keyword, f"**:orange[{keyword}]**")
                            st.markdown(f"**{s['speaker']}（{s['date']}）**")
                            st.markdown(f"会議名：{s.get('meeting', '不明')}")
                            st.markdown(f"> {highlighted}")
                            st.markdown(f"[🔗 会議録を見る]({s['meetingURL']})")
                            st.markdown("---")
            else:
                st.error(f"❌ APIリクエスト失敗（status: {response.status_code}）\n\n{response.text}")
        except Exception as e:
            st.error(f"❌ エラー発生: {e}")
