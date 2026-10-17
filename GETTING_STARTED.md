# Getting started: set up The Holdout and play

Steps 1-5 are one-time setup. After that, Step 6 is all you need each time you play.

## Step 1: Get an Anthropic API key (the AI)
1. Go to https://console.anthropic.com and sign up.
2. Settings -> Billing: add the minimum credit (about $5). One full game costs well under a dollar.
3. API Keys -> Create Key (name it `holdout`).
4. Copy the key (starts with `sk-ant-`) into a note. It is shown only once.

## Step 2: Get a Pinecone API key (the database)
1. Go to https://app.pinecone.io and sign up (free Starter plan is enough).
2. API Keys -> copy the existing key, or Create API Key. Put it in your note.

## Step 3: Open Terminal in the project folder
1. Press Command + Space, type Terminal, press Enter.
2. Type `cd` and one space (don't press Enter yet).
3. In Finder go to Documents -> Claude -> College Projects -> Rag_Project.
4. Drag the `detective-rag` folder into the Terminal window, then press Enter.
   (Dragging matters: the `Rag_Project ` folder name ends with a hidden space.)
5. Type `ls` and press Enter. You should see `Makefile`, `README.md`, `src`, `web`.

## Step 4: Put your keys in the settings file
```
cp .env.example .env
open -e .env
```
In TextEdit, paste each key right after its `=` (no spaces, no quotes):
```
ANTHROPIC_API_KEY=sk-ant-...
PINECONE_API_KEY=...
```
Leave everything else alone. Save (Command + S) and close. The file is hidden in Finder; that's normal.

## Step 5: Install and load the case files
```
make install
make ingest
```
`make ingest` should finish with a 30-row table and `Namespace now holds 30 records`.
If it shows fewer than 30, wait a minute and run `make ingest` again (safe to repeat).

## Step 6: Start the game (every time)
Window 1:
```
make api
```
Wait for `The Holdout API ready (llm=real, vectors=pinecone ...)`. Leave it open.

Window 2: press Command + N in Terminal, repeat Step 3 in the new window, then:
```
make web
```
Open Chrome or Safari at http://localhost:5173 and click **Take the case**.

## Step 7: How to play
You have 30 moves to find who killed Elena Voss.
- **Ask forensics / Request records / Examine Server Room 11-S** (buttons above the text box) find
  evidence. Type something first to make it a specific request, e.g. "Lobby Turnstile exit log".
  New clues appear in the Evidence locker on the right.
- **Question a suspect:** click them on the left, type a question, press Enter. Suspects lie, and
  their words never count as evidence.
- **Present evidence:** tick clues in the locker, then "Present to [name]".
- Some records only unlock after you've found earlier clues. Follow the trail.
- **Accuse** (red button, top right): pick a suspect, explain why, tick supporting clues.
  You get 2 wrong accusations. Score: right person 40, broken alibi 20, others ruled out 20,
  motive 10, moves left 10.
- After the game ends you see your score and the full true story.

## Step 8: Stopping
Press Control + C in each Terminal window, then close them. Next time, just do Step 6.

## Troubleshooting
| You see | Do this |
|---|---|
| `No such file or directory` after `cd` | Redo Step 3; drag the folder instead of typing. |
| `No rule to make target` | Wrong folder. Redo Step 3; `ls` must show `Makefile`. |
| `requires ANTHROPIC_API_KEY` / `PINECONE_API_KEY` | Key missing. `open -e .env`, check both keys, save. |
| `401` / `invalid api key` | Key copied wrong. Make a new key and paste again. |
| `credit balance is too low` | Add credit in Anthropic Settings -> Billing. |
| Browser: "Could not reach the precinct" | Window 1 (`make api`) isn't running. Restart it. |
| Browser page won't load | Window 2 (`make web`) isn't running. Restart it. |
| `address already in use` | Close all Terminal windows and redo Step 6. |
| "Slow down, detective" | Rate limit (20 messages/minute). Wait a minute. |

## Free practice mode (no keys)
Skip Steps 1, 2, 4 and 5. In Step 6 use this instead of `make api`:
```
LLM_MODE=fake VECTOR_BACKEND=memory make api
```
Suspects give short canned answers, but clues, scoring and the reveal all work.

## Optional: real evaluation results for your report
```
make eval
```
Takes about 20-40 minutes and a few dollars of Anthropic credit (`make eval ARGS=--limit 5` for a
cheap trial). It rewrites `eval/REPORT.md` with real leak rates.
