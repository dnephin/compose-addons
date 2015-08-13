import pytest
import yaml

from compose_addons import namespace


def test_add_namespace():
    config = {
        'web': {
            'image': 'example/web',
            'links': ['db:alias', 'other', 'external.web'],
            'volumes_from': ['config', 'external.config'],
            'net': 'container:db',
        },
        'db': {
            'image': 'example/db',
            'environment': ['isstillhere=yes'],
        },
        'config': {'image': 'example/config'},
        'other': {
            'image': 'example/other',
            'links': ['db'],
        },
    }
    expected = {
        'namespace': 'star',
        'star.web': {
            'image': 'example/web',
            'links': ['star.db:alias', 'star.other:other', 'external.web'],
            'volumes_from': ['star.config', 'external.config'],
            'net': 'container:star.db',
        },
        'star.db': {
            'image': 'example/db',
            'environment': ['isstillhere=yes'],
        },
        'star.config': {'image': 'example/config'},
        'star.other': {
            'image': 'example/other',
            'links': ['star.db:db'],
        },
    }

    result = namespace.add_namespace(config, 'star')
    assert result == expected


def test_parse_field_exact():
    assert namespace.parse_field('a:b:c:d', 4) == ['a', 'b', 'c', 'd']


def test_parse_field_under():
    assert namespace.parse_field('a', 3) == ['a', None, None]
    assert namespace.parse_field('a:b', 3) == ['a', 'b', None]


def test_parse_field_over():
    assert namespace.parse_field('a:b:c:d', 2) == ['a', 'b:c:d']


def test_namespace_net_not_container():
    service = orig = {'net': 'host'}
    namespace.namespace_net(service, 'namespace', {'host'})
    assert service == orig


def test_namespace_net_external_service():
    service = orig = {'net': 'container:ext.foo'}
    namespace.namespace_net(service, 'namespace', {'db', 'config'})
    assert service == orig


def test_namespace_net_internal_service():
    service = {'net': 'container:db'}
    namespace.namespace_net(service, 'namespace.', {'db', 'config'})
    assert service == {'net': 'container:namespace.db'}


@pytest.mark.acceptance
def test_namespace_end_to_end(tmpdir):
    tmpdir.join('docker-compose.yml').write("""
        web:
            image: example/web:latest
            links: [db]
            volumes_from: [config]
        db:
            image: example/db:latest
            environment: ['REPO=/db']
        config:
            image: example/config:latest
    """)

    expected = {
        'namespace': 'servicea',
        'servicea.web': {
            'image': 'example/web:latest',
            'links': ['servicea.db:db'],
            'volumes_from': ['servicea.config'],
        },
        'servicea.db': {
            'image': 'example/db:latest',
            'environment': ['REPO=/db'],
        },
        'servicea.config': {
            'image': 'example/config:latest',
        },
    }

    with tmpdir.as_cwd():
        namespace.main(args=['-o', 'out.yml', 'docker-compose.yml', 'servicea'])
    assert yaml.load(tmpdir.join('out.yml').read()) == expected
