#!/usr/bin/env python3
"""Read-only runtime/config inventory. Does not claim live Codex settings are active."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/textbook-to-zh-tw-notes/scripts'))
from book import find_xelatex


def inspect_environment():
    modules = {name: importlib.util.find_spec(name) is not None for name in ('pypdf', 'fitz', 'sympy', 'yaml')}
    config = tomllib.loads((ROOT / '.codex/config.toml').read_text(encoding='utf-8-sig'))
    return {'python': sys.version.split()[0], 'python_compatible': sys.version_info >= (3, 11),
            'python_modules': modules, 'xelatex': find_xelatex(),
            'codex': shutil.which('codex'), 'shared_subagent_settings': config.get('agents', {}),
            'opencode': shutil.which('opencode'),
            'live_opencode_model_verified': False,
            'live_codex_settings_verified': False,
            'note': 'Inspect the actual host to confirm models, image review and subagents. '
                    'The Codex snapshot is not OpenCode configuration.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('--find-xelatex', action='store_true')
    args = parser.parse_args()
    if args.find_xelatex:
        result = find_xelatex()
        if result:
            print(result)
        return 0 if result else 1
    report = inspect_environment()
    print(json.dumps(report, ensure_ascii=True, indent=2))
    complete = report['python_compatible'] and all(report['python_modules'].values()) and report['xelatex']
    return 1 if args.strict and not complete else 0


if __name__ == '__main__':
    sys.exit(main())
