# Optional integration: Claude Code prompt control through tmux

This recipe applies only when the user requests control of their current
Claude Code TUI inside tmux. It is outside shared skill discovery because
its prompt commands and tool names are specific to that client. Other agents,
non-TUI sessions, and ordinary coursework use their own direct tools; no
framework workflow requires this recipe. Check the installed client's behavior
before using it, since prompt queuing and background notifications can change.

When this Claude Code session runs inside a tmux pane, the agent can type into
its **own** input box with `tmux send-keys`, exactly as if the user typed it.
That lets the agent do things the tool API can't reach directly: run a TUI
built-in command, use `!`-shell mode, or queue a follow-up prompt to itself.

## Prefer the direct route first

This skill predates tools that now cover most of its old uses. Self-injection
costs a turn boundary and cannot observe its own result, so it is the last
resort, not the default:

| Want | Use instead |
| :--- | :--- |
| Run a project or global **skill** (`/cite-check`, `/fix-terms`, `/flow-check` …) | the **Skill tool** — same turn, result in hand |
| Kick off a **long job** (`./fw build`, a Quarto render) and pick it up later | **Bash with `run_in_background: true`** — it re-invokes you on exit (wrap per the machine's keep-awake rule, e.g. `caffeinate -is`) |
| Wait on a condition / poll | the Monitor or scheduling tools, not an inject-sleep loop |
| Drive a **different** interactive program or session (a wizard, `/artifacts` in another pane) | the global **tui-drive** skill (detached tmux session + capture-pane) |

What is left for self-inject: TUI **built-ins** that have no tool equivalent,
`!`-shell mode, and a queued prompt to yourself.

## The one hard constraint

Keystrokes are only *acted on when the prompt is idle*. While the agent is
mid-turn (a tool is running, the spinner is up), injected text is **queued**, not
executed — the TUI shows `Press up to edit queued messages` — and it fires the
moment the turn ends. So you can never inject-and-observe inside a single tool
call. Instead: **arm the injection to fire after this turn, then end the turn.**

## Find your pane

```bash
pane="${TMUX_PANE:-$(tmux display-message -p '#{pane_id}')}"   # e.g. %0
```

Prefer `$TMUX_PANE` (set by tmux for the pane you're in); fall back to
`display-message`. Never hardcode `%0` — it is only today's id.

## The robust pattern (arm → end turn → get re-invoked)

Run this as a **Bash tool call with `run_in_background: true`**. It sleeps past
the current turn, injects, then exits — and a backgrounded Bash tool *re-invokes
you when it exits*, so you wake up after the injected command has run and can read
the result. Passing the pane via an env var keeps the quoting sane.

```bash
pane="${TMUX_PANE:-$(tmux display-message -p '#{pane_id}')}"
PANE="$pane" bash -c '
  sleep 3                              # let the CURRENT turn finish; prompt must be idle
  tmux send-keys -t "$PANE" -l "/compact"      # -l = send literal text
  sleep 0.4
  tmux send-keys -t "$PANE" Enter              # key name (no -l) = submit
'
```

Then stop calling tools and give a short final message so the prompt goes idle.
The `sleep` only needs to be long enough that the prompt is idle when the keys
land; if the turn overruns it, the keys simply queue and fire at turn-end anyway
— benign. Send the **text and the `Enter` as two separate `send-keys` calls** with
a small gap; a combined `'…' Enter` can trip bracketed-paste/debounce handling.

## Recipes

- **Shell mode** — run a command through the TUI and fold its output into the
  transcript: inject `-l "!./fw build"` then `Enter`. The leading `!`
  toggles shell mode; the rest is the command.
- **TUI built-in command** — inject `-l "/compact"` (or `/model …`, `/config`)
  then `Enter`. Built-ins are not skills, so the Skill tool can't fire them;
  this is the only programmatic route. (A *skill's* slash name goes through
  the Skill tool instead.) Anything destructive to the session (`/clear`)
  needs the user's say-so first — you would be erasing the context they are
  relying on.
- **Prompt to yourself** — inject plain prose then `Enter` to hand yourself a
  fresh instruction on the next turn (e.g. a checklist item to continue).
- **Verify** — read back what's on screen with
  `tmux capture-pane -t "$pane" -p | tail -n 40`.

## Uses in a course repo

- **Compact before a long lint pass.** Self-inject `/compact` at a milestone so
  the fix-terms → flow-check → cite-check chain starts with headroom, then
  continue from the queued follow-up prompt.
- **Put a build log in the transcript.** `!./fw build` when the user
  wants the raw Quarto/xelatex output recorded as their own command — for
  just *running* the build, background Bash is the right tool.
- **Hand yourself the next checklist item** across a turn boundary when no
  scheduling tool is available.

## Gotchas & safety

- **Only your own pane.** `send-keys` can target any pane; scope it to
  `$TMUX_PANE`. Don't drive other sessions.
- **No injection loops.** A turn that injects a command which re-invokes you,
  which injects again, will spin forever. Inject once per intent; gate any repeat
  on an explicit stop condition.
- **Literal vs. key-name.** `-l "text"` types characters verbatim; bare `Enter`,
  `Escape`, `C-c` are interpreted as keys. Mixing them up either submits nothing
  or types the word "Enter".
- **Not tmux?** If `$TMUX` is unset the session isn't in tmux and this skill does
  not apply — fall back to normal tool calls.
