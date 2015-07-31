"""Include external projects, allowing services to link to a service
defined in an external project.
"""
import argparse
import logging
import sys

import requests
import requests.exceptions
from six.moves.urllib.parse import urlparse
import yaml


from compose_addons import version

log = logging.getLogger(__name__)


class ConfigError(Exception):
    pass


class FetchExternalConfigError(ConfigError):
    pass


def normalize_url(url):
    url = urlparse(url)
    return url if url.scheme else url._replace(scheme='file')


def read_config(content):
    return yaml.safe_load(content)


def get_project_from_file(url):
    # Handle urls in the form file://./some/relative/path
    path = url.netloc + url.path if url.netloc.startswith('.') else url.path
    with open(path, 'r') as fh:
        return read_config(fh)


# TODO: integration test for this
def get_project_from_http(url, config):
    try:
        response = requests.get(
            url.geturl(),
            timeout=config.get('timeout', 20),
            verify=config.get('verify_ssl_cert', True),
            cert=config.get('ssl_cert', None),
            proxies=config.get('proxies', None))
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise FetchExternalConfigError("Failed to include %s: %s" % (
            url.geturl(), e))
    return read_config(response.text)


# Return the connection from a function, so it can be mocked in tests
def get_boto_conn():
    # Local import so that boto is only a dependency if it's used
    import boto.s3.connection
    return boto.s3.connection.S3Connection()


def get_project_from_s3(url):
    import boto.exception
    try:
        conn = get_boto_conn()
        bucket = conn.get_bucket(url.netloc)
    except (boto.exception.BotoServerError, boto.exception.BotoClientError) as e:
        raise FetchExternalConfigError(
            "Failed to include %s: %s" % (url.geturl(), e))

    key = bucket.get_key(url.path)
    if not key:
        raise FetchExternalConfigError(
            "Failed to include %s: Not Found" % url.geturl())

    return read_config(key.get_contents_as_string())


def fetch_external_config(url, fetch_config):
    log.info("Fetching config from %s" % url.geturl())

    if url.scheme in ('http', 'https'):
        return get_project_from_http(url, fetch_config)

    if url.scheme == 'file':
        return get_project_from_file(url)

    # TODO: pass fetch_config, for timeout
    if url.scheme == 's3':
        return get_project_from_s3(url)

    raise ConfigError("Unsupported url scheme \"%s\" for %s." % (
        url.scheme,
        url))


class ConfigCache(object):
    """Cache each config by url. Always return a new copy of the cached dict.
    """

    def __init__(self, fetch_func):
        self.cache = {}
        self.fetch_func = fetch_func

    def get(self, url):
        if url not in self.cache:
            self.cache[url] = self.fetch_func(url)
        return dict(self.cache[url])


def merge_configs(base, configs):
    for config in configs:
        base.update(config)
    return base


def fetch_includes(base_config, cache):
    return [fetch_include(cache, url) for url in base_config.pop('include', [])]


def fetch_include(cache, url):
    config = cache.get(normalize_url(url))

    namespace = config.pop('namespace', None)
    if not namespace:
        raise ConfigError("Configuration %s requires a namespace" % url)

    configs = fetch_includes(config, cache)
    # TODO: validate service config (no build, no host volumes, etc)
    # TODO: do I need namespacing?
    return merge_configs(config, configs)


def include(base_config, fetch_config):
    def fetch(url):
        return fetch_external_config(url, fetch_config)

    cache = ConfigCache(fetch)
    # TODO: pop namespace for base?
    return merge_configs(base_config, fetch_includes(base_config, cache))


def get_args(args=None):
    parser = argparse.ArgumentParser(
        description="Include remote compose configuration."
    )
    parser.add_argument('--version', action='version', version=version)
    parser.add_argument(
        'compose_file',
        type=argparse.FileType('r'),
        default=sys.stdin,
        help="Path to a docker-compose configuration with includes.")
    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'),
        default=sys.stdout,
        help="Output filename, defaults to stdout.")
    # TODO: separate argument group for fetch config args
    parser.add_argument(
        '--timeout',
        help="Timeout used when making network calls.",
        type=int)

    return parser.parse_args(args=args)


# TODO: other fetch config args
def build_fetch_config(args):
    return {
        'timeout': args.timeout,
    }


def main(args=None):
    args = get_args(args=args)
    config = include(read_config(args.compose_file), build_fetch_config(args))
    yaml.dump(
        config,
        stream=args.output,
        indent=4,
        width=80,
        default_flow_style=False)
