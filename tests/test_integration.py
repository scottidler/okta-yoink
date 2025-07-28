"""Integration tests for the complete Okta token automation workflow."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from okta_token_automation.config import Config
from okta_token_automation.main import main
from okta_token_automation.token_extractor import OktaTokenExtractor


class TestIntegration:
    """Integration test cases for the complete workflow."""

    @patch("builtins.input", side_effect=["testuser@example.com", "testpassword"])
    @patch("okta_token_automation.token_extractor.ChromeDriverManager")
    @patch("okta_token_automation.token_extractor.webdriver.Chrome")
    @patch("okta_token_automation.token_extractor.WebDriverWait")
    def test_complete_workflow_success(self, mock_wait, mock_chrome, mock_driver_manager, mock_input) -> None:
        """Test complete successful workflow from start to finish."""
        # Clear environment to prevent .env interference
        with patch.dict(os.environ, {}, clear=True):
            # Setup temporary directory for token file
            with tempfile.TemporaryDirectory() as temp_dir:
                token_file = Path(temp_dir) / "test-token"

                # Setup config
                config = Config()
                config.TOKEN_FILE = token_file
                config.TOKEN_ENV_VAR = "TEST_OKTA_COOKIE"
                config.HEADLESS = True  # Run in headless mode for testing

                # Setup mocks
                mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
                mock_driver = Mock()
                mock_chrome.return_value = mock_driver

                # Mock login form elements
                mock_username_field = Mock()
                mock_password_field = Mock()
                mock_submit_button = Mock()

                # Mock JSON response element
                mock_json_element = Mock()
                json_response = {
                    "headers": {
                        "Authorization": "Bearer some-token",
                        "X-Oauth2-Proxy": "_oauth2_proxy=integration-test-token-12345",
                        "User-Agent": "Chrome/91.0"
                    }
                }
                mock_json_element.text = json.dumps(json_response)

                # Setup WebDriverWait mock sequence
                mock_yubikey_button = Mock()  # Add YubiKey button mock
                wait_calls = [
                    mock_username_field,  # Login form wait
                    mock_yubikey_button,  # YubiKey button selection
                    True,  # MFA completion wait
                    mock_json_element,  # JSON response wait
                ]
                mock_wait_instance = Mock()
                mock_wait_instance.until.side_effect = wait_calls
                mock_wait.return_value = mock_wait_instance

                # Setup driver.find_element mock sequence
                find_element_calls = [
                    mock_password_field,  # Password field
                    mock_submit_button,   # Submit button
                    mock_json_element,    # JSON element
                ]
                mock_driver.find_element.side_effect = find_element_calls

                # Run the extraction
                extractor = OktaTokenExtractor(config)
                token = extractor.run()

                # Verify the complete workflow
                assert token == "_oauth2_proxy=integration-test-token-12345"

                # Verify file was created with correct content
                assert token_file.exists()
                assert token_file.read_text() == "_oauth2_proxy=integration-test-token-12345"

                # Verify environment variable was set
                assert os.environ["TEST_OKTA_COOKIE"] == "_oauth2_proxy=integration-test-token-12345"

                # Verify all expected interactions
                mock_driver.get.assert_any_call("https://tatari.okta.com")  # Login page
                mock_driver.get.assert_any_call("https://httpbin.ops.tatari.dev/headers")  # Token extraction
                mock_username_field.send_keys.assert_called_once_with("testuser@example.com")
                mock_password_field.send_keys.assert_called_once_with("testpassword")
                mock_submit_button.click.assert_called_once()
                mock_driver.quit.assert_called_once()

    @patch("okta_token_automation.main.OktaTokenExtractor")
    @patch("okta_token_automation.main.Config")
    def test_main_integration_success(self, mock_config_class, mock_extractor_class) -> None:
        """Test main function integration with all components."""
        # Setup mocks
        mock_config = Mock()
        mock_config.TOKEN_ENV_VAR = "OKTA_COOKIE"
        mock_config.TOKEN_FILE = Path("/tmp/test-token")
        mock_config_class.return_value = mock_config

        mock_extractor = Mock()
        mock_extractor.run.return_value = "_oauth2_proxy=main-integration-token"
        mock_extractor.__enter__ = Mock(return_value=mock_extractor)
        mock_extractor.__exit__ = Mock(return_value=None)
        mock_extractor_class.return_value = mock_extractor

        # Run main
        result = main()

        # Verify success
        assert result == 0

        # Verify component interactions
        mock_config_class.assert_called_once()
        mock_extractor_class.assert_called_once_with(mock_config)
        mock_extractor.run.assert_called_once()
        mock_extractor.__enter__.assert_called_once()
        mock_extractor.__exit__.assert_called_once()

    @patch("okta_token_automation.token_extractor.ChromeDriverManager")
    @patch("okta_token_automation.token_extractor.webdriver.Chrome")
    @patch("okta_token_automation.token_extractor.WebDriverWait")
    def test_workflow_with_different_oauth2_header_formats(self, mock_wait, mock_chrome, mock_driver_manager) -> None:
        """Test workflow handles different oauth2_proxy header formats."""
        test_cases = [
            ("X-Oauth2-Proxy", "_oauth2_proxy=token123", "_oauth2_proxy=token123"),
            ("x-oauth2-proxy", "token456", "_oauth2_proxy=token456"),
            ("Authorization-Oauth2-Proxy", "_oauth2_proxy=token789", "_oauth2_proxy=token789"),
        ]

        for header_name, header_value, expected_token in test_cases:
            with tempfile.TemporaryDirectory() as temp_dir:
                token_file = Path(temp_dir) / "test-token"
                config = Config()
                config.TOKEN_FILE = token_file
                config.TOKEN_ENV_VAR = f"TEST_TOKEN_{header_name.replace('-', '_').upper()}"
                config.OKTA_USERNAME = "testuser@example.com"  # Set username to avoid input prompt

                # Setup mocks
                mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
                mock_driver = Mock()
                mock_chrome.return_value = mock_driver

                # Mock elements
                mock_username_field = Mock()
                mock_password_field = Mock()
                mock_submit_button = Mock()
                mock_json_element = Mock()

                json_response = {
                    "headers": {
                        header_name: header_value,
                        "User-Agent": "Chrome/91.0"
                    }
                }
                mock_json_element.text = json.dumps(json_response)

                # Setup wait sequence
                wait_calls = [mock_username_field, True, mock_json_element]
                mock_wait_instance = Mock()
                mock_wait_instance.until.side_effect = wait_calls
                mock_wait.return_value = mock_wait_instance

                # Setup find_element sequence
                find_element_calls = [mock_password_field, mock_submit_button, mock_json_element]
                mock_driver.find_element.side_effect = find_element_calls

                # Run extraction
                extractor = OktaTokenExtractor(config)
                with patch("builtins.input", return_value="testpassword"):
                    token = extractor.run()

                # Verify correct token format
                assert token == expected_token
                assert token_file.read_text() == expected_token

    @patch("builtins.input", side_effect=["testuser@example.com", "testpassword"])
    @patch("okta_token_automation.token_extractor.ChromeDriverManager")
    @patch("okta_token_automation.token_extractor.webdriver.Chrome")
    @patch("okta_token_automation.token_extractor.WebDriverWait")
    def test_workflow_with_configured_username(self, mock_wait, mock_chrome, mock_driver_manager, mock_input) -> None:
        """Test workflow with pre-configured username."""
        with tempfile.TemporaryDirectory() as temp_dir:
            token_file = Path(temp_dir) / "test-token"

            # Setup config with username
            config = Config()
            config.TOKEN_FILE = token_file
            config.TOKEN_ENV_VAR = "TEST_OKTA_COOKIE"
            config.OKTA_USERNAME = "configured.user@example.com"

            # Setup mocks
            mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
            mock_driver = Mock()
            mock_chrome.return_value = mock_driver

            # Mock elements
            mock_username_field = Mock()
            mock_password_field = Mock()
            mock_submit_button = Mock()
            mock_json_element = Mock()

            json_response = {
                "headers": {
                    "X-Oauth2-Proxy": "_oauth2_proxy=configured-user-token",
                }
            }
            mock_json_element.text = json.dumps(json_response)

            # Setup wait sequence
            wait_calls = [mock_username_field, True, mock_json_element]
            mock_wait_instance = Mock()
            mock_wait_instance.until.side_effect = wait_calls
            mock_wait.return_value = mock_wait_instance

            # Setup find_element sequence
            find_element_calls = [mock_password_field, mock_submit_button, mock_json_element]
            mock_driver.find_element.side_effect = find_element_calls

            # Run extraction
            extractor = OktaTokenExtractor(config)
            token = extractor.run()

            # Verify username was used from config
            mock_username_field.send_keys.assert_called_once_with("configured.user@example.com")
            # Should only prompt for password, not username
            mock_input.assert_called_once_with("Enter your Okta password: ")

            assert token == "_oauth2_proxy=configured-user-token"

    @patch("okta_token_automation.token_extractor.ChromeDriverManager")
    @patch("okta_token_automation.token_extractor.webdriver.Chrome")
    def test_workflow_cleanup_on_failure(self, mock_chrome, mock_driver_manager) -> None:
        """Test that cleanup is called even when workflow fails."""
        # Setup mocks
        mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver

        # Make login fail
        mock_driver.get.side_effect = Exception("Network error")

        config = Config()
        extractor = OktaTokenExtractor(config)

        # Verify extraction fails but cleanup is still called
        with pytest.raises(Exception):
            extractor.run()

        # Verify driver was still cleaned up
        mock_driver.quit.assert_called_once()

    def test_config_integration_with_environment(self) -> None:
        """Test that config properly integrates with environment variables."""
        test_env = {
            "OKTA_LOGIN_URL": "https://test.okta.com",
            "HTTPBIN_URL": "https://test.httpbin.dev/headers",
            "HEADLESS": "true",
            "BROWSER_TIMEOUT": "45",
            "OKTA_USERNAME": "test@example.com",
        }

        with patch.dict(os.environ, test_env):
            config = Config()

            # Verify all environment variables are properly loaded
            assert config.OKTA_LOGIN_URL == "https://test.okta.com"
            assert config.HTTPBIN_URL == "https://test.httpbin.dev/headers"
            assert config.HEADLESS is True
            assert config.BROWSER_TIMEOUT == 45
            assert config.OKTA_USERNAME == "test@example.com"

            # Verify validation passes
            config.validate()

    def test_token_file_permissions_integration(self) -> None:
        """Test that token file is created with correct permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            token_file = Path(temp_dir) / "permission-test-token"

            config = Config()
            config.TOKEN_FILE = token_file

            extractor = OktaTokenExtractor(config)
            extractor.save_token("_oauth2_proxy=permission-test-token")

            # Verify file exists and has restrictive permissions
            assert token_file.exists()
            file_mode = oct(token_file.stat().st_mode)[-3:]
            assert file_mode == "600"  # Owner read/write only
