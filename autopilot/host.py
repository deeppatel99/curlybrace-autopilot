"""Host images (and archive copies) in a public GitHub repo via the Contents API.

No git clone needed — works the same on your laptop and in GitHub Actions.
Every uploaded file gets a public URL Medium can pull images from.
"""
from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

API = "https://api.github.com"


class GitHubHost:
    def __init__(self, cfg):
        self.token = cfg.secret("GH_PAT") or cfg.secret("GITHUB_TOKEN")
        self.repo = cfg.get("hosting.repo")
        self.branch = cfg.get("hosting.branch", "main")
        self.folder = cfg.get("hosting.folder", "posts").strip("/")
        self.url_style = cfg.get("hosting.url_style", "raw")
        self.pages_base = (cfg.get("hosting.pages_base_url") or "").rstrip("/")
        if not self.token or not self.repo:
            raise SystemExit("Hosting needs hosting.repo in config.yaml and GH_PAT (or GITHUB_TOKEN) in .env.")
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    # ------------------------------------------------------------------
    def check(self) -> str:
        r = self.s.get(f"{API}/repos/{self.repo}", timeout=30)
        if r.status_code != 200:
            raise SystemExit(f"GitHub: cannot access {self.repo} ({r.status_code}) {r.text[:200]}")
        j = r.json()
        if j.get("private"):
            return f"{self.repo} is PRIVATE — Medium cannot fetch images from it. Make it public."
        if not j.get("permissions", {}).get("push", True):
            return f"Token has no write access to {self.repo}."
        return f"ok ({self.repo}, public)"

    def remote_path(self, slug: str, name: str) -> str:
        return f"{self.folder}/{slug}/{name}"

    def public_url(self, path: str) -> str:
        if self.url_style == "jsdelivr":
            return f"https://cdn.jsdelivr.net/gh/{self.repo}@{self.branch}/{path}"
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/{path}"

    def pages_url(self, path: str) -> str:
        if self.pages_base:
            return f"{self.pages_base}/{path}"
        owner, name = self.repo.split("/")
        if name.lower() == f"{owner.lower()}.github.io":
            return f"https://{owner}.github.io/{path}"
        return f"https://{owner}.github.io/{name}/{path}"

    def upload(self, local: Path | None, path: str, message: str, content: bytes | None = None) -> str:
        data = content if content is not None else Path(local).read_bytes()
        url = f"{API}/repos/{self.repo}/contents/{path}"
        sha = None
        r = self.s.get(url, params={"ref": self.branch}, timeout=30)
        if r.status_code == 200:
            sha = r.json().get("sha")
        body = {"message": message, "content": base64.b64encode(data).decode(), "branch": self.branch}
        if sha:
            body["sha"] = sha
        for attempt in range(3):
            r = self.s.put(url, json=body, timeout=120)
            if r.status_code in (200, 201):
                return self.public_url(path)
            if r.status_code in (409, 422, 502, 503) and attempt < 2:
                time.sleep(2 + attempt * 3)
                continue
            raise SystemExit(f"GitHub upload failed for {path}: {r.status_code} {r.text[:300]}")
        return self.public_url(path)

    def wait_until_live(self, url: str, timeout: int = 90) -> bool:
        """raw.githubusercontent can lag a few seconds after a commit."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                if requests.head(url, timeout=15, allow_redirects=True).status_code == 200:
                    return True
            except requests.RequestException:
                pass
            time.sleep(4)
        return False
