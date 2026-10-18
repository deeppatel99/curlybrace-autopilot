"""python test_autopilot.py — checks Medium paste shaping and the next-run date in the Telegram update."""
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from autopilot.pipeline import next_run
from autopilot.publish import for_medium_paste

out = for_medium_paste('<pre><code class="language-csharp">using X;\n\nvar a = 1;\n    b();\n</code></pre>')
assert out == "<pre>using X;<br>&nbsp;<br>var a = 1;<br>    b();</pre>", out

out = for_medium_paste("<blockquote>\n<p>One.</p>\n<p>Two.</p>\n</blockquote>\n<p>after</p>")
assert out == "<blockquote>One.<br>Two.</blockquote>\n<p>after</p>", out

with tempfile.TemporaryDirectory() as d:
    wf = Path(d) / "autopilot.yml"
    sun = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)  # Sunday 18 Oct, 21:30 IST
    wf.write_text('    - cron: "30 3 * * 1"\n')            # Mondays 09:00 IST
    assert next_run(wf, sun) == "Mon 19 Oct, 09:00 AM IST", next_run(wf, sun)
    mon_after = datetime(2026, 10, 19, 4, 0, tzinfo=timezone.utc)  # just after Monday's run
    assert next_run(wf, mon_after) == "Mon 26 Oct, 09:00 AM IST", next_run(wf, mon_after)
    wf.write_text('    - cron: "0 17 * * 4,6"\n')          # Thu/Sat 22:30 IST
    assert next_run(wf, sun) == "Thu 22 Oct, 10:30 PM IST", next_run(wf, sun)
    wf.write_text('    - cron: "*/5 * * * *"\n')           # not a simple schedule -> no date
    assert next_run(wf, sun) is None

# ── article formats ───────────────────────────────────────────────────────
import re  # noqa: E402

from autopilot import config  # noqa: E402
from autopilot import prompts  # noqa: E402
from autopilot.article import Asset, Article, validate  # noqa: E402
from autopilot.writer import cta_for, fill  # noqa: E402

cfg = config.load()


def art(fmt, body, n_assets=5):
    assets = [Asset(index=i + 1, spec={"type": "cover" if i == 0 else "table"}) for i in range(n_assets)]
    return Article("T", "S", "t", ["A", "B", "C", "D", "E"], body, fmt, assets)


cta = cta_for(cfg, "deep-dive")
deep = art("deep-dive", "word " * 1800 + cta)
assert validate(deep, cfg) == [], validate(deep, cfg)                       # no question rules for a deep dive
assert any("words" in w for w in validate(art("deep-dive", "word " * 300 + cta), cfg))   # too short is flagged

q = ("## Q{n}. Why?\n**What they're actually testing:** x\n**The analogy:** x\n**Say this in the interview:**\n> x\n"
     "**The trap / follow-up:** x\n**Memory hook:** *x*\n---\n")
icta = cta_for(cfg, "interview")
interview = art("interview", "".join(q.format(n=n) for n in range(1, 8)) + "word " * 2600 + "\n## Self-Check\n" + icta, 6)
assert validate(interview, cfg) == [], validate(interview, cfg)            # 7 questions is fine, not forced to 12
three = art("interview", "".join(q.format(n=n) for n in range(1, 4)) + "word " * 2600 + "\n## Self-Check\n" + icta, 6)
assert any("3 questions" in w for w in validate(three, cfg))
assert icta != cta                                                          # interview keeps its own CTA

for name, spec in prompts.FORMATS.items():                                 # every slot gets filled
    s = fill(prompts.WRITER_BASE, research=prompts.RESEARCH_ON, format=name, guide=spec["guide"], cta=cta,
             words_min=1, words_max=2, visuals_min=1, visuals_max=2, published="- x")
    left = set(re.findall(r"\{(research|format|guide|cta|words_min|words_max|visuals_min|visuals_max|published)\}", s))
    assert not left, (name, left)

# ── Medium export import: stories in, replies and drafts out ──────────────────
from autopilot.published import import_export  # noqa: E402

page = ('<h1 class="p-name">{t}</h1><section data-field="subtitle">Sub</section>'
        '<section data-field="body">{b}</section><a href="https://medium.com/@x/{t}" class="p-canonical">c</a>')
with tempfile.TemporaryDirectory() as d:
    (Path(d) / "posts").mkdir()
    (Path(d) / "posts" / "2026-06-07_story.html").write_text(page.format(t="Story", b="word " * 600), encoding="utf-8")
    (Path(d) / "posts" / "2026-06-08_reply.html").write_text(page.format(t="Reply", b="Thanks!"), encoding="utf-8")
    (Path(d) / "posts" / "draft_x.html").write_text(page.format(t="Draft", b="word " * 900), encoding="utf-8")
    got = import_export(Path(d))
    assert got == [{"date": "2026-06-07", "title": "Story", "subtitle": "Sub", "url": "https://medium.com/@x/Story"}], got

print("ok")
