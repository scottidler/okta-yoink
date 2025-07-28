# Okta Token Automation

Automated extraction of Okta `_oauth2_proxy` tokens using Selenium WebDriver for CLI authentication with intelligent caching and transparent shell integration.

## Overview

This tool automates the process of extracting Okta authentication tokens from your company's internal services. It provides a smart shell function that handles token caching, automatic refresh, and seamless integration with CLI tools requiring Okta authentication.

**⚠️ Important Limitations:**
- Requires **separate browser session** from your main browser
- You must perform **MFA authentication** when tokens expire (configurable TTL)
- Browser sessions are isolated by design - there's no way to share authentication between processes

## Installation

### Prerequisites

- Python 3.8 or higher
- Chrome/Chromium browser
- [uv](https://github.com/astral-sh/uv) package manager

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install chromium-browser

# macOS with Homebrew
brew install chromium

# The tool will automatically download chromedriver using webdriver-manager
```

### Install the Project

```bash
# Clone the repository
git clone <repository-url>
cd okta-yoink

# Install with uv (recommended)
uv pip install -e .

# Or install with development dependencies
uv pip install -e ".[dev]"
```

### Shell Function Setup

**The key step**: Source the okta shell function to enable the `okta` command:

```bash
# For current session only
source bin/okta.sh

# For permanent installation, add to your shell startup file
echo "source ~/repos/scottidler/okta-yoink/bin/okta.sh" >> ~/.zshrc
# or for bash users:
echo "source ~/repos/scottidler/okta-yoink/bin/okta.sh" >> ~/.bashrc

# Reload your shell
source ~/.zshrc  # or ~/.bashrc
```

Verify installation:
```bash
type okta
# Should output: okta is a shell function from bin/okta.sh
```

## Configuration

### Environment Variables

The okta function uses two key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OKTA_YOINK_TTL` | `3600` | Token time-to-live in seconds (1 hour default) |
| `OKTA_YOINK_REPO` | `~/repos/scottidler/okta-yoink` | Path to this repository |

### Application Configuration

Copy `env.example` to `.env` and customize for your organization:

```bash
cp env.example .env
```

Key configuration options:

| Variable | Default | Description |
|----------|---------|-------------|
| `OKTA_LOGIN_URL` | `https://tatari.okta.com` | Your Okta login URL |
| `HTTPBIN_URL` | `https://httpbin.ops.tatari.dev/headers` | Internal service for token extraction |
| `OKTA_USERNAME` | _(empty)_ | Pre-configure username (optional) |
| `OKTA_PASSWORD` | _(empty)_ | Pre-configure password (optional) |
| `TOKEN_FILE` | `~/.okta-cookie` | File path for token storage |
| `HEADLESS` | `false` | Run browser in headless mode |
| `BROWSER_TIMEOUT` | `30` | Timeout for browser operations (seconds) |
| `MFA_TIMEOUT` | `120` | Timeout for MFA completion (seconds) |

## Usage

The `okta` function provides two modes of operation:

### Standalone Mode (Just Get Authenticated)

```bash
# Refresh token and export to shell environment
okta

# Example output:
# [okta] OKTA_YOINK_TTL=3600
# [okta] OKTA_YOINK_REPO=/home/user/repos/scottidler/okta-yoink
# [okta] Using cached token
# [okta] Token exported to OKTA_COOKIE (persists in shell)
# [okta] Token ready for use in current shell session

# Now any command can use the token
some-cli-tool-that-needs-okta
```

### Wrapper Mode (Transparent Command Execution)

```bash
# Wrap any command with automatic token management
okta persona -o Engineering -m dec

# Example output:
# [okta] OKTA_YOINK_TTL=3600
# [okta] OKTA_YOINK_REPO=/home/user/repos/scottidler/okta-yoink
# [okta] Using cached token
# [okta] Token exported to OKTA_COOKIE (persists in shell)
# [okta] Executing: persona -o Engineering -m dec
#
# Organization: Engineering, Name: Scott Idler, Anniversary: 5
# Organization: Engineering, Name: Jai Baik, Anniversary: 4
# ...
```

### Silent Mode

Suppress okta output messages with `-s` or `--silent`:

```bash
# Only show command output
okta -s persona -o Engineering -m dec

# Output:
# Organization: Engineering, Name: Scott Idler, Anniversary: 5
# Organization: Engineering, Name: Jai Baik, Anniversary: 4
# ...
```

### Token Refresh Workflow

When tokens are expired or missing:

1. **Configuration Display**: Shows TTL and repository path
2. **Browser Launch**: Opens Chrome/Chromium browser
3. **Okta Login**: Navigates to your Okta login page
4. **Credentials**: Uses configured credentials or prompts
5. **MFA**: Waits for you to complete MFA (YubiKey touch/PIN)
6. **Token Extraction**: Navigates to internal service and extracts token
7. **Storage**: Saves token to file and exports to environment
8. **Command Execution**: Runs your command (if provided)

### Customization Examples

```bash
# Use longer token TTL (2 hours)
OKTA_YOINK_TTL=7200 okta persona -o Engineering -m dec

# Use different repository location
OKTA_YOINK_REPO=/path/to/my/okta-yoink okta
```

## Features

- ✅ **Intelligent Caching**: Tokens cached with configurable TTL (default 1 hour)
- ✅ **Dual Mode Operation**: Standalone token refresh or command wrapper
- ✅ **Silent Mode**: Clean output for scripting (`-s`/`--silent`)
- ✅ **Shell Integration**: Token persists in shell environment
- ✅ **Configuration Display**: Shows active settings for transparency
- ✅ **Automatic MFA Handling**: YubiKey/WebAuthn support
- ✅ **Secure Storage**: Token files with restrictive permissions (600)
- ✅ **Cross-Platform**: Works on Linux and macOS
- ✅ **Error Handling**: Comprehensive validation and user-friendly messages

## Advanced Usage

### Custom Token TTL

```bash
# Set token to expire after 30 minutes
export OKTA_YOINK_TTL=1800

# Verify setting
okta
# [okta] OKTA_YOINK_TTL=1800
# ...
```

### Integration with Shell Scripts

```bash
#!/bin/bash
# my-script.sh

# Ensure we have a valid token
okta -s  # Silent mode, just refresh if needed

# Now use the token
curl -H "Cookie: $OKTA_COOKIE" https://internal-api.company.com/data
```

### Automation and CI/CD

```bash
# In automated environments, pre-configure credentials
export OKTA_USERNAME="your-username"
export OKTA_PASSWORD="your-password"

# Run with longer timeout for slower environments
export OKTA_YOINK_TTL=3600
export MFA_TIMEOUT=300

okta -s your-cli-command
```

## Troubleshooting

### Common Issues

**Function not found:**
```bash
# Make sure you sourced the file
source bin/okta.sh
type okta  # Should show it's a function
```

**Repository not found:**
```bash
# Check OKTA_YOINK_REPO path
echo $OKTA_YOINK_REPO
# Update if needed
export OKTA_YOINK_REPO=/correct/path/to/okta-yoink
```

**Token refresh fails:**
```bash
# Run in normal mode to see browser
HEADLESS=false okta

# Check credentials in .env file
cat .env | grep OKTA_
```

**Permission issues:**
```bash
# Check token file permissions
ls -la ~/.okta-cookie
# Should show: -rw------- (600)
```

### Debug Mode

```bash
# Run the underlying tool directly for debugging
cd $OKTA_YOINK_REPO
uv run okta-yoink
```

## Technical Implementation

### Project Structure

```
okta-yoink/
├── bin/
│   └── okta.sh              # Main shell function
├── src/okta_yoink/
│   ├── __init__.py          # Package initialization
│   ├── config.py            # Configuration management
│   ├── token_extractor.py   # Main extraction logic
│   └── main.py              # CLI entry point
├── tests/
│   ├── test_config.py       # Config tests
│   ├── test_token_extractor.py  # Extractor tests
│   ├── test_main.py         # Main function tests
│   └── test_integration.py  # Integration tests
├── docs/
│   └── okta-shim-design.md  # Detailed design documentation
├── pyproject.toml           # Project configuration
├── env.example              # Environment configuration template
└── README.md                # This file
```

### Architecture

The system consists of two main components:

1. **Shell Function** (`bin/okta.sh`): Provides caching, validation, and command wrapping
2. **Python Application** (`src/okta_yoink/`): Handles browser automation and token extraction

See [docs/okta-shim-design.md](docs/okta-shim-design.md) for detailed architectural documentation.

## Development

### Setup Development Environment

```bash
# Install with development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=okta_yoink --cov-report=html

# Code quality checks
black --check src/ tests/
isort --check-only src/ tests/
mypy src/
```

### API Reference

For programmatic usage:

```python
from okta_yoink import OktaTokenExtractor, Config

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

## Security Considerations

- Token files are created with `600` permissions (owner read/write only)
- Passwords can be configured in `.env` but are never logged
- Browser sessions are isolated and cleaned up after use
- Environment variables persist only in the current shell session
- Tokens automatically expire based on configurable TTL

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
pytest --cov=okta_yoink
```
