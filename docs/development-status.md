# Okta-Yoink Development Status

## Project Overview

**okta-yoink** is a Selenium-based automation tool that extracts Okta `_oauth2_proxy` tokens for CLI authentication. The tool automates the browser-based OAuth2 flow to obtain tokens that can be used for authenticated API requests to internal services.

### Core Concept
1. Navigate to protected internal service (`https://httpbin.ops.tatari.dev/headers`)
2. Get redirected to Okta for authentication
3. Automate login + MFA process
4. Get redirected back to internal service with OAuth2 proxy token
5. Extract `_oauth2_proxy` token from JSON response
6. Save token to `~/.okta-cookie` file for CLI usage

## Current Status: ✅ MOSTLY WORKING

### What's Working ✅
- **Correct URL Flow**: Tool now goes directly to `https://httpbin.ops.tatari.dev/headers` instead of hardcoded Okta URLs
- **OAuth2 Proxy Integration**: Properly handles redirect flow through oauth2-proxy
- **Token Extraction**: Successfully reaches httpbin page and can see JSON with `_oauth2_proxy` cookie
- **Configuration**: Environment-based config with proper logging to `~/.local/share/okta-yoink/okta-yoink.log`
- **Package Structure**: Proper Python package with console script `okta-yoink`
- **Test Coverage**: 56 tests with 71% code coverage (45 passing, 11 failing due to recent changes)

### Current Issues ❌
1. **Username Auto-fill**: Not populating username field automatically despite `OKTA_USERNAME=scott.idler@tatari.tv` in `.env`
2. **YubiKey Auto-selection**: Not automatically selecting "Security Key or Biometric Authenticator" option
3. **Chrome Session Conflicts**: Occasional "user data directory already in use" errors
4. **Token Extraction Incomplete**: Tool reaches httpbin page but may crash before saving token to file

## Technical Architecture

### Key Files
- `src/okta_token_automation/main.py` - Entry point and logging setup
- `src/okta_token_automation/token_extractor.py` - Core Selenium automation (566 lines)
- `src/okta_token_automation/config.py` - Environment-based configuration
- `.env` - Local configuration (not in repo)
- `pyproject.toml` - Package definition with console script

### Dependencies
- **selenium>=4.34.2** - Browser automation
- **webdriver-manager>=4.0.2** - Chrome driver management
- **requests>=2.32.4** - HTTP requests for token extraction
- **python-dotenv>=1.1.1** - Environment variable loading

### Configuration
```bash
# Current .env setup
HTTPBIN_URL=https://httpbin.ops.tatari.dev/headers
HEADLESS=false
BROWSER_TIMEOUT=60
IMPLICIT_WAIT=10
MFA_TIMEOUT=120
TOKEN_FILE=~/.okta-cookie
TOKEN_ENV_VAR=OKTA_COOKIE
OKTA_USERNAME=scott.idler@tatari.tv
LOG_LEVEL=INFO
LOG_FILE=~/.local/share/okta-yoink/okta-yoink.log
```

## What We've Tried

### ✅ Successful Changes
1. **Removed Hardcoded Okta URLs**: Eliminated `OKTA_LOGIN_URL` and now go directly to httpbin
2. **Improved Token Extraction**: Added dual approach (HTTP requests + page scraping)
3. **Enhanced Logging**: Comprehensive DEBUG logging throughout the flow
4. **Updated Dependencies**: All packages upgraded to latest versions
5. **Fixed Naming Consistency**: `~/.okta-cookie` file matches `OKTA_COOKIE` env var
6. **Added Username Selectors**: Multiple fallback selectors for username field detection
7. **Added YubiKey Selectors**: Various selectors for MFA option detection
8. **Chrome Conflict Fix**: Added unique user data directory per session

### ❌ Attempted But Still Broken
1. **Authentication Skip Logic**: Tried to detect if already authenticated but caused test failures
2. **Mock Test Updates**: Many integration tests still failing due to recent changes
3. **Selector Specificity**: Current selectors still not finding username/MFA elements

## Current Selector Strategy

### Username Field Selectors (in order of preference)
```python
(By.ID, "okta-signin-username"),
(By.NAME, "username"),
(By.NAME, "identifier"),
(By.CSS_SELECTOR, "input[type='text']"),
(By.CSS_SELECTOR, "input[type='email']"),
(By.CSS_SELECTOR, "input[autocomplete='username']"),
(By.CSS_SELECTOR, "input[autocomplete='email']"),
(By.XPATH, "//input[contains(@placeholder, 'Username') or contains(@placeholder, 'username')]"),
(By.XPATH, "//label[contains(text(), 'Username')]/following-sibling::input"),
(By.XPATH, "//label[contains(text(), 'Username')]/..//input"),
(By.XPATH, "(//input[@type='text'])[1]"),  # First text input
(By.XPATH, "(//input[not(@type) or @type='text'])[1]")  # Very generic
```

### YubiKey/MFA Selectors (in order of preference)
```python
(By.CSS_SELECTOR, "[data-se='webauthn'] button"),
(By.CSS_SELECTOR, "[data-se='webauthn'] .select-factor"),
(By.XPATH, "//div[@data-se='webauthn']//button"),
(By.XPATH, "//button[contains(text(), 'Select') and ancestor::*[contains(text(), 'Security Key')]]"),
(By.XPATH, "//button[contains(text(), 'Select') and ancestor::*[contains(text(), 'Biometric')]]"),
(By.XPATH, "//div[contains(text(), 'Security Key or Biometric')]//following::button[contains(text(), 'Select')]"),
(By.XPATH, "//div[contains(text(), 'Security Key')]//following::button[contains(text(), 'Select')]"),
(By.XPATH, "//button[contains(text(), 'Security Key') or contains(text(), 'Biometric')]"),
(By.CSS_SELECTOR, "button[data-se='webauthn']"),
(By.XPATH, "//span[contains(text(), 'Security Key')]//ancestor::div//button")
```

## Next Steps (Priority Order)

### 🔥 Immediate (Critical)
1. **Debug Selector Issues**:
   - Run with `LOG_LEVEL=DEBUG` to see which selectors are being tried
   - Use Chrome DevTools to inspect actual HTML structure of login/MFA pages
   - Update selectors based on real page structure

2. **Fix Chrome Session Management**:
   - Ensure unique user data directories are working
   - Add proper cleanup of temp directories
   - Handle browser crashes gracefully

3. **Complete Token Extraction Flow**:
   - Ensure tool doesn't crash after reaching httpbin page
   - Verify token is properly extracted from JSON and saved to `~/.okta-cookie`
   - Test that saved token works for API requests

### 🎯 Short Term (Important)
4. **Fix Failing Tests**:
   - Update integration tests to handle new flow (no hardcoded Okta URL)
   - Fix mock setups for MFA and login tests
   - Ensure all config tests pass with new structure

5. **Improve Error Handling**:
   - Better error messages for selector failures
   - Graceful handling of MFA timeouts
   - Recovery from browser crashes

6. **Add Missing Test Coverage**:
   - Test new logging functionality
   - Test HTTP request token extraction method
   - Test new console script entry point

### 🚀 Future Enhancements (Nice to Have)
7. **Multiple Okta Instance Support**:
   - Make tool work with different Okta domains
   - Configurable MFA methods beyond YubiKey

8. **Performance Improvements**:
   - Faster startup time
   - Better caching of browser sessions
   - Reduced dependency on sleep() calls

9. **User Experience**:
   - Progress indicators during long operations
   - Better error messages for common issues
   - Optional GUI mode for debugging

## Testing Strategy

### Current Test Status
- **Total Tests**: 56 (45 passing, 11 failing)
- **Code Coverage**: 71%
- **Test Types**: Unit tests, Integration tests, Config tests

### Key Test Areas
- Configuration loading and validation
- Selenium automation workflows
- Token extraction from different header formats
- File operations and permissions
- Error handling scenarios

### Test Failures to Fix
Most failures are due to:
- Removed `OKTA_LOGIN_URL` config parameter
- Changed mock expectations for new flow
- MFA mock setup issues (`'bool' object has no attribute 'click'`)

## Development Environment

### Setup Commands
```bash
# Install with uv (recommended)
uv sync --extra dev

# Run tool
uv run okta-yoink

# Run with debug logging
LOG_LEVEL=DEBUG uv run okta-yoink

# Run tests
uv run pytest

# Check logs
tail -f ~/.local/share/okta-yoink/okta-yoink.log
```

### Key Files to Monitor
- `~/.okta-cookie` - Token output file
- `~/.local/share/okta-yoink/okta-yoink.log` - Debug logs
- `.env` - Local configuration

## Known Working Flow

1. ✅ Tool starts and loads config
2. ✅ Chrome browser opens (with unique user data dir)
3. ✅ Navigates to `https://httpbin.ops.tatari.dev/headers`
4. ✅ Gets redirected to Okta login page
5. ❌ **BROKEN**: Username field not auto-filled (manual entry required)
6. ❌ **BROKEN**: YubiKey option not auto-selected (manual selection required)
7. ✅ After manual MFA completion, redirects back to httpbin
8. ✅ JSON response visible with `_oauth2_proxy` cookie
9. ❌ **UNKNOWN**: Token extraction and file saving (needs verification)

## Success Criteria

The tool will be considered fully working when:
1. Username auto-fills from `.env` configuration
2. YubiKey MFA option auto-selects
3. Token successfully extracts and saves to `~/.okta-cookie`
4. File has correct permissions (600)
5. Token works for authenticated API requests
6. All tests pass
7. No manual intervention required during flow

---

*Last Updated: 2025-07-27*
*Status: In Active Development*
*Next Session Focus: Debug selector issues and complete token extraction flow*
