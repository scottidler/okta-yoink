#!/usr/bin/env python3
"""Main entry point for Okta token automation."""

import logging
import sys
from typing import Optional

from .config import Config
from .token_extractor import OktaTokenExtractor, OktaTokenExtractionError


def setup_logging(config: Config) -> None:
    """Setup logging configuration."""
    # Ensure log directory exists
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )


def main() -> int:
    """Main entry point for the application.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    try:
        # Initialize configuration
        config = Config()
        setup_logging(config)

        logger = logging.getLogger(__name__)
        logger.info("Starting Okta token extraction...")

        # Run token extraction
        with OktaTokenExtractor(config) as extractor:
            token = extractor.run()

        # Success message
        print("\n" + "=" * 50)
        print("🎯 SUCCESS! Token extracted and saved!")
        print(f"📁 Token file: {config.TOKEN_FILE}")
        print(f"🔧 To set environment variable in your current shell:")
        print(f"   export {config.TOKEN_ENV_VAR}=$(cat {config.TOKEN_FILE})")
        print(f"🚀 Or add this function to your ~/.zshrc:")
        print(f"   okta-cookie() {{ export {config.TOKEN_ENV_VAR}=$(cat {config.TOKEN_FILE}); }}")
        print(f"   Then use: okta-cookie")
        print("=" * 50)

        return 0

    except KeyboardInterrupt:
        print("\n❌ Process interrupted by user")
        return 1

    except OktaTokenExtractionError as e:
        print(f"\n💥 Token extraction error: {e}")
        return 1

    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
