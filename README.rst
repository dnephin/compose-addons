
docker-compose addons
=====================

A set of command line tools to supplement the features already available
in docker-compose. These tools generally focus on development or testing
environment use-cases.


.. contents::
    :backlinks: none


Install
-------

Currently the only install option is pip with git url


.. code:: sh

    pip install git+https://github.com/dnephin/compose-addons.git


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


dcao-merge
----------

Merge ``docker-compose.yml`` configuration files by overriding values in the
base configuration with values from other files.

Use Cases
~~~~~~~~~

- Often in development you'll want to include code using a volume for faster
  iteration, but for testing on a CI you want to include the source in the
  container with ``ADD``. You could use an ``overrides-dev.yml`` to add
  volumes to the configuration.
- If the composition is running on a shared host each developer needs to use a
  different host port. This variation can be included in a file maintained by
  each developer, separate from the source repo.
