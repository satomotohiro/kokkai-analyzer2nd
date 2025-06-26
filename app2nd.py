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

clicked_keywords = []
cols = st.columns(4)
for i, kw in enumerate(example_keywords):
    if cols[i % 4].button(kw):
        clicked_keywords.append(kw)

# セッションステートに入力履歴を保持
if "kw1" not in st.session_state:
    st.session_state.kw1 = ""
if "kw2" not in st.session_state:
    st.session_state.kw2 = ""
if "kw3" not in st.session_state:
    st.session_state.kw3 = ""

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

# 以下のロジックは変更せずに続きます ...（検索ボタン以降）
