#!/usr/bin/env python3
"""Main entry point for Okta token automation."""

import sys
from typing import Optional

from .config import Config
from .token_extractor import OktaTokenExtractor, OktaTokenExtractionError


def main() -> int:
    """Main entry point for the application.
    
    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    try:
        # Initialize configuration
        config = Config()
        
        # Run token extraction
        with OktaTokenExtractor(config) as extractor:
            token = extractor.run()

        # Success message
        print("\n" + "=" * 50)
        print("🎯 SUCCESS! Your CLI should now work with:")
        print(f"   export {config.TOKEN_ENV_VAR}=$(cat {config.TOKEN_FILE})")
        print("   cargo run -- -o Engineering -m jan")
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