import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunnerShotModeTests(unittest.TestCase):
    def test_run_tests_forwards_explicit_shot_mode(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            folder = temp / 'images'
            folder.mkdir()
            (folder / 'image.png').touch()
            prompt = temp / 'prompt.md'
            prompt.touch()
            python = temp / 'python'
            python.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$TRACE"\n')
            python.chmod(0o755)
            trace = temp / 'trace'
            subprocess.run([str(root / 'run_tests.sh'), '--folder', str(folder),
                            '--resolution', '256', '--prompt-file', str(prompt),
                            '--shot-mode', 'zero', '--power-mode', '15w',
                            '--output-dir', str(temp / 'results')],
                           env={**os.environ, 'PYTHON': str(python), 'TRACE': str(trace)},
                           check=True, capture_output=True, text=True)
            args = trace.read_text().splitlines()
            self.assertEqual(args[args.index('--shot-mode') + 1], 'zero')

    def test_power_sweep_forwards_mode_for_both_entry_points(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'test').mkdir()
            (root / 'bin').mkdir()
            for name in ('run_first_model_power.sh', 'run_first_model_power_zeroshot.sh'):
                shutil.copy(source / 'test' / name, root / 'test' / name)
            folder = root / 'res/mvtec-ad/transistor/test/good'
            folder.mkdir(parents=True)
            (folder / 'image.png').touch()
            prompts = root / 'res/prompts/transistor'
            prompts.mkdir(parents=True)
            for shot in ('one', 'zero'):
                (prompts / f'transistor_prompt_{shot}shot.md').touch()
            for name, content in {
                'sudo': ':', 'docker': ':', 'python': 'echo model',
                'run_tests.sh': 'printf "%s\\n" "$*" >> "$TRACE"',
            }.items():
                path = (root if name == 'run_tests.sh' else root / 'bin') / name
                path.write_text('#!/bin/sh\n' + content + '\n')
                path.chmod(0o755)
            trace = root / 'trace'
            env = {**os.environ, 'PATH': str(root / 'bin') + ':' + os.environ['PATH'],
                   'PYTHON': str(root / 'bin/python'), 'TRACE': str(trace)}
            for script, shot in (('run_first_model_power.sh', 'one'),
                                 ('run_first_model_power_zeroshot.sh', 'zero')):
                trace.write_text('')
                subprocess.run([str(root / 'test' / script)], env=env, check=True,
                               capture_output=True, text=True)
                calls = trace.read_text().splitlines()
                self.assertEqual(len(calls), 3)
                self.assertTrue(all(f'--shot-mode {shot}' in call for call in calls))


if __name__ == '__main__':
    unittest.main()
