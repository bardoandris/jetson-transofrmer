import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from mvtec_ad import run_test_folder_analysis


class PromptPreparationTests(unittest.TestCase):
    def test_explicit_zero_shot_overrides_one_shot_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'transistor' / 'test' / 'good'
            folder.mkdir(parents=True)
            (folder.parent / 'bent_lead').mkdir()
            Image.new('RGB', (2, 2)).save(folder / 'image.png')
            prompt = root / 'transistor_prompt_oneshot.md'
            prompt.write_text('Inspect the image', encoding='utf-8')
            csv_path = root / 'results.csv'
            args = ['analysis', '--folder', str(folder), '--resolution', '256',
                    '--prompt-file', str(prompt), '--shot-mode', 'zero',
                    '--model', 'model', '--power-mode', '15w', '--csv', str(csv_path)]
            response = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"defect_category":"good"}'))],
                model_dump=lambda: {},
            )
            with (patch('sys.argv', args), patch('run_inference.OpenAI') as client,
                  patch('run_inference.wait_for_safe_temperature')):
                client.return_value.chat.completions.create.return_value = response
                run_test_folder_analysis.main()
                request = client.return_value.chat.completions.create.call_args.kwargs
            with csv_path.open(newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]['shot_mode'], 'zero-shot')
            self.assertEqual(len([part for part in request['messages'][1]['content']
                                  if part['type'] == 'image_url']), 1)

    def test_one_shot_uses_labeled_references_and_excludes_them_from_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            test_root = root / 'transistor' / 'test'
            for category in ('good', 'bent_lead'):
                folder = test_root / category
                folder.mkdir(parents=True)
                for name in ('00.png', '01.png'):
                    Image.new('RGB', (2, 2)).save(folder / name)
            prompt = root / 'prompt.md'
            prompt.write_text('Inspect', encoding='utf-8')
            csv_path = root / 'results.csv'
            args = ['analysis', '--folder', str(test_root / 'good'),
                    '--folder', str(test_root / 'bent_lead'), '--resolution', '256',
                    '--prompt-file', str(prompt), '--shot-mode', 'one',
                    '--model', 'model', '--power-mode', '15w', '--csv', str(csv_path)]
            response = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"defect_category":"good"}'))],
                model_dump=lambda: {},
            )
            with (patch('sys.argv', args), patch('run_inference.OpenAI') as client,
                  patch('run_inference.wait_for_safe_temperature')):
                client.return_value.chat.completions.create.return_value = response
                run_test_folder_analysis.main()
                calls = client.return_value.chat.completions.create.call_args_list
            with csv_path.open(newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([Path(row['test_image']).name for row in rows], ['01.png', '01.png'])
            self.assertTrue(all(row['shot_mode'] == 'one-shot' for row in rows))
            self.assertEqual(len(calls), 3)  # One warm-up, then one request per category.
            for call in calls:
                request = call.kwargs
                self.assertEqual(request['extra_body']['cache_prompt'], True)
                parts = request['messages'][1]['content']
                self.assertEqual(sum(part['type'] == 'image_url' for part in parts), 3)
                self.assertTrue(any('[good]' in part.get('text', '') for part in parts))
                self.assertTrue(any('[bent_lead]' in part.get('text', '') for part in parts))


if __name__ == '__main__':
    unittest.main()
