"""Shared paths and config loading for the Momoka fork.

The whole project is small enough that this is the only place that knows where
the root sits. Every other module takes a config dict from here.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")


def load_config(path=None):
    with open(path or CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def root_path(*parts):
    return os.path.join(ROOT, *parts)


def resolve(path):
    """A config path as an absolute path, relative ones taken from the root."""
    if not path:
        return path
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def read_text(path):
    with open(resolve(path), encoding="utf-8") as f:
        return f.read()


def system_prompt(cfg, extra=""):
    """Her bible and her speech guide, plus whatever extra the caller adds."""
    p = cfg["prompt"]
    bible = read_text(os.path.join(p["dir"], p["bible"]))
    style = read_text(os.path.join(p["dir"], p["style"]))
    head = (bible.rstrip() + "\n\n---\n\n" + style.rstrip())
    return head + ("\n\n---\n\n" + extra.rstrip() if extra else "")
