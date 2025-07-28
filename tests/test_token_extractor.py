"""Unit tests for the OktaTokenExtractor class."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

from okta_token_automation.config import Config
from okta_token_automation.token_extractor import (
    OktaTokenExtractor,
    OktaTokenExtractionError,
)


class TestOktaTokenExtractor:
    """Test cases for OktaTokenExtractor class."""

    def test_init_with_default_config(self) -> None:
        """Test initialization with default config."""
        extractor = OktaTokenExtractor()
        assert extractor.config is not None
        assert extractor.driver is None

    def test_init_with_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = Config()
        extractor = OktaTokenExtractor(config)
        assert extractor.config is config
        assert extractor.driver is None

    @patch("okta_token_automation.token_extractor.ChromeDriverManager")
    @patch("okta_token_automation.token_extractor.webdriver.Chrome")
    def test_setup_driver_success(self, mock_chrome, mock_driver_manager) -> None:
        """Test successful driver setup."""
        mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver

        extractor = OktaTokenExtractor()
        extractor.setup_driver()

        assert extractor.driver is mock_driver
        mock_chrome.assert_called_once()
        mock_driver.implicitly_wait.assert_called_once_with(10)

    @patch("okta_token_automation.token_extractor.ChromeDriverManager")
    @patch("okta_token_automation.token_extractor.webdriver.Chrome")
    def test_setup_driver_headless(self, mock_chrome, mock_driver_manager) -> None:
        """Test driver setup in headless mode."""
        mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver

        config = Config()
        config.HEADLESS = True
        extractor = OktaTokenExtractor(config)
        extractor.setup_driver()

        # Check that Chrome was called with options containing --headless
        args, kwargs = mock_chrome.call_args
        options = kwargs["options"]
        assert "--headless" in options.arguments

    @patch("okta_token_automation.token_extractor.ChromeDriverManager")
    @patch("okta_token_automation.token_extractor.webdriver.Chrome")
    def test_setup_driver_custom_paths(self, mock_chrome, mock_driver_manager) -> None:
        """Test driver setup with custom binary and driver paths."""
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver

        config = Config()
        config.CHROME_BINARY_PATH = "/custom/chrome"
        config.CHROMEDRIVER_PATH = "/custom/chromedriver"
        
        extractor = OktaTokenExtractor(config)
        extractor.setup_driver()

        # Should not call ChromeDriverManager when custom path is provided
        mock_driver_manager.assert_not_called()
        
        # Check that Chrome was called with custom binary location
        args, kwargs = mock_chrome.call_args
        options = kwargs["options"]
        assert options.binary_location == "/custom/chrome"

    @patch("okta_token_automation.token_extractor.webdriver.Chrome")
    def test_setup_driver_failure(self, mock_chrome) -> None:
        """Test driver setup failure."""
        mock_chrome.side_effect = WebDriverException("Driver failed")

        extractor = OktaTokenExtractor()
        with pytest.raises(OktaTokenExtractionError, match="Failed to initialize Chrome WebDriver"):
            extractor.setup_driver()

    def test_login_to_okta_no_driver(self) -> None:
        """Test login fails when driver is not initialized."""
        extractor = OktaTokenExtractor()
        with pytest.raises(OktaTokenExtractionError, match="Driver not initialized"):
            extractor.login_to_okta()

    @patch("builtins.input", side_effect=["testuser", "testpass"])
    def test_login_to_okta_success(self, mock_input) -> None:
        """Test successful login to Okta."""
        mock_driver = Mock()
        mock_wait = Mock()
        mock_username_field = Mock()
        mock_password_field = Mock()
        mock_submit_button = Mock()

        # Setup mocks
        mock_wait.until.return_value = mock_username_field
        mock_driver.find_element.side_effect = [mock_password_field, mock_submit_button]

        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        with patch("okta_token_automation.token_extractor.WebDriverWait", return_value=mock_wait):
            extractor.login_to_okta()

        # Verify interactions
        mock_driver.get.assert_called_once_with("https://tatari.okta.com")
        mock_username_field.clear.assert_called_once()
        mock_username_field.send_keys.assert_called_once_with("testuser")
        mock_password_field.clear.assert_called_once()
        mock_password_field.send_keys.assert_called_once_with("testpass")
        mock_submit_button.click.assert_called_once()

    @patch("builtins.input", return_value="testpass")
    def test_login_to_okta_with_configured_username(self, mock_input) -> None:
        """Test login with pre-configured username."""
        config = Config()
        config.OKTA_USERNAME = "configured.user@example.com"
        
        mock_driver = Mock()
        mock_wait = Mock()
        mock_username_field = Mock()
        mock_password_field = Mock()
        mock_submit_button = Mock()

        mock_wait.until.return_value = mock_username_field
        mock_driver.find_element.side_effect = [mock_password_field, mock_submit_button]

        extractor = OktaTokenExtractor(config)
        extractor.driver = mock_driver

        with patch("okta_token_automation.token_extractor.WebDriverWait", return_value=mock_wait):
            extractor.login_to_okta()

        # Should only ask for password, not username
        mock_input.assert_called_once_with("Enter your Okta password: ")
        mock_username_field.send_keys.assert_called_once_with("configured.user@example.com")

    def test_login_to_okta_timeout(self) -> None:
        """Test login timeout."""
        mock_driver = Mock()
        mock_wait = Mock()
        mock_wait.until.side_effect = TimeoutException("Timeout")

        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        with patch("okta_token_automation.token_extractor.WebDriverWait", return_value=mock_wait):
            with pytest.raises(OktaTokenExtractionError, match="Timeout waiting for Okta login page"):
                extractor.login_to_okta()

    def test_handle_mfa_no_driver(self) -> None:
        """Test MFA handling fails when driver is not initialized."""
        extractor = OktaTokenExtractor()
        with pytest.raises(OktaTokenExtractionError, match="Driver not initialized"):
            extractor.handle_mfa()

    def test_handle_mfa_success(self) -> None:
        """Test successful MFA handling."""
        mock_driver = Mock()
        mock_wait = Mock()
        mock_wait.until.return_value = True

        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        with patch("okta_token_automation.token_extractor.WebDriverWait", return_value=mock_wait):
            extractor.handle_mfa()

        # Verify WebDriverWait was called with correct timeout
        mock_wait.until.assert_called_once()

    def test_handle_mfa_timeout(self) -> None:
        """Test MFA timeout."""
        mock_driver = Mock()
        mock_wait = Mock()
        mock_wait.until.side_effect = TimeoutException("MFA timeout")

        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        with patch("okta_token_automation.token_extractor.WebDriverWait", return_value=mock_wait):
            with pytest.raises(OktaTokenExtractionError, match="MFA timeout after 120s"):
                extractor.handle_mfa()

    def test_extract_token_no_driver(self) -> None:
        """Test token extraction fails when driver is not initialized."""
        extractor = OktaTokenExtractor()
        with pytest.raises(OktaTokenExtractionError, match="Driver not initialized"):
            extractor.extract_token_from_internal_service()

    def test_extract_token_success(self) -> None:
        """Test successful token extraction."""
        mock_driver = Mock()
        mock_wait = Mock()
        mock_json_element = Mock()
        
        # Mock JSON response with oauth2_proxy header
        json_response = {
            "headers": {
                "Authorization": "Bearer some-token",
                "X-Oauth2-Proxy": "_oauth2_proxy=test-token-value",
                "User-Agent": "Chrome/91.0"
            }
        }
        mock_json_element.text = json.dumps(json_response)
        
        mock_wait.until.return_value = mock_json_element
        mock_driver.find_element.return_value = mock_json_element

        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        with patch("okta_token_automation.token_extractor.WebDriverWait", return_value=mock_wait):
            token = extractor.extract_token_from_internal_service()

        assert token == "_oauth2_proxy=test-token-value"
        mock_driver.get.assert_called_once_with("https://httpbin.ops.tatari.dev/headers")

    def test_extract_token_no_oauth2_header(self) -> None:
        """Test token extraction fails when oauth2_proxy header is missing."""
        mock_driver = Mock()
        mock_wait = Mock()
        mock_json_element = Mock()
        
        # Mock JSON response without oauth2_proxy header
        json_response = {
            "headers": {
                "Authorization": "Bearer some-token",
                "User-Agent": "Chrome/91.0"
            }
        }
        mock_json_element.text = json.dumps(json_response)
        
        mock_wait.until.return_value = mock_json_element
        mock_driver.find_element.return_value = mock_json_element

        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        with patch("okta_token_automation.token_extractor.WebDriverWait", return_value=mock_wait):
            with pytest.raises(OktaTokenExtractionError, match="No _oauth2_proxy header found"):
                extractor.extract_token_from_internal_service()

    def test_extract_token_invalid_json(self) -> None:
        """Test token extraction fails with invalid JSON."""
        mock_driver = Mock()
        mock_wait = Mock()
        mock_json_element = Mock()
        mock_json_element.text = "invalid json"
        
        mock_wait.until.return_value = mock_json_element
        mock_driver.find_element.return_value = mock_json_element

        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        with patch("okta_token_automation.token_extractor.WebDriverWait", return_value=mock_wait):
            with pytest.raises(OktaTokenExtractionError, match="Invalid JSON response"):
                extractor.extract_token_from_internal_service()

    def test_extract_token_empty_response(self) -> None:
        """Test token extraction fails with empty response."""
        mock_driver = Mock()
        mock_wait = Mock()
        mock_json_element = Mock()
        mock_json_element.text = ""
        
        mock_wait.until.return_value = mock_json_element
        mock_driver.find_element.return_value = mock_json_element

        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        with patch("okta_token_automation.token_extractor.WebDriverWait", return_value=mock_wait):
            with pytest.raises(OktaTokenExtractionError, match="Empty response from httpbin service"):
                extractor.extract_token_from_internal_service()

    def test_save_token_success(self) -> None:
        """Test successful token saving."""
        with tempfile.TemporaryDirectory() as temp_dir:
            token_file = Path(temp_dir) / "test-token"
            config = Config()
            config.TOKEN_FILE = token_file
            config.TOKEN_ENV_VAR = "TEST_OKTA_COOKIE"

            extractor = OktaTokenExtractor(config)
            test_token = "_oauth2_proxy=test-token-value"
            
            extractor.save_token(test_token)

            # Verify file was created and contains correct content
            assert token_file.exists()
            assert token_file.read_text() == test_token
            
            # Verify file permissions are restrictive
            assert oct(token_file.stat().st_mode)[-3:] == "600"
            
            # Verify environment variable was set
            assert os.environ["TEST_OKTA_COOKIE"] == test_token

    def test_save_token_file_creation_failure(self) -> None:
        """Test token saving fails when file cannot be created."""
        config = Config()
        config.TOKEN_FILE = Path("/nonexistent/directory/token")

        extractor = OktaTokenExtractor(config)
        
        with pytest.raises(OktaTokenExtractionError, match="Failed to save token"):
            extractor.save_token("test-token")

    def test_cleanup_with_driver(self) -> None:
        """Test cleanup closes driver properly."""
        mock_driver = Mock()
        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        extractor.cleanup()

        mock_driver.quit.assert_called_once()
        assert extractor.driver is None

    def test_cleanup_without_driver(self) -> None:
        """Test cleanup handles missing driver gracefully."""
        extractor = OktaTokenExtractor()
        # Should not raise any exception
        extractor.cleanup()

    def test_cleanup_driver_quit_error(self) -> None:
        """Test cleanup handles driver quit errors gracefully."""
        mock_driver = Mock()
        mock_driver.quit.side_effect = WebDriverException("Quit failed")
        
        extractor = OktaTokenExtractor()
        extractor.driver = mock_driver

        # Should not raise exception, just print warning
        extractor.cleanup()
        assert extractor.driver is None

    @patch.object(OktaTokenExtractor, "setup_driver")
    @patch.object(OktaTokenExtractor, "login_to_okta")
    @patch.object(OktaTokenExtractor, "handle_mfa")
    @patch.object(OktaTokenExtractor, "extract_token_from_internal_service")
    @patch.object(OktaTokenExtractor, "save_token")
    @patch.object(OktaTokenExtractor, "cleanup")
    @patch("time.sleep")
    def test_run_success(self, mock_sleep, mock_cleanup, mock_save, mock_extract, 
                        mock_mfa, mock_login, mock_setup) -> None:
        """Test successful complete run."""
        mock_extract.return_value = "test-token"

        extractor = OktaTokenExtractor()
        result = extractor.run()

        assert result == "test-token"
        mock_setup.assert_called_once()
        mock_login.assert_called_once()
        mock_mfa.assert_called_once()
        mock_extract.assert_called_once()
        mock_save.assert_called_once_with("test-token")
        mock_cleanup.assert_called_once()
        mock_sleep.assert_called_once_with(2)

    @patch.object(OktaTokenExtractor, "setup_driver")
    @patch.object(OktaTokenExtractor, "cleanup")
    def test_run_failure_cleanup_called(self, mock_cleanup, mock_setup) -> None:
        """Test that cleanup is called even when run fails."""
        mock_setup.side_effect = OktaTokenExtractionError("Setup failed")

        extractor = OktaTokenExtractor()
        
        with pytest.raises(OktaTokenExtractionError):
            extractor.run()

        mock_cleanup.assert_called_once()

    def test_context_manager(self) -> None:
        """Test context manager functionality."""
        extractor = OktaTokenExtractor()
        
        with extractor as ctx_extractor:
            assert ctx_extractor is extractor

        # Cleanup should have been called
        # (We can't easily test this without mocking, but the structure is correct)

    @patch.object(OktaTokenExtractor, "cleanup")
    def test_context_manager_cleanup_on_exception(self, mock_cleanup) -> None:
        """Test context manager calls cleanup on exception."""
        extractor = OktaTokenExtractor()
        
        with pytest.raises(ValueError):
            with extractor:
                raise ValueError("Test exception")

        mock_cleanup.assert_called_once() 