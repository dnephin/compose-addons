"""Namespace services in a docker-compose.yml so they can be used as an include.

Service names, links, net, and volumes from are updated to include a prefix
and a ``namespace`` key is added to the configuration with this prefix.
"""
import argparse
import sys
from functools import partial

from compose_addons import version
from compose_addons.config_utils import read_config, write_config


def add_namespace(config, namespace):
    service_names = set(config)
    prefix = namespace + '.'

    def add_to_service(name, service_config):
        namespace_links(service_config, prefix, service_names)
        namespace_volumes_from(service_config, prefix, service_names)
        namespace_net(service_config, prefix, service_names)
        return prefix + name, service_config

    config = dict(
        add_to_service(service, conf)
        for service, conf in config.items()
    )
    config['namespace'] = namespace
    return config


def namespace_volumes_from(service, namespace, service_names):
    def namespace_each(service):
        if service not in service_names:
            return service
        return namespace + service

    set_field(service, 'volumes_from', partial(list_map, namespace_each))


def namespace_links(service, namespace, service_names):
    def namespace_link(link):
        service, alias = parse_field(link, 2)
        alias = alias or service
        if service not in service_names:
            return link
        return '%s:%s' % (namespace + service, alias)

    set_field(service, 'links', partial(list_map, namespace_link))


def namespace_net(service, namespace, service_names):
    def namespace_field(value):
        type, name = parse_field(value, 2)
        if type != 'container' or name not in service_names:
            return value
        return 'container:' + namespace + name

    set_field(service, 'net', namespace_field)


def list_map(func, seq):
    return list(map(func, seq))


def set_field(service, field, partial_func):
    if field not in service:
        return
    service[field] = partial_func(service[field])


def parse_field(field, length):
    parts = field.split(':', length - 1)
    return parts + [None] * (length - len(parts))


def get_args(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=version)
    parser.add_argument(
        'compose_file',
        type=argparse.FileType('r'),
        default=sys.stdin,
        help="Path to a docker-compose configuration to namespace.")
    parser.add_argument(
        'namespace',
        help="Namespace to add to all service names.")
    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'),
        default=sys.stdout,
        help="Output filename, defaults to stdout.")

    return parser.parse_args(args=args)


def main(args=None):
    args = get_args(args=args)
    config = add_namespace(read_config(args.compose_file), args.namespace)
    write_config(config, args.output)
