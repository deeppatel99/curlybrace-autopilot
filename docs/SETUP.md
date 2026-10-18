# Setup and operations guide

Everything you need to run Curly Brace Autopilot yourself: installation, keys, the weekly GitHub Actions run, the Telegram bot, configuration and troubleshooting. For an overview of what the project does, start with the [README](../README.md).

- [1. Install](#1-install)
- [2. Keys and secrets](#2-keys-and-secrets)
- [3. Verify](#3-verify)
- [4. Run it every week with GitHub Actions](#4-run-it-every-week-with-github-actions)
- [5. Telegram updates](#5-telegram-updates)
- [6. How articles reach Medium](#6-how-articles-reach-medium)
- [7. Everyday commands](#7-everyday-commands)
- [8. Topic queue](#8-topic-queue)
- [9. Configuration reference](#9-configuration-reference)
- [10. Customising](#10-customising)
- [11. Cost](#11-cost)
- [12. Troubleshooting](#12-troubleshooting)

## 1. Install

### Prerequisites

| Requirement | Notes |
|---|---|
| Python **3.11 to 3.14** | Python 3.15 is too new: PyYAML and Pillow have no prebuilt wheels for it yet, so installing needs a C compiler. |
| [Claude Code](https://claude.com/claude-code) | The writer. Signed in with a Claude Pro or Max account, so no API key is needed. |
| A **public** GitHub repository | Hosts the images. It must be public so Medium can fetch them. |

### Install Claude Code and sign in

```powershell
# Windows (PowerShell)
irm https://claude.ai/install.ps1 | iex
```

```bash
# macOS / Linux
curl -fsSL https://claude.ai/install.sh | bash
```

Open a new terminal, run `claude`, choose **Claude account**, sign in, then type `/exit`.

### Install the project

**Windows:** double-click `setup.bat`. It picks Python 3.14, 3.13, 3.12 or 3.11 (in that order), creates `.venv`, installs the dependencies, creates `.env` from `.env.example` and puts the workflow file in `.github/workflows/`.

**macOS / Linux:**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Commands in this guide use the Windows form `run <command>`. On macOS and Linux, use `.venv/bin/python run.py <command>`.

## 2. Keys and secrets

Local secrets live in `.env`, which is git-ignored. In GitHub Actions the same values are **repository secrets**.

| Key | Where to get it | Needed? |
|---|---|---|
| Claude login | `claude` sign-in (step 1) | **Yes**. Each article uses three calls from your plan's usage limits. |
| `GH_PAT` | GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate. Repository access: *Only select repositories* → your repo. Permissions: **Contents: Read and write** and **Workflows: Read and write**. | **Yes** on your PC, for uploads and for pushing workflow changes. Not needed in Actions, which provides `GITHUB_TOKEN`. |
| `CLAUDE_CODE_OAUTH_TOKEN` | Run `claude setup-token` on your PC | Only in GitHub Actions. Valid for about a year. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | See [section 5](#5-telegram-updates) | Optional |
| `MEDIUM_TOKEN` | Medium → Settings → Security and apps → Integration tokens | Only for `publish.mode: api`. Medium no longer issues new tokens. |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Only for `writer.backend: api`, which is billed separately from Pro |

Then set `hosting.repo` in `config.yaml` to `<your-user>/<your-repo>`.

## 3. Verify

```text
run file samples\sample-article.md --dry-run    renders offline, no Claude, no upload
run check                                       checks every integration
```

`run check` prints one line per integration:

```text
  Claude Code CLI   : ok — logged in, model opus replied 'ok'
  GitHub hosting    : ok (deeppatel99/curlybrace-autopilot, public)
  Medium token      : not set (fine for mode 'local')
  Publish mode      : local / status: draft
  Telegram          : ok — test message sent
  Topic queue       : 3 pending of 3
```

On Windows, double-clicking `run.bat` runs `check` and keeps the window open.

## 4. Run it every week with GitHub Actions

1. Push the project to your public repository. `.env`, `out/` and `.venv/` are git-ignored.
2. Repo → **Settings → Secrets and variables → Actions → Secrets** → add `CLAUDE_CODE_OAUTH_TOKEN`, plus `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` if you use Telegram. They must be **Secrets**, not Variables.
3. Repo → **Settings → Actions → General → Workflow permissions** → **Read and write permissions**.
4. Repo → **Settings → Pages** → Source: **Deploy from a branch** → `main` / `(root)`. This serves each `paste.html` as a web page.
5. Test it from **Actions → Curly Brace autopilot → Run workflow**. Put a topic in the *topic* field to test without touching the queue.

### Schedule

The schedule is the `cron` line in [`.github/workflows/autopilot.yml`](../.github/workflows/autopilot.yml). Keep [`ci/autopilot.yml`](../ci/autopilot.yml) identical, because `setup.bat` copies from it. Cron runs in **UTC**, and IST is UTC+5:30. Days run from 0 (Sunday) to 6 (Saturday).

| Schedule | cron |
|---|---|
| Monday 09:00 IST (default) | `30 3 * * 1` |
| Monday and Thursday 09:00 IST | `30 3 * * 1,4` |
| Every day 07:00 IST | `30 1 * * *` |
| Saturday 22:30 IST | `0 17 * * 6` |

GitHub may start scheduled runs 10 to 30 minutes late. The Telegram update and the run summary show the next scheduled date, worked out from this line.

### What a run does

Install, then write, review, fix, render, host and notify. After that the workflow commits the updated `topics/queue.yaml`, keeps `out/` as a run artifact for 14 days and, if any step failed, sends a ❌ Telegram alert with a link to the run.

## 5. Telegram updates

1. In Telegram, open **@BotFather**, send `/newbot` and copy the token.
2. Send any message to your new bot.
3. Put the token in `.env` as `TELEGRAM_BOT_TOKEN` and run `run check`. It prints your chat ID.
4. Put the chat ID in `.env` as `TELEGRAM_CHAT_ID` and run `run check` again. A test message arrives.
5. Add both values as repository **secrets** for Actions.

Recommended BotFather settings: `/setjoingroups` → **Disable**, a profile picture with `/setuserpic`, and a short `/setdescription`. Skip `/setcommands`, because the bot only sends messages.

Each update has three parts: **What was done** (format, words and read time, visuals, review results), **Your turn** (paste page, new Medium story, fact-checks to confirm, tags) and **What's next** (next topic, queue size, next run).

## 6. How articles reach Medium

Set `publish.mode` in `config.yaml`:

| Mode | What happens | Trade-off |
|---|---|---|
| `local` (default) | Builds `paste.html` with hosted images and a **Copy article** button. Tap it, paste into a new Medium story, add tags, publish. | Recommended. The story is fully native to Medium. |
| `import` | Hosts a page whose URL you give to medium.com/p/import | Medium adds a canonical link to the hosted page, so search credit goes there. |
| `api` | Creates a Medium draft through the API | Needs a legacy integration token |

The paste page reshapes the HTML for Medium's editor: code blocks survive blank lines, blockquotes gain no trailing empty line, and the yellow banner is never copied. It works from a phone too. If images do not come through in the Medium app, open medium.com/new-story with **Desktop site** turned on in your mobile browser.

## 7. Everyday commands

```text
run next                                    next queued topic
run topic "Span<T> and Memory<T>" --track csharp --format deep-dive   one-off topic, queue untouched
run add "Polly v8 resilience pipelines" --track aspnetcore --format versus
run file out\2026-10-18-<slug>\source.md    re-render an article without calling Claude
```

| Flag | Effect |
|---|---|
| `--format <name>` | Format for `topic` / `add` (see [section 8](#8-topic-queue)) |
| `--dry-run` | Render locally, upload nothing, send no Telegram message |
| `--no-review` | Skip the review and fix passes |
| `--mode local\|import\|api` | Override `publish.mode` for this run |

Each run writes `out/<date>-<slug>/`:

| File | Purpose |
|---|---|
| `source.md` | Claude's raw output, including the JSON asset blocks |
| `article.md` | Clean Markdown with local image paths |
| `images/` | Every PNG and GIF |
| `preview.html` | Local review copy. Do not paste it, because its images are local files. |
| `paste.html` | Paste-ready page with hosted images (also in `posts/<slug>/` on GitHub Pages) |
| `review.md` | Checklist, format warnings, the reviewer's issues and the fact-check notes |

> **Run new articles in GitHub Actions, not on your PC.** A local `run next` updates only your local `topics/queue.yaml`. Commit and push it, or the next scheduled run will write the same topic again. Run `git pull` before editing anything, because the workflow commits to `main` every week.

## 8. Topic queue

`topics/queue.yaml` is an ordered list. The first `pending` topic is written next.

```yaml
- topic: "The payment that was charged twice: lock expiry, retries and idempotent consumers in Azure Service Bus"
  track: azure                      # picks the lead tag (config.yaml → article.lead_tags)
  format: bug-hunt                  # see the table below; empty = article.default_format
  notes: "Duplicate payment processed twice because the message lock expired during a slow handler."
  auto: true                        # set by the planner: notes are an idea, not a real incident
  status: pending                   # pending | done | skipped
```

| Format | Best for | Length | Visuals |
|---|---|---|---|
| `deep-dive` | One concept or feature, explained with a clear stance | 1,400–2,600 words | 4–7 |
| `bug-hunt` | A failure traced from symptom to root cause to prevention | 1,300–2,400 | 3–6 |
| `build-log` | How something was designed and built, with the trade-offs | 1,500–2,800 | 4–7 |
| `versus` | A decision guide between options developers confuse | 1,200–2,200 | 4–6 |
| `interview` | 6–12 interview questions with model answers | 2,200–4,200 | 5–9 |
| `news` | What a new release changes for developers (needs research) | 900–1,800 | 3–5 |

**Notes are how your experience gets in.** When you write `notes` yourself, without `auto: true`, the writer treats them as something that really happened and builds the opening on those details. A real incident from your own work is the strongest hook you can give it, and it is what Medium's curators look for. Planner ideas carry `auto: true`, and the writer tells them as a recognisable scenario, never as your past.

When fewer than two topics are pending, Claude plans `topics.plan_batch` new ones, each with a format and an angle. It skips the queue, `topics.already_published` and the titles live on your Medium feed. To write a topic again, set its status back to `pending`. To add a series teaser, give the topic a `series:` name.

## 9. Configuration reference

| Key | Default | Meaning |
|---|---|---|
| `writer.backend` | `claude-code` | `claude-code` uses your subscription, `api` uses `ANTHROPIC_API_KEY` |
| `writer.claude_code_model` | `opus` | `opus` or `sonnet`. Sonnet uses less of your plan's limit. |
| `writer.claude_code_fallback` | `sonnet` | Used when the main model is unavailable (ignored if it is the same model) |
| `writer.max_tokens` / `timeout_sec` | `32000` / `1500` | Output cap and per-call timeout |
| `writer.research` | `true` | Writer, reviewer and planner verify facts with WebSearch/WebFetch and link official docs. Slower and uses more of your plan. Required for the `news` format. |
| `writer.review` / `auto_fix` | `true` / `true` | Run the review pass, and apply its fixes |
| `article.default_format` | `deep-dive` | Format for topics that do not set one |
| `article.cta` | `{default, interview}` | Closing call to action per format, reproduced word for word |
| `article.lead_tags` | (map) | Track → first Medium tag |
| `hosting.repo` / `branch` / `folder` | — / `main` / `posts` | Where images and pages are committed |
| `hosting.url_style` | `raw` | `raw` (raw.githubusercontent.com) or `jsdelivr` |
| `publish.mode` | `local` | See [section 6](#6-how-articles-reach-medium) |
| `publish.auto_open` | `true` | On a PC, open the paste page and a new Medium story when done |
| `topics.auto_plan` / `plan_batch` | `true` / `5` | Refill the queue automatically |
| `topics.medium_feed` | your RSS feed | Live Medium titles are added to the do-not-repeat list |
| `topics.already_published` | (list) | Series the planner must not repeat |

## 10. Customising

| To change | Edit |
|---|---|
| Voice, structure, review strictness | [`autopilot/prompts.py`](../autopilot/prompts.py) |
| Colours, fonts, layouts of the visuals | [`autopilot/design.py`](../autopilot/design.py) (palette at the top) |
| Paste page look and the Copy button | [`autopilot/publish.py`](../autopilot/publish.py) (`PAGE`, `COPY_BANNER`) |
| Telegram message | [`autopilot/pipeline.py`](../autopilot/pipeline.py) (`_update_message`) |
| Format rules that raise warnings | [`autopilot/article.py`](../autopilot/article.py) (`validate`) |

After any change, run `python test_autopilot.py` and a dry run.

## 11. Cost

- **Writer on a subscription (default):** no extra charge. Each article uses three Claude calls from your plan's limits, more when research mode looks things up. If you hit limits, set `writer.research: false` or `claude_code_model: sonnet`.
- **Writer on the API:** roughly $0.50 to $1.50 per article with Opus, billed on console.anthropic.com.
- **GitHub:** Actions, Pages and storage are free for public repositories.

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `Microsoft Visual C++ 14.0 or greater is required` during setup | You are on Python 3.15. Install 3.13 or 3.14, delete `.venv` and run `setup.bat` again. |
| Double-clicking `run.bat` flashes and closes | Update to the current `run.bat`, which runs `check` and pauses. |
| `Claude Code CLI not found` | Install Claude Code (step 1) and open a new terminal. |
| `not logged in`, or a run fails in Actions after months of working | Run `claude setup-token` and replace the `CLAUDE_CODE_OAUTH_TOKEN` secret. |
| `usage limit` | Wait for your plan's limit to reset, or switch to `sonnet`. |
| No Telegram message from Actions | The two Telegram values are under Variables instead of Secrets. |
| Broken images in Medium | The repository is private, or the images were still propagating. Check that an image URL opens in a browser. |
| The same topic was written twice | A local run's queue change was not pushed. Commit and push `topics/queue.yaml`. |
| Format warnings in `review.md` (word count, visuals, questions) | The writer drifted from the format. Fix it in the Medium draft, or rerun with `run topic ... --format ...`. |
| `Format 'news' needs writer.research: true` | Turn research on in `config.yaml`, or pick another format. |
| `Asset block skipped (invalid JSON)` | Rare. The JSON was repaired once automatically and the block was still broken. That one visual is missing. |
