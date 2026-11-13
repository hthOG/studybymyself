#!/usr/bin/env python3
"""Fingerprint completed task artifacts; never certify reading or semantic quality."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import json

import project


def task_dir(root, task):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', task):
        raise ValueError('Task ID must contain ASCII letters, digits, underscores or hyphens')
    return project.local(root, 'tasks/' + task)


def fingerprint(root, task, kind, unit_ids, inputs, outputs):
    folder = task_dir(root, task)
    source = project.load(root / 'source.json')
    actual = project.digest(Path(source['path']))
    if actual != source['sha256']:
        raise ValueError('Original source hash changed; reconcile source before reuse')
    known = {u['id']: u for u in source['units']}
    if not unit_ids or len(unit_ids) != len(set(unit_ids)) or not set(unit_ids).issubset(known):
        raise ValueError('Need unique registered unit IDs')
    handoff_path = folder / 'handoff.json'
    handoff = project.load(handoff_path)
    if (handoff.get('task_id') != task or handoff.get('status') != 'ready' or handoff.get('issues') != []
            or handoff.get('source_sha256') != actual
            or set(handoff.get('unit_ids', [])) != set(unit_ids)):
        raise ValueError('Task handoff is incomplete, unresolved or has a different source/scope')
    if kind not in {'reading', 'verification'}:
        raise ValueError('Unknown task kind')
    if kind == 'verification' and not inputs:
        raise ValueError('Verification reuse must fingerprint the reviewed draft and dependencies')
    if not outputs:
        raise ValueError('Need actual evidence/output artifacts')
    assets = {}
    for uid in sorted(unit_ids):
        u = known[uid]
        assets[uid] = {'locator': u, 'text_sha256': project.digest(project.local(root, u['text_path'])),
                       'preview_sha256': project.digest(project.local(root, u['preview_path']))}
    def hashes(paths, output=False):
        result = {}
        for rel in sorted(set(paths)):
            p = project.local(root, rel)
            if output and not p.is_relative_to(folder):
                raise ValueError('Task outputs must stay within its own task directory')
            if not project.nonempty(p):
                raise ValueError('Missing/empty dependency or evidence: ' + rel)
            result[p.relative_to(root).as_posix()] = project.digest(p)
        return result
    return {'source_sha256': actual, 'kind': kind, 'task_id': task, 'units': assets,
            'inputs': hashes(inputs), 'outputs': hashes(outputs, True),
            'handoff_sha256': project.digest(handoff_path)}


def seal(root, task, kind, unit_ids, inputs, outputs):
    receipt = task_dir(root, task) / 'reuse-receipt.json'
    if receipt.exists():
        raise ValueError('Receipt exists; archive old evidence and record rerun reason before resealing')
    # A receipt records a reviewed result; it does not update coverage, QA or any lock.
    value = fingerprint(root, task, kind, unit_ids, inputs, outputs)
    project.save(receipt, {'schema_version': 1, 'sealed_utc': datetime.now(timezone.utc).isoformat(),
                           'unit_ids': sorted(unit_ids), 'input_paths': inputs, 'output_paths': outputs,
                           'fingerprint': value})
    return {'reuse_candidate': True, 'task_id': task, 'scope': 'file integrity only; semantic acceptance still required'}


def check(root, task):
    try:
        saved = project.load(task_dir(root, task) / 'reuse-receipt.json')
        if saved.get('schema_version') != 1:
            raise ValueError('Unsupported receipt version')
        old = saved['fingerprint']
        current = fingerprint(root, task, old['kind'], saved['unit_ids'], saved['input_paths'], saved['output_paths'])
        same = old == current
        return {'reuse_candidate': same, 'task_id': task,
                'reason': 'Recorded inputs and evidence unchanged' if same else 'Scoped inputs, source assets or evidence changed',
                'scope': 'does not prove complete reading, correct dependencies or independent verification'}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {'reuse_candidate': False, 'task_id': task, 'reason': str(exc)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('seal', 'check'):
        p = sub.add_parser(name)
        p.add_argument('project')
        p.add_argument('--task', required=True)
        if name == 'seal':
            p.add_argument('--kind', choices=('reading', 'verification'), required=True)
            p.add_argument('--units', nargs='+', required=True)
            p.add_argument('--input', action='append', default=[])
            p.add_argument('--output', action='append', default=[])
    args = parser.parse_args(argv)
    try:
        root = Path(args.project).resolve()
        result = (check(root, args.task) if args.command == 'check' else
                  seal(root, args.task, args.kind, args.units, args.input, args.output))
        print(json.dumps(result, ensure_ascii=True))
        return 0 if result['reuse_candidate'] else 1
    except Exception as exc:
        print(json.dumps({'reuse_candidate': False, 'error': str(exc)}, ensure_ascii=True))
        return 2


if __name__ == '__main__':
    sys.exit(main())
