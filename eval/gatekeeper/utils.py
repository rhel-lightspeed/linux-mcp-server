import yaml


# Use block style (|) for multi-line strings instead of inline quoting
class BlockStyleDumper(yaml.SafeDumper):
    pass


def _str_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


BlockStyleDumper.add_representer(str, _str_representer)
