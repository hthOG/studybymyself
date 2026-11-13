"""Bash control-flow tests with fake system commands; not an Ubuntu install test."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import uuid

BASH = os.environ.get('BASH_EXECUTABLE') or shutil.which('bash')
REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(BASH, 'Bash unavailable; set BASH_EXECUTABLE to run installer control-flow tests')
class SetupShellTests(unittest.TestCase):
    def setUp(self):
        self.parent = (Path.cwd() / 'work/setup-tests').resolve()
        self.parent.mkdir(parents=True, exist_ok=True)
        self.root = self.parent / ('fixture-' + uuid.uuid4().hex)
        self.root.mkdir()
        shutil.copyfile(REPO / 'setup.sh', self.root / 'setup.sh')
        self.bin = self.root / 'fake-bin'
        self.bin.mkdir()
        self.trace = self.root / 'calls.txt'
        self.trace.write_text('', encoding='utf-8')
        self.stub('uname', 'printf "Linux\\n"')
        self.stub('id', 'printf "1000\\n"')
        self.stub('dpkg-query', 'exit 1')
        self.stub('sudo', 'printf "sudo %s\\n" "$*" >> "$SETUP_TRACE"\nexec "$@"')
        self.stub('apt-get', 'printf "apt %s\\n" "$*" >> "$SETUP_TRACE"\nexit "${APT_RESULT:-0}"')
        self.stub('python3', '''printf 'python %s\\n' "$*" >> "$SETUP_TRACE"
if [[ "${1:-}" == -m && "${2:-}" == venv ]]; then
  mkdir -p "$3/bin"
  cp "$0" "$3/bin/python"
  chmod +x "$3/bin/python"
fi
exit 0''')

    def stub(self, name, body):
        p = self.bin / name
        p.write_text('#!/usr/bin/env bash\n'+body+'\n', encoding='utf-8', newline='\n')
        p.chmod(0o755)

    def run_setup(self, *args, **variables):
        # Set PATH inside Bash so Git Bash and POSIX shells use the same path syntax.
        env = dict(os.environ, SETUP_TRACE=self.trace.as_posix(), **variables)
        return subprocess.run([BASH, '-c', 'export PATH="$PWD/fake-bin:$PATH"; exec bash setup.sh "$@"',
                               'setup-test', *args], cwd=self.root, env=env, capture_output=True, text=True)

    def tearDown(self):
        assert self.root.resolve().is_relative_to(self.parent)
        shutil.rmtree(self.root)

    def test_dry_run_performs_no_commands_or_mutations(self):
        r = self.run_setup('--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.trace.read_text(), '')
        self.assertFalse((self.root / '.venv').exists())

    def test_check_only_does_not_install(self):
        r = self.run_setup('--check-only')
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.trace.read_text()
        self.assertIn('doctor.py --strict', calls)
        self.assertNotIn('apt ', calls)
        self.assertNotIn('pip ', calls)
        self.assertFalse((self.root / '.venv').exists())

    def test_skip_system_creates_venv_and_runs_smoke_without_sudo(self):
        r = self.run_setup('--skip-system')
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.trace.read_text()
        self.assertNotIn('sudo ', calls)
        self.assertNotIn('apt ', calls)
        self.assertIn('-m venv', calls)
        self.assertIn('-m pip install --requirement', calls)
        self.assertIn('smoke_test.py', calls)
        self.assertIn('doctor.py --strict', calls)

    def test_apt_failure_stops_before_python_mutations(self):
        r = self.run_setup(APT_RESULT='17')
        self.assertEqual(r.returncode, 17, r.stderr)
        calls = self.trace.read_text()
        self.assertIn('sudo apt-get update', calls)
        self.assertNotIn('python ', calls)
        self.assertFalse((self.root / '.venv').exists())

    def test_unknown_option_fails_without_commands(self):
        r = self.run_setup('--unsupported')
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.trace.read_text(), '')
