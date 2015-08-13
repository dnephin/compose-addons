"""
Merge a yaml configuration file with others to produce a single configuration.

May be used to override a default configuration with temporary or local
configuration options.

Example:

From a base configuration, expose volumes and use a different image for
debugging.

**base.yml**

.. code-block:: yaml

    web:
        build: .
        links:
            - db
            - serviceb

    db:
        build: database/

    serviceb:
        image: example.com/services_b:latest

**overrides.yml**

.. code-block:: yaml

    web:
        volumes:
            - '.:/code'

    serviceb:
        image: my_version_of_service_b:abf4a


Run:

.. code-block:: sh


    $ fig-merge base.yml overrides.yml > fig.yml


**fig.yml** would contain:


.. code-block:: yaml

    web:
        build: .
        links:
            - db
            - serviceb
        volumes:
            - '.:/code'

    db:
        build: database/

    serviceb:
        image: my_version_of_service_b:abf4a
"""
import argparse
import sys

import yaml


def deep_merge(base, override):
    def merge(base, override):
        for key in set(base) | set(override):
            value = override.get(key, base.get(key))
            if isinstance(value, dict):
                yield key, dict(merge(
                    base.get(key) or {},
                    override.get(key) or {}))
            else:
                yield key, value

    return dict(merge(base, override))


def merge_config(base, override):
    for name, service in base.items():
        if 'build' in service and 'image' in override.get(name, {}):
            service.pop('build')
        if 'image' in service and 'build' in override.get(name, {}):
            service.pop('image')
    return deep_merge(base, override)


def merge_files(base, overrides, output):
    base = yaml.load(base)
    for override in overrides:
        base = merge_config(base, yaml.load(override))

    yaml.dump(base, output, default_flow_style=False, width=80, indent=4)


def parse_args(args):
    parser = argparse.ArgumentParser(description='Merge configuration files.')
    parser.add_argument(
        'base',
        type=argparse.FileType('r'),
        help="Base configuration file.")
    parser.add_argument(
        'files',
        type=argparse.FileType('r'),
        nargs="+",
        help="Files to merge onto the base.")
    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'),
        default=sys.stdout,
        help="Output file, defaults to stdout.")
    return parser.parse_args(args=args)


def main(args=None):
    args = parse_args(args)
    merge_files(args.base, args.files, args.output)


if __name__ == "__main__":
    main()
