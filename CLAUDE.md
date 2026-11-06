# curia - the mechanism

This repo is the **mechanism** for a seat-based agent estate: the launcher, the
seat/session model, account fallback, the `/handoff` skill, the read-only
nudge report, the morning branch sweep, and the template a new estate is made
from. Read `README.md` for the vocabulary before changing anything.

## The one hard rule

**Mechanism is reusable; law is not.** Nothing in this repo may name a client,
a product, a person, a repository, or a number belonging to one. Those live in
an estate (`<workspace>/curia/`), never here. This is enforced:

```sh
python3 -m pytest -q tests    # fails if any file here names a registered estate
```

The denylist is read at test time from the estates registered in
`~/.config/curia/estates.toml`, so this repo never has to contain the words it
is forbidden to contain. If a prompt string needs to talk about an estate's
notes, its vault, or its people, say "per your charter" and let the estate's
charter carry the specifics. That test failing is the fence working; do not
weaken it to get green. A repo an estate registers that IS the mechanism gives
no word (it is this repo's own name), and an estate registered but absent from
the machine is a warning in the test summary, because its words went unscreened.
Where `python3` has no pytest: `uv run --no-project --with pytest python -m pytest -q tests`.

## Layout

- `bin/curia` - the whole CLI, one stdlib-only Python file (3.11+ for tomllib)
- `skills/` - skills every seat gets; `launch` links them into the RESOLVED
  account's `$CLAUDE_CONFIG_DIR/skills`, not just `~/.claude/skills`
- `templates/estate/` - what every estate gets from `curia init`
- `templates/shapes/<shape>/` - the roster and README of each shape (`seat`,
  `crew`, `factory`); `init` copies one over the base
- `templates/charters/` - a charter scaffold per kind (`crew`, `office`,
  `fleet`) and per office role the mechanism wakes (`censor`, `lictor`,
  `notarius`); `init` stamps one per rostered seat with the roster's words
- `templates/handoff.md` - the note shape a seat writes at sleep
- `templates/ruling.md` - the shape of a ruling: `status:` and `enforced by:` lines the
  mechanism reads, then what, why, what enforces it
- `docs/` - the public landing page at curia.build: `index.html`, one
  self-contained file, and `media/`, the film's web encode and posters.
  `deploy.sh` ships it as a Cloudflare Worker with static assets
  (`worker.js` only answers range requests for `media/`), writing the
  `/github` redirect from the git remote into the upload, so the org is never
  named here. Run wrangler from outside the repo: its `.wrangler/` cache
  holds the account owner's name, and the fence reads it like any other file
- `tests/test_jev.py` - the judgment seam and everything built on it, all faked
- `tests/` - the fence, plus `conftest.py`, which builds a scratch estate from
  the template with a fake `claude`, and `test_cli.py` on top of it

## Working here

- Every change: `python3 -m py_compile bin/curia && python3 -m pytest -q tests`.
  A behaviour change gets a test. The `estate` fixture is a scratch estate in
  a temp dir and `invoke_claude` is the one place claude starts, so replace
  that and nothing needs a live estate or a real session.
- Try a command without launching a session: most take `--print-cmd`, which
  shows the resolved account, cwd and prompt instead of running.
- To rehearse something destructive (a rename, a roster edit), copy an estate
  to a scratch directory and run against it with `--estate <path>`; never
  experiment on a live estate.
- Adding a command: a `cmd_*` function plus a subparser in `main()`, and a line
  in the README's daily-use block. Offices are looked up by `role`, not name,
  so a renamed seat keeps working - keep it that way.
- Anything that runs git or gh does so through `git()`, `gh_json()`, `gh_run()`
  and `bd_close()`, so tests replace those and never reach a forge. A dispatch
  test builds a real git repo in the scratch estate; that is cheap, keep it.
- Anything that asks the judgment model does so through `jev()`, and
  `jev_open()` is the one place the network is. Tests replace `jev()` (see
  `with_jev` in `tests/test_jev.py`); conftest's `no_network` fails any test
  that reaches `jev_open()`. A new use gets three tests: off is unchanged,
  on shows the output, no answer degrades to off.
- **`curia help` is part of the change, not documentation of it.** Any new
  command, new flag, or changed behaviour updates the help in the same commit.
  There are four places and they are easy to half-do:
  - `HELP_OVERVIEW` - the command list; a flag worth knowing goes in the
    parenthetical after its command
  - `HELP_DETAIL[<cmd>]` - the prose page behind `curia help <cmd>`; say what
    the command does and what it will NOT do
  - `HELP_EXAMPLES[<cmd>]` - the epilog; real invocations, aligned to column 40
  - the `add_argument` help string, which is what `-h` shows
  Read it back (`curia help <cmd>`) rather than trusting the diff - argparse
  reflows prose and swallows misalignment. Help that lies is worse than absent:
  a seat reads it as law. The fence applies here too - no client, person or
  repo names, so examples use `<seat>`, `<repo>`, `<acct>` placeholders.
- Prompts the CLI composes are read by a model with the seat's prime already in
  context. Say what is forbidden and what to do, not how to phrase it.

## Design commitments (do not casually reverse)

- A seat's memory is files it writes itself. The launcher reads them in; the
  seat writes them back at `/handoff`. Nothing else consolidates them silently.
  Headless, that memory is the journal: `run` orders one entry per waking into
  `seats/<seat>/journal/`, the prime reads the last few, and the mechanism
  only ever notes that an entry is missing, never writes one.
- Time is read when asked (`now()`, `stamp()`, `today()`), never cached at
  import. A looping launcher and an hour-long headless run outlive their start;
  a cached clock stamped every end with its start and primed a seat relaunched
  after midnight with yesterday.
- Account rotation happens at LAUNCH, walking a chain for the first account
  with headroom: not marked limited, not measured past `limited_at`, under
  `rotate_at` on its fullest window as the seat's status line last read it.
  A running session cannot change account; that is a fact about the harness,
  not a gap to paper over. So the hooks make the session END well: the Stop
  hook says "hand off now" past `handoff_at`, `shift_hours`, `context_at` or
  `context_tokens_at` (the status line's reading of the session's context
  window). Stop fires only when a turn ends and one turn can run for hours, so
  `PostToolUse` asks the same question inside the turn, at most once a minute,
  and repeats itself every `shift_remind_minutes`. It tells; it stops nothing. The StopFailure
  hook marks the account when a turn dies on the limit and leaves LIMITED for
  the launcher, which ends the session and relaunches. A headless run is a
  launch, so it marks its own limit and retries down the chain; a `--loop`
  launch waits out a spent chain rather than dying overnight. Measurement is
  what Claude Code hands the status line, never an API call of our own; with
  no reading on file the walk is markers only, and so it is for an account on
  usage-based billing, which reports no windows: a spent budget shows first as
  a dead turn, and a banner naming no reset is tried again after a few hours.
  A headless run tries a roster
  `fallback_model` on the same account before it marks the account: a limit
  may be the model's. `shared = false` accounts are
  nobody's fallback. A cut session is not carried to the next account:
  `--carry` was tried and removed, because it leaned on Claude Code's
  transcript layout, which is not ours; the handoff and the transcript path
  in the prime are what the next session gets. A LIMITED marker names its
  session, and a headless run's is named for the run, so a seat awake
  interactively and reviewing headless at once never ends the wrong one.
  Every account limited, a `--loop` launcher waits in fifteen-minute slices
  and re-walks the chain after each.
- `account_env` is the one place a session's account reaches its environment.
  An account on `~/.claude` runs with `CLAUDE_CONFIG_DIR` unset: Claude Code keys
  the stored login on the variable being set, so naming the default dir is a
  second login beside a bare `claude`'s, and it expires unseen. Every other
  account names its dir, and logs in under that exact name.
- How the principal is told is the estate's to say: `notify` in estate.toml is
  a command, and the mechanism only ever calls it with a subject, a body and a
  report path. Nothing here knows a channel. `tell` is the seat's own way to
  that command, logged and capped; a question to the principal goes there by
  itself once it has stood `ask_notify_minutes`, so one answered at the keyboard
  costs nobody a mail.
- Judgment selects and reports; it never writes, lands or ends anything.
  `jev()` puts typed questions (noul, choice, score) to a small decision
  model that generates no text. It is off until estate.toml names `jev_key`
  (a command that prints the key: the mechanism holds no secret and knows no
  keychain), and off means every command's output is what it was, byte for
  byte; on and failing means the same, with the reason said. It chooses what
  is put in front of a seat (`recall`, ## Recalled), says whose concern a
  note is (`route`), and reports (`triage`, the ingest screen, a handoff's
  NEEDS YOU, the Lictor's CUSTOM and its reading of a BUSY fence, `board`'s
  proposals on a repo's open beads, which a person approves and runs: it
  never runs bd). It never writes a seat's files or an estate's notes, and
  it is kept out of the Portcullis, the `--everything` stop conditions,
  rotation, `reap` and every hook. No network call inside `build_prime` (it
  is handed a finished recall), `cmd_check`'s loop, or `handoff --done`: the launcher and the
  offices ask. `handoff --lint` is the one question a session may put, before
  --done, and it advises and refuses nothing. Dates, counts, ages and the choice of
  candidates stay in code; each question gets small state, and the text
  being judged goes in `state`, never in the instructions, so pasted text is
  data. The one place a judgment has a consequence is where the principal
  asks for it by flag (`mail --route`, `ingest --screen`), and both do
  nothing when unsure or unanswered. Notes are asked about only on the
  principal's word (`jev_on_notes`): by flag (`ingest --jev` or `--screen`,
  `triage --notes --jev`), or once for the estate by `jev_notes = true` in
  estate.toml, which `--no-jev` withdraws for one command. They are other
  people's words, so an estate having jev on never sends them by itself, and
  an absent or non-boolean `jev_notes` is the fence. The model is pinned, not an alias:
  thresholds (`jev_*_at`, in `THRESHOLDS`) were judged against a version.
  Every call is a line in `brain/jev/calls.log`; answers are cached a file
  per request, since jobs overlap and nothing here locks.
- Read-only offices stay read-only. If a command starts writing to a board,
  that is a new office, not a flag. The Portcullis is the one that writes
  (merges, closes beads), and it is a gate, not an office: its yes or no is
  gh's facts and no model wakes for it. Keep it that way; judgment belongs
  to a reviewer seat, before the gate.
- `--everything` reads the board and never writes it. Each waking's orders come
  from the repo's beads export, the seat is told to export before handing off,
  and the loop ends on mechanical conditions only - the board clear, the board
  unmoved for two wakings, the deadline reached, the budget reached - and none
  of them needs judgment; do not add one that does. That is the seat's, in its
  handoff. Each waking's reading of the board is a `board` line in
  sessions.log and each handoff goes to the principal through `notify`, with
  the board's movement and the handoff's own line for them. An epic with nothing
  workable beneath it counts for nothing: it is a folder, not work. A loop that
  stops on a clear or unmoved board last waits, spending nothing, on the
  integration run of what it landed (`settle_minutes`), puts how that stands in
  its final notice, and spends one more waking only if it is red and the night
  has room; `progress` is the
  read-only view over that record and writes nothing but the page `--html`
  asks for. The default review brief keeps the board convergent for the same
  reason: a reviewer fixes on the branch or hands the bead back, and never
  files a new bead. An estate whose reviews file findings will find the loop
  working its own reviews, not the backlog. `--by` narrows the loop to the
  beads a person filed, by exact name or email from the bead's own record,
  never by judgment; those beads are still sorted against the whole board,
  and the orders, not a fence, keep the seat off the rest. A bead assigned to
  someone neither named in `--by` nor a seat has been handed to them: it is
  theirs, whoever filed it.
- Mail is a file the reader archives. `seats/<seat>/mail.md` is read into the
  prime at every waking until the seat runs `curia mail <seat> --archive`;
  nothing archives it silently, and a seat mails a seat, never the outside.
- A fleet worker's home is given at `dispatch` and taken back by `reap`, and
  reap only ever removes a worktree whose branch has landed and which holds
  nothing uncommitted. Reap closes a session record only when the launcher
  pid on the start line is provably gone; a live pid is left alone.
  A reviewer works in a home of its own at the branch's tip, never in the
  worker's: the worker is free when it returns, and no dispatch checks a branch
  out under a running gate.
- A session leaves nothing running. Every session's descendants carry its id in
  `CURIA_RUN`, so when it ends what it left is stopped, whatever process group
  it put itself in, and `reap` and `stop` act only on what the record proves is
  a finished run's or the named seat's. `bg` is the one way to outlive a session.
  A process with no run id, another estate's, or a shared daemon (`SWEEP_SPARES`,
  `sweep_spares`) is never touched. `ps` is not the whole of it: macOS hides the
  environment of its own binaries, so `stop` signals the job on the record, which
  ends its own process group; the run id is for what left the group.
- The machine has a floor. `dispatch`, `run` and `bg` refuse past
  `floor_disk_gb` or `floor_swap_gb` and tell the principal; nothing else on an
  estate owns the machine. Repos' own gate slots still decide what runs at once.
- Fences are the estate's law with the mechanism as transport. `hooks.json`
  rides into every seat session through `--settings`; the mechanism ships
  `hook release-guard` as the worked example and nothing in it names a
  branch, and `hook record-guard`, which fences the mechanism's own record
  (paths in `RECORD_GLOBS`, structural, no estate's facts). A ruling's
  `enforced by:` line names its program; `check` and `lictor` say which
  rulings are still only custom. Do not add a fence that needs an estate's
  facts to the mechanism; put the facts in repos.toml and read them.
  Fences are counted, never silently accumulated: every refusal by a
  mechanism fence is a line in `brain/fences.log` (`fence_log`), the
  Lictor reads it back for idle and busy fences, and `check` notes more
  than `fences_max`. The mechanism reports the count; it never prunes.
- Authority is in the prime. `build_prime` ends with what the seat may do
  without asking, what is refused, the fences by name and the rulings in
  force, so a seat looks its authority up rather than probes for it. Keep
  that section factual: names and statuses, not exhortation. `seat_settings`
  tells the auto-mode classifier which seat this is and what is its own, as
  `environment` prose; it never writes an allow rule, because widening what a
  seat may do is the principal's decision, in the estate. What a waking carries
  is measured by `weight`: a prime's standing text is spent at every waking.
- A secondment is marked, not barred. A headless waking on a model that is
  not the roster's for it (fallback or `--model`) is told so in its prime
  and told to open its journal entry with `seconded: <model>`; the next
  prime labels that entry. The mechanism never writes the mark into the
  entry itself: the seat's memory stays the seat's to write.
- A seat is parked, not deleted. `active = false` refuses launch, run and
  dispatch and skips a broadcast, and keeps the directory. Nothing reads a
  parked seat's memory away.
- Skills are linked per ACCOUNT, at launch. Claude Code reads user skills from
  `$CLAUDE_CONFIG_DIR/skills`, and a seat runs under whichever account it
  resolved to - so linking into one config dir by hand leaves every seat on
  every other account without them (which is how `/handoff` went missing for a
  whole account's seats). Launch is the moment the account is known; link there.
  What a session LISTS is the estate's to say, and is decided there too:
  estate.toml `[skills]`/`[plugins]` and a seat's own, carried in `--settings`
  as Claude Code's `skillOverrides`/`enabledPlugins`, patterns matched against
  the resolved account, never written into it. The mechanism's skills are
  always listed in full. Judgment does not choose the listing; if it ever
  does, its floor is name-only (still callable), never off.
- A shape is where an estate starts, not what it is. `init --shape` lays
  down a roster, a charter per seat and the prompts and units that roster
  needs, and no more; afterwards the roster is the truth, and `check` asks
  for an office prompt only where a seat needs it (`prompts_needed`). Do not
  record the shape anywhere the mechanism reads: an estate grows by editing
  its roster, and a recorded shape would only go stale.
- The estate is discovered (`--estate`, `CURIA_ESTATE`, a walk up from the
  working directory, then the registry: the estate whose roster has the seat
  named, or the only one registered), so no command needs a particular
  working directory. Two estates and no seat to tell them apart means stop,
  never guess: there is no default estate, so no command lands on the wrong
  client.
- The working directory chooses the repo. `launch`, `run` and `ingest`
  default `--repo` to the registered repo containing the cwd (the most
  specific where repos nest); the roster home applies only from outside any
  repo, and `ingest` treats the estate root as plain home, not a repo hint.
  Discovery still needs no particular directory; this is about where a seat
  starts, not whether it can.
- Claude Code is the only harness today, and not forever. The direction is
  an estate that runs with no Claude Code at all (Codex, OpenCode, Pi,
  Grok Build): crew, offices and nights alike, on one harness. The work is
  deferred and taken up as needed; `specs/2026-09-04-harness-seam.html`
  maps it. Until then, do not deepen the coupling: keep Claude-specific
  reaches inside `seat_settings`, `invoke_claude`, `headless_result`,
  `ensure_skills`, `resolve_account` and `claude_md_chain` with
  `session_start_commands`, not spread through commands.
  Where a commitment above names a Claude Code mechanism (`--settings`, the
  status line, StopFailure), the principle is what binds and the mechanism
  is today's way of keeping it; another harness keeps it its own way or
  says in help that it cannot. An unset harness will mean Claude Code, so
  existing estates and printed commands do not move.

## State that lives outside this repo

`~/.config/curia/estates.toml` (which estates exist on this machine), each
account's `$CLAUDE_CONFIG_DIR/skills/*` and `~/.local/bin/curia` (symlinks into
here), each estate's own directory, and any launchd units an estate installs.
Changing a path here can break those; check before you move something.

## Session notes (Obsidian vault)

Persistent prose (session notes, decisions, research) lives in the owner's vault
at `~/Documents/Obsidian Vault`, project folder `Business/Curia/`, index `Curia MOC.md`. The
repo keeps code and its docs; the vault keeps what should outlive a session.

- **Confidentiality**: the vault holds notes for other clients and private
  notes. Never read, list, search or write outside `Business/Curia/`. Scope
  every `obsidian` CLI call with `path=` or `folder=`; vault-wide commands
  (`search` without `path=`, `files` without `folder=`, `properties`,
  `orphans`, `deadends`, `recents`, `random`, `bases`, `daily:*`) are
  forbidden here.
- **Start**: read `Curia Session Log.md` for continuity; open a note under
  `Sessions/` only when you need the detail. If the folder or log does not
  exist yet, create `Curia MOC.md` and `Curia Session Log.md` (a table of date,
  note and summary, newest row first).
- **Finding past context**: use the `vault-search` skill (`vault-search
  "<question>"`) before reading or grepping notes by hand. It is scoped to
  this folder by `.claude/vault-search.toml` and ranks passages with Jev
  (the owner's decision; never edit that file).
- **End**: write `Sessions/YYYY-MM-DD<letter>-topic.md` and add a one-line row
  at the top of the table in `Curia Session Log.md`. Frontmatter: `project:
  Curia`, `source: claude`, `date: YYYY-MM-DD`, `type:
  session|meeting|decision|research|note`, `summary: <one line>`. Link new
  evergreen notes from `Curia MOC.md`.
- The `obsidian` CLI needs the app running; if it errors, read and write the
  files directly under the same folder.
