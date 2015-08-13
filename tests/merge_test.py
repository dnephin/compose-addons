import textwrap

import pytest
import yaml

from compose_addons import merge


def test_merge_file_build_to_image():
    base = {
        'web': {
            'build': '.',
            'ports': []
        }
    }
    override = {
        'web': {
            'image': 'service:latest',
            'environment': [],
        }
    }
    expected = {
        'web': {
            'image': 'service:latest',
            'environment': [],
            'ports': [],
        }
    }
    assert merge.merge_config(base, override) == expected


def test_merge_file_image_to_build():
    base = {
        'web': {
            'image': 'service:latest',
            'ports': []
        }
    }
    override = {
        'web': {
            'build': '.',
            'environment': [],
        }
    }
    expected = {
        'web': {
            'build': '.',
            'environment': [],
            'ports': [],
        }
    }
    assert merge.merge_config(base, override) == expected


@pytest.mark.acceptance
def test_merge_end_to_end(tmpdir, capsys):
    tmpdir.join('base.yaml').write(textwrap.dedent("""
        web:
            build: .
            links:
                - db
                - serviceb

        db:
            build: database/

        serviceb:
            image: example.com/services_b:latest
    """))
    tmpdir.join('overrides.yaml').write(textwrap.dedent("""
        web:
            volumes:
                - '.:/code'

        serviceb:
            image: my_version_of_service_b:abf4a
    """))

    expected = {
        'web': {
            'build': '.',
            'links': ['db', 'serviceb'],
            'volumes': ['.:/code'],
        },
        'db': {
            'build': 'database/',
        },
        'serviceb': {
            'image': 'my_version_of_service_b:abf4a',
        }
    }

    with tmpdir.as_cwd():
        merge.main(['base.yaml', 'overrides.yaml'])

    out, err = capsys.readouterr()
    assert yaml.load(out) == expected
