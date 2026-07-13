#!/usr/bin/env bash
# Shared config.yaml detection for Docker Compose and image builds.
# Sourced by scripts/deploy.sh and scripts/docker.sh — not meant to be executed alone.
#
# Requires the caller to set REPO_ROOT or PROJECT_ROOT to the repository root.

_compose_detect_root() {
    if [ -n "${REPO_ROOT:-}" ]; then
        printf '%s' "$REPO_ROOT"
    elif [ -n "${PROJECT_ROOT:-}" ]; then
        printf '%s' "$PROJECT_ROOT"
    else
        return 1
    fi
}

_compose_detect_config_file() {
    local root
    root="$(_compose_detect_root)" || return 1
    printf '%s' "${DEER_FLOW_CONFIG_PATH:-$root/config.yaml}"
}

_compose_detect_python() {
    if command -v python3 >/dev/null 2>&1; then
        printf '%s' python3
    elif command -v python >/dev/null 2>&1; then
        printf '%s' python
    else
        return 1
    fi
}

# Export UV_EXTRAS from config.yaml when not already set (e.g. postgres for asyncpg).
apply_uv_extras_from_config() {
    local root config_file detect_py python_bin val
    if [ -n "${UV_EXTRAS:-}" ]; then
        return 0
    fi
    root="$(_compose_detect_root)" || return 0
    config_file="$(_compose_detect_config_file)" || return 0
    detect_py="$root/scripts/detect_uv_extras.py"
    if [ ! -f "$config_file" ] || [ ! -f "$detect_py" ]; then
        return 0
    fi
    python_bin="$(_compose_detect_python)" || {
        echo "python3 not found; cannot auto-detect UV_EXTRAS from config.yaml" >&2
        return 0
    }
    val=$(
        DEER_FLOW_CONFIG_PATH="$config_file" "$python_bin" "$detect_py" --print-uv-extras 2>/dev/null || true
    )
    if [ -n "$val" ]; then
        export UV_EXTRAS="$val"
    fi
}

# Enable Compose profile "postgres" when config.yaml uses PostgreSQL.
apply_compose_postgres_profile_from_config() {
    local root config_file detect_py python_bin profile
    root="$(_compose_detect_root)" || return 0
    config_file="$(_compose_detect_config_file)" || return 0
    detect_py="$root/scripts/detect_uv_extras.py"
    if [ ! -f "$config_file" ] || [ ! -f "$detect_py" ]; then
        return 0
    fi
    python_bin="$(_compose_detect_python)" || {
        echo "python3 not found; cannot detect postgres profile from config.yaml" >&2
        return 0
    }
    profile=$(
        DEER_FLOW_CONFIG_PATH="$config_file" "$python_bin" "$detect_py" --print-compose-profile 2>/dev/null || true
    )
    if [ "$profile" = "postgres" ]; then
        if [ -n "${COMPOSE_PROFILES:-}" ]; then
            case ",${COMPOSE_PROFILES}," in
                *,postgres,*) ;;
                *) export COMPOSE_PROFILES="${COMPOSE_PROFILES},postgres" ;;
            esac
        else
            export COMPOSE_PROFILES="postgres"
        fi
    fi
}

# Apply both UV extras (image build) and Compose postgres profile (runtime).
apply_compose_database_from_config() {
    apply_uv_extras_from_config
    apply_compose_postgres_profile_from_config
}
