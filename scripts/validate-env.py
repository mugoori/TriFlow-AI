#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Environment Variable Validation Script

Validates .env files have all required variables set.

Usage:
    python scripts/validate-env.py
    python scripts/validate-env.py --env backend/.env
"""

import re
import sys
import argparse
from pathlib import Path

REQUIRED_VARS = {
    "ANTHROPIC_API_KEY": {
        "pattern": r"^sk-ant-api03-",
        "description": "Anthropic API Key from https://console.anthropic.com",
        "example": "sk-ant-api03-...",
    },
    "DATABASE_URL": {
        "pattern": r"^postgresql://",
        "description": "PostgreSQL connection URL",
        "example": "postgresql://triflow:password@localhost:5432/triflow_ai",
    },
    "REDIS_URL": {
        "pattern": r"^redis://",
        "description": "Redis connection URL",
        "example": "redis://:password@localhost:6379/0",
    },
    "SECRET_KEY": {
        "min_length": 32,
        "description": "JWT secret (generate with: openssl rand -hex 32)",
        "example": "Generated 64-character hex string",
    },
}

OPTIONAL_VARS = {
    "MINIO_ENDPOINT": "MinIO object storage endpoint",
    "SLACK_WEBHOOK_URL": "Slack webhook for notifications",
    "SMTP_HOST": "SMTP server for email notifications",
}


def load_env_file(env_path):
    """Load .env file into dictionary"""
    env_vars = {}
    if not env_path.exists():
        return env_vars

    with open(env_path, encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                try:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
                except ValueError:
                    print(f"⚠ Line {line_num}: Invalid format")

    return env_vars


def validate_required_var(var_name, var_value, rules):
    """Validate a single required variable"""
    # Check if empty
    if not var_value:
        print(f"✗ {var_name} is missing or empty")
        print(f"  → {rules['description']}")
        print(f"  → Example: {rules.get('example', 'N/A')}")
        return False

    # Check default values
    default_values = ["your_", "CHANGE_THIS", "change_in_production"]
    if any(default in var_value for default in default_values):
        print(f"✗ {var_name} still has default/placeholder value")
        print(f"  → {rules['description']}")
        return False

    # Pattern validation
    if "pattern" in rules:
        if not re.match(rules["pattern"], var_value):
            print(f"✗ {var_name} format is invalid")
            print(f"  → Expected pattern: {rules['pattern']}")
            print(f"  → Current value: {var_value[:20]}...")
            return False

    # Length validation
    if "min_length" in rules:
        if len(var_value) < rules["min_length"]:
            print(f"✗ {var_name} is too short (min: {rules['min_length']} chars)")
            return False

    print(f"✓ {var_name} is valid")
    return True


def validate_env_file(env_path):
    """Validate .env file"""
    print("=" * 60)
    print(f"Validating: {env_path}")
    print("=" * 60)

    if not env_path.exists():
        print(f"\n✗ {env_path} not found")
        print(f"\nCreate it by copying from .env.example:")
        print(f"  cp .env.example {env_path}")
        return False

    env_vars = load_env_file(env_path)
    print(f"\nLoaded {len(env_vars)} variables from {env_path.name}")

    print("\nRequired Variables:")
    print("-" * 60)

    all_valid = True
    for var, rules in REQUIRED_VARS.items():
        var_value = env_vars.get(var, "")
        if not validate_required_var(var, var_value, rules):
            all_valid = False

    print("\nOptional Variables:")
    print("-" * 60)

    for var, description in OPTIONAL_VARS.items():
        if var in env_vars and env_vars[var]:
            print(f"✓ {var} is set")
        else:
            print(f"○ {var} is not set ({description})")

    return all_valid


def main():
    parser = argparse.ArgumentParser(description="Validate .env file")
    parser.add_argument(
        "--env",
        default="backend/.env",
        help="Path to .env file (default: backend/.env)"
    )
    args = parser.parse_args()

    env_file = Path(args.env)

    if validate_env_file(env_file):
        print("\n" + "=" * 60)
        print("✓ ALL REQUIRED VARIABLES ARE VALID")
        print("=" * 60)
        print("\nYou can now run:")
        print("  docker-compose up -d")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ SOME VARIABLES NEED ATTENTION")
        print("=" * 60)
        print(f"\nEdit {env_file} and fix the issues above")
        sys.exit(1)


if __name__ == "__main__":
    main()
