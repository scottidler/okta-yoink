"""Unit tests for the main module."""

from unittest.mock import Mock, patch

import pytest

from okta_yoink.main import main
from okta_yoink.token_extractor import OktaTokenExtractionError


class TestMain:
    """Test cases for main function."""

    @patch("okta_yoink.main.OktaTokenExtractor")
    @patch("okta_yoink.main.Config")
    def test_main_success(self, mock_config_class, mock_extractor_class) -> None:
        """Test successful main execution."""
        # Setup mocks
        mock_config = Mock()
        mock_config.TOKEN_ENV_VAR = "OKTA_COOKIE"
        mock_config.TOKEN_FILE = "/home/user/.okta-cookie"
        mock_config_class.return_value = mock_config

        mock_extractor = Mock()
        mock_extractor.run.return_value = "test-token"
        mock_extractor.__enter__ = Mock(return_value=mock_extractor)
        mock_extractor.__exit__ = Mock(return_value=None)
        mock_extractor_class.return_value = mock_extractor

        # Test main function
        result = main()

        # Verify calls
        mock_config_class.assert_called_once()
        mock_extractor_class.assert_called_once_with(mock_config)
        mock_extractor.run.assert_called_once()

        # Verify success return code
        assert result == 0

    @patch("okta_yoink.main.OktaTokenExtractor")
    @patch("okta_yoink.main.Config")
    def test_main_keyboard_interrupt(self, mock_config_class, mock_extractor_class) -> None:
        """Test main handles KeyboardInterrupt."""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_extractor = Mock()
        mock_extractor.run.side_effect = KeyboardInterrupt()
        mock_extractor.__enter__ = Mock(return_value=mock_extractor)
        mock_extractor.__exit__ = Mock(return_value=None)
        mock_extractor_class.return_value = mock_extractor

        result = main()

        assert result == 1

    @patch("okta_yoink.main.OktaTokenExtractor")
    @patch("okta_yoink.main.Config")
    def test_main_token_extraction_error(self, mock_config_class, mock_extractor_class) -> None:
        """Test main handles OktaTokenExtractionError."""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_extractor = Mock()
        mock_extractor.run.side_effect = OktaTokenExtractionError("Token extraction failed")
        mock_extractor.__enter__ = Mock(return_value=mock_extractor)
        mock_extractor.__exit__ = Mock(return_value=None)
        mock_extractor_class.return_value = mock_extractor

        result = main()

        assert result == 1

    @patch("okta_yoink.main.OktaTokenExtractor")
    @patch("okta_yoink.main.Config")
    def test_main_unexpected_error(self, mock_config_class, mock_extractor_class) -> None:
        """Test main handles unexpected exceptions."""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_extractor = Mock()
        mock_extractor.run.side_effect = RuntimeError("Unexpected error")
        mock_extractor.__enter__ = Mock(return_value=mock_extractor)
        mock_extractor.__exit__ = Mock(return_value=None)
        mock_extractor_class.return_value = mock_extractor

        result = main()

        assert result == 1

    @patch("okta_yoink.main.OktaTokenExtractor")
    @patch("okta_yoink.main.Config")
    def test_main_config_validation_error(self, mock_config_class, mock_extractor_class) -> None:
        """Test main handles config validation errors."""
        mock_config_class.side_effect = ValueError("Invalid configuration")

        result = main()

        assert result == 1
        # Extractor should not be called if config fails
        mock_extractor_class.assert_not_called()

    @patch("okta_yoink.main.OktaTokenExtractor")
    @patch("okta_yoink.main.Config")
    def test_main_context_manager_usage(self, mock_config_class, mock_extractor_class) -> None:
        """Test that main uses OktaTokenExtractor as context manager."""
        mock_config = Mock()
        mock_config.TOKEN_ENV_VAR = "OKTA_COOKIE"
        mock_config.TOKEN_FILE = "/home/user/.okta-cookie"
        mock_config_class.return_value = mock_config

        mock_extractor = Mock()
        mock_extractor.run.return_value = "test-token"
        mock_extractor.__enter__ = Mock(return_value=mock_extractor)
        mock_extractor.__exit__ = Mock(return_value=None)
        mock_extractor_class.return_value = mock_extractor

        result = main()

        # Verify context manager methods were called
        mock_extractor.__enter__.assert_called_once()
        mock_extractor.__exit__.assert_called_once()
        assert result == 0
