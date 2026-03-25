"""テーマ選定エージェントのテスト。"""
import pytest
from unittest.mock import MagicMock, patch

from agents.theme_selector import ThemeSelectorAgent
from models.schemas import ThemeRequest


@pytest.fixture
def agent():
    return ThemeSelectorAgent(retriever=None)


def test_run_returns_candidates(agent):
    mock_response = """
    {
      "candidates": [
        {
          "title": "副業で月5万円稼ぐ3つの方法",
          "hook_type": "数字系",
          "estimated_ctr": "High",
          "reasoning": "具体的な数字で信頼性が高い"
        }
      ]
    }
    """
    with patch.object(agent, "_call_claude", return_value=mock_response):
        result = agent.run(ThemeRequest(purpose="副業ノウハウ", genre="ノウハウ系", count=1))

    assert len(result.candidates) == 1
    assert result.candidates[0].title == "副業で月5万円稼ぐ3つの方法"
    assert result.candidates[0].estimated_ctr == "High"
