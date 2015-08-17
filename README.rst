
docker-compose addons
=====================

A set of command line tools to supplement the features already available
in docker-compose. These tools generally focus on development or testing
environment use-cases.

.. image:: https://img.shields.io/pypi/v/compose-addons.svg
    :target: https://pypi.python.org/pypi/compose-addons
    :alt: Latest PyPI version

.. image:: https://travis-ci.org/dnephin/compose-addons.svg?branch=master
    :target: https://travis-ci.org/dnephin/compose-addons
    :alt: Travis CI


.. contents::
    :backlinks: none


Install
-------

Currently the only install option is pip

.. code:: sh

    pip install compose-addons


dcao-include
------------

Given a docker-compose.yml file, fetch each configuration in the include
section and merge it into a base docker-compose.yml. If any of the included
files have include sections continue to fetch and merge each of them until
there are no more files to include.

Use Cases
~~~~~~~~~

- If you have a service-oriented architecture, where each of your services
  is developed and deployed in a separate code repo, and each has its own
  docker-compose.yml. When you want to create a full testing or development
  environment for an individual service, you need to include all the
  downstream services. Instead of duplicating the topology of each
  downstream service, you can include the ``docker-compose.yml`` from the
  downstream service. Including (instead of duplicating) this topology
  allows you to change dependencies in a single place without worrying
  about breaking the test suite of dependent services.
- If the scope of your composition can change based on the task you're
  performing. Your application might have a "core" set of services that are
  always run, and some adhoc, or administrative services that are only run
  sometimes. You can split your composition into two (or more) files.
  The core ``docker-compose.yml`` would only contain the core services. The
  ``compose-admin.yml`` would include the ``docker-compose.yml`` and add
  extra services which could link to or use volumes from the core services,
  without having to duplicate any of the service configuration.
- If your composition varies by environment (dev vs prod). Similar to the
  case above, the core ``docker-compose.yml`` would remain the same for all
  environments, but ``docker-compose-dev.yml`` could include the "core"
  services, and add additional service, like database or proxies.

Working with Includes
~~~~~~~~~~~~~~~~~~~~~

``dcao-include`` works with a configuration that is different from the
``docker-compose`` config in a few ways:

- an optional top level ``include`` key, which contains a list of urls (which
  may be local file paths, http(s) urls, or s3 paths)
- a required top level ``namespace`` key, which is used by a config to link
  to services in an included file. For example, if a config includes
  http://example.com/compositions/servicea.yaml which has a ``namespace``
  of ``servicea``, all "public" services in ``servicea.yaml`` should start
  with ``servicea.``.
- since configuration can be included from a remote url, or different
  directories, the configuration should not include anything that depends
  on the host. There should be no ``build`` keys in any service, and no
  host volumes.

Example
~~~~~~~

An example composition file with includes:

.. code:: yaml

    include:
        - http://example.com/compositions/servicea.yaml
        - http://example.com/compositions/serviceb.yaml

    namespace: core

    web:
        image: example/service_a:latest
        links: ['servicea.web', 'serviceb.api']

**servicea.yaml** might look something like this

.. code:: yaml

    namespace: servicea

    servicea.web:
        image: services/a:latest

**serviceb.yaml** might look something like this

.. code:: yaml

    namespace: serviceb

    serviceb.api:
        image: services/b:latest

Usage
~~~~~

To use ``dcao-include`` with ``docker-compose`` you have a couple options:

Use it with a pipe to stdin:

.. code:: sh

    dcao-include compose-with-includes.yml | docker-compose -f - up -d


Use it once to generate a new file:

.. code:: sh

    dcao-include -o docker-compose.yml compose-with-includes.yml
    docker-compose up -d
    docker-compose ps


dcao-namespace
--------------

Given a standard ``docker-compose.yml`` file, add a namespace key, and prefix
all instances of service names with that namespace. This command is used to
prepare a standard ``docker-compose.yml`` file for being used as an include
by ``dcao-include``. This could be considered the "export" step required
before a compose file can be included by another project.


Example
~~~~~~~

Given a ``docker-compose.yml``:

.. code:: yaml

    web:
        image: example.com/web:latest
        links: ['db']
        volumes_from: ['configs']
    db:
        image: example.com/db:latest
    configs:
        image: example.com/configs:latest

running ``dcao-namespace docker-compose.yml myservice`` would produce

.. code:: yaml

    namespace: myservice
    myservice.web:
        image: example.com/web:latest
        links: ['myservice.db:db']
        volumes_from: ['myservice.configs']
    myservice.db:
        image: example.com/db:latest
    myservice.configs:
        image: example.com/configs:latest


Usage
~~~~~

First generate the namespaced config

.. code:: sh

    dcao-namespace -o myservice.yml docker-compose.yml myservice

Next you'll want to make ``myservice.yml`` available to other services. In this
example we'll assume we're using an s3 bucket

.. code:: sh

    aws s3 cp myservice.yml s3://some-bucket/compose-registry/myservice.yml


Now we can use that configuration as an include in another service. In a
different services ``compose-with-includes.yml`` (which will be consumed by
``dcao-include``)

.. code:: sh

    include:
        - s3://some-bucket/compose-registry/myservice.yml


dcao-merge
----------

Merge ``docker-compose.yml`` configuration files by overriding values in the
base configuration with values from other files. It is used to transform a
configuration without having to duplicate any fields that should remain
consistent.

Use Cases
~~~~~~~~~

- Often in development you'll want to include code using a volume for faster
  iteration, but for testing on a CI you want to include the source in the
  container with ``ADD`` (or ``COPY``). You could use an ``overrides-dev.yml`` to add
  volumes to the configuration, and skip that step during CI.
- If the composition is running on a shared host each developer needs to use a
  different host port. This variation can be included in a file maintained by
  each developer outside of version control.
- If a ``docker-compose.yml`` contains ``build`` directives for local
  development, but needs ``image`` directives in other environments (testing,
  stage, prod, etc), merge can be used to rewrite ``build`` to ``image`` with
  the correct image tag.


Usage
~~~~~

To rewrite a configuration to use image instead of build, and remove any host
specific configuration:

.. code:: sh

    dcao-merge -o export.yml docker-compose.yml compose-overrides.yml

Where ``docker-compose.yml`` is:

.. code:: yaml

    web:
        build: .
        links: ['db']
        volumes: ['./logs:/app/logs']
    db:
        build: database/

and ``compose-overrides.yml``:

.. code:: yaml

    web:
        image: example.com/web:latest
        volumes: []
    db:
        image: example.com/db:latest

would produce an ``export.yml``

.. code:: yaml

    web:
        image: example.com/web:latest
        links: ['db']
        volumes: []
    db:
        image: example.com/db:latest
