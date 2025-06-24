import streamlit as st
import requests
import datetime
import google.generativeai as genai
import os
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini APIの初期化
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash")

# タイトル
st.title("国会議事録_AI分析")

# 入力フォーム
with st.form("search_form"):
    speaker = st.text_input("政治家の名前（例：河野太郎）")
    keyword = st.text_input("キーワード（例：防衛）")

    today = datetime.date.today()
    five_years_ago = today.replace(year=today.year - 5)

    from_date = st.date_input("国会議事録検索_開始日", value=five_years_ago, format="YYYY-MM-DD")
    to_date = st.date_input("国会議事録検索_終了日", value=today, format="YYYY-MM-DD")

    submitted = st.form_submit_button("検索して分析")

# フォーム送信後の処理
if submitted:
    with st.spinner("国会議事録を検索中..."):
        # APIのURL構築
        base_url = "https://kokkai.ndl.go.jp/api/speech"
        params = {
            "speaker": speaker,
            "any": keyword,
            "from": from_date.strftime("%Y-%m-%d"),
            "until": to_date.strftime("%Y-%m-%d"),
            "recordPacking": "json",
            "maximumRecords": 10,
            "startRecord": 1,
        }

        try:
            response = requests.get(base_url, params=params)
            st.markdown(f"🔗 APIに送信されたURL：\n\n`{response.url}`")

            if response.status_code == 200:
                data = response.json()

                if data["numberOfRecords"] == 0:
                    st.warning("該当する発言が見つかりませんでした。")
                else:
                    # 発言をまとめてテキスト化
                    speeches = data.get("speechRecord", [])
                    combined_text = "\n\n".join(
                        [f"{s['speaker']}（{s['date']}）: {s['speech']}" for s in speeches]
                    )
                    with st.spinner("生成AIで分析中..."):
                        try:
                            prompt = (
                                f"以下は日本の国会での発言の抜粋です。\n\n"
                                f"この政治家がこのテーマについてどのような考えを持っているかを、簡潔に3～5項目で箇条書きしてください。\n"
                                f"1文あたり50文字以内で、明確な主張や論点を中心にまとめてください。\n"
                                f"敬語や冗長な言い回しは避け、率直な分析を行ってください。\n\n"
                                f"{combined_text}"
                            )
                            result = model.generate_content(prompt)
                            ai_summary = result.text.strip()
                    
                            st.subheader("🧠 生成AIによる分析結果（簡潔要約）")
                            st.markdown(ai_summary)
                    
                            st.subheader("📚 根拠となる発言抜粋")
                            for s in speeches:
                                st.markdown(f"**{s['speaker']}（{s['date']}）**")
                                st.markdown(f"> {s['speech']}")
                                st.markdown(f"[🔗 会議録を見る]({s['meetingURL']})")
                                st.markdown("---")
                    
                        except Exception as e:
                            st.error(f"❌ Gemini APIエラー: {e}")
            else:
                st.error(f"❌ APIリクエストに失敗しました（status: {response.status_code}）\n\n{response.text}")

        except Exception as e:
            st.error(f"❌ エラーが発生しました: {e}")
