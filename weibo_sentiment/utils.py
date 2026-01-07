"""Visualization and text utilities."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
import math

import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from wordcloud import WordCloud
import unicodedata

try:
    import jieba
except ImportError:  # pragma: no cover - fallback when jieba not installed
    jieba = None


def _resolve_chinese_font() -> Optional[str]:
    """Return a font path that supports Chinese characters."""
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)

    for font in font_manager.findSystemFonts(fontext="ttf"):
        lower = font.lower()
        if any(name in lower for name in ["msyh", "simhei", "hei", "pingfang", "noto"]):
            return font
    return None


def _resolve_emoji_font() -> Optional[str]:
    """Return a font path that supports emoji (if available)."""
    candidates = [
        Path("C:/Windows/Fonts/seguiemj.ttf"),  # Windows Segoe UI Emoji
        Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
        Path("/usr/share/fonts/noto/NotoColorEmoji.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)

    for font in font_manager.findSystemFonts(fontext="ttf"):
        lower = font.lower()
        if any(name in lower for name in ["seguiemj", "color emoji", "emoji"]):
            return font
    return None


FONT_PATH = _resolve_chinese_font()
FONT_PROP = font_manager.FontProperties(fname=FONT_PATH) if FONT_PATH else None
if FONT_PROP:
    rcParams["font.family"] = FONT_PROP.get_name()
    rcParams["axes.unicode_minus"] = False

EMOJI_FONT_PATH = _resolve_emoji_font()
EMOJI_FONT_PROP = font_manager.FontProperties(fname=EMOJI_FONT_PATH) if EMOJI_FONT_PATH else None


def draw_pie(emotion_dist: Dict[str, float]) -> plt.Figure:
    """Render a pie chart from an emotion distribution dictionary."""
    # Map English emotion names to Chinese + emoji separately to allow mixed fonts
    emotion_text = {
        "anger": "愤怒",
        "disgust": "厌恶",
        "fear": "恐惧",
        "joy": "喜悦",
        "sadness": "悲伤",
        "surprise": "惊讶",
    }
    emotion_emoji = {
        "anger": "😠",
        "disgust": "🤢",
        "fear": "😨",
        "joy": "😄",
        "sadness": "😢",
        "surprise": "😲",
    }
    
    # Convert keys to Chinese
    labels = [emotion_text.get(key, key) for key in emotion_dist.keys()]
    values = [emotion_dist[label] for label in emotion_dist.keys()]
    
    # Create figure with better styling
    figure, ax = plt.subplots(figsize=(6, 6))
    
    # Define color palette for emotions
    colors = ['#ff6b6b', '#95a5a6', '#8e44ad', '#f1c40f', '#3498db', '#e67e22']
    
    wedges, texts, autotexts = ax.pie(
        values, 
        labels=labels, 
        autopct='%1.1f%%',
        startangle=90,
        colors=colors,
        textprops={'fontsize': 11, 'weight': 'bold'},
        explode=[0.05] * len(values)  # Slightly separate slices
    )
    
    # Style the percentage text
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(10)
        autotext.set_weight('bold')
        if FONT_PROP:
            autotext.set_fontproperties(FONT_PROP)

    # Apply Chinese font to labels
    if FONT_PROP:
        for text in texts:
            text.set_fontproperties(FONT_PROP)

    # Overlay emoji using emoji-capable font without affecting Chinese glyphs
    if EMOJI_FONT_PROP:
        for wedge, key in zip(wedges, emotion_dist.keys()):
            theta = 0.5 * (wedge.theta2 + wedge.theta1)
            radius = wedge.r  # default 1.0
            x = 1.1 * radius * math.cos(math.radians(theta))
            y = 1.1 * radius * math.sin(math.radians(theta))
            ax.text(
                x,
                y,
                emotion_emoji.get(key, ""),
                fontproperties=EMOJI_FONT_PROP,
                fontsize=16,
                ha="center",
                va="center",
            )
    
    ax.axis("equal")
    if FONT_PROP:
        ax.set_title("情绪分布", fontproperties=FONT_PROP, fontsize=14, weight='bold', pad=20)
    else:
        ax.set_title("情绪分布", fontsize=14, weight='bold', pad=20)
    
    plt.tight_layout()
    return figure


def draw_wordcloud(texts: Sequence[str]) -> plt.Figure:
    """Render a word cloud based on tokenized comments."""
    tokens = tokenize(texts)
    # Filter out tokens that are pure emoji to avoid font glyph warnings in matplotlib/Pillow
    filtered_tokens = [tok for tok in tokens if not _is_emoji_token(tok)]
    freq = Counter(filtered_tokens)
    
    # Enhanced word cloud with better styling
    wc = WordCloud(
        width=1000,
        height=500,
        font_path=FONT_PATH,
        background_color="white",
        max_words=100,
        colormap='viridis',
        relative_scaling=0.5,
        min_font_size=10,
        contour_width=2,
        contour_color='steelblue'
    ).generate_from_frequencies(freq)

    figure, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    if FONT_PROP:
        ax.set_title("评论词云", fontproperties=FONT_PROP, fontsize=14, weight='bold', pad=15)
    else:
        ax.set_title("评论词云", fontsize=14, weight='bold', pad=15)
    plt.tight_layout()
    return figure


def _is_emoji_token(token: str) -> bool:
    """Return True if the token consists entirely of emoji-like symbols."""
    if not token:
        return False
    for ch in token:
        if _is_emoji_char(ch):
            continue
        return False
    return True


def _is_emoji_char(ch: str) -> bool:
    # Rough emoji detection based on Unicode categories and ranges
    if "EMOJI" in unicodedata.name(ch, ""):
        return True
    code = ord(ch)
    return (
        0x1F300 <= code <= 0x1FAD6  # Misc emoji and symbols
        or 0x1F600 <= code <= 0x1F64F  # Emoticons
        or 0x1F680 <= code <= 0x1F6FF  # Transport & map
        or 0x1F900 <= code <= 0x1F9FF  # Supplemental symbols
        or 0x1FA70 <= code <= 0x1FAFF  # Symbols & pictographs
        or 0x2600 <= code <= 0x27BF   # Misc symbols
    )


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
