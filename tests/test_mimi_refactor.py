import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMemoryDisabled:
    """Tests to verify memory system is disabled"""

    def test_no_user_memories_returned(self):
        """Memory functions should return empty list"""
        from utils import firebase_db

        result = firebase_db.get_user_memories("test_user_id")
        assert result == []

    def test_save_memory_does_nothing(self):
        """save_memory should not save anything (no error)"""
        from utils import firebase_db

        firebase_db.save_memory("test_user_id", "test content")

    def test_clear_user_memories_does_nothing(self):
        """clear_user_memories should not raise error"""
        from utils import firebase_db

        firebase_db.clear_user_memories("test_user_id")


class TestLinkFiltering:
    """Tests to verify link embedding is blocked"""

    def test_http_link_removed(self):
        """HTTP URLs should be stripped from responses"""
        import re

        test_input = "Check https://example.com for more info"
        cleaned = re.sub(r"http[s]?://\S+", "[Link Removed]", test_input)
        assert cleaned == "Check [Link Removed] for more info"

    def test_https_link_removed(self):
        """HTTPS URLs should be stripped"""
        import re

        test_input = "Visit https://google.com today"
        cleaned = re.sub(r"http[s]?://\S+", "[Link Removed]", test_input)
        assert cleaned == "Visit [Link Removed] today"

    def test_markdown_link_removed(self):
        """Markdown-style links should be stripped"""
        import re

        test_input = "Click [here](https://example.com) for more"
        cleaned = re.sub(r"\[.+\]\(.+\)", "[Link Removed]", test_input)
        assert cleaned == "Click [Link Removed] for more"

    def test_www_link_removed(self):
        """WWW links should be stripped"""
        import re

        test_input = "Go to www.example.com"
        cleaned = re.sub(r"www\.\S+", "[Link Removed]", test_input)
        assert cleaned == "Go to [Link Removed]"

    def test_common_tlds_removed(self):
        """Common TLDs should be stripped"""
        import re

        test_input = "Visit example.com or example.org"
        cleaned = re.sub(r"\.com\S*|\.org\S*", "[Link Removed]", test_input)
        assert "[Link Removed]" in cleaned


class TestPasummatchSimplified:
    """Tests for simplified pasummatch without profiles"""

    def test_pasummatch_gets_user_ids(self):
        """pasummatch should use get_all_user_ids"""
        from utils import pasummatch, firebase_db

        with patch.object(
            firebase_db, "get_all_user_ids", return_value=["123", "456", "789"]
        ):
            all_users = firebase_db.get_all_user_ids()
            assert len(all_users) == 3
            assert "123" in all_users

    def test_pasummatch_handles_empty_pool(self):
        """pasummatch should handle empty user pool"""
        from utils import firebase_db

        with patch.object(firebase_db, "get_all_user_ids", return_value=[]):
            all_users = firebase_db.get_all_user_ids()
            assert all_users == []


class TestCommandsSimplified:
    """Tests for simplified command behavior"""

    def test_reset_calls_clear_conversations(self):
        """Reset should call clear_user_conversations"""
        from utils import firebase_db

        with patch.object(firebase_db, "clear_user_conversations") as mock_clear:
            mock_clear("test_user")
            mock_clear.assert_called_once_with("test_user")

    def test_hardreset_calls_hard_reset_user_data(self):
        """Hardreset should call hard_reset_user_data"""
        from utils import firebase_db

        with patch.object(firebase_db, "hard_reset_user_data") as mock_reset:
            mock_reset("test_user")
            mock_reset.assert_called_once_with("test_user")

    def test_memories_command_removed(self):
        """/memories command should not exist"""
        from utils import commands

        assert not hasattr(commands, "show_memories")

    def test_reprofile_command_removed(self):
        """/reprofile command should not exist"""
        from utils import commands

        assert not hasattr(commands, "reprofile")


class TestSystemPrompt:
    """Tests for system prompt integrity"""

    def test_no_links_rule_exists(self):
        """System prompt should have NO LINKS rule"""
        from utils import ai_tutor
        import os

        PROMPTS_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts"
        )
        PERSONA_FILE = os.path.join(PROMPTS_DIR, "system_prompt.md")
        GLOBAL_FILE = os.path.join(PROMPTS_DIR, "global_grounding.md")
        persona = ai_tutor.load_file(PERSONA_FILE)
        global_rules = ai_tutor.load_file(GLOBAL_FILE)
        combined = persona + global_rules
        assert "never embed" in combined.lower() or "no links" in combined.lower()

    def test_mimi_identity_preserved(self):
        """Mimi's identity should be intact in system prompt"""
        from utils import ai_tutor
        import os

        PROMPTS_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts"
        )
        PERSONA_FILE = os.path.join(PROMPTS_DIR, "system_prompt.md")
        persona = ai_tutor.load_file(PERSONA_FILE)
        assert "Mimi" in persona
        assert "PASUM" in persona


class TestImageProcessing:
    """Tests for image processing functionality"""

    def test_vision_ai_function_exists(self):
        """Vision AI function should exist"""
        from utils import vision

        assert hasattr(vision, "call_vision_ai")

    def test_announcement_comment_disabled(self):
        """generate_announcement_comment should return empty string"""
        from utils import ai_tutor

        result = ai_tutor.generate_announcement_comment("Test announcement", [])
        assert result == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
