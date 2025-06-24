import streamlit as st
import requests
import datetime
import google.generativeai as genai
from bs4 import BeautifulSoup

# --- 環境変数読み込み（Cloud Secrets前提）
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash")

# --- Wikipedia API：所属政党取得 + 衆/参判定
@st.cache_data(ttl=86400)
def fetch_politician_info(name):
    url = "https://ja.wikipedia.org/wiki/" + requests.utils.quote(name)
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    party = soup.find("th", string="所属政党")
    chamber = soup.select_one("th:contains('所属') ~ td")
    return {
        "party": party.find_next_sibling("td").get_text(strip=True) if party else "不明",
        "chamber": "参議院" if "参議院" in name or "参議院" in str(chamber) else "衆議院"
    }

# --- Wikipedia API：議員一覧取得
@st.cache_data(ttl=86400)
def fetch_politicians(house):
    URL = "https://ja.wikipedia.org/w/api.php"
    title = ("Category:Members_of_the_House_of_Representatives_(Japan)_2024–"
             if house=="衆議院" else "Category:Members_of_the_Sangiin_(Japan)_2024–")
    r = requests.get(URL, params={"action":"query","format":"json",
                                  "list":"categorymembers","cmtitle":title,"cmlimit":"500"})
    return sorted(m["title"] for m in r.json()["query"]["categorymembers"])

# --- UI
st.title("🧩 国会議事録AI分析＋強化機能")

house = st.sidebar.selectbox("議院を選択", ("衆議院", "参議院"))
politicians = fetch_politicians(house)
st.sidebar.write("または自由入力で議員名を入力")
speaker = st.sidebar.selectbox("議員を選ぶ", options=politicians)
custom = st.sidebar.text_input("または入力", "")
speaker = custom.strip() or speaker

keyword = st.text_input("検索キーワード（例：防衛）")

fd = datetime.date.today()
td = fd.replace(year=fd.year-5)
from_date = st.date_input("開始日", value=td, format="YYYY-MM-DD")
to_date = st.date_input("終了日", value=fd, format="YYYY-MM-DD")

if st.button("🔍 分析開始"):
    info = fetch_politician_info(speaker)
    st.write(f"**所属政党：{info['party']}／所属議院：{info['chamber']}**")

    # API取得
    resp = requests.get("https://kokkai.ndl.go.jp/api/speech", params={
        "speaker": speaker, "any": keyword,
        "from": from_date, "until": to_date,
        "recordPacking":"json", "maximumRecords":10
    })
    st.markdown(f"`{resp.url}`")
    recs = resp.json().get("speechRecord", [])
    if not recs:
        st.warning("発言なし")
        st.stop()

    # 要約（キーワード中心）
    merged = "\n\n".join(f"{r['speech']}" for r in recs)
    prompt = (f"以下の国会発言を「{keyword}」に関して3～5行で箇条書きにしてください。\n\n{merged}")
    ai = model.generate_content(prompt).text.strip()
    st.subheader("🧠 AI要約（キーワード中心）")
    st.markdown(ai)

    # 抜粋とリンク
    st.subheader("📚 発言抜粋（キーワードハイライト付）")
    for r in recs:
        meta = f"{r['date']}／{r['nameOfMeeting']}・号数{r['issue']}"
        text = r['speech'].replace(keyword, f"**<mark>{keyword}</mark>**")
        st.markdown(f"**{meta}**")
        st.markdown(text, unsafe_allow_html=True)
        st.markdown(f"[🔗 会議録へ]({r['meetingURL']})")
        st.markdown("---")
