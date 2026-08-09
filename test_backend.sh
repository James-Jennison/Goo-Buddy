#!/bin/sh

set -eu

cd backend
../venv/bin/ruff check
../venv/bin/ruff format --check

TEST_WORKERS="${GOO_BUDDY_PYTEST_WORKERS:-8}"
case "$TEST_WORKERS" in
    ''|*[!0-9]*|0)
        echo "GOO_BUDDY_PYTEST_WORKERS must be a positive integer" >&2
        exit 2
        ;;
esac

if [ "$1" = "--full" ]; then
../venv/bin/python3 -m pytest tests/ -v -n "$TEST_WORKERS"
else
../venv/bin/python3 -m pytest tests/ -v -n "$TEST_WORKERS" --ignore=tests/unit/services/test_bambu_ftp.py
fi
