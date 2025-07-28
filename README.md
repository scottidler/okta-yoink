# Okta Token Automation

Automated extraction of Okta `_oauth2_proxy` tokens using Selenium WebDriver for CLI authentication.

## Overview

This tool automates the process of extracting Okta authentication tokens from your company's internal services. It uses Selenium to create a separate browser session, authenticate with Okta (including MFA), and extract the `_oauth2_proxy` token for use with CLI tools.

**⚠️ Important Limitations:**
- Requires **separate browser session** from your main browser
- You must perform **MFA authentication twice daily** (once for main browser, once for automation)
- Browser sessions are isolated by design - there's no way to share authentication between processes

## Features

- ✅ Automated Okta login and MFA handling
- ✅ Token extraction from any internal service
- ✅ Secure token storage with restrictive file permissions
- ✅ Environment variable integration
- ✅ Comprehensive error handling and logging
- ✅ Configurable timeouts and browser options
- ✅ Context manager support for proper cleanup
- ✅ Type hints and full test coverage

## Installation

### Prerequisites

- Python 3.8 or higher
- Chrome/Chromium browser
- [uv](https://github.com/astral-sh/uv) package manager

### Install with uv

```bash
# Clone the repository
git clone <repository-url>
cd okta-token-automation

# Install with uv (recommended)
uv pip install -e .

# Or install with development dependencies
uv pip install -e ".[dev]"
```

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install chromium-browser

# macOS with Homebrew
brew install chromium

# The tool will automatically download chromedriver using webdriver-manager
```

## Configuration

### Environment Variables

Copy `env.example` to `.env` and customize:

```bash
cp env.example .env
```

Key configuration options:

| Variable | Default | Description |
|----------|---------|-------------|
| `OKTA_LOGIN_URL` | `https://tatari.okta.com` | Your Okta login URL |
| `HTTPBIN_URL` | `https://httpbin.ops.tatari.dev/headers` | Internal service for token extraction |
| `HEADLESS` | `false` | Run browser in headless mode |
| `BROWSER_TIMEOUT` | `30` | Timeout for browser operations (seconds) |
| `MFA_TIMEOUT` | `120` | Timeout for MFA completion (seconds) |
| `TOKEN_FILE` | `~/.okta-token` | File path for token storage |
| `TOKEN_ENV_VAR` | `OKTA_COOKIE` | Environment variable name for token |
| `OKTA_USERNAME` | _(empty)_ | Pre-configure username (optional) |

## Usage

### Basic Usage

```bash
# Run the token extraction
okta-token

# Or run directly with Python
python -m okta_token_automation.main
```

### Workflow

1. **Browser Launch**: Opens Chrome/Chromium browser
2. **Okta Login**: Navigates to your Okta login page
3. **Credentials**: Prompts for username (if not configured) and password
4. **MFA**: Waits for you to complete MFA (YubiKey touch/PIN)
5. **Token Extraction**: Navigates to internal service and extracts token
6. **Storage**: Saves token to file and sets environment variable
7. **Cleanup**: Closes browser and reports success

### Using the Token

After successful extraction:

```bash
# The token is automatically available in your environment
export OKTA_COOKIE=$(cat ~/.okta-token)

# Use with your CLI tools
cargo run -- -o Engineering -m jan
```

### Shell Integration

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# Function to get Okta token via automation
get_okta_token() {
    echo "🔄 Running Okta token automation..."
    okta-token
    
    if [ $? -eq 0 ]; then
        export OKTA_COOKIE=$(cat ~/.okta-token)
        echo "✅ OKTA_COOKIE exported"
    else
        echo "❌ Token extraction failed"
        return 1
    fi
}

# Alias for convenience
alias get-token="get_okta_token"
```

## Development

### Setup Development Environment

```bash
# Install with development dependencies
uv pip install -e ".[dev]"

# Or install individual dev tools
uv pip install pytest pytest-mock pytest-cov black isort mypy
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=okta_token_automation --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Run all quality checks
black --check src/ tests/
isort --check-only src/ tests/
mypy src/
pytest
```

### Project Structure

```
okta-token-automation/
├── src/okta_token_automation/
│   ├── __init__.py          # Package initialization
│   ├── config.py            # Configuration management
│   ├── token_extractor.py   # Main extraction logic
│   └── main.py              # CLI entry point
├── tests/
│   ├── __init__.py
│   ├── test_config.py       # Config tests
│   ├── test_token_extractor.py  # Extractor tests
│   ├── test_main.py         # Main function tests
│   └── test_integration.py  # Integration tests
├── pyproject.toml           # Project configuration
├── env.example              # Environment configuration template
├── README.md                # This file
└── okta-token-automation.md # Design documentation
```

## API Reference

### OktaTokenExtractor

Main class for token extraction:

```python
from okta_token_automation import OktaTokenExtractor, Config

# Basic usage
extractor = OktaTokenExtractor()
token = extractor.run()

# With custom config
config = Config()
config.HEADLESS = True
extractor = OktaTokenExtractor(config)

# As context manager (recommended)
with OktaTokenExtractor() as extractor:
    token = extractor.run()
```

### Config

Configuration management:

```python
from okta_token_automation import Config

config = Config()
config.validate()  # Raises ValueError if invalid
print(config)      # Safe representation (no sensitive data)
```

## Troubleshooting

### Common Issues

**ChromeDriver Issues:**
```bash
# Update webdriver-manager
uv pip install --upgrade webdriver-manager

# Use custom chromedriver path
export CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
```

**Timeout Issues:**
```bash
# Increase timeouts in .env
BROWSER_TIMEOUT=60
MFA_TIMEOUT=180
```

**Headless Mode Issues:**
```bash
# Disable headless mode for debugging
HEADLESS=false
```

**Permission Issues:**
```bash
# Check token file permissions
ls -la ~/.okta-token
# Should show: -rw------- (600)
```

### Debug Mode

Run with verbose logging:

```bash
# Set environment variable for debug output
export SELENIUM_LOG_LEVEL=DEBUG
okta-token
```

### Getting Help

1. Check the [design documentation](okta-token-automation.md) for architectural details
2. Run tests to verify your environment: `pytest -v`
3. Check browser compatibility: ensure Chrome/Chromium is installed and accessible
4. Verify network access to your Okta and internal services

## Security Considerations

- Token files are created with `600` permissions (owner read/write only)
- Passwords are never stored, only prompted interactively
- Browser sessions are isolated and cleaned up after use
- Environment variables are only set in the current shell session

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the full test suite and quality checks
5. Submit a pull request

Ensure all tests pass and code follows the project style:

```bash
black --check src/ tests/
isort --check-only src/ tests/
mypy src/
pytest --cov=okta_token_automation
``` 