import yaml


def read_config(content):
    return yaml.safe_load(content)


def write_config(config, target):
    yaml.dump(
        config,
        stream=target,
        indent=4,
        width=80,
        default_flow_style=False)
