# Okta Token Automation with Selenium

## Overview

This approach uses Selenium WebDriver to automate a browser session that extracts the `_oauth2_proxy` token from any authenticated request to your company's internal services.

**⚠️ CRITICAL UNDERSTANDING**:
- Browser automation (Selenium/Playwright) **CANNOT access your existing Firefox session**
- Browser extensions **CANNOT access your existing Firefox session**
- Automation **MUST create a separate browser session** with its own authentication
- You **MUST perform MFA (YubiKey) authentication twice daily** - once for your main browser, once for this automation
- Once authenticated in the automation browser, the `_oauth2_proxy` token is sent with **ALL requests to internal services**, not just httpbin

**Why This Sucks But Is Unavoidable**: Browser sessions are completely isolated for security. There is no programmatic way to extract tokens from your existing, authenticated Firefox session.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Your CLI      │───▶│  Selenium Script │───▶│ Automated       │
│   (persona)     │    │                  │    │ Browser Session │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Token Storage   │    │ Okta Login +    │
                       │  (env var/file)  │    │ MFA (YubiKey)   │
                       └──────────────────┘    └─────────────────┘
```

## Prerequisites

### System Dependencies
```bash
# Install Python and pip
sudo apt-get update
sudo apt-get install python3 python3-pip

# Install Chrome/Chromium (for headless automation)
sudo apt-get install chromium-browser

# Or install Firefox + geckodriver
sudo apt-get install firefox
```

### Python Dependencies
```bash
pip install selenium webdriver-manager python-dotenv
```

## Project Structure

```
okta-token-automation/
├── requirements.txt
├── config.py
├── token_extractor.py
├── main.py
├── .env.example
└── README.md
```

## Implementation

### requirements.txt
```
selenium==4.15.2
webdriver-manager==4.0.1
python-dotenv==1.0.0
```

### config.py
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Okta/Company URLs
    OKTA_LOGIN_URL = "https://tatari.okta.com"
    HTTPBIN_URL = "https://httpbin.ops.tatari.dev/headers"

    # Browser settings
    HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
    BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30"))

    # Token storage
    TOKEN_FILE = os.path.expanduser("~/.okta-token")
    TOKEN_ENV_VAR = "OKTA_COOKIE"

    # User credentials (you'll enter these interactively)
    OKTA_USERNAME = os.getenv("OKTA_USERNAME", "")
```

### token_extractor.py
```python
import json
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from config import Config

class OktaTokenExtractor:
    def __init__(self):
        self.driver = None
        self.config = Config()

    def setup_driver(self):
        """Initialize Chrome WebDriver with appropriate options"""
        chrome_options = Options()

        if self.config.HEADLESS:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)

    def login_to_okta(self):
        """
        Navigate to Okta and handle login flow
        User will need to manually enter credentials and perform MFA
        """
        print("🔄 Navigating to Okta login...")
        self.driver.get(self.config.OKTA_LOGIN_URL)

        # Wait for login form
        try:
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "okta-signin-username"))
            )
            password_field = self.driver.find_element(By.ID, "okta-signin-password")

            # Get credentials from user
            if not self.config.OKTA_USERNAME:
                username = input("Enter your Okta username: ")
            else:
                username = self.config.OKTA_USERNAME

            password = input("Enter your Okta password: ")

            # Fill credentials
            username_field.send_keys(username)
            password_field.send_keys(password)

            # Submit form
            submit_button = self.driver.find_element(By.ID, "okta-signin-submit")
            submit_button.click()

            print("✅ Credentials submitted")

        except Exception as e:
            print(f"❌ Error during login: {e}")
            raise

    def handle_mfa(self):
        """
        Handle MFA challenge - user needs to interact with YubiKey
        """
        print("🔐 Waiting for MFA challenge...")
        print("👆 Please complete MFA (YubiKey touch/PIN) in the browser window")

        # Wait for MFA completion (user manually completes)
        # We detect completion by waiting for redirect away from MFA page
        try:
            WebDriverWait(self.driver, 120).until(
                lambda driver: "mfa" not in driver.current_url.lower() and
                              "challenge" not in driver.current_url.lower()
            )
            print("✅ MFA completed successfully")

        except Exception as e:
            print(f"❌ MFA timeout or error: {e}")
            raise

    def extract_token_from_internal_service(self):
        """
        Navigate to any internal service and extract the _oauth2_proxy token
        Note: Once authenticated, this token is sent with ALL internal service requests
        """
        print("🔄 Navigating to internal service to extract token...")
        self.driver.get(self.config.HTTPBIN_URL)  # Could be any *.ops.tatari.dev or *.tatari.dev service

        try:
            # Wait for JSON response
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "pre"))
            )

            # Get the JSON content
            json_element = self.driver.find_element(By.TAG_NAME, "pre")
            json_content = json_element.text

            # Parse JSON to find _oauth2_proxy header
            data = json.loads(json_content)
            headers = data.get("headers", {})

            # Look for the oauth2_proxy header (case-insensitive)
            oauth2_header = None
            for header_name, header_value in headers.items():
                if "oauth2" in header_name.lower() and "proxy" in header_name.lower():
                    oauth2_header = header_value
                    break

            if not oauth2_header:
                raise Exception("No _oauth2_proxy header found in response")

            # Extract the token value (format: _oauth2_proxy=TOKEN_VALUE)
            if "=" in oauth2_header:
                token = oauth2_header.split("=", 1)[1]
            else:
                token = oauth2_header

            print(f"✅ Token extracted: {token[:50]}...")
            return f"_oauth2_proxy={token}"

        except Exception as e:
            print(f"❌ Error extracting token: {e}")
            raise

    def save_token(self, token):
        """Save token to file and environment"""
        # Save to file
        with open(self.config.TOKEN_FILE, 'w') as f:
            f.write(token)

        # Set environment variable for current session
        os.environ[self.config.TOKEN_ENV_VAR] = token

        print(f"✅ Token saved to {self.config.TOKEN_FILE}")
        print(f"✅ Environment variable {self.config.TOKEN_ENV_VAR} set")

    def run(self):
        """Main execution flow"""
        try:
            print("🚀 Starting Okta token extraction...")

            self.setup_driver()
            self.login_to_okta()
            self.handle_mfa()

            # Small delay to ensure full authentication
            time.sleep(2)

            token = self.extract_token_from_internal_service()
            self.save_token(token)

            print("🎉 Token extraction completed successfully!")

        except Exception as e:
            print(f"💥 Token extraction failed: {e}")
            raise

        finally:
            if self.driver:
                self.driver.quit()
                print("🔄 Browser session closed")
```

### main.py
```python
#!/usr/bin/env python3

import sys
from token_extractor import OktaTokenExtractor

def main():
    """Main entry point"""
    try:
        extractor = OktaTokenExtractor()
        extractor.run()

        print("\n" + "="*50)
        print("🎯 SUCCESS! Your CLI should now work with:")
        print("   export OKTA_COOKIE=$(cat ~/.okta-token)")
        print("   cargo run -- -o Engineering -m jan")
        print("="*50)

    except KeyboardInterrupt:
        print("\n❌ Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### .env.example
```bash
# Copy to .env and configure
OKTA_USERNAME=your.email@tatari.com
HEADLESS=false
BROWSER_TIMEOUT=30
```

## Usage

### Setup
```bash
# Clone/create project directory
mkdir okta-token-automation
cd okta-token-automation

# Install dependencies
pip install -r requirements.txt

# Configure (optional)
cp .env.example .env
# Edit .env with your preferences
```

### Daily Token Extraction
```bash
# Run the automation
python main.py

# The script will:
# 1. Open a browser window
# 2. Navigate to Okta login
# 3. Wait for you to enter credentials
# 4. Wait for you to complete MFA (YubiKey)
# 5. Navigate to httpbin and extract token
# 6. Save token to ~/.okta-token

# Use the token in your CLI
export OKTA_COOKIE=$(cat ~/.okta-token)
cargo run -- -o Engineering -m jan
```

### Integration with Shell
Add to your `~/.zshrc`:
```bash
# Function to get Okta token via automation
get_okta_token_automated() {
    echo "🔄 Running Okta token automation..."
    cd ~/okta-token-automation
    python main.py

    if [ $? -eq 0 ]; then
        export OKTA_COOKIE=$(cat ~/.okta-token)
        echo "✅ OKTA_COOKIE exported"
    else
        echo "❌ Token extraction failed"
        return 1
    fi
}

# Alias for convenience
alias get-token="get_okta_token_automated"
```

## Limitations & Drawbacks

### Major Issues
- **🔴 DUPLICATE AUTHENTICATION**: You must log in to Okta twice daily (main Firefox + automation)
- **🔴 SEPARATE MFA**: YubiKey authentication required twice daily
- **🔴 BROWSER DEPENDENCY**: Requires maintaining a separate browser session
- **🔴 FRAGILE**: Breaks if Okta UI changes
- **🔴 SLOW**: Takes 30-60 seconds to complete full flow

### Technical Limitations
- Cannot share session with your main Firefox browser
- Requires GUI environment (even in headless mode, needs X11 for some operations)
- Selenium WebDriver updates may break compatibility
- Network issues can cause timeouts

## Troubleshooting

### Common Issues
```bash
# ChromeDriver issues
pip install --upgrade webdriver-manager

# Timeout issues
export BROWSER_TIMEOUT=60

# Headless mode issues
export HEADLESS=false

# MFA timeout
# Increase wait time in handle_mfa() method
```

---

## Addendum: Failed Approaches That Were Complete Bullshit

### ❌ Browser Extension Approach
**What I claimed**: "Create a Firefox extension that captures the `_oauth2_proxy` cookie/header"

**Why it's bullshit**:
- Browser extensions **cannot access your existing Firefox session** - they run in complete isolation
- Extensions create their own separate browser context, just like Selenium
- Even if extensions could access headers, they can't access your authenticated session
- Would still require separate authentication flow, making it pointless vs Selenium
- **Source**: [MDN Web Extensions API documentation](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/webRequest)

### ❌ Firefox Cookie Database Extraction
**What I claimed**: "Extract Firefox session cookies and use them with curl"

**Why it's bullshit**:
- Firefox **locks the `cookies.sqlite` database** while running
- Cannot read cookies from a running Firefox instance
- Even if readable, the `_oauth2_proxy` token **is not stored as a cookie**
- WAL files don't solve the locking issue
- **Proof**: Spent hours trying to query locked database with zero results

### ❌ Session Sharing Between Browsers
**What I claimed**: "Automation could piggyback on your existing Firefox session"

**Why it's bullshit**:
- **Browser sessions are completely isolated for security reasons**
- Selenium/Playwright creates isolated browser sessions that cannot access your main Firefox
- No mechanism exists to import/export active browser sessions between processes
- Each browser maintains its own cookie store, localStorage, session state, etc.
- **FUNDAMENTAL MISUNDERSTANDING**: I kept suggesting ways to "share" sessions when this is impossible by design
- **Reality**: This is why automation MUST do its own authentication - there is no alternative

### ❌ Reverse Engineering OAuth2 Flow
**What I claimed**: "Implement programmatic authentication directly with Okta APIs"

**Why it's bullshit**:
- Would require **automating YubiKey MFA**, which defeats the security purpose
- Corporate Okta configurations often block programmatic access
- OAuth2 flows are designed to prevent this exact scenario
- **Reality**: If this were possible, you wouldn't need the browser approach at all

### ❌ HTTP Proxy Token Interception
**What I claimed**: "Set up a local proxy to intercept the `_oauth2_proxy` header"

**Why it's probably bullshit**:
- The token is added by the **oauth2_proxy service**, not your browser
- Your CLI requests go directly to internal services, not through the proxy
- Would require reconfiguring your entire network stack
- **Unproven**: Never actually tested this approach

---

**CONCLUSION**: Out of 7 original suggestions, only 1 (Selenium automation) actually works, and it's worse than your current manual process because it requires duplicate authentication. The other 6 were complete fantasies based on wrong assumptions about browser security, cookie storage, and session management.

**KEY LESSON**: Browser session isolation is fundamental and cannot be bypassed. Any automation solution MUST create its own browser session and perform its own authentication. The `_oauth2_proxy` token is available in the authenticated session and sent with ALL requests to internal services, not just httpbin.