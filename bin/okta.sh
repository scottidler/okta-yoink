#!/bin/bash

# Okta Shim Wrapper Function
# Provides transparent Okta token management for command-line tools
# Usage: source this file to define the okta() function
# See docs/okta-shim-design.md for complete design documentation

okta() {
    # Configuration
    local OKTA_YOINK_TTL=${OKTA_YOINK_TTL:-3600} # Default: 1 hour

    # Auto-discover repository path using git, with fallback to environment variable
    local OKTA_YOINK_REPO="${OKTA_YOINK_REPO:-}"
    if [[ -z "$OKTA_YOINK_REPO" ]]; then
        # Auto-discover using git from the location of this script
        local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if git -C "$script_dir" rev-parse --git-dir >/dev/null 2>&1; then
            OKTA_YOINK_REPO="$(git -C "$script_dir" rev-parse --show-toplevel)"
        else
            # Auto-discovery failed - script likely copied outside repo
            # Try common locations as fallbacks
            local fallback_paths=(
                ~/repos/scottidler/okta-yoink
                ~/okta-yoink
                ~/.local/share/okta-yoink
            )

            local found_repo=""
            for path in "${fallback_paths[@]}"; do
                if [[ -d "$path" && -f "$path/pyproject.toml" ]]; then
                    OKTA_YOINK_REPO="$path"
                    found_repo="$path"
                    break
                fi
            done

            # If still not found, use the first fallback and let error handling deal with it
            if [[ -z "$OKTA_YOINK_REPO" ]]; then
                OKTA_YOINK_REPO=~/repos/scottidler/okta-yoink
            fi

            # Show warning about auto-discovery failure (unless silent)
            if [[ "$SILENT" != true ]]; then
                if [[ -n "$found_repo" ]]; then
                    echo "[okta] Warning: Auto-discovery failed, using fallback: $found_repo" >&2
                    echo "[okta] Consider setting OKTA_YOINK_REPO environment variable" >&2
                else
                    echo "[okta] Warning: Auto-discovery failed, using default: $OKTA_YOINK_REPO" >&2
                    echo "[okta] Set OKTA_YOINK_REPO environment variable to correct path" >&2
                fi
            fi
        fi
    fi

    local TOKEN_FILE=~/.okta-cookie
    local SILENT=false

    # Parse flags
    local args=()
    while [[ $# -gt 0 ]]; do
        case $1 in
        -s | --silent)
            SILENT=true
            shift
            ;;
        *)
            args+=("$1")
            shift
            ;;
        esac
    done

    # Set positional parameters to remaining args
    set -- "${args[@]}"

    # Error handling function
    error_exit() {
        echo "[okta] Error: $1" >&2
        return 1
    }

    # Output function that respects silent mode
    okta_echo() {
        if [[ "$SILENT" != true ]]; then
            echo "[okta] $1" >&2
        fi
    }

    # Check if command exists (only if command provided)
    validate_command() {
        local target_command="$1"

        # If no command provided, that's okay - just export token
        if [[ -z "$target_command" ]]; then
            return 0
        fi

        if ! command -v "$target_command" >/dev/null 2>&1; then
            error_exit "Command '$target_command' not found"
            return 1
        fi
    }

    # Check token freshness
    is_token_fresh() {
        local current_time
        local file_mtime
        local age

        # Check if token file exists
        if [[ ! -f "$TOKEN_FILE" ]]; then
            return 1 # Token doesn't exist, not fresh
        fi

        current_time=$(date +%s)

        # Get file modification time (cross-platform)
        if command -v stat >/dev/null 2>&1; then
            # Try GNU stat first (Linux)
            if stat -c %Y "$TOKEN_FILE" >/dev/null 2>&1; then
                file_mtime=$(stat -c %Y "$TOKEN_FILE" 2>/dev/null || echo 0)
            # Try BSD stat (macOS)
            elif stat -f %m "$TOKEN_FILE" >/dev/null 2>&1; then
                file_mtime=$(stat -f %m "$TOKEN_FILE" 2>/dev/null || echo 0)
            else
                file_mtime=0
            fi
        else
            file_mtime=0
        fi

        age=$((current_time - file_mtime))

        # Token is fresh if age is less than TTL
        [[ $age -lt $OKTA_YOINK_TTL ]]
    }

    # Refresh token using okta-yoink
    refresh_token() {
        local repo_path

        # Expand tilde in repo path
        repo_path="${OKTA_YOINK_REPO/#\~/$HOME}"

        okta_echo "Token expired or missing, refreshing..."

        # Validate repository exists
        if [[ ! -d "$repo_path" ]]; then
            error_exit "okta-yoink repository not found at: $repo_path"
        fi

        # Change to repo directory and run okta-yoink
        if ! (cd "$repo_path" && uv run okta-yoink); then
            error_exit "Token refresh failed"
        fi

        # Verify token file was created
        if [[ ! -f "$TOKEN_FILE" ]]; then
            error_exit "Token file not created after refresh"
        fi

        okta_echo "Token refreshed successfully"
    }

    # Export token to environment
    export_token() {
        local token_content

        if [[ ! -f "$TOKEN_FILE" ]]; then
            error_exit "Token file not found: $TOKEN_FILE"
        fi

        if [[ ! -r "$TOKEN_FILE" ]]; then
            error_exit "Cannot read token file: $TOKEN_FILE"
        fi

        token_content=$(cat "$TOKEN_FILE")

        if [[ -z "$token_content" ]]; then
            error_exit "Token file is empty: $TOKEN_FILE"
        fi

        # Export to global environment (persists in shell)
        export OKTA_COOKIE="$token_content"
        okta_echo "Token exported to OKTA_COOKIE (persists in shell)"
    }

    # Main execution logic
    local target_command="${1:-}"
    if [[ -n "$target_command" ]]; then
        shift
    fi

    # Show configuration (unless silent)
    if [[ "$SILENT" != true ]]; then
        echo "[okta] OKTA_YOINK_TTL=${OKTA_YOINK_TTL}" >&2
        echo "[okta] OKTA_YOINK_REPO=${OKTA_YOINK_REPO}" >&2
    fi

    # Step 1: Validate target command exists
    validate_command "$target_command" || return $?

    # Step 2: Check token freshness and refresh if needed
    if ! is_token_fresh; then
        refresh_token || return $?
    else
        okta_echo "Using cached token"
    fi

    # Step 3: Export token to environment (persists in shell)
    export_token || return $?

    # Step 4: Execute target command with all arguments (if provided)
    if [[ -n "$target_command" ]]; then
        okta_echo "Executing: $target_command $*"

        # Add empty line before command output (unless silent)
        if [[ "$SILENT" != true ]]; then
            echo >&2
        fi

        "$target_command" "$@"
        local exit_code=$?
        return $exit_code
    else
        okta_echo "Token ready for use in current shell session"
        return 0
    fi
}
