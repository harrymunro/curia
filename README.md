

https://github.com/user-attachments/assets/9d5e48b1-c447-4d05-9585-237c0170f2b7



<h1 align="center">Curia</h1>

<p align="center"><b>The mechanism for a software society.</b><br>
Persistent seats for your Claude Code agents: memory they write themselves,
offices that keep order, account fallback that survives the night, and law with teeth.</p>

<p align="center">
  <a href="https://curia.build">curia.build</a> ·
  <a href="https://curia.build/#film">the film</a> ·
  <a href="#install">install</a> ·
  <a href="#vocabulary">vocabulary</a> ·
  <a href="LICENSE">MIT</a>
</p>

<p align="center"><sub>one Python file · standard library only · your estate holds the rest</sub></p>

---

Run a software factory long enough and its hardest problems stop being about
code. They are older than software, and each has an answer here:

| The factory's trouble | Curia's remedy |
|---|---|
| **Forgetting.** Every session starts from nothing, and compaction swaps what it knew for a summary. | **Seats.** A named role that outlives every session. It wakes primed with its charter, its authority, its last handoff and its mail, and hands off in its own words before its context fills. |
| **Want.** At two in the morning the account runs dry, and every agent on it stops. | **The chain.** Each launch takes the first account with headroom, read from what Claude Code itself measures. A seat cut off mid-task restarts on the next, told what happened. |
| **Delay.** Agents idle on a build, and every message between them goes through you. | **Offices.** The Lictor watches every board and changes nothing, the Censor wakes a model only where a branch is failing, the Portcullis lands what is reviewed and green. Seats leave each other mail. |
| **Custom.** The rules live in someone's head, so a new agent breaks them in good faith. | **Law.** Rulings say whether they are in force and name what enforces them. Fences are programs that refuse what the law forbids, in every seat session, and every refusal is counted. |

> “Humanity has only one mature technology for coordinating mortal,
> replaceable strangers via text — namely, law.”
> — Steve Yegge, *Fences, not Sandboxes* (2026)

Rome's senate met in a house called the Curia. Curia builds that house for your agents.

### What a seat wakes up with

```text
$ curia launch praetor

## Your charter      You hold the api backlog: its data layer, its migrations.
## Your authority    May merge through the gate. Refused: push to release.
## Your last handoff Orders table migrated. Next: read the retry ruling.
## Mail (unread)     quaestor: the brief is in PR 412; start there.
## Laurels           "The new import finally makes sense."
```

A seat looks its authority up instead of probing for it. Give an office the
board with `--everything` and go to bed: it works the backlog waking after
waking, and stops only on mechanical conditions (the board clear, the board
unmoved for two wakings, `--until`, `--budget`). By morning its handoffs are
waiting for you.

## Mechanism, not law

A city's law can't be downloaded, so Curia ships only the machinery. An
**estate** is one client's workspace. Its `curia/` directory holds the
roster (who the seats are), the manifest (which repos), the accounts (whose
tokens), the seats' memory (charter, handoff, laurels) and the brain (rulings
that span repos). That is the law, and it is bespoke: it names products,
people and numbers. Keep one estate per client, and they never mix. This repo
holds only what every estate shares:

- `bin/curia` - launch seats with their memory primed, run offices headless,
  the read-only Lictor report, the Censor sweep, account fallback, handoffs.
- `skills/handoff/` - the `/handoff` skill (install at user level, see below).
- `templates/estate/` - what every estate gets from `curia init`;
  `templates/shapes/` the roster and README of each shape (seat, crew,
  factory); `templates/charters/` a charter scaffold per kind and per office
  role, stamped from the roster at init.
- `tests/` - the fence: nothing in this repo may name an estate, its
  products or its principal. The denylist is read from the estates
  registered in `~/.config/curia/estates.toml`, so the mechanism never has to
  know the names it is forbidden to know.

Start with one seat and grow: `curia init <dir> --shape seat` (one seat you
talk to), `crew` (seats with jurisdictions, watched and gated by the offices)
or `factory` (an office dispatching a fleet, each worker in its own worktree).
A shape is where an estate starts, not what it is.

## Vocabulary

| Word | Meaning |
|---|---|
| seat | a named, persistent role with memory; survives sessions and model upgrades |
| session | one waking of a seat |
| office | a standing seat with a function; scheduled or on demand |
| crew | a seat with a jurisdiction (concerns, not repos); the principal talks to it |
| fleet | seats an office dispatches; never launched directly; each has its own worktree |
| prime | the system prompt a seat wakes up with: identity, colleagues, charter, last handoff, laurels, house rules |
| handoff | the note a seat writes on its way to sleep; the next session reads it first |
| laurel | spontaneous praise for a seat's work, recorded so the seat sees it on waking; carries no work |
| mail | a note one seat leaves another; read in the prime at waking, archived by the reader |
| gate | a mechanical yes or no; the Portcullis lands work that passes it, and no model wakes for it |
| fence | a program that refuses what the law forbids; the estate declares them in `hooks.json` |
| ruling | law that spans repos, with a status and what enforces it; `brain/rulings/` |
| shape | what `init` lays down: `seat` (one seat the principal talks to), `crew` (crew, watched and gated), `factory` (offices, crew and a fleet); afterwards the roster is the truth |
| parked | a seat kept on the roster but woken by nothing (`active = false`); its memory stays |
| secondment | a headless waking on a model not the seat's own (the fallback after a limit, or `run --model`); the prime says so and the journal entry is marked |

## Install

Needs Python 3.11+, [Claude Code](https://claude.com/claude-code) and git.

```sh
git clone https://curia.build/github.git curia && cd curia
ln -s "$PWD/bin/curia" ~/.local/bin/curia
ln -s "$PWD/skills/handoff" ~/.claude/skills/handoff     # user-level skill
```

## Daily use

```sh
curia help                       # the vocabulary, every command and worked examples; `curia help <command>` for one in full
curia roster                     # who is on the estate
curia check                      # is the estate consistent
curia status                     # who is awake, whose memory is how old, what the offices last said
curia progress <seat>            # a long run waking by waking: cost, how the board moved, the distance to done; --html draws it
curia launch <seat>              # wake a crew seat, primed with its handoff
cd <repo> && curia launch <seat>  # ...in the repo you are in; --repo <repo> names one from anywhere
curia launch <office> --loop     # wake an office; relaunch after each /handoff, and after a mid-session limit
curia launch <office> --repo <repo> --everything   # work the board in a loop until nothing remains but what waits on a human
curia launch <office> --everything --repo <repo> --repo <repo2>   # ...several boards, in that order, one night
curia launch <office> --repo <repo> --everything --until 06:30   # ...the board, until 06:30 local time
curia launch <office> --repo <repo> --everything --budget 200    # ...the board, until $200 of recorded spend
curia launch <office> --repo <repo> --everything --by "<name>"   # ...only the beads that person filed; repeat --by for each name they file under
curia ingest <notes...>          # capture beads from meeting notes (wakes the intake office)
curia ingest --paste             # ...from the clipboard; `... ingest -` reads stdin
curia ingest --paste --repo <repo>   # ...when the notes concern one repo: start and file there
curia ingest <notes...> --jev    # ...and these notes may leave the machine: a screen and a bead shortlist first
curia ingest <notes...> --no-jev # ...these stay on the machine, where estate.toml says jev_notes = true
curia jev                        # judgment without a waking: on or off, the model, what it has cost (`curia help jev`)
curia recall <seat> "rotate the signing key"   # ...which of a seat's older notes, and which rulings, bear on it
curia board propose --repo <repo>   # ...a board's duplicates, work already landed, flags: proposals; `board emit` prints the bd lines you approved
curia route "the signing key expires next month"   # ...whose concern it is; `curia mail --route "..."` sends when sure
curia triage <seat>              # ...old entries that are durable and not carried; drift from the rulings
curia triage --notes --jev       # ...the estate's notes: folder, tags, duplicates, what to ingest; moves nothing (refuses without --jev, unless estate.toml says jev_notes = true)
curia lictor                     # read-only nudge report (crons watch): the boards, the rulings, the fences
curia censor                     # check integration branches; wake the Censor where red (models act)
curia laurel <seat> "a user said the new page finally makes sense"
curia mail <seat> "the brief is in the bead; start there"   # read at the seat's next waking; --all broadcasts
curia dispatch <fleet> --bead <id> --repo <repo> --review <seat>   # a worker gets a worktree and a job; a reviewer judges it
curia dispatch <fleet> --bead <id> --repo <repo> --detach   # ...back at once; the job is its own process either way and outlives your shell
curia portcullis                 # land the seats' reviewed, green PRs and close their beads (a cron runs this)
curia reap                       # close the record of dead sessions; remove worktrees that landed (or, --stale, went stale)
curia rulings                    # the brain's rulings, with status and what enforces each
curia limit <account> --hours 5  # an account hit its limit; launches fall back down the chain
curia launch <seat> --account <acct>   # start on a named account, e.g. one with headroom
```

The estate is found from `--estate`, `CURIA_ESTATE`, walking up from the
working directory, or the registry in `~/.config/curia/estates.toml`: the
estate whose roster has the seat you named, or the only one registered. Two
estates and no seat to tell them apart, and a command stops rather than guess.

## A new client

```sh
curia init ~/Workspace/NewClient --name "NewClient" --principal "Name" --shape seat      # one crew seat; nothing unattended
curia init ~/Workspace/NewClient --name "NewClient" --principal "Name" --shape crew      # crew and a clerk; Censor, Lictor and Portcullis watch and land
curia init ~/Workspace/NewClient --name "NewClient" --principal "Name" --shape factory   # an office and a fleet, crew, intake: the whole factory
```

A shape is a roster with a charter scaffolded per seat, plus the office
prompts and launchd units that roster needs; every shape gets the fences
(`hooks.json`, with release-guard wired in), the house rules and the brain.
Then: `curia rename` each `example_*` seat into the estate's own naming
family (the registry finds a seat's estate by its name, so a name shared by
two estates is ambiguous), fill `repos.toml` and `accounts.toml`, write the
charters where they say "Fill in for this estate", and run `curia check`
until it is quiet. The shape is where an estate starts, not what it is: the
roster is the truth afterwards, `check` asks for a prompt only where a seat
needs it, and the estate's README says how it grows into the next shape.
A client with a dedicated account gets its own config dir, listed in that
estate alone; a client without one lists the principal's own accounts, the
pool, which such estates share. Seats never roam between estates.

## Principles the mechanism encodes

- Seats wake with purpose: prime, charter, last handoff, laurels.
- Authority is looked up, not derived: the prime states what the seat may do without asking, what is refused, which fences will refuse it and every ruling in force. A seat that can look that up spends no context working out whether an act is safe; that is what a seat is for.
- Hand off, don't exit: `/handoff` is a request the seat consents to.
- A headless waking keeps a journal: `run` ends with orders to write one entry, the prime reads the last few.
- Never falsify the record: `sessions.log`, handoff history and brain are append-only.
- Crons watch, models act: `lictor` gathers facts deterministically; `censor` wakes a model only when something is red.
- Read-only offices stay read-only: the Lictor never writes beads.
- Design out the drudgery: no seat idle-waits on a PR. The Portcullis, a gate with no model behind it, lands what is reviewed and green and closes the bead.
- A review ends on the bead it began with: the reviewer fixes what it is sure of on the branch, or hands the bead back; it never files a new one. A board its own reviews refill never clears.
- A home of one's own: `dispatch` gives a fleet worker its own worktree and a job; `reap` takes the worktree back only once the branch has landed and nothing is uncommitted. It clears each repo's scratch worktrees (`.claude/worktrees/`) the same way, never one on a standing branch, never one just touched, and runs by itself after every session of a seat whose roster entry says `reap_after`.
- Seats talk to each other: `mail` is read at waking and archived by the reader, so the principal is not the relay.
- Law grows teeth: a ruling carries a status (proposed, advisory, enacted, enforced, retired) and names what enforces it; `hooks.json` turns a rule into a refusal in every seat session; `check` faults a ruling with no status and `lictor` nudges when an enacted ruling has nothing enforcing it, or a postmortem has no ruling.
- Fences are counted and watched: every refusal is a line in `brain/fences.log`; `lictor` says which fences are idle and which are busy, `check` notes more fences than `fences_max`. Fences are distrust written down, and past a point no work is legal; the principal decides what stays.
- The record fences itself: `record-guard` refuses a seat's edit to sessions.log, laurels, handoff history, other wakings' journal entries and the offices' reports. Never falsify the record is enforced, not only enacted.
- A substitute is marked: a headless waking on a model not the roster's for it is a secondment; the prime says so, the standing memory is left alone, and the journal entry opens with `seconded: <model>` so the next waking knows whose notes it reads.
- A seat is parked before it is deleted: `active = false` keeps a seat and its memory on the roster while nothing wakes it; `status` shows each seat's spend for the last seven days, which is what says whether it earns its keep.
- The envelope is the roster's: `disallowed_tools` are refused in every session, `tools` are allowed without asking.
- A seat sees the skills its work needs: estate.toml `[skills]` and `[plugins]`, and a seat's own `skills` and `plugins` in the roster, say what each session lists (in full, by name only, or not at all), carried by `--settings` and matched against the account the launch resolved; `/handoff` is always listed in full, and with neither table set a session lists what the account always did.
- A headless run falls back by model before it falls back by account: a roster `fallback_model` is tried on the same account when the primary dies on a limit, and the record says which model answered.
- Rotation is measured: each seat's status line records what Claude Code measures of its account's rate-limit windows; a launch takes the first account in the chain with headroom, a dedicated account (`shared = false`) is only ever its own seats'. An account on usage-based billing reports no windows, so for it the walk is markers only and a spent budget shows first as a turn that dies.
- A night has a goal: `--everything` reads the board each waking, names what is ready and what waits on a human, and stops when the board is clear or has not moved in two wakings. Given several repos, it works their boards in that order. It can also have an end: `--until` (HH:MM local, or ISO datetime) and `--budget` (USD of recorded spend) cap the night; the seat is told to wrap up `wrap_minutes` before the deadline and at budget percent, the way a shift ends.
- The night does not die on a limit: a seat's Stop hook says "hand off now" past a threshold, a shift length or a context depth (`context_at`), while it still has tokens to write the note; its StopFailure hook marks the account when a turn dies on the limit, and the looping launcher ends that session and relaunches on the fallback, telling the seat what happened and where the transcript is.
- Fallback, not failure: an account at its limit hands its seats down the chain; a headless run marks the limit itself and retries, a looped seat waits it out.
- The record is dated when it happens: the clock is read per event, never cached at start.

## License

[MIT](LICENSE). Quotations are from Steve Yegge's essays at yegge.ai (2026).
Curia is an independent project, not affiliated with Anthropic.
