"""Configuration module for Okta token automation."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


class Config:
    """Configuration class for Okta token automation settings."""

    def __init__(self) -> None:
        """Initialize configuration with environment variables and defaults."""
        # Okta/Company URLs
        self.OKTA_LOGIN_URL: str = os.getenv(
            "OKTA_LOGIN_URL", "https://tatari.okta.com"
        )
        self.HTTPBIN_URL: str = os.getenv(
            "HTTPBIN_URL", "https://httpbin.ops.tatari.dev/headers"
        )

        # Browser settings
        self.HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"
        self.BROWSER_TIMEOUT: int = int(os.getenv("BROWSER_TIMEOUT", "60"))
        self.IMPLICIT_WAIT: int = int(os.getenv("IMPLICIT_WAIT", "10"))
        self.MFA_TIMEOUT: int = int(os.getenv("MFA_TIMEOUT", "120"))

        # Token storage
        self.TOKEN_FILE: Path = Path(
            os.getenv("TOKEN_FILE", os.path.expanduser("~/.okta-cookie"))
        )
        self.TOKEN_ENV_VAR: str = os.getenv("TOKEN_ENV_VAR", "OKTA_COOKIE")

        # User credentials (optional - can be entered interactively)
        self.OKTA_USERNAME: str = os.getenv("OKTA_USERNAME", "")

        # Browser binary paths (optional)
        self.CHROME_BINARY_PATH: Optional[str] = os.getenv("CHROME_BINARY_PATH")
        self.CHROMEDRIVER_PATH: Optional[str] = os.getenv("CHROMEDRIVER_PATH")

    def validate(self) -> None:
        """Validate configuration settings."""
        if not self.OKTA_LOGIN_URL:
            raise ValueError("OKTA_LOGIN_URL cannot be empty")

        if not self.HTTPBIN_URL:
            raise ValueError("HTTPBIN_URL cannot be empty")

        if self.BROWSER_TIMEOUT <= 0:
            raise ValueError("BROWSER_TIMEOUT must be positive")

        if self.IMPLICIT_WAIT <= 0:
            raise ValueError("IMPLICIT_WAIT must be positive")

        if self.MFA_TIMEOUT <= 0:
            raise ValueError("MFA_TIMEOUT must be positive")

    def __repr__(self) -> str:
        """Return string representation of config (without sensitive data)."""
        return (
            f"Config("
            f"OKTA_LOGIN_URL='{self.OKTA_LOGIN_URL}', "
            f"HTTPBIN_URL='{self.HTTPBIN_URL}', "
            f"HEADLESS={self.HEADLESS}, "
            f"BROWSER_TIMEOUT={self.BROWSER_TIMEOUT}, "
            f"TOKEN_FILE='{self.TOKEN_FILE}', "
            f"OKTA_USERNAME='{'***' if self.OKTA_USERNAME else ''}'"
            f")"
        )
