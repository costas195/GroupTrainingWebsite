import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_release import FILES, build_release


class ReleaseTests(unittest.TestCase):
    def fixture(self, folder):
        root = Path(folder)
        for name in FILES:
            (root / name).write_text('public source', encoding='utf-8')
        (root / '.env.local.json').write_text(json.dumps({'WEBSMS_API_KEY': 'private-key-never-distribute'}), encoding='utf-8')
        (root / 'data').mkdir()
        (root / 'data/member.sqlite3').write_bytes(b'private member records')
        (root / 'previews').mkdir()
        (root / 'previews/private-screenshot.png').write_bytes(b'private screenshot')
        return root

    def test_release_excludes_private_files_and_has_verifiable_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            output = root / 'dist/release.zip'
            build_release(root, output)
            with zipfile.ZipFile(output) as archive:
                self.assertNotIn('.env.local.json', archive.namelist())
                self.assertFalse(any(name.startswith(('data/', 'previews/', '.git/', '.venv/')) for name in archive.namelist()))
                manifest = json.loads(archive.read('RELEASE-MANIFEST.json'))
                self.assertIn('app.py', manifest)
                for name, expected in manifest.items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)
                    self.assertNotIn(b'private-key-never-distribute', archive.read(name))

    def test_release_refuses_embedded_real_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            (root / 'app.py').write_text('private-key-never-distribute', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Private configuration detected'):
                build_release(root, root / 'dist/release.zip')

    def test_archive_is_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            first = root / 'dist/first.zip'
            second = root / 'dist/second.zip'
            build_release(root, first)
            build_release(root, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
