#!/usr/bin/env python
"""
Entry point for SpecSync Bridge CLI.

Usage:
    python bridge.py init [--role consumer|provider|both]
    python bridge.py add-dependency <name> --git-url <url> [--contract-path <path>]
    python bridge.py sync [dependency-name]
    python bridge.py validate
    python bridge.py status
"""
import sys
from backend.bridge_cli import main

if __name__ == '__main__':
    main()
