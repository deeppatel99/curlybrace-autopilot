"""Claude API calls: write -> review -> fix."""
from __future__ import annotations

import re

from . import prompts
from .config import Settings


class Writer:
    """Two ways to reach Claude (config.yaml -> writer.backend):

    claude-code  Uses the Claude Code CLI you are logged into with your Claude
                 Pro/Max subscription. No API key, no extra purchase — it counts
                 against your plan's usage limits.
    api          Uses an ANTHROPIC_API_KEY from console.anthropic.com
                 (pay-as-you-go, billed separately from Pro).
    """

    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.backend = cfg.get("writer.backend", "claude-code")
        self.max_tokens = int(cfg.get("writer.max_tokens", 32000))
        self.usage = {"input": 0, "output": 0, "usd": 0.0}
        if self.backend == "api":
            import anthropic

            key = cfg.secret("ANTHROPIC_API_KEY")
            if not key:
                raise SystemExit("ANTHROPIC_API_KEY missing — add it to .env, or set writer.backend: claude-code.")
            self.client = anthropic.Anthropic(api_key=key)
            self.model = cfg.get("writer.model", "claude-opus-5-5")
        else:
            self.claude = find_claude_cli()
            if not self.claude:
                raise SystemExit("Claude Code CLI not found. Install it (README step 2) and run `claude` once to log in, "
                                 "or set writer.backend: api.")
            self.model = cfg.get("writer.claude_code_model", "opus")

    # ------------------------------------------------------------------
    def _call(self, system: str, user: str, max_tokens: int | None = None) -> str:
        if self.backend != "api":
            return self._call_cli(system, user)
        # streaming keeps long generations from hitting HTTP timeouts
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            msg = stream.get_final_message()
        self.usage["input"] += msg.usage.input_tokens
        self.usage["output"] += msg.usage.output_tokens
        price = self.cfg.get("writer.price_per_mtok", {"input": 4, "output": 20})
        self.usage["usd"] += (msg.usage.input_tokens * price["input"] + msg.usage.output_tokens * price["output"]) / 1e6
        if msg.stop_reason == "max_tokens":
            print("  ! output hit max_tokens — raise writer.max_tokens in config.yaml")
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()

    def _call_cli(self, system: str, user: str) -> str:
        """claude -p in print mode: no tools, our own system prompt, prompt via stdin."""
        import json
        import os
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(system)
            sys_file = fh.name
        cmd = [self.claude, "-p",
               "--system-prompt-file", sys_file,
               "--tools", "",
               "--disallowedTools", "mcp__*",
               "--model", self.model,
               "--output-format", "json",
               "--no-session-persistence",
               "--max-turns", "3",
               # skip user-level plugins, hooks, CLAUDE.md and MCP servers so they can't leak into the article
               "--setting-sources", "project",
               "--strict-mcp-config"]
        fallback = self.cfg.get("writer.claude_code_fallback", "sonnet")
        if fallback and fallback != self.model:  # claude refuses a fallback equal to the main model
            cmd += ["--fallback-model", fallback]
        env = dict(os.environ)
        env.setdefault("CLAUDE_CODE_MAX_OUTPUT_TOKENS", str(self.max_tokens))
        tok = self.cfg.secret("CLAUDE_CODE_OAUTH_TOKEN")
        if tok:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = tok
        env.pop("ANTHROPIC_API_KEY", None)  # an API key in the env would override the subscription login
        try:
            proc = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                                  env=env, timeout=int(self.cfg.get("writer.timeout_sec", 1500)),
                                  cwd=tempfile.gettempdir())
        finally:
            try:
                os.remove(sys_file)
            except OSError:
                pass
        out = (proc.stdout or "").strip()
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            raise SystemExit(f"Claude Code returned no JSON (exit {proc.returncode}).\n"
                             f"stderr: {proc.stderr[-800:]}\nstdout: {out[-800:]}")
        if data.get("is_error") or proc.returncode != 0:
            raise SystemExit(f"Claude Code error: {data.get('result') or proc.stderr[-800:]}\n"
                             "If it says you are not logged in, run `claude` once in a terminal and log in "
                             "with your Claude Pro account. If you hit a usage limit, wait for it to reset.")
        u = data.get("usage") or {}
        self.usage["input"] += sum(int(u.get(k, 0) or 0) for k in
                                   ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        self.usage["output"] += int(u.get("output_tokens", 0))
        return str(data.get("result", "")).strip()

    def _fill(self, template: str) -> str:
        return (template
                .replace("{questions}", str(self.cfg.get("article.questions", 12)))
                .replace("{cta}", self.cfg.get("article.cta", "")))

    # ------------------------------------------------------------------
    def write(self, item: dict, next_topic: str | None) -> str:
        track = item.get("track", "")
        lead = (self.cfg.get("article.lead_tags", {}) or {}).get(track, track or "Dotnet")
        user = prompts.WRITER_USER.format(
            topic=item["topic"],
            track=track or "general .NET",
            lead_tag=lead,
            kicker=item.get("kicker") or self.cfg.get("article.default_kicker", "Interview Ready"),
            notes=item.get("notes") or "none",
            next_topic=next_topic or "not decided yet — tease the broader series instead",
        )
        return _strip_wrapper(self._call(self._fill(prompts.WRITER_SYSTEM), user))

    def plan_topics(self, covered: list[str], n: int = 5) -> list[dict]:
        import json as _json

        user = (f"Already covered (do not repeat):\n- " + "\n- ".join(covered or ["(none)"]) +
                f"\n\nPropose the next {n} topics, best first.")
        raw = self._call(prompts.TOPIC_SYSTEM, user, max_tokens=3000)
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        start, end = raw.find("["), raw.rfind("]")
        items = _json.loads(raw[start:end + 1])
        return [{"topic": i["topic"], "track": i.get("track", ""), "notes": i.get("notes", ""),
                 "kicker": self.cfg.get("article.default_kicker", "Interview Ready") + " · Deep Dive",
                 "status": "pending", "auto": True} for i in items if i.get("topic")]

    def review(self, article_md: str) -> str:
        return self._call(self._fill(prompts.REVIEWER_SYSTEM),
                          "Review this article:\n\n" + article_md, max_tokens=8000)

    def fix(self, article_md: str, review_md: str) -> str:
        user = f"ARTICLE:\n\n{article_md}\n\nREVIEW ISSUES:\n\n{review_md}"
        return _strip_wrapper(self._call(self._fill(prompts.FIXER_SYSTEM), user))

    def fix_json(self, broken: str, error: str) -> str:
        return self._call(prompts.JSON_FIX_SYSTEM, f"Error: {error}\n\n{broken}", max_tokens=4000)

    def cost_estimate(self) -> str:
        toks = f"{self.usage['input']:,} in / {self.usage['output']:,} out tokens"
        if self.backend == "api":
            return f"{toks} ≈ ${self.usage['usd']:.2f}"
        return f"{toks} (Claude subscription — no extra charge)"


def find_claude_cli() -> str | None:
    import shutil
    from pathlib import Path

    for name in ("claude", "claude.cmd", "claude.exe"):
        p = shutil.which(name)
        if p:
            return p
    for p in (Path.home() / ".local" / "bin" / "claude.exe", Path.home() / ".local" / "bin" / "claude",
              Path.home() / "AppData" / "Roaming" / "npm" / "claude.cmd"):
        if p.exists():
            return str(p)
    return None


def _strip_wrapper(text: str) -> str:
    """Remove an accidental ```markdown fence around the whole document."""
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", text, re.S)
    text = m.group(1) if m else text
    fm = re.search(r"^---\s*\n(?:title|subtitle|slug|tags):", text, re.M)
    return text[fm.start():] if fm else text
