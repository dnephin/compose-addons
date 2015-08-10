from setuptools import setup

from compose_addons import version

setup(
    name="compose-addons",
    version=version,
    provides=["compose_addons"],
    author="Daniel Nephin",
    author_email="dnephin@gmail.com",
    url="http://github.com/dnephin/compose-addons",
    description='Tools to supplement',
    classifiers=[
        "Programming Language :: Python",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Apache Software License",
        "Intended Audience :: Developers",
    ],
    license="Apache License 2.0",
    packages=['compose_addons'],
    install_requires=[
        'requests',
        'docker-py',
        'six',
        'pyyaml',
    ],
    extras_require={
        's3': ['boto'],
    },
    entry_points={
        'console_scripts': [
            'dcao-include = compose_addons.includes:main'
        ],
    },
)
