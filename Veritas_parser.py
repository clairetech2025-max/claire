#!/usr/bin/env python3
"""
Veritas Parser
--------------
Compatibility entry point for the Claire evidence parser.

Use this name when presenting the parser as the Veritas / evidence-intake
layer. The implementation lives in claire_parser.py so the project has one
maintained parser instead of two drifting versions.
"""

from claire_parser import main


if __name__ == "__main__":
    raise SystemExit(main())
