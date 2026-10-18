"""python test_paste.py — checks the Medium paste HTML shaping (code blocks + quotes)."""
from autopilot.publish import for_medium_paste

out = for_medium_paste('<pre><code class="language-csharp">using X;\n\nvar a = 1;\n    b();\n</code></pre>')
assert out == "<pre>using X;<br>&nbsp;<br>var a = 1;<br>    b();</pre>", out

out = for_medium_paste("<blockquote>\n<p>One.</p>\n<p>Two.</p>\n</blockquote>\n<p>after</p>")
assert out == "<blockquote>One.<br>Two.</blockquote>\n<p>after</p>", out

print("ok")
