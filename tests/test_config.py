"""Unit tests for the Config class."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from okta_token_automation.config import Config


class TestConfig:
    """Test cases for Config class."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = Config()
        
        assert config.OKTA_LOGIN_URL == "https://tatari.okta.com"
        assert config.HTTPBIN_URL == "https://httpbin.ops.tatari.dev/headers"
        assert config.HEADLESS is False
        assert config.BROWSER_TIMEOUT == 30
        assert config.IMPLICIT_WAIT == 10
        assert config.MFA_TIMEOUT == 120
        assert config.TOKEN_ENV_VAR == "OKTA_COOKIE"
        assert config.OKTA_USERNAME == ""
        assert config.CHROME_BINARY_PATH is None
        assert config.CHROMEDRIVER_PATH is None

    def test_token_file_default(self) -> None:
        """Test default token file path."""
        config = Config()
        expected_path = Path(os.path.expanduser("~/.okta-token"))
        assert config.TOKEN_FILE == expected_path

    @patch.dict(os.environ, {
        "OKTA_LOGIN_URL": "https://custom.okta.com",
        "HTTPBIN_URL": "https://custom.httpbin.dev/headers",
        "HEADLESS": "true",
        "BROWSER_TIMEOUT": "60",
        "IMPLICIT_WAIT": "15",
        "MFA_TIMEOUT": "180",
        "TOKEN_FILE": "/custom/token/path",
        "TOKEN_ENV_VAR": "CUSTOM_OKTA_COOKIE",
        "OKTA_USERNAME": "test.user@example.com",
        "CHROME_BINARY_PATH": "/usr/bin/chrome",
        "CHROMEDRIVER_PATH": "/usr/bin/chromedriver",
    })
    def test_environment_variable_override(self) -> None:
        """Test that environment variables override defaults."""
        config = Config()
        
        assert config.OKTA_LOGIN_URL == "https://custom.okta.com"
        assert config.HTTPBIN_URL == "https://custom.httpbin.dev/headers"
        assert config.HEADLESS is True
        assert config.BROWSER_TIMEOUT == 60
        assert config.IMPLICIT_WAIT == 15
        assert config.MFA_TIMEOUT == 180
        assert config.TOKEN_FILE == Path("/custom/token/path")
        assert config.TOKEN_ENV_VAR == "CUSTOM_OKTA_COOKIE"
        assert config.OKTA_USERNAME == "test.user@example.com"
        assert config.CHROME_BINARY_PATH == "/usr/bin/chrome"
        assert config.CHROMEDRIVER_PATH == "/usr/bin/chromedriver"

    @patch.dict(os.environ, {"HEADLESS": "false"})
    def test_headless_false_parsing(self) -> None:
        """Test that HEADLESS=false is parsed correctly."""
        config = Config()
        assert config.HEADLESS is False

    @patch.dict(os.environ, {"HEADLESS": "TRUE"})
    def test_headless_case_insensitive(self) -> None:
        """Test that HEADLESS parsing is case insensitive."""
        config = Config()
        assert config.HEADLESS is True

    def test_validate_success(self) -> None:
        """Test successful validation."""
        config = Config()
        # Should not raise any exception
        config.validate()

    @patch.dict(os.environ, {"OKTA_LOGIN_URL": ""})
    def test_validate_empty_okta_url(self) -> None:
        """Test validation fails with empty OKTA_LOGIN_URL."""
        config = Config()
        with pytest.raises(ValueError, match="OKTA_LOGIN_URL cannot be empty"):
            config.validate()

    @patch.dict(os.environ, {"HTTPBIN_URL": ""})
    def test_validate_empty_httpbin_url(self) -> None:
        """Test validation fails with empty HTTPBIN_URL."""
        config = Config()
        with pytest.raises(ValueError, match="HTTPBIN_URL cannot be empty"):
            config.validate()

    @patch.dict(os.environ, {"BROWSER_TIMEOUT": "0"})
    def test_validate_zero_browser_timeout(self) -> None:
        """Test validation fails with zero BROWSER_TIMEOUT."""
        config = Config()
        with pytest.raises(ValueError, match="BROWSER_TIMEOUT must be positive"):
            config.validate()

    @patch.dict(os.environ, {"BROWSER_TIMEOUT": "-10"})
    def test_validate_negative_browser_timeout(self) -> None:
        """Test validation fails with negative BROWSER_TIMEOUT."""
        config = Config()
        with pytest.raises(ValueError, match="BROWSER_TIMEOUT must be positive"):
            config.validate()

    @patch.dict(os.environ, {"IMPLICIT_WAIT": "0"})
    def test_validate_zero_implicit_wait(self) -> None:
        """Test validation fails with zero IMPLICIT_WAIT."""
        config = Config()
        with pytest.raises(ValueError, match="IMPLICIT_WAIT must be positive"):
            config.validate()

    @patch.dict(os.environ, {"MFA_TIMEOUT": "-5"})
    def test_validate_negative_mfa_timeout(self) -> None:
        """Test validation fails with negative MFA_TIMEOUT."""
        config = Config()
        with pytest.raises(ValueError, match="MFA_TIMEOUT must be positive"):
            config.validate()

    def test_repr_without_username(self) -> None:
        """Test string representation without username."""
        config = Config()
        repr_str = repr(config)
        
        assert "Config(" in repr_str
        assert "OKTA_LOGIN_URL='https://tatari.okta.com'" in repr_str
        assert "HTTPBIN_URL='https://httpbin.ops.tatari.dev/headers'" in repr_str
        assert "HEADLESS=False" in repr_str
        assert "BROWSER_TIMEOUT=30" in repr_str
        assert "OKTA_USERNAME=''" in repr_str

    @patch.dict(os.environ, {"OKTA_USERNAME": "test.user@example.com"})
    def test_repr_with_username_masked(self) -> None:
        """Test string representation masks username."""
        config = Config()
        repr_str = repr(config)
        
        assert "OKTA_USERNAME='***'" in repr_str
        assert "test.user@example.com" not in repr_str

    @patch.dict(os.environ, {"BROWSER_TIMEOUT": "invalid"})
    def test_invalid_integer_env_var(self) -> None:
        """Test that invalid integer environment variables raise ValueError."""
        with pytest.raises(ValueError):
            Config()

    def test_token_file_expansion(self) -> None:
        """Test that token file path is properly expanded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"TOKEN_FILE": f"{temp_dir}/test-token"}):
                config = Config()
                assert str(config.TOKEN_FILE) == f"{temp_dir}/test-token"
                assert config.TOKEN_FILE.is_absolute() 