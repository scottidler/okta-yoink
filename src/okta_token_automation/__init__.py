"""
Okta Token Automation Package

Automated extraction of Okta _oauth2_proxy tokens using Selenium WebDriver.
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .config import Config
from .token_extractor import OktaTokenExtractor

__all__ = ["Config", "OktaTokenExtractor"] 