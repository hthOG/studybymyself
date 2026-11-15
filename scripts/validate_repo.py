#!/usr/bin/env python3
"""Validate package metadata, links, subagent settings and Python syntax."""
import ast
import json
from pathlib import Path
import re
import sys
import tomllib

import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT):
    checked = 0
    for doc in root.rglob('*.md'):
        if any(part in {'.venv', 'work', 'books', 'inputs', '.git'} for part in doc.relative_to(root).parts):
            continue
        text = doc.read_text(encoding='utf-8-sig')
        for link in re.findall(r'\]\(([^)\n]+)\)', text):
            if '://' in link or link.startswith('#'):
                continue
            target = (doc.parent / link.split('#')[0]).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                raise ValueError(f'Broken relative link: {doc.relative_to(root)} -> {link}')
            checked += 1
    skill = root / 'skills/textbook-to-zh-tw-notes'
    text = (skill / 'SKILL.md').read_text(encoding='utf-8')
    front = yaml.safe_load(text.split('---', 2)[1])
    if front.get('name') != skill.name or not front.get('description') or len(front['description']) > 1024:
        raise ValueError('Invalid Skill frontmatter')
    ui = yaml.safe_load((skill / 'agents/openai.yaml').read_text(encoding='utf-8'))
    if not 25 <= len(ui['interface']['short_description']) <= 64 or '$' + skill.name not in ui['interface']['default_prompt']:
        raise ValueError('Invalid Skill UI metadata')
    agents = tomllib.loads((root / '.codex/config.toml').read_text(encoding='utf-8'))['agents']
    expected = {'enabled': True, 'max_concurrent_threads_per_session': 15,
                'default_subagent_model': 'gpt-6.1-terra', 'default_subagent_reasoning_effort': 'medium'}
    if agents != expected:
        raise ValueError('Shared subagent snapshot differs from confirmed settings')
    opencode = json.loads((root / 'opencode.json').read_text(encoding='utf-8'))
    if opencode != {'$schema': 'https://opencode.ai/config.json', 'instructions': ['docs/OPENCODE.md']}:
        raise ValueError('OpenCode entry must load the guide without overriding user model or permissions')
    native = root / '.opencode/skills/textbook-to-zh-tw-notes/SKILL.md'
    native_front = yaml.safe_load(native.read_text(encoding='utf-8').split('---', 2)[1])
    if native_front.get('name') != skill.name or not native_front.get('description'):
        raise ValueError('Invalid OpenCode skill entry')
    for p in root.rglob('*.py'):
        if any(part in {'.venv', 'work', 'books', 'inputs', '.git'} for part in p.relative_to(root).parts):
            continue
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    for required in ('AGENTS.md', 'agent.md', 'README.md', 'setup.ps1', 'prompts/start-book.md',
                     'prompts/resume-book.md', 'prompts/source-reader.md', 'prompts/verifier.md', 'docs/VALIDATION.md',
                     'setup.sh', '.gitattributes', 'docs/PLATFORMS.md',
                     'prompts/write-chapter.md',
                     'skills/textbook-to-zh-tw-notes/references/chapter-authoring.md',
                     'skills/textbook-to-zh-tw-notes/references/reference-patterns.md',
                     'skills/textbook-to-zh-tw-notes/references/writing-example.md',
                     'skills/textbook-to-zh-tw-notes/references/efficiency.md',
                     'skills/textbook-to-zh-tw-notes/scripts/reuse.py',
                     'docs/OPENCODE.md', 'prompts/opencode-book.md',
                     'examples/codex-style/source.md', 'examples/codex-style/lesson.md',
                     'examples/codex-style/verify.py',
                     'skills/textbook-to-zh-tw-notes/references/codex-quality-baseline.md',
                     'skills/textbook-to-zh-tw-notes/references/formula-verification.md',
                     'skills/textbook-to-zh-tw-notes/scripts/math_audit.py',
                     'skills/textbook-to-zh-tw-notes/scripts/pdf_text_audit.py'):
        if not (root / required).is_file():
            raise ValueError('Missing package entry: ' + required)
    print(f'Validated Skill/OpenCode entries, Codex TOML, Python syntax and {checked} relative links.')


if __name__ == '__main__':
    try:
        validate()
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
