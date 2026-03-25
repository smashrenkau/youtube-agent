"""台本作成エージェントのテスト。"""
import pytest
from unittest.mock import patch

from agents.script_writer import ScriptWriterAgent
from models.schemas import ScriptRequest


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.script_writer.Path", lambda p: tmp_path)
    a = ScriptWriterAgent(retriever=None)
    a.output_dir = tmp_path
    return a


def test_review_approval_stops_loop(agent):
    draft = "【オープニング】\nこんにちは！\n【本編】\n内容です。\n【エンディング】\nありがとう！"
    approved_review = """
    {
      "hook_score": 4, "style_score": 4, "length_score": 4, "structure_score": 5,
      "total": 17, "feedback": "良い台本です", "approved": true
    }
    """

    with patch.object(agent, "_call_claude", side_effect=[draft, approved_review]):
        result = agent.run(ScriptRequest(title="テストタイトル", target_chars=100))

    assert result.revision_count == 0
    assert len(result.review_history) == 1
    assert result.review_history[0].approved is True
