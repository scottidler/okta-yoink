"""Token extraction module for Okta automation."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .config import Config


class OktaTokenExtractionError(Exception):
    """Custom exception for token extraction errors."""

    pass


class OktaTokenExtractor:
    """Main class for extracting Okta tokens using Selenium automation."""

    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize the token extractor with configuration.

        Args:
            config: Configuration object. If None, creates default config.
        """
        self.config = config or Config()
        self.config.validate()
        self.driver: Optional[webdriver.Chrome] = None
        self.logger = logging.getLogger(__name__)
        self.logger.debug("OktaTokenExtractor initialized with config: %s", self.config)

    def setup_driver(self) -> None:
        """Initialize Chrome WebDriver with appropriate options."""
        self.logger.debug("Setting up Chrome WebDriver...")
        chrome_options = ChromeOptions()

        if self.config.HEADLESS:
            self.logger.debug("Running in headless mode")
            chrome_options.add_argument("--headless")
        else:
            self.logger.debug("Running with GUI")

        # Security and performance options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--window-size=1920,1080")

        # Set custom binary path if provided
        if self.config.CHROME_BINARY_PATH:
            chrome_options.binary_location = self.config.CHROME_BINARY_PATH

        try:
            # Use custom chromedriver path if provided, otherwise use webdriver-manager
            if self.config.CHROMEDRIVER_PATH:
                service = ChromeService(executable_path=self.config.CHROMEDRIVER_PATH)
            else:
                service = ChromeService(ChromeDriverManager().install())

            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(self.config.IMPLICIT_WAIT)

        except Exception as e:
            raise OktaTokenExtractionError(f"Failed to initialize Chrome WebDriver: {e}")

    def login_to_okta(self) -> None:
        """Navigate to Okta and handle login flow.

        User will need to manually enter credentials and perform MFA.

        Raises:
            OktaTokenExtractionError: If login process fails.
        """
        if not self.driver:
            raise OktaTokenExtractionError("Driver not initialized")

        print("🔄 Navigating to Okta login...")
        self.logger.debug("Navigating to Okta login URL: %s", self.config.OKTA_LOGIN_URL)
        try:
            self.driver.get(self.config.OKTA_LOGIN_URL)
            self.logger.debug("Successfully navigated to: %s", self.driver.current_url)

            # Wait for login form - try multiple possible selectors
            username_field = None
            password_field = None

            # Try to find username field with various selectors
            for selector in [
                (By.ID, "okta-signin-username"),
                (By.NAME, "username"),
                (By.CSS_SELECTOR, "input[type='text']"),
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.XPATH, "//input[contains(@placeholder, 'Username') or contains(@placeholder, 'username')]")
            ]:
                try:
                    self.logger.debug("Trying to find username field with selector: %s", selector)
                    username_field = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(selector)
                    )
                    print(f"✅ Found username field using: {selector}")
                    self.logger.debug("Successfully found username field")
                    break
                except Exception as e:
                    self.logger.debug("Failed to find username field with selector %s: %s", selector, e)
                    continue

            if not username_field:
                raise OktaTokenExtractionError("Could not find username field with any known selector")

            # Try to find password field
            for selector in [
                (By.ID, "okta-signin-password"),
                (By.NAME, "password"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.XPATH, "//input[contains(@placeholder, 'Password') or contains(@placeholder, 'password')]")
            ]:
                try:
                    password_field = self.driver.find_element(*selector)
                    print(f"✅ Found password field using: {selector}")
                    break
                except:
                    continue

            if not password_field:
                raise OktaTokenExtractionError("Could not find password field with any known selector")

            # Get credentials from user or environment
            if not self.config.OKTA_USERNAME:
                username = input("Enter your Okta username: ")
            else:
                username = self.config.OKTA_USERNAME

            password = input("Enter your Okta password: ")

            # Fill credentials
            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)

            # Find and click submit button
            submit_button = None
            for selector in [
                (By.ID, "okta-signin-submit"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.XPATH, "//button[contains(text(), 'Sign in') or contains(text(), 'Sign In') or contains(text(), 'Login')]")
            ]:
                try:
                    submit_button = self.driver.find_element(*selector)
                    print(f"✅ Found submit button using: {selector}")
                    break
                except:
                    continue

            if not submit_button:
                raise OktaTokenExtractionError("Could not find submit button")

            submit_button.click()

            print("✅ Credentials submitted")

        except TimeoutException:
            raise OktaTokenExtractionError(
                f"Timeout waiting for Okta login page after {self.config.BROWSER_TIMEOUT}s"
            )
        except NoSuchElementException as e:
            raise OktaTokenExtractionError(f"Could not find login form elements: {e}")
        except Exception as e:
            raise OktaTokenExtractionError(f"Error during login: {e}")

    def handle_mfa(self) -> None:
        """Handle MFA challenge - automatically select YubiKey and wait for completion.

        Raises:
            OktaTokenExtractionError: If MFA process fails or times out.
        """
        if not self.driver:
            raise OktaTokenExtractionError("Driver not initialized")

        print("🔐 Checking for MFA challenge...")
        self.logger.debug("Starting MFA handling, current URL: %s", self.driver.current_url)

        try:
            # First, check if we're on an MFA selection page
            time.sleep(2)  # Wait for page to load
            self.logger.debug("After 2s wait, current URL: %s", self.driver.current_url)

            # Look for YubiKey/Security Key option and auto-select it
            yubikey_selectors = [
                (By.XPATH, "//button[contains(text(), 'Security Key') or contains(text(), 'Biometric')]"),
                (By.XPATH, "//div[contains(text(), 'Security Key') or contains(text(), 'Biometric')]//following::button[contains(text(), 'Select')]"),
                (By.CSS_SELECTOR, "button[data-se='webauthn']"),
                (By.XPATH, "//span[contains(text(), 'Security Key')]//ancestor::div//button"),
            ]

            yubikey_button = None
            for selector in yubikey_selectors:
                try:
                    yubikey_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable(selector)
                    )
                    print(f"✅ Found YubiKey option using: {selector}")
                    break
                except:
                    continue

            if yubikey_button:
                print("🔑 Automatically selecting YubiKey/Security Key option...")
                yubikey_button.click()
                time.sleep(2)  # Wait for selection to process

            print("👆 Please complete MFA (YubiKey touch/PIN) in the browser window")

            # Wait for MFA completion by checking URL change
            self.logger.debug("Waiting for MFA completion, timeout: %s seconds", self.config.MFA_TIMEOUT)
            WebDriverWait(self.driver, self.config.MFA_TIMEOUT).until(
                lambda driver: (
                    "mfa" not in driver.current_url.lower()
                    and "challenge" not in driver.current_url.lower()
                    and "login" not in driver.current_url.lower()
                    and "verify" not in driver.current_url.lower()
                )
            )
            print("✅ MFA completed successfully")
            self.logger.debug("MFA completed, final URL: %s", self.driver.current_url)

        except TimeoutException:
            raise OktaTokenExtractionError(
                f"MFA timeout after {self.config.MFA_TIMEOUT}s. "
                "Please complete MFA faster or increase MFA_TIMEOUT."
            )
        except Exception as e:
            raise OktaTokenExtractionError(f"Error during MFA: {e}")

    def extract_token_via_requests(self) -> str:
        """Extract token by making direct HTTP request with browser cookies.

        This is faster and more reliable than scraping the JSON from the page.

        Returns:
            The extracted token in format "_oauth2_proxy=TOKEN_VALUE"

        Raises:
            OktaTokenExtractionError: If token extraction fails.
        """
        if not self.driver:
            raise OktaTokenExtractionError("Driver not initialized")

        print("🔄 Extracting token via direct HTTP request...")
        self.logger.debug("Starting token extraction via HTTP request")

        try:
            # Get all cookies from the browser session
            selenium_cookies = self.driver.get_cookies()
            self.logger.debug("Retrieved %d cookies from browser session", len(selenium_cookies))

            # Convert selenium cookies to requests session cookies
            session = requests.Session()
            for cookie in selenium_cookies:
                session.cookies.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie.get('domain'),
                    path=cookie.get('path', '/'),
                    secure=cookie.get('secure', False)
                )

            # Make direct request to httpbin endpoint
            self.logger.debug("Making HTTP request to: %s", self.config.HTTPBIN_URL)
            response = session.get(self.config.HTTPBIN_URL, timeout=30)
            self.logger.debug("HTTP response status: %d", response.status_code)
            response.raise_for_status()

            # Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                raise OktaTokenExtractionError(f"Invalid JSON response: {e}")

            headers = data.get("headers", {})
            if not headers:
                raise OktaTokenExtractionError("No headers found in response")

            self.logger.debug("Found headers: %s", list(headers.keys()))
            if "Cookie" in headers:
                self.logger.debug("Cookie header found: %s", headers["Cookie"][:200] + "..." if len(headers["Cookie"]) > 200 else headers["Cookie"])

            # Method 1: Look for _oauth2_proxy in Cookie header (most common)
            cookie_header = headers.get("Cookie", "")
            if cookie_header:
                # Parse cookies to find _oauth2_proxy
                for cookie in cookie_header.split(";"):
                    cookie = cookie.strip()
                    if cookie.startswith("_oauth2_proxy="):
                        token = cookie.split("=", 1)[1]
                        if token.strip():
                            print(f"✅ Token extracted via HTTP request: {token[:50]}...")
                            return f"_oauth2_proxy={token}"

            # Method 2: Look for _oauth2_proxy as separate header (fallback)
            oauth2_header = None
            oauth2_header_name = None
            for header_name, header_value in headers.items():
                if "oauth2" in header_name.lower() and "proxy" in header_name.lower():
                    oauth2_header = header_value
                    oauth2_header_name = header_name
                    break

            if oauth2_header:
                # Extract the token value
                if "=" in oauth2_header:
                    token = oauth2_header.split("=", 1)[1]
                else:
                    token = oauth2_header

                if token.strip():
                    print(f"✅ Token extracted from header '{oauth2_header_name}': {token[:50]}...")
                    return f"_oauth2_proxy={token}"

            # Method 3: Look in Authorization header (another possibility)
            auth_header = headers.get("Authorization", "")
            if "oauth2_proxy" in auth_header.lower():
                # Try to extract token from Authorization header
                if "=" in auth_header:
                    token = auth_header.split("=", 1)[1]
                    if token.strip():
                        print(f"✅ Token extracted from Authorization header: {token[:50]}...")
                        return f"_oauth2_proxy={token}"

            # If we get here, no token was found
            available_headers = list(headers.keys())
            cookie_preview = cookie_header[:200] + "..." if len(cookie_header) > 200 else cookie_header
            raise OktaTokenExtractionError(
                f"No _oauth2_proxy token found in response. "
                f"Available headers: {available_headers}. "
                f"Cookie header preview: {cookie_preview}"
            )

        except requests.RequestException as e:
            raise OktaTokenExtractionError(f"HTTP request failed: {e}")
        except Exception as e:
            if isinstance(e, OktaTokenExtractionError):
                raise
            raise OktaTokenExtractionError(f"Error extracting token via HTTP request: {e}")

    def extract_token_from_internal_service(self) -> str:
        """Navigate to internal service and extract the _oauth2_proxy token.

        Note: Once authenticated, this token is sent with ALL internal service requests.

        Returns:
            The extracted token in format "_oauth2_proxy=TOKEN_VALUE"

        Raises:
            OktaTokenExtractionError: If token extraction fails.
        """
        if not self.driver:
            raise OktaTokenExtractionError("Driver not initialized")

        print("🔄 Navigating to internal service to extract token...")
        self.logger.debug("Navigating browser to httpbin URL: %s", self.config.HTTPBIN_URL)

        try:
            self.driver.get(self.config.HTTPBIN_URL)
            self.logger.debug("Successfully navigated to: %s", self.driver.current_url)

            # Wait for JSON response
            WebDriverWait(self.driver, self.config.BROWSER_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "pre"))
            )

            # Get the JSON content
            json_element = self.driver.find_element(By.TAG_NAME, "pre")
            json_content = json_element.text

            if not json_content.strip():
                raise OktaTokenExtractionError("Empty response from httpbin service")

            # Parse JSON to find _oauth2_proxy token
            try:
                data = json.loads(json_content)
            except json.JSONDecodeError as e:
                raise OktaTokenExtractionError(f"Invalid JSON response: {e}")

            headers = data.get("headers", {})
            if not headers:
                raise OktaTokenExtractionError("No headers found in response")

            # Method 1: Look for _oauth2_proxy in Cookie header (most common)
            cookie_header = headers.get("Cookie", "")
            if cookie_header:
                # Parse cookies to find _oauth2_proxy
                for cookie in cookie_header.split(";"):
                    cookie = cookie.strip()
                    if cookie.startswith("_oauth2_proxy="):
                        token = cookie.split("=", 1)[1]
                        if token.strip():
                            print(f"✅ Token extracted from Cookie header: {token[:50]}...")
                            return f"_oauth2_proxy={token}"

            # Method 2: Look for _oauth2_proxy as separate header (fallback)
            oauth2_header = None
            oauth2_header_name = None
            for header_name, header_value in headers.items():
                if "oauth2" in header_name.lower() and "proxy" in header_name.lower():
                    oauth2_header = header_value
                    oauth2_header_name = header_name
                    break

            if oauth2_header:
                # Extract the token value
                if "=" in oauth2_header:
                    token = oauth2_header.split("=", 1)[1]
                else:
                    token = oauth2_header

                if token.strip():
                    print(f"✅ Token extracted from header '{oauth2_header_name}': {token[:50]}...")
                    return f"_oauth2_proxy={token}"

            # Method 3: Look in Authorization header (another possibility)
            auth_header = headers.get("Authorization", "")
            if "oauth2_proxy" in auth_header.lower():
                # Try to extract token from Authorization header
                if "=" in auth_header:
                    token = auth_header.split("=", 1)[1]
                    if token.strip():
                        print(f"✅ Token extracted from Authorization header: {token[:50]}...")
                        return f"_oauth2_proxy={token}"

            # If we get here, no token was found
            available_headers = list(headers.keys())
            cookie_preview = cookie_header[:200] + "..." if len(cookie_header) > 200 else cookie_header
            raise OktaTokenExtractionError(
                f"No _oauth2_proxy token found in response. "
                f"Available headers: {available_headers}. "
                f"Cookie header preview: {cookie_preview}"
            )

        except TimeoutException:
            raise OktaTokenExtractionError(
                f"Timeout waiting for httpbin response after {self.config.BROWSER_TIMEOUT}s"
            )
        except NoSuchElementException:
            raise OktaTokenExtractionError("Could not find JSON response element")
        except Exception as e:
            if isinstance(e, OktaTokenExtractionError):
                raise
            raise OktaTokenExtractionError(f"Error extracting token: {e}")

    def save_token(self, token: str) -> None:
        """Save token to file and environment variable.

        Args:
            token: The token string to save.

        Raises:
            OktaTokenExtractionError: If saving fails.
        """
        try:
            # Save to file
            self.config.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.config.TOKEN_FILE.write_text(token, encoding="utf-8")

            # Set restrictive permissions on token file
            self.config.TOKEN_FILE.chmod(0o600)

            # Set environment variable for current session
            os.environ[self.config.TOKEN_ENV_VAR] = token

            print(f"✅ Token saved to {self.config.TOKEN_FILE}")
            print(f"✅ Environment variable {self.config.TOKEN_ENV_VAR} set")

        except Exception as e:
            raise OktaTokenExtractionError(f"Failed to save token: {e}")

    def cleanup(self) -> None:
        """Clean up resources (close browser)."""
        if self.driver:
            try:
                self.driver.quit()
                print("🔄 Browser session closed")
            except Exception as e:
                print(f"⚠️  Warning: Error closing browser: {e}")
            finally:
                self.driver = None

    def run(self) -> str:
        """Main execution flow.

        Returns:
            The extracted token string.

        Raises:
            OktaTokenExtractionError: If any step in the process fails.
        """
        try:
            print("🚀 Starting Okta token extraction...")
            self.logger.info("Starting token extraction process")

            self.setup_driver()
            self.logger.debug("Driver setup completed")

            self.login_to_okta()
            self.logger.debug("Login completed")

            self.handle_mfa()
            self.logger.debug("MFA completed")

            # Small delay to ensure full authentication
            self.logger.debug("Waiting 2 seconds for authentication to settle")
            time.sleep(2)

            # Try the faster HTTP request method first, fall back to page scraping
            try:
                self.logger.debug("Attempting token extraction via HTTP requests")
                token = self.extract_token_via_requests()
                self.logger.debug("HTTP request method succeeded")
            except OktaTokenExtractionError as e:
                print(f"⚠️  HTTP request method failed: {e}")
                self.logger.warning("HTTP request method failed: %s", e)
                print("🔄 Falling back to page scraping method...")
                self.logger.debug("Attempting token extraction via page scraping")
                token = self.extract_token_from_internal_service()
                self.logger.debug("Page scraping method succeeded")

            self.save_token(token)
            self.logger.debug("Token saved successfully")

            print("🎉 Token extraction completed successfully!")
            self.logger.info("Token extraction completed successfully")
            return token

        except Exception as e:
            if isinstance(e, OktaTokenExtractionError):
                raise
            raise OktaTokenExtractionError(f"Token extraction failed: {e}")

        finally:
            self.cleanup()

    def __enter__(self) -> "OktaTokenExtractor":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup resources."""
        self.cleanup()
