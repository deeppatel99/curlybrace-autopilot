# The Curly Brace — Medium Autopilot

An AI agent that writes, illustrates and posts articles to
[medium.com/@thecurlybrace](https://medium.com/@thecurlybrace), with no copy-pasting and no image downloads.

```
topics/queue.yaml ─► Claude writes ─► Claude reviews ─► fixes applied
                                                         │
             Medium draft ◄── images hosted on GitHub ◄── branded PNGs + GIFs rendered
                 │
          you review → Publish
```

Each run produces one article in the Interview Ready format: a production-failure hook,
12 questions (testing → analogy → code → say this → trap → memory hook), 3–4 table images,
2–3 diagrams, 2 animated GIFs, a 60-second revision sheet, a self-check, a teaser and the fixed CTA.

---

## 1. One-time setup (Windows)

1. Install **Python 3.11+** from python.org and tick **"Add python.exe to PATH"**.
2. Install **Claude Code**, which is the writer. It runs on your Claude Pro login, so you
   don't need an API key and there's no extra bill. Open PowerShell and run:

   ```
   irm https://claude.ai/install.ps1 | iex
   ```

   Close and reopen the terminal, type `claude`, choose **Claude account** login, sign in with
   your Pro account, then type `/exit`. You only do this once.
3. Double-click **`setup.bat`**. It creates `.venv`, installs the packages, creates `.env` and
   copies `ci/autopilot.yml` into `.github/workflows/` for the scheduled GitHub run.
4. Open `.env` in Notepad and paste your GitHub token (`GH_PAT`, see next section).
5. In this folder, open a terminal and run:

   ```
   run check
   ```

   Every line should say `ok`.

## 2. Keys

| Key | Where to get it | Needed? |
|---|---|---|
| Claude Pro login | Step 2 above | **Yes**. Articles count against your Pro usage limits. |
| `GH_PAT` | GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate → Repository access: *Only select repositories* → `curlybrace-autopilot` → Permissions → **Contents: Read and write** | **Yes**, for image hosting |
| `MEDIUM_TOKEN` | Medium → profile picture → Settings → **Security and apps** → Integration tokens | Only for `mode: api` (many accounts no longer have this option) |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Only if you set `writer.backend: api` (paid separately from Pro) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | @BotFather | Optional ping when a draft is ready |

**The GitHub repo must be public**, so Medium can fetch the images.

## 3. Choose how the article reaches Medium

Set `publish.mode` in `config.yaml`:

| Mode | What happens | Your manual work |
|---|---|---|
| `local` (default) | Builds `paste.html` with publicly hosted images and opens it next to a blank Medium story | Ctrl+A → Ctrl+C in paste.html → Ctrl+V in Medium → delete the yellow note → add tags → Publish |
| `import` | Builds a hosted HTML page; you paste its URL into medium.com/p/import | 1 paste + Publish. Needs GitHub Pages on (Settings → Pages → Deploy from branch `main`). Medium adds a canonical link to that page. |
| `api` | Creates a **draft** on Medium through the API | Open draft → read → Publish |

Medium stopped giving out **new** integration tokens, so `api` only works if your account still
shows the Integration tokens section. Everything before the Medium step is automatic in every mode.

`publish.status` (api mode) is `draft` by default. Keep it that way: one wrong code sample costs
more credibility than the 5 minutes a review takes.

## 4. Daily use

```
run next                                    take the next topic from topics/queue.yaml
run topic "Span<T> and Memory<T>" --track csharp
run add "Polly v8 resilience pipelines" --track aspnetcore    add to the queue
run file samples\sample-article.md --dry-run                  render only, upload nothing
```

Output for every run goes to `out\<date>-<slug>\`:

- `images\`: every PNG and GIF
- `preview.html`: local review copy
- `article.md`: final markdown
- `review.md`: your checklist, format checks, and the AI reviewer's fact-check notes

The same `article.md` and `review.md` are also saved in the GitHub repo under `posts/<slug>/`.

## 4b. How the next topic is chosen

`run next` takes the first `pending` topic in `topics/queue.yaml`. When fewer than 2 are left,
Claude plans 5 new ones on its own, avoiding everything already done and the series listed under
`topics.already_published` in `config.yaml`, and adds them to the queue. You can still add your
own topics at any time with `run add "..." --track ...`, or by editing the file. Put a real
production incident in `notes` and the article opens with it.

## 5. Run it on a schedule

**Option A: GitHub Actions (recommended, your PC can stay off)**

1. Push this folder to the public repo (`.env` is git-ignored and never pushed).
2. On your PC run `claude setup-token`, which prints a long-lived token for your Pro subscription.
   Repo → Settings → Secrets and variables → Actions → add it as `CLAUDE_CODE_OAUTH_TOKEN`
   (plus `MEDIUM_TOKEN` and the Telegram keys if you use them). You do not need `GH_PAT` here,
   because Actions provides its own token.
3. Repo → Settings → Actions → General → Workflow permissions → **Read and write**.
4. Repo → Settings → Pages → Source: **Deploy from a branch** → `main` / root. This makes each
   run's `paste.html` open as a web page, so you can paste from any PC. These pages are marked
   noindex, so Google won't treat them as duplicates of your Medium article.
5. It runs every Monday at 09:00 IST. To change that, edit `cron` in
   `.github/workflows/autopilot.yml`. To run it now, go to Actions → Curly Brace autopilot → **Run workflow**.

**Option B: Windows Task Scheduler (runs on your PC)**

```
schtasks /create /tn "CurlyBraceAutopilot" /sc weekly /d MON /st 09:00 /tr "\"%CD%\run.bat\" next"
```

## 6. Make it yours

| Want to change | Edit |
|---|---|
| Voice, article structure, number of questions | `autopilot/prompts.py`, `config.yaml → article` |
| Colours, fonts, layouts of the images | `autopilot/design.py`. To use your own `build_cover_v2()`, swap it into `render_cover` |
| Model / cost | `config.yaml → writer.claude_code_model` (or `writer.model` for the API backend) |
| What gets written next | `topics/queue.yaml` |

## 7. Cost

- **Default (`writer.backend: claude-code`): ₹0 extra.** Each article uses three Claude calls
  (write, review, fix) from your Pro plan's usage limits. If you hit the limit, wait for the reset
  or set `claude_code_model: sonnet`, which uses less.
- `writer.backend: api`: about $0.50–$1.50 per article with Opus 5.5, billed separately on
  console.anthropic.com.
- GitHub hosting and Actions are free for a public repo.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `Claude Code CLI not found` | Do step 2, then reopen the terminal. |
| `not logged in` / usage limit | Run `claude` once and log in with your Pro account. On a limit, wait for the reset. |
| Broken images in the Medium draft | Repo is private, or the images were still propagating. Make it public and rerun. |
| `Medium token rejected` | Switch `publish.mode` to `import` or `local`. |
| `Expected 12 questions, found 11` in review.md | The writer slipped. Fix it in the draft or rerun `run topic ...`. |
| Asset skipped (invalid JSON) | Rare. The JSON is repaired automatically once, and anything still broken is listed in review.md. |
| Only 3 tags on the draft | Older API integrations keep only the first 3. Add the other 2 in the editor. |

Fonts: Inter and JetBrains Mono, both under the SIL Open Font License.
