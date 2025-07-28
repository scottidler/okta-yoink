"""Token extraction module for Okta automation."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple, List

import requests
from bs4 import BeautifulSoup
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
        # Use unique user data directory to prevent conflicts
        import tempfile
        user_data_dir = tempfile.mkdtemp(prefix="okta-yoink-chrome-")
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

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

        print("🔄 Navigating to httpbin (will redirect to Okta)...")
        self.logger.debug("Navigating to httpbin URL: %s", self.config.HTTPBIN_URL)
        try:
            self.driver.get(self.config.HTTPBIN_URL)
            self.logger.debug("Successfully navigated to: %s", self.driver.current_url)

            # Wait for redirect to Okta and login form to appear
            print("🔄 Waiting for redirect to Okta login page...")
            try:
                # Wait for URL to contain 'okta' and for login form elements to be present
                WebDriverWait(self.driver, 15).until(
                    lambda driver: (
                        'okta' in driver.current_url.lower() and
                        (driver.find_elements(By.TAG_NAME, "input") or
                         driver.find_elements(By.TAG_NAME, "form"))
                    )
                )
                print(f"✅ Redirected to Okta: {self.driver.current_url}")

                # Additional wait for form elements to be fully loaded
                time.sleep(2)

            except TimeoutException:
                print(f"⚠️  Timeout waiting for Okta redirect. Current URL: {self.driver.current_url}")
                # Continue anyway, might still work

            # Debug: Print page title and current URL
            print(f"🔍 Page title: {self.driver.title}")
            print(f"🔍 Current URL: {self.driver.current_url}")

            # Debug: Look for any input elements on the page
            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
            print(f"🔍 Found {len(all_inputs)} input elements on page:")
            for i, input_elem in enumerate(all_inputs):
                try:
                    input_type = input_elem.get_attribute("type") or "text"
                    input_name = input_elem.get_attribute("name") or "no-name"
                    input_id = input_elem.get_attribute("id") or "no-id"
                    input_placeholder = input_elem.get_attribute("placeholder") or "no-placeholder"
                    input_autocomplete = input_elem.get_attribute("autocomplete") or "no-autocomplete"
                    input_class = input_elem.get_attribute("class") or "no-class"
                    print(f"  Input {i}: type='{input_type}', name='{input_name}', id='{input_id}', placeholder='{input_placeholder}', autocomplete='{input_autocomplete}', class='{input_class}'")
                except Exception as e:
                    print(f"  Input {i}: Error getting attributes: {e}")

            # Now try to find the username field - we know from debug it's name='identifier'
            username_field = None

            print("🔍 Looking for username field...")
            try:
                # First try the exact selector we know works from the debug output
                username_field = self.driver.find_element(By.NAME, "identifier")
                print("✅ Found username field with name='identifier'")
            except Exception as e:
                print(f"❌ Failed to find by name='identifier': {e}")

                # Try other approaches
                selectors_to_try = [
                    (By.CSS_SELECTOR, "input[name='identifier']"),
                    (By.CSS_SELECTOR, "input[autocomplete='username']"),
                    (By.CSS_SELECTOR, "input[type='text']"),
                    (By.XPATH, "//input[@name='identifier']"),
                    (By.XPATH, "//input[@autocomplete='username']"),
                ]

                for selector_type, selector_value in selectors_to_try:
                    try:
                        print(f"🔍 Trying selector: {selector_type} = '{selector_value}'")
                        username_field = self.driver.find_element(selector_type, selector_value)
                        print(f"✅ Found username field using: {selector_type} = '{selector_value}'")
                        break
                    except Exception as ex:
                        print(f"❌ Failed: {ex}")
                        continue

            if not username_field:
                # Last resort - get the first text input we found in debug
                try:
                    all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                    for input_elem in all_inputs:
                        if input_elem.get_attribute("type") == "text":
                            username_field = input_elem
                            print("✅ Found username field as first text input")
                            break
                except Exception as e:
                    print(f"❌ Last resort failed: {e}")

            if not username_field:
                # Use BeautifulSoup to analyze the DOM and find the right selectors
                print("🔍 Using BeautifulSoup to analyze DOM...")
                username_field = self._find_element_with_soup()

            if not username_field:
                raise OktaTokenExtractionError("Could not find username field with any known selector")

            # Get username from environment or prompt user
            if not self.config.OKTA_USERNAME:
                username = input("Enter your Okta username: ")
            else:
                username = self.config.OKTA_USERNAME
                print(f"🔑 Using username from config: {username}")

            # Fill username field
            username_field.clear()
            username_field.send_keys(username)
            print("✅ Username filled")

            # Check if there's a password field on the same page (common in newer Okta)
            password_field = None
            print("🔍 Looking for password field on same page...")

            # Use our debug info - we know there's a password field: name='credentials.passcode', id='input36'
            try:
                password_field = self.driver.find_element(By.NAME, "credentials.passcode")
                print("✅ Found password field with name='credentials.passcode'")
            except Exception as e:
                print(f"❌ Failed to find by name='credentials.passcode': {e}")

                # Try other selectors
                for selector_type, selector_value in [
                    (By.CSS_SELECTOR, "input[type='password']"),
                    (By.CSS_SELECTOR, "input[autocomplete='current-password']"),
                    (By.XPATH, "//input[@type='password']"),
                ]:
                    try:
                        password_field = self.driver.find_element(selector_type, selector_value)
                        print(f"✅ Found password field using: {selector_type} = '{selector_value}'")
                        break
                    except Exception as ex:
                        print(f"❌ Failed: {ex}")
                        continue

            # Fill password field if it exists
            if password_field:
                if not self.config.OKTA_PASSWORD:
                    password = input("Enter your Okta password: ")
                else:
                    password = self.config.OKTA_PASSWORD
                    print("🔑 Using password from config")

                password_field.clear()
                password_field.send_keys(password)
                print("✅ Password filled")
            else:
                print("ℹ️  No password field found on this page")

            # Now find and click submit button (after both fields are filled)
            submit_button = self._find_submit_button_with_soup()

            if not submit_button:
                raise OktaTokenExtractionError("Could not find submit button")

            submit_button.click()
            if password_field:
                print("✅ Username and password submitted, proceeding to MFA...")
            else:
                print("✅ Username submitted, proceeding to next step...")

        except TimeoutException:
            raise OktaTokenExtractionError(
                f"Timeout waiting for login page after {self.config.BROWSER_TIMEOUT}s"
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
            # Wait for MFA page to load properly
            print("🔄 Waiting for MFA page to load...")

            # Wait for URL to change to MFA/verify page or for MFA elements to appear
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda driver: (
                        'verify' in driver.current_url.lower() or
                        'mfa' in driver.current_url.lower() or
                        'challenge' in driver.current_url.lower() or
                        driver.find_elements(By.XPATH, "//*[contains(text(), 'Security Key') or contains(text(), 'Biometric') or contains(text(), 'Authenticator')]")
                    )
                )
                print(f"✅ MFA page loaded: {self.driver.current_url}")
            except TimeoutException:
                print(f"⚠️  Timeout waiting for MFA page. Current URL: {self.driver.current_url}")
                # Continue anyway, might still work

            # Additional wait for MFA elements to be fully rendered
            time.sleep(3)
            self.logger.debug("After MFA page load wait, current URL: %s", self.driver.current_url)

            # Look for YubiKey/Security Key option using BeautifulSoup
            yubikey_button = self._find_mfa_options_with_soup()

            if yubikey_button:
                print("🔑 Automatically selecting YubiKey/Security Key option...")
                yubikey_button.click()
                time.sleep(2)  # Wait for selection to process

            print("👆 Please complete MFA (YubiKey touch/PIN) in the browser window")

            # Wait for MFA completion by checking for successful redirect to httpbin
            self.logger.debug("Waiting for MFA completion, timeout: %s seconds", self.config.MFA_TIMEOUT)

            start_time = time.time()
            mfa_completed = False

            while time.time() - start_time < self.config.MFA_TIMEOUT:
                current_url = self.driver.current_url
                print(f"🔍 Current URL: {current_url}")

                # Check if we've successfully reached httpbin (authentication complete)
                if "httpbin.ops.tatari.dev" in current_url:
                    print("✅ Successfully redirected to httpbin - authentication complete!")
                    mfa_completed = True
                    break

                # Check if we're back at login page (MFA failed or session expired)
                if any(indicator in current_url.lower() for indicator in ["signin", "login", "oauth2/default/v1/authorize"]):
                    # Check if there are username/password fields (indicates we're back at login)
                    try:
                        username_field = self.driver.find_element(By.NAME, "identifier")
                        print("❌ Redirected back to login page - MFA may have failed or session expired")
                        raise OktaTokenExtractionError("MFA failed - redirected back to login page")
                    except:
                        # No username field found, might be a different page
                        pass

                # Still in MFA process, wait a bit more
                time.sleep(2)

            if not mfa_completed:
                raise OktaTokenExtractionError(f"MFA timeout after {self.config.MFA_TIMEOUT}s - never reached httpbin")
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
                # Handle case where Cookie header might be a list
                if isinstance(cookie_header, list):
                    cookie_header = "; ".join(cookie_header)

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
                # Handle case where Cookie header might be a list
                if isinstance(cookie_header, list):
                    cookie_header = "; ".join(cookie_header)

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

            print(f"✅ Token saved to {self.config.TOKEN_FILE}")
            print(f"ℹ️  Use 'export {self.config.TOKEN_ENV_VAR}=$(cat {self.config.TOKEN_FILE})' to set in your shell")

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

    def check_if_already_authenticated(self) -> bool:
        """Check if we can access the protected httpbin resource without login.

        Returns:
            True if already authenticated, False if login is needed.
        """
        if not self.driver:
            return False

        try:
            self.logger.debug("Checking if already authenticated by testing httpbin access")

            # First, check current URL to see if we're on Okta dashboard
            current_url = self.driver.current_url
            self.logger.debug("Current URL before httpbin test: %s", current_url)

            # If we're on Okta dashboard, we're likely authenticated
            if "tatari.okta.com" in current_url and ("UserHome" in current_url or "app" in current_url):
                self.logger.debug("On Okta dashboard, testing httpbin access")

                # Test httpbin access
                self.driver.get(self.config.HTTPBIN_URL)
                time.sleep(3)

                httpbin_url = self.driver.current_url
                self.logger.debug("After httpbin navigation, current URL: %s", httpbin_url)

                # If we're still on httpbin (not redirected to login), we're authenticated
                if "httpbin.ops.tatari.dev" in httpbin_url and "headers" in httpbin_url:
                    try:
                        pre_element = self.driver.find_element(By.TAG_NAME, "pre")
                        content = pre_element.text
                        if content.strip().startswith("{") and "headers" in content:
                            self.logger.debug("Found JSON headers content, authentication confirmed")
                            return True
                    except:
                        pass

                # If we got redirected to Okta login, we need to authenticate
                if "okta.com" in httpbin_url and ("login" in httpbin_url or "signin" in httpbin_url):
                    self.logger.debug("Redirected to Okta login, authentication needed")
                    return False

            return False

        except Exception as e:
            self.logger.debug("Error checking authentication status: %s", e)
            return False

    def __enter__(self) -> "OktaTokenExtractor":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup resources."""
        self.cleanup()

    def _find_element_with_soup(self) -> Optional[object]:
        """Use BeautifulSoup to analyze the DOM and find form elements.

        Returns:
            The Selenium WebElement if found, None otherwise.
        """
        if not self.driver:
            return None

        try:
            # Get the page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            print("🔍 BeautifulSoup DOM Analysis:")
            print(f"   Page title: {soup.title.string if soup.title else 'No title'}")

            # Find all input elements
            inputs = soup.find_all('input')
            print(f"   Found {len(inputs)} input elements:")

            username_candidates = []
            password_candidates = []

            for i, input_elem in enumerate(inputs):
                input_type = input_elem.get('type', 'text')
                input_name = input_elem.get('name', '')
                input_id = input_elem.get('id', '')
                input_class = input_elem.get('class', [])
                input_placeholder = input_elem.get('placeholder', '')
                input_autocomplete = input_elem.get('autocomplete', '')

                print(f"     Input {i}: type='{input_type}', name='{input_name}', id='{input_id}'")
                print(f"                class='{input_class}', placeholder='{input_placeholder}'")
                print(f"                autocomplete='{input_autocomplete}'")

                # Identify username field candidates
                if (input_type in ['text', 'email'] or
                    'username' in input_autocomplete.lower() or
                    'identifier' in input_name.lower() or
                    'username' in input_name.lower() or
                    'email' in input_name.lower()):
                    username_candidates.append((input_name, input_id, input_type, input_autocomplete))

                # Identify password field candidates
                if (input_type == 'password' or
                    'password' in input_autocomplete.lower() or
                    'passcode' in input_name.lower()):
                    password_candidates.append((input_name, input_id, input_type, input_autocomplete))

            print(f"   Username candidates: {username_candidates}")
            print(f"   Password candidates: {password_candidates}")

            # Try to find the username field using the candidates
            for name, elem_id, elem_type, autocomplete in username_candidates:
                selectors_to_try = []
                if name:
                    selectors_to_try.append((By.NAME, name))
                if elem_id:
                    selectors_to_try.append((By.ID, elem_id))

                for selector_type, selector_value in selectors_to_try:
                    try:
                        element = self.driver.find_element(selector_type, selector_value)
                        print(f"✅ BeautifulSoup found username field: {selector_type} = '{selector_value}'")
                        return element
                    except Exception as e:
                        print(f"❌ BeautifulSoup selector failed: {selector_type} = '{selector_value}': {e}")
                        continue

            return None

        except Exception as e:
            print(f"❌ BeautifulSoup analysis failed: {e}")
            return None

    def _find_submit_button_with_soup(self) -> Optional[object]:
        """Use BeautifulSoup to find submit button.

        Returns:
            The Selenium WebElement if found, None otherwise.
        """
        if not self.driver:
            return None

        try:
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            print("🔍 BeautifulSoup looking for submit button...")

            # Find submit buttons and regular buttons
            submit_candidates = []

            # Look for input[type="submit"]
            submit_inputs = soup.find_all('input', {'type': 'submit'})
            for input_elem in submit_inputs:
                input_id = input_elem.get('id', '')
                input_class = input_elem.get('class', [])
                input_value = input_elem.get('value', '')
                submit_candidates.append(('input', 'submit', input_id, input_class, input_value))

            # Look for button elements
            buttons = soup.find_all('button')
            for button in buttons:
                button_type = button.get('type', 'button')
                button_id = button.get('id', '')
                button_class = button.get('class', [])
                button_text = button.get_text(strip=True)
                submit_candidates.append(('button', button_type, button_id, button_class, button_text))

            print(f"   Found {len(submit_candidates)} button candidates:")
            for i, (tag, btn_type, btn_id, btn_class, btn_text) in enumerate(submit_candidates):
                print(f"     Button {i}: {tag}[type='{btn_type}'], id='{btn_id}', class='{btn_class}', text='{btn_text}'")

            # Try to find the submit button using the candidates
            for tag, btn_type, btn_id, btn_class, btn_text in submit_candidates:
                selectors_to_try = []

                if btn_id:
                    selectors_to_try.append((By.ID, btn_id))
                if btn_type == 'submit':
                    if tag == 'input':
                        selectors_to_try.append((By.CSS_SELECTOR, "input[type='submit']"))
                    else:
                        selectors_to_try.append((By.CSS_SELECTOR, "button[type='submit']"))
                if 'button' in ' '.join(btn_class).lower() and 'primary' in ' '.join(btn_class).lower():
                    selectors_to_try.append((By.CSS_SELECTOR, ".button.button-primary"))

                for selector_type, selector_value in selectors_to_try:
                    try:
                        element = self.driver.find_element(selector_type, selector_value)
                        print(f"✅ BeautifulSoup found submit button: {selector_type} = '{selector_value}'")
                        return element
                    except Exception as e:
                        print(f"❌ Submit button selector failed: {selector_type} = '{selector_value}': {e}")
                        continue

            return None

        except Exception as e:
            print(f"❌ BeautifulSoup submit button analysis failed: {e}")
            return None

    def _find_mfa_options_with_soup(self) -> Optional[object]:
        """Use BeautifulSoup to find MFA/YubiKey options.

        Returns:
            The Selenium WebElement for YubiKey option if found, None otherwise.
        """
        if not self.driver:
            return None

        try:
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            print("🔍 BeautifulSoup looking for MFA/YubiKey options...")
            print(f"   Page title: {soup.title.string if soup.title else 'No title'}")
            print(f"   Page contains 'Security Key': {'security key' in soup.get_text().lower()}")
            print(f"   Page contains 'Biometric': {'biometric' in soup.get_text().lower()}")
            print(f"   Page contains 'Authenticator': {'authenticator' in soup.get_text().lower()}")

            # Look for elements that might contain MFA options
            mfa_candidates = []

            # Look for buttons with MFA-related text
            buttons = soup.find_all('button')
            print(f"   Found {len(buttons)} buttons on MFA page")

            for button in buttons:
                button_text = button.get_text(strip=True).lower()
                button_id = button.get('id', '')
                button_class = button.get('class', [])
                data_attrs = {k: v for k, v in button.attrs.items() if k.startswith('data-')}

                print(f"     Button: text='{button_text}', id='{button_id}', class='{button_class}', data='{data_attrs}'")

                if any(keyword in button_text for keyword in ['security key', 'biometric', 'yubikey', 'authenticator', 'select', 'webauthn']):
                    mfa_candidates.append(('button', button_id, button_class, button_text, data_attrs))

            # Look for divs with MFA-related content
            divs = soup.find_all('div')
            print(f"   Found {len(divs)} divs on MFA page")

            mfa_related_divs = []
            for div in divs:
                div_text = div.get_text(strip=True).lower()
                div_id = div.get('id', '')
                div_class = div.get('class', [])
                data_attrs = {k: v for k, v in div.attrs.items() if k.startswith('data-')}

                if any(keyword in div_text for keyword in ['security key', 'biometric', 'yubikey', 'authenticator', 'webauthn']):
                    mfa_related_divs.append(div)
                    print(f"     MFA div: text='{div_text[:100]}...', id='{div_id}', class='{div_class}', data='{data_attrs}'")

                    # Look for buttons within this div
                    inner_buttons = div.find_all('button')
                    for inner_button in inner_buttons:
                        inner_text = inner_button.get_text(strip=True).lower()
                        inner_id = inner_button.get('id', '')
                        inner_class = inner_button.get('class', [])
                        inner_data = {k: v for k, v in inner_button.attrs.items() if k.startswith('data-')}
                        print(f"       Inner button: text='{inner_text}', id='{inner_id}', class='{inner_class}'")
                        mfa_candidates.append(('div_button', inner_id, inner_class, inner_text, inner_data))

            print(f"   Found {len(mfa_related_divs)} MFA-related divs")

            print(f"   Found {len(mfa_candidates)} MFA candidates:")
            for i, (elem_type, elem_id, elem_class, elem_text, data_attrs) in enumerate(mfa_candidates):
                print(f"     MFA {i}: {elem_type}, id='{elem_id}', class='{elem_class}'")
                print(f"              text='{elem_text}', data='{data_attrs}'")

            # Try to find the YubiKey/Security Key option
            for elem_type, elem_id, elem_class, elem_text, data_attrs in mfa_candidates:
                selectors_to_try = []

                if elem_id:
                    selectors_to_try.append((By.ID, elem_id))

                # Try data-se attribute (common in Okta)
                if 'data-se' in data_attrs:
                    selectors_to_try.append((By.CSS_SELECTOR, f"[data-se='{data_attrs['data-se']}']"))
                    if elem_type in ['button', 'div_button']:
                        selectors_to_try.append((By.CSS_SELECTOR, f"[data-se='{data_attrs['data-se']}'] button"))

                # Try class-based selectors
                if elem_class and any('select' in cls.lower() for cls in elem_class):
                    class_selector = '.'.join(elem_class)
                    selectors_to_try.append((By.CSS_SELECTOR, f".{class_selector}"))

                for selector_type, selector_value in selectors_to_try:
                    try:
                        element = self.driver.find_element(selector_type, selector_value)
                        print(f"✅ BeautifulSoup found MFA option: {selector_type} = '{selector_value}'")
                        return element
                    except Exception as e:
                        print(f"❌ MFA selector failed: {selector_type} = '{selector_value}': {e}")
                        continue

            return None

        except Exception as e:
            print(f"❌ BeautifulSoup MFA analysis failed: {e}")
            return None
