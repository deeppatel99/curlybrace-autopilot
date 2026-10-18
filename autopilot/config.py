"""Loads config.yaml + .env into one simple object."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    raw: dict
    root: Path = ROOT
    secrets: dict = field(default_factory=dict)

    # convenience accessors -------------------------------------------------
    def get(self, dotted: str, default=None):
        node = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def secret(self, name: str) -> str | None:
        v = self.secrets.get(name) or os.environ.get(name)
        return v.strip() if v else None

    @property
    def out_dir(self) -> Path:
        return self.root / self.get("output_dir", "out")

    @property
    def queue_file(self) -> Path:
        return self.root / self.get("queue_file", "topics/queue.yaml")


def load(config_path: str | Path | None = None) -> Settings:
    try:
        from dotenv import dotenv_values
        secrets = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v}
    except Exception:
        secrets = {}
    path = Path(config_path) if config_path else ROOT / "config.yaml"
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return Settings(raw=raw, secrets=secrets)
