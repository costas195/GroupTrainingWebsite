"""Validate Render configuration without creating or changing hosted resources."""
import json
from pathlib import Path
import sys

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    schema = json.loads((ROOT / 'schemas/render.schema.json').read_text(encoding='utf-8'))
    validator = jsonschema.Draft202012Validator(schema)
    for filename in ('render.yaml', 'render.demo.yaml'):
        document = yaml.safe_load((ROOT / filename).read_text(encoding='utf-8'))
        errors = sorted(validator.iter_errors(document), key=lambda error: str(error.path))
        if errors:
            for error in errors:
                print(f'{filename}: {error.message}', file=sys.stderr)
            return 1
        print(f'{filename}: valid Render Blueprint')
    production = yaml.safe_load((ROOT / 'render.yaml').read_text(encoding='utf-8'))
    service = production['services'][0]
    settings = {item['key']: item for item in service['envVars']}
    assert settings['APP_ENV']['value'] == 'production'
    assert settings['DEMO_MODE']['value'] == 'false'
    assert settings['AUTO_MIGRATE']['value'] == 'false'
    assert settings['DATABASE_SSLMODE']['value'] == 'require'
    assert settings['WEBSMS_API_KEY'].get('sync') is False
    assert settings['SECRET_KEY'].get('generateValue') is True
    assert service['autoDeployTrigger'] == 'checksPass'
    assert production['databases'][0]['ipAllowList'] == []
    print('Production guards: enabled; secret values: supplied by Render')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
