"""Build a source release from an explicit allowlist, never a workspace snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    '.env.example', '.gitignore', '.python-version', 'README.md', 'PRODUCTION.md',
    'requirements.txt', 'requirements-dev.txt', 'render.yaml', 'render.demo.yaml', 'app.py', 'accounts.py',
    'database.py', 'invitations.py', 'localization.py', 'manage.py',
)
DIRECTORIES = ('.github/workflows', 'migrations', 'templates', 'static', 'tests', 'scripts', 'docs', 'schemas')
EXTENSIONS = {'.py', '.sql', '.html', '.js', '.css', '.png', '.ttf', '.txt', '.md', '.yaml', '.yml', '.json'}
SECRET_KEYS = ('WEBSMS_API_KEY', 'RESEND_API_KEY', 'SECRET_KEY', 'OWNER_PASSWORD', 'DATABASE_URL')


def release_files(root):
    paths = [root / name for name in FILES]
    for directory in DIRECTORIES:
        paths.extend(path for path in (root / directory).rglob('*')
                     if path.is_file() and path.suffix.lower() in EXTENSIONS
                     and '__pycache__' not in path.parts
                     and not path.name.startswith('.env'))
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Release inputs must be ordinary files inside the project.')
        if not path.is_file():
            raise ValueError(f'Missing release input: {path.relative_to(root)}')
    return sorted(set(paths))


def private_values(root):
    values = [os.getenv(key, '') for key in SECRET_KEYS]
    settings = root / '.env.local.json'
    if settings.exists():
        data = json.loads(settings.read_text(encoding='utf-8'))
        values.extend(data.get(key, '') for key in SECRET_KEYS)
    return [value.encode() for value in values if isinstance(value, str) and len(value) >= 12]


def build_release(root, output):
    payloads = {}
    secrets = private_values(root)
    for path in release_files(root):
        content = path.read_bytes()
        if any(secret in content for secret in secrets):
            raise ValueError(f'Private configuration detected in {path.relative_to(root)}')
        payloads[path.relative_to(root).as_posix()] = content
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}
    payloads['RELEASE-MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payloads.items()):
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(f'{digest}  {output.name}\n', encoding='ascii')
    return len(manifest), digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / 'nf-hybrid-render.zip')
    args = parser.parse_args()
    count, digest = build_release(ROOT, args.output.resolve())
    print(f'Release: {args.output.resolve()} ({count} files)')
    print(f'SHA-256: {digest}')


if __name__ == '__main__':
    main()
