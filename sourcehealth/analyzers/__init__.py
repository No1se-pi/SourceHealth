"""Готовые адаптеры. Новые анализаторы можно передавать runner напрямую."""

from .git_activity import GitActivityAnalyzerAdapter
from .sast import SASTAnalyzerAdapter

__all__ = ["GitActivityAnalyzerAdapter", "SASTAnalyzerAdapter"]
