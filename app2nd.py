import streamlit as st
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import re

# --- ハイライト表示用関数 ---
def highlight_keywords(text, keyword):
    if keyword:
        highlighted = re.sub(
            f"({re.escape(keyword)})",
            r'<span style="background: repeating-linear-gradient(45deg, yellow, yellow 4px, transparent 4px, transparent 8px);"></span>',
            text,
            flags=re.IGNORECASE
        )
        return highlighted
    return text

# --- 賛否スコア可視化 ---
def show_sentiment_bar(score):
    fig, ax = plt.subplots(figsize=(5, 0.4))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("sentiment", ["red", "gray", "green"])
    norm_score = (score + 1) / 2  # -1 to 1 → 0 to 1
    ax.barh([0], [norm_score], color=cmap(norm_score), height=0.5)
    ax.set_xlim(0, 1)
    ax.set_yticks([])
    ax.set_xticks([0, 0.5, 1])
    ax.set_xticklabels(["反対", "中立", "賛成"])
    ax.set_title("立場スコア（-1=反対、+1=賛成）", fontsize=10)
    st.pyplot(fig)

# --- テスト用表示 ---
st.title("💬 発言の視覚的分析 UI")

sample_speech = "私は消費税の引き上げに賛成です。しかしその際には低所得者対策が必要です。"
keyword = st.text_input("キーワード", value="消費税")

st.markdown("### 📌 ハイライト表示")
st.markdown(highlight_keywords(sample_speech, keyword), unsafe_allow_html=True)

st.markdown("### 📊 賛否スコア表示")
sample_score = st.slider("AIが推定した賛否スコア", -1.0, 1.0, 0.6, 0.1)
show_sentiment_bar(sample_score)
