"""Streamlit entry point wiring together crawler, sentiment, and storage."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd
import streamlit as st

import crawler
import db
import sentiment
import utils

st.set_page_config(page_title="微博情绪分析", layout="wide")
db.init_db()


def main() -> None:
    st.title("微博评论情绪分析与可视化")
    st.caption("输入微博热帖链接、评论文本或批量文件，快速完成六情绪多标签分析。")

    tab_url, tab_text, tab_file, tab_history = st.tabs(
        ["网址直分析", "文本即时分析", "文件批量分析", "历史查询"]
    )

    with tab_url:
        render_url_tab()
    with tab_text:
        render_text_tab()
    with tab_file:
        render_file_tab()
    with tab_history:
        render_history_tab()


def render_url_tab() -> None:
    st.subheader("输入微博 URL")
    url = st.text_input("微博热帖链接")
    col1, col2, col3 = st.columns(3)
    title = col1.text_input("标题（可选）")
    topic = col2.text_input("话题（可选）")
    max_comments = col3.slider("抓取评论数量", min_value=10, max_value=2000, value=200, step=10)

    if st.button("开始采集并分析", use_container_width=True, disabled=not url):
        try:
            with st.spinner("抓取评论并执行情绪分析..."):
                post_meta, comments = crawler.fetch_post_with_comments(url, max_comments=max_comments)
        except Exception as exc:
            st.error(f"采集失败：{exc}")
            return

        if not comments:
            st.warning("未成功抓取到评论，请检查链接或稍后重试。")
            return

        if title:
            post_meta["title"] = title
        if topic:
            post_meta["topic"] = topic

        st.success(f"共采集 {len(comments)} 条评论，分析完成。")

        post_id = db.insert_post(
            {
                "url": post_meta.get("url") or url,
                "title": post_meta.get("title") or "未命名热帖",
                "topic": post_meta.get("topic") or "",
                "like_cnt": post_meta.get("like_cnt"),
                "repost_cnt": post_meta.get("repost_cnt"),
                "comment_cnt": len(comments),
            }
        )
        comment_ids = db.insert_comments(post_id, comments)

        texts = [comment["text"] for comment in comments]
        prob_list, label_list = sentiment.predict(texts)
        db.insert_emotions(prob_list, label_list, comment_ids)

        render_analysis_results(post_id, comments, prob_list, label_list, post_meta=post_meta)


def render_text_tab() -> None:
    st.subheader("单条评论即时分析")
    text = st.text_area("请输入微博评论内容")
    threshold = st.slider("情绪标签阈值", min_value=0.1, max_value=0.9, value=0.5, step=0.05)

    if st.button("分析文本", disabled=not text.strip()):
        prob_list, label_list = sentiment.predict([text], thresh=threshold)
        if not prob_list:
            st.info("未能分析该文本，请重试。")
            return
        table = pd.DataFrame(
            [prob_list[0]],
            columns=sentiment.EMOTIONS,
        )
        st.write("概率分布")
        st.dataframe(table.style.format("{:.2%}"), use_container_width=True)
        st.write("情绪标签", "、".join(label_list[0]))


def render_file_tab() -> None:
    st.subheader("批量导入评论文件")
    uploaded = st.file_uploader("上传 CSV / XLSX / TXT 文件", type=["csv", "xlsx", "txt"])
    threshold = st.slider("情绪标签阈值", min_value=0.1, max_value=0.9, value=0.5, step=0.05, key="file_thresh")

    if uploaded and st.button("批量分析"):
        comments = load_comments_from_file(uploaded)
        if not comments:
            st.warning("未从文件中解析到有效文本。")
            return
        texts = [row["text"] for row in comments]
        prob_list, label_list = sentiment.predict(texts, thresh=threshold)
        render_analysis_summary(comments, prob_list, label_list)


def render_history_tab() -> None:
    st.subheader("历史分析记录")
    posts = db.get_recent_posts()
    if not posts:
        st.info("暂无历史记录。")
        return
    options = {f"{row['title']}（{row['created_at']}）": row["id"] for row in posts}
    selection = st.selectbox("选择历史帖", options.keys())
    post_id = options[selection]

    comments = db.get_comments_with_emotions(post_id)
    if not comments:
        st.info("历史记录暂无评论分析结果。")
        return

    prob_list = [
        [
            (row["anger"] or 0.0),
            (row["disgust"] or 0.0),
            (row["fear"] or 0.0),
            (row["joy"] or 0.0),
            (row["sadness"] or 0.0),
            (row["surprise"] or 0.0),
        ]
        for row in comments
    ]
    label_list = [
        [label for label in (row["top_labels"] or "").split(",") if label] for row in comments
    ]
    formatted_comments = []
    for row in comments:
        data = dict(row)
        formatted_comments.append(
            {
                "user": data.get("user", "未知用户"),
                "text": data.get("text", ""),
                "ts": data.get("ts", ""),
                "likes": data.get("likes", 0),
            }
        )
    post_meta = next((dict(row) for row in posts if row["id"] == post_id), None)
    render_analysis_results(post_id, formatted_comments, prob_list, label_list, post_meta=post_meta)


def render_analysis_results(
    post_id: int,
    comments: Sequence[Dict[str, str]],
    prob_list: Sequence[Sequence[float]],
    label_list: Sequence[Sequence[str]],
    post_meta: Optional[Dict[str, object]] = None,
) -> None:
    if post_meta:
        st.markdown(
            f"**标题**：{post_meta.get('title', '未命名热帖')}  \n"
            f"**链接**：{post_meta.get('url', '')}  \n"
            f"**作者**：{post_meta.get('author', '未知')}  \n"
            f"**话题**：{post_meta.get('topic', '')}"
        )
    st.markdown("#### 评论情绪概览")
    render_analysis_summary(comments, prob_list, label_list)

    dist = db.get_emotion_dist(post_id)
    if dist:
        col1, col2 = st.columns(2)
        with col1:
            st.pyplot(utils.draw_pie(dist))
        with col2:
            texts = [row["text"] for row in comments if row.get("text")]
            if texts:
                st.pyplot(utils.draw_wordcloud(texts))


def render_analysis_summary(
    comments: Sequence[Dict[str, str]],
    prob_list: Sequence[Sequence[float]],
    label_list: Sequence[Sequence[str]],
) -> None:
    dataframe = build_result_dataframe(comments, prob_list, label_list)
    st.dataframe(dataframe, use_container_width=True)


def build_result_dataframe(
    comments: Sequence[Dict[str, str]],
    prob_list: Sequence[Sequence[float]],
    label_list: Sequence[Sequence[str]],
) -> pd.DataFrame:
    probabilities = [
        {emotion: f"{score:.1%}" for emotion, score in zip(sentiment.EMOTIONS, scores)}
        for scores in prob_list
    ]
    records = []
    for idx, comment in enumerate(comments):
        base = {
            "用户": comment.get("user", "未知用户"),
            "评论内容": comment.get("text", ""),
            "时间": comment.get("ts", ""),
            "情绪标签": "、".join(label_list[idx]) if idx < len(label_list) else "",
            "点赞数": comment.get("likes", 0),
        }
        base.update(probabilities[idx] if idx < len(probabilities) else {})
        records.append(base)
    return pd.DataFrame(records)


def load_comments_from_file(uploaded_file) -> List[Dict[str, str]]:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(uploaded_file)
    elif suffix == ".xlsx":
        df = pd.read_excel(uploaded_file)
    else:
        lines = [line.decode("utf-8", errors="ignore").strip() for line in uploaded_file.readlines()]
        df = pd.DataFrame({"text": [line for line in lines if line]})

    if "text" not in df.columns:
        first_column = df.columns[0] if not df.empty else "text"
        df = df.rename(columns={first_column: "text"})
    df = df.dropna(subset=["text"])
    return [{"user": row.get("user", "批量用户"), "text": row["text"], "ts": row.get("ts", "")} for _, row in df.iterrows()]


if __name__ == "__main__":
    main()
