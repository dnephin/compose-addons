import boto.exception
import boto.s3.connection
import mock
import pytest
import yaml

from compose_addons import includes
from compose_addons.includes import (
    ConfigCache,
    ConfigError,
    FetchExternalConfigError,
    fetch_external_config,
    get_project_from_file,
    get_project_from_s3,
    normalize_url,
)


def test_normalize_url_with_scheme():
    url = normalize_url('HTTPS://example.com')
    assert url.scheme == 'https'


def test_normalize_url_without_scheme():
    url = normalize_url('./path/to/somewhere')
    assert url.scheme == 'file'


class TestGetProjectFromS3Test(object):

    @mock.patch('compose_addons.includes.get_boto_conn', autospec=True)
    def test_get_project_from_s3(self, mock_get_conn):
        mock_bucket = mock_get_conn.return_value.get_bucket.return_value
        mock_key = mock_bucket.get_key.return_value
        mock_key.get_contents_as_string.return_value = 'foo:\n  build: .'
        url = normalize_url('s3://bucket/path/to/key/compose_addons.yml')

        project = get_project_from_s3(url)
        assert project == {'foo': {'build': '.'}}

        mock_get_conn.assert_called_once_with()
        mock_get_conn.return_value.get_bucket.assert_called_once_with('bucket')
        mock_bucket.get_key.assert_called_once_with(
            '/path/to/key/compose_addons.yml')

    @mock.patch('compose_addons.includes.get_boto_conn', autospec=True)
    def test_get_project_from_s3_not_found(self, mock_get_conn):
        mock_bucket = mock_get_conn.return_value.get_bucket.return_value
        mock_bucket.get_key.return_value = None
        url = normalize_url('s3://bucket/path/to/key/compose_addons.yml')

        with pytest.raises(FetchExternalConfigError) as exc_context:
            get_project_from_s3(url)
        expected = "Failed to include %s: Not Found" % url.geturl()
        assert expected in str(exc_context.exconly())

    @mock.patch('compose_addons.includes.get_boto_conn', autospec=True)
    def test_get_project_from_s3_bucket_error(self, mock_get_conn):
        mock_get_bucket = mock_get_conn.return_value.get_bucket
        mock_get_bucket.side_effect = boto.exception.S3ResponseError(
            404, "Bucket Not Found")

        url = normalize_url('s3://bucket/path/to/key/fig.yml')
        with pytest.raises(FetchExternalConfigError) as exc_context:
            get_project_from_s3(url)

        expected = (
            "Failed to include %s: "
            "S3ResponseError: 404 Bucket Not Found" % url.geturl())
        assert expected in str(exc_context.exconly())


@pytest.fixture
def local_config(tmpdir):
    filename = tmpdir.join('fig.yml')

    filename.write("""
        web:
            image: example/web:latest
        db:
            image: example/db:latest
    """)
    return filename


class TestGetProjectFromFile(object):

    expected = {'web', 'db'}

    def test_fetch_from_file_relative_no_context(self, local_config):
        with local_config.dirpath().as_cwd():
            config = get_project_from_file(normalize_url(local_config.basename))
        assert set(config.keys()) == self.expected

    def test_fetch_from_file_relative_with_context(self, local_config):
        url = './' + local_config.basename
        with local_config.dirpath().as_cwd():
            config = get_project_from_file(normalize_url(url))
        assert set(config.keys()) == self.expected

    def test_fetch_from_file_absolute_path(self, local_config):
        config = get_project_from_file(normalize_url(str(local_config)))
        assert set(config.keys()) == self.expected

    def test_fetch_from_file_relative_with_scheme(self, local_config):
        url = 'file://./' + local_config.basename
        with local_config.dirpath().as_cwd():
            config = get_project_from_file(normalize_url(url))
        assert set(config.keys()) == self.expected

    def test_fetch_from_file_absolute_with_scheme(self, local_config):
        url = 'file://' + str(local_config)
        with local_config.dirpath().as_cwd():
            config = get_project_from_file(normalize_url(url))
        assert set(config.keys()) == self.expected


class TestFetchExternalConfig(object):

    def test_unsupported_scheme(self):
        with pytest.raises(ConfigError) as exc:
            fetch_external_config(normalize_url("bogus://something"), None)
        assert 'Unsupported url scheme "bogus"' in str(exc.exconly())

    def test_fetch_from_file(self, local_config):
        config = fetch_external_config(normalize_url(str(local_config)), None)
        assert set(config.keys()) == {'db', 'web'}


def test_config_cache():
    url, fetch_func = mock.Mock(), mock.Mock(return_value=dict(a=1))
    cache = ConfigCache(fetch_func)
    assert cache.get(url) == fetch_func.return_value
    assert cache.get(url) == fetch_func.return_value
    assert cache.get(url) is not fetch_func.return_value
    fetch_func.assert_called_once_with(url)


def test_merge_configs():
    result = includes.merge_configs(dict(a=1), [dict(b=2), dict(c=3, d=4)])
    assert result == dict(a=1, b=2, c=3, d=4)


def test_fetch_includes_no_includes():
    config = {'web': {'image': 'foo'}}
    assert includes.fetch_includes(config, {}) == []


def test_fetch_include_missing_namespace():
    url = 'http://example.com/project.yml'
    cache = mock.create_autospec(ConfigCache)
    cache.get.return_value = {}
    with pytest.raises(ConfigError) as exc:
        includes.fetch_include(cache, url)
    expected = "Configuration %s requires a namespace" % url
    assert expected in str(exc.exconly())


def test_fetch_include():
    url = 'http://example.com/project.yml'
    fetch_func = mock.Mock(side_effect=[
        {
            'namespace': 'a',
            'include': ['b', 'c'],
            'a.web': {'image': 'a', 'links': ['b.web', 'c.web', 'a.db']},
            'a.db': {'image': 'db'},
        },
        {
            'namespace': 'b',
            'include': ['c'],
            'b.web': {'image': 'b', 'links': ['c.web']},
        },
        {
            'namespace': 'c',
            'c.web': {'image': 'c'},
        },
    ])
    cache = ConfigCache(fetch_func)
    config = includes.fetch_include(cache, url)
    expected = {
        'a.web': {'image': 'a', 'links': ['b.web', 'c.web', 'a.db']},
        'a.db':  {'image': 'db'},
        'b.web': {'image': 'b', 'links': ['c.web']},
        'c.web': {'image': 'c'},
    }
    assert config == expected


@pytest.mark.acceptance
def test_include_end_to_end(tmpdir, capsys):
    tmpdir.join('docker-compose.yml').write("""
        include:
            - ./api_a/docker-compose.yml
            - ./api_b/docker-compose.yml
        namespace: core
        web:
            image: example/web:latest
            links: ['api_a.web', 'db', 'api_b.web']
            volumes_from: ['configs']
        db:
            image: example/db:latest
        configs:
            image: example/configs:latest
    """)
    tmpdir.mkdir('api_a').join('docker-compose.yml').write("""
        include:
            - ./api_b/docker-compose.yml
        namespace: api_a
        api_a.web:
            image: services/a:latest
            links: ['api_a.db', 'api_b.web']
        api_a.db:
            image: services/db_a:latest
    """)
    tmpdir.mkdir('api_b').join('docker-compose.yml').write("""
        namespace: api_b
        api_b.web:
            image: services/b:latest
    """)

    expected = {
        'web': {
            'image': 'example/web:latest',
            'links': ['api_a.web', 'db', 'api_b.web'],
            'volumes_from': ['configs'],
        },
        'db': {'image': 'example/db:latest'},
        'configs': {'image': 'example/configs:latest'},
        'api_a.web': {
            'image': 'services/a:latest',
            'links': ['api_a.db', 'api_b.web'],
        },
        'api_a.db': {'image': 'services/db_a:latest'},
        'api_b.web': {'image': 'services/b:latest'},
    }

    with tmpdir.as_cwd():
        includes.main(args=['docker-compose.yml'])
    out, err = capsys.readouterr()
    assert yaml.load(out) == expected
