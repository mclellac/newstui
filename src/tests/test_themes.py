import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from news_tui import themes


class TestThemeLoading(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("/tmp/test_theme_loading")
        self.config_dir = self.test_dir / ".config/news"
        os.makedirs(self.config_dir, exist_ok=True)
        self.default_themes_dir = self.test_dir / "default_themes"
        os.makedirs(self.default_themes_dir, exist_ok=True)

        self.default_themes = {
            "test-theme": {
                "primary": "#ffffff",
                "secondary": "#eeeeee",
                "accent": "#dddddd",
                "foreground": "#cccccc",
                "background": "#bbbbbb",
                "surface": "#aaaaaa",
                "panel": "#999999",
                "success": "#888888",
                "warning": "#777777",
                "error": "#666666",
                "dark": True,
            }
        }
        self.default_themes_path = self.default_themes_dir / "themes.json"
        with open(self.default_themes_path, "w") as f:
            json.dump(self.default_themes, f)

        self.user_themes_path = self.config_dir / "themes.json"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("news_tui.themes.USER_THEMES_PATH", new_callable=lambda: Path("/tmp/test_theme_loading/.config/news/themes.json"))
    @patch("news_tui.themes.DEFAULT_THEMES_PATH", new_callable=lambda: Path("/tmp/test_theme_loading/default_themes/themes.json"))
    def test_default_themes_are_copied(self, mock_default_path, mock_user_path):
        # Ensure user themes file doesn't exist initially
        if os.path.exists(self.user_themes_path):
            os.remove(self.user_themes_path)

        # Act
        loaded_themes = themes.load_themes()

        # Assert
        self.assertTrue(os.path.exists(self.user_themes_path))
        with open(self.user_themes_path, "r") as f:
            user_themes_data = json.load(f)
        self.assertEqual(user_themes_data, self.default_themes)
        self.assertIn("test-theme", loaded_themes)

    @patch("news_tui.themes.USER_THEMES_PATH", new_callable=lambda: Path("/tmp/test_theme_loading/.config/news/themes.json"))
    @patch("news_tui.themes.DEFAULT_THEMES_PATH", new_callable=lambda: Path("/tmp/test_theme_loading/default_themes/themes.json"))
    def test_custom_theme_is_loaded(self, mock_default_path, mock_user_path):
        # Arrange
        custom_themes = {
            "custom-light": {
                "primary": "#111111",
                "background": "#222222",
                "dark": False,
            }
        }
        with open(self.user_themes_path, "w") as f:
            json.dump(custom_themes, f)

        # Act
        loaded_themes = themes.load_themes()

        # Assert
        self.assertIn("custom-light", loaded_themes)
        self.assertEqual(loaded_themes["custom-light"].background, "#222222")
        self.assertFalse(loaded_themes["custom-light"].dark)


if __name__ == "__main__":
    unittest.main()
