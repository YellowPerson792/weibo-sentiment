"""Visualization and text utilities."""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Sequence

import matplotlib.pyplot as plt
from wordcloud import WordCloud

try:
    import jieba
except ImportError:  # pragma: no cover - fallback when jieba not installed
    jieba = None


def draw_pie(emotion_dist: Dict[str, float]) -> plt.Figure:
    """Render a pie chart from an emotion distribution dictionary."""
    labels = list(emotion_dist.keys())
    values = [emotion_dist[label] for label in labels]
    figure, ax = plt.subplots(figsize=(4, 4))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=150)
    ax.axis("equal")
    ax.set_title("情绪分布")
    return figure


def draw_wordcloud(texts: Sequence[str]) -> plt.Figure:
    """Render a word cloud based on tokenized comments."""
    tokens = tokenize(texts)
    freq = Counter(tokens)
    wc = WordCloud(
        width=800,
        height=400,
        font_path=None,
        background_color="white",
    ).generate_from_frequencies(freq)

    figure, ax = plt.subplots(figsize=(8, 4))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title("评论词云")
    return figure


def tokenize(texts: Sequence[str]) -> List[str]:
    """Segment text into tokens. Falls back to whitespace splits."""
    tokens: List[str] = []
    for text in texts:
        if not text:
            continue
        if jieba:
            tokens.extend(word.strip() for word in jieba.cut(text) if word.strip())
        else:
            tokens.extend(text.strip().split())
    return tokens


__all__ = ["draw_pie", "draw_wordcloud", "tokenize"]
