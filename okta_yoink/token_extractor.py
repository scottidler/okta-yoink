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

            # Wait for the OAuth redirect to complete and login form to be ready
            print("⏳ Waiting for Okta login page to load...")
            self.logger.debug("Waiting for Okta domain in URL...")

            # Wait until we're on an Okta domain (shorter timeout)
            WebDriverWait(self.driver, 15).until(
                lambda driver: "okta.com" in driver.current_url.lower()
            )
            self.logger.debug("Redirected to Okta domain: %s", self.driver.current_url)

            # Wait for login form to be present (this is the real indicator we're ready)
            print("⏳ Waiting for login form to appear...")
            WebDriverWait(self.driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.NAME, "identifier")),
                    EC.presence_of_element_located((By.ID, "okta-signin-username")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
                )
            )

            print("✅ Okta login form ready, filling credentials...")

            # Wait for login form - try multiple possible selectors
            username_field = None
            password_field = None

                                                # Try to find username field - hardcoded known working selector first
            print("🔍 Looking for username field...")
            username_selectors = [
                (By.NAME, "identifier"),  # ✅ HARDCODED - Name: identifier, Type: text
                (By.ID, "input28"),  # ✅ HARDCODED - Current ID (may change)
                (By.ID, "okta-signin-username"),  # Fallback for other Okta instances
                (By.CSS_SELECTOR, "input[type='text'][name='identifier']"),  # Most specific
                (By.CSS_SELECTOR, "input[type='text']")  # Generic fallback
            ]

            for selector in username_selectors:
                try:
                    self.logger.debug("Trying to find username field with selector: %s", selector)
                    username_field = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(selector)
                    )
                    # Log the actual element details for hardcoding
                    element_id = username_field.get_attribute('id')
                    element_name = username_field.get_attribute('name')
                    element_class = username_field.get_attribute('class')
                    element_type = username_field.get_attribute('type')

                    print(f"🔍 USERNAME FIELD FOUND:")
                    print(f"   Selector used: {selector}")
                    print(f"   ID: {element_id}")
                    print(f"   Name: {element_name}")
                    print(f"   Class: {element_class}")
                    print(f"   Type: {element_type}")

                    self.logger.info("USERNAME FIELD - Selector: %s, ID: %s, Name: %s, Class: %s, Type: %s",
                                   selector, element_id, element_name, element_class, element_type)
                    break
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

            # Try to find password field - hardcoded known working selector first
            print("🔍 Looking for password field...")
            password_selectors = [
                (By.NAME, "credentials.passcode"),  # ✅ HARDCODED - Name: credentials.passcode, Type: password
                (By.ID, "input36"),  # ✅ HARDCODED - Current ID (may change)
                (By.CSS_SELECTOR, "input.password-with-toggle"),  # ✅ HARDCODED - Class: password-with-toggle
                (By.ID, "okta-signin-password"),  # Fallback for other Okta instances
                (By.CSS_SELECTOR, "input[type='password']")  # Generic fallback
            ]

            for selector in password_selectors:
                try:
                    password_field = self.driver.find_element(*selector)
                    # Log the actual element details for hardcoding
                    element_id = password_field.get_attribute('id')
                    element_name = password_field.get_attribute('name')
                    element_class = password_field.get_attribute('class')
                    element_type = password_field.get_attribute('type')

                    print(f"🔍 PASSWORD FIELD FOUND:")
                    print(f"   Selector used: {selector}")
                    print(f"   ID: {element_id}")
                    print(f"   Name: {element_name}")
                    print(f"   Class: {element_class}")
                    print(f"   Type: {element_type}")

                    self.logger.info("PASSWORD FIELD - Selector: %s, ID: %s, Name: %s, Class: %s, Type: %s",
                                   selector, element_id, element_name, element_class, element_type)
                    break
                except Exception as e:
                    self.logger.debug("Failed to find password field with selector %s: %s", selector, e)
                    continue

            if not password_field:
                raise OktaTokenExtractionError("Could not find password field with any known selector")

            # Get credentials from user or environment
            if not self.config.OKTA_USERNAME:
                username = input("Enter your Okta username: ")
            else:
                username = self.config.OKTA_USERNAME
                print(f"✅ Using username from config: {username}")

            if not self.config.OKTA_PASSWORD:
                password = input("Enter your Okta password: ")
            else:
                password = self.config.OKTA_PASSWORD
                print("✅ Using password from config")

            # Fill credentials with human-like interaction
            print(f"🔄 Filling username field with: {username}")
            username_field.click()  # Focus the field
            username_field.clear()
            username_field.send_keys(username)
            # Trigger change event
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", username_field)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", username_field)
            print(f"✅ Username field filled. Current value: {username_field.get_attribute('value')}")

            print("🔄 Filling password field...")
            password_field.click()  # Focus the field
            password_field.clear()
            password_field.send_keys(password)
            # Trigger change event
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", password_field)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", password_field)
            print(f"✅ Password field filled. Length: {len(password_field.get_attribute('value'))}")

            # Small delay to ensure fields are properly filled
            import time
            time.sleep(0.5)

            # Verify fields are still filled after delay
            print(f"🔍 Username field after delay: {username_field.get_attribute('value')}")
            print(f"🔍 Password field after delay: Length {len(password_field.get_attribute('value'))}")

            # Find and click submit button
            print("🔄 Looking for submit button...")
            submit_button = None
            submit_selectors = [
                (By.CSS_SELECTOR, "input.button.button-primary[type='submit'][value='Sign in']"),  # ✅ HARDCODED - Most specific
                (By.CSS_SELECTOR, "input.button.button-primary[type='submit']"),  # ✅ HARDCODED - Class + type
                (By.CSS_SELECTOR, "input[type='submit'][value='Sign in']"),  # ✅ HARDCODED - Type + value
                (By.ID, "okta-signin-submit"),  # Standard Okta fallback
                (By.CSS_SELECTOR, "input[type='submit']")  # Generic fallback
            ]

            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(*selector)
                    # Log the actual element details for hardcoding
                    element_id = submit_button.get_attribute('id')
                    element_name = submit_button.get_attribute('name')
                    element_class = submit_button.get_attribute('class')
                    element_type = submit_button.get_attribute('type')
                    element_value = submit_button.get_attribute('value')

                    print(f"🔍 SUBMIT BUTTON FOUND:")
                    print(f"   Selector used: {selector}")
                    print(f"   ID: {element_id}")
                    print(f"   Name: {element_name}")
                    print(f"   Class: {element_class}")
                    print(f"   Type: {element_type}")
                    print(f"   Value: {element_value}")

                    self.logger.info("SUBMIT BUTTON - Selector: %s, ID: %s, Name: %s, Class: %s, Type: %s, Value: %s",
                                   selector, element_id, element_name, element_class, element_type, element_value)
                    break
                except Exception as e:
                    self.logger.debug("Failed to find submit button with selector %s: %s", selector, e)
                    continue

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
            # First, check if we're on an MFA selection page
            time.sleep(0.5)  # Reduced wait for page to load
            self.logger.debug("After 0.5s wait, current URL: %s", self.driver.current_url)

            # HARDCODED YUBIKEY BUTTON SELECTOR - NO MORE SEARCHING
            # Based on screenshot: "Security Key or Biometric Authenticator" -> "Select" button
            yubikey_button = None
            try:
                # Single hardcoded selector - from previous logs we know this works
                yubikey_button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-se='webauthn'] .select-factor"))
                )
                print("✅ Found YubiKey button using hardcoded selector")
            except Exception as e:
                self.logger.error("HARDCODED YubiKey selector failed: %s", e)
                # Emergency fallback - but this should never happen
                try:
                    yubikey_button = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[text()='Select' and ancestor::*[contains(text(), 'Security Key')]]"))
                    )
                    print("⚠️ Used emergency fallback for YubiKey button")
                except:
                    pass

            if yubikey_button:
                print("🔑 Automatically selecting YubiKey/Security Key option...")
                yubikey_button.click()

                # Ensure the page has focus for WebAuthn dialog, not the URL bar
                self.driver.execute_script("window.focus();")
                self.driver.execute_script("document.body.focus();")

                time.sleep(1)  # Give WebAuthn dialog time to appear and gain focus

            print("👆 Please complete MFA (YubiKey touch/PIN) in the browser window")

            # Wait for MFA completion by checking for redirect away from OAuth authorize URL
            self.logger.debug("Waiting for MFA completion, timeout: %s seconds", self.config.MFA_TIMEOUT)
            current_url = self.driver.current_url
            self.logger.debug("Current URL before MFA: %s", current_url)

            WebDriverWait(self.driver, self.config.MFA_TIMEOUT).until(
                lambda driver: (
                    driver.current_url != current_url  # URL changed from the OAuth authorize page
                    or "callback" in driver.current_url.lower()  # Or we got redirected to callback
                    or "headers" in driver.current_url.lower()  # Or we reached the final destination
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
                cookie_str = str(headers["Cookie"]) if isinstance(headers["Cookie"], list) else headers["Cookie"]
                self.logger.debug("Cookie header found: %s", cookie_str[:200] + "..." if len(cookie_str) > 200 else cookie_str)

            # Method 1: Look for _oauth2_proxy in Cookie header (most common)
            cookie_header = headers.get("Cookie", "")
            if cookie_header:
                # Handle case where cookie_header might be a list instead of string
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
            if isinstance(auth_header, list):
                auth_header = " ".join(auth_header)
            if "_oauth2_proxy" in auth_header.lower():
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
                # Handle case where cookie_header might be a list instead of string
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
            if isinstance(auth_header, list):
                auth_header = " ".join(auth_header)
            if "_oauth2_proxy" in auth_header.lower():
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
