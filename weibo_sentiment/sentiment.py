"""Sentiment analysis backed by Hugging Face zero-shot classifier."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, List, Sequence, Tuple

import numpy as np

LOGGER = logging.getLogger(__name__)

EMOTIONS: Tuple[str, ...] = ("anger", "disgust", "fear", "joy", "sadness", "surprise")
CHINESE_LABELS: Tuple[str, ...] = ("愤怒", "厌恶", "恐惧", "喜悦", "悲伤", "惊讶")

MODEL_NAME = "IDEA-CCNL/Erlangshen-RoBERTa-330M-NLI"


@dataclass
class PredictionResult:
    probabilities: List[List[float]]
    labels: List[List[str]]


class SentimentAnalyzer:
    """Lazy loading zero-shot classifier with keyword fallback."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self.model_name = model_name
        self._pipeline = None
        self._error: str | None = None

    def predict(self, texts: Sequence[str], thresh: float = 0.5) -> PredictionResult:
        cleaned = [text.strip() for text in texts if text and text.strip()]
        if not cleaned:
            return PredictionResult([], [])

        pipeline = self._load_pipeline()
        if pipeline is not None:
            try:
                return self._predict_pipeline(pipeline, cleaned, thresh)
            except Exception as exc:  # pragma: no cover - logging only
                self._error = f"HuggingFace pipeline inference failed: {exc}"
                LOGGER.exception(self._error)

        LOGGER.info("Falling back to keyword heuristic sentiment classification.")
        return self._predict_keyword(cleaned, thresh)

    def _predict_pipeline(self, pipeline, texts: Sequence[str], thresh: float) -> PredictionResult:
        outputs = pipeline(
            list(texts),
            candidate_labels=list(CHINESE_LABELS),
            hypothesis_template="这段话表达了{}的情绪。",
            multi_label=True,
        )

        if not isinstance(outputs, list):  # Single input returns dict
            outputs = [outputs]

        probabilities: List[List[float]] = []
        label_groups: List[List[str]] = []

        for result in outputs:
            scores = self._scores_to_probs(result["scores"])
            selected_labels = [
                EMOTIONS[idx] for idx, score in enumerate(scores) if score >= thresh
            ]
            if not selected_labels:
                selected_labels = [EMOTIONS[int(np.argmax(scores))]]
            probabilities.append(scores)
            label_groups.append(selected_labels)

        return PredictionResult(probabilities=probabilities, labels=label_groups)

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=-1,
            )
        except Exception as exc:  # pragma: no cover - handled via fallback
            self._error = f"Failed to load HF pipeline: {exc}"
            LOGGER.warning(self._error)
            self._pipeline = None
        return self._pipeline

    @staticmethod
    def _scores_to_probs(scores: Sequence[float]) -> List[float]:
        logits = np.array(scores, dtype=float)
        exp = np.exp(logits - np.max(logits))
        softmax = exp / exp.sum()
        return softmax.tolist()

    @staticmethod
    def _predict_keyword(texts: Sequence[str], thresh: float) -> PredictionResult:
        probabilities: List[List[float]] = []
        label_groups: List[List[str]] = []
        for text in texts:
            scores = heuristic_scores(text)
            probabilities.append(scores)
            candidates = [
                EMOTIONS[idx] for idx, score in enumerate(scores) if score >= thresh
            ]
            if not candidates:
                candidates = [EMOTIONS[int(np.argmax(scores))]]
            label_groups.append(candidates)
        return PredictionResult(probabilities=probabilities, labels=label_groups)


FALLBACK_KEYWORDS = {
    "anger": ("怒", "生气", "愤", "火大", "气死", "垃圾"),
    "disgust": ("恶心", "讨厌", "无语", "滚", "呕", "烦"),
    "fear": ("怕", "恐惧", "担心", "慌", "紧张"),
    "joy": ("喜", "乐", "高兴", "开心", "哈哈", "太好了", "祝贺"),
    "sadness": ("难过", "伤心", "哭", "可怜", "崩溃"),
    "surprise": ("惊", "震撼", "没想到", "哇", "竟然"),
}


def heuristic_scores(text: str) -> List[float]:
    lowered = text.lower()
    scores = []
    for emotion in EMOTIONS:
        keywords = FALLBACK_KEYWORDS.get(emotion, ())
        hits = sum(lowered.count(word.lower()) for word in keywords)
        scores.append(min(1.0, hits / 3.0))
    total = sum(scores)
    if total == 0:
        return [1 / len(EMOTIONS)] * len(EMOTIONS)
    return [score / total for score in scores]


_ANALYZER = SentimentAnalyzer()


def predict(texts: Sequence[str], thresh: float = 0.5) -> Tuple[List[List[float]], List[List[str]]]:
    result = _ANALYZER.predict(texts, thresh=thresh)
    return result.probabilities, result.labels


__all__ = ["predict", "SentimentAnalyzer", "EMOTIONS"]
