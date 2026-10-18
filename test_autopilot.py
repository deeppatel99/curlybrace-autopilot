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

print("ok")
