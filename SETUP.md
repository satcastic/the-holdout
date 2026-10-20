# Setup guide: download and play The Holdout

This guide assumes no programming experience. It works on **Windows, macOS and Linux**.
Allow about 20 minutes the first time.

You can play two ways:

| Mode | What you need | What you get |
|---|---|---|
| **Full game** | Free Pinecone account + Anthropic account with a few dollars of credit | Real AI suspects you can talk to freely |
| **Practice mode** | Nothing | Everything works (clues, scoring, the reveal), but suspects give short canned replies |

---

## Part 1: Install the tools (one time)

You need three free programs: **Git** (downloads the project), **Python** (runs the game
server) and **Node.js** (runs the game screen).

### Windows
1. **Python:** go to https://www.python.org/downloads/ and download **Python 3.12**.
   Run the installer and **tick "Add python.exe to PATH"** on the first screen before clicking
   Install.
2. **Node.js:** go to https://nodejs.org and download the **LTS** version. Install with the
   default options.
3. **Git:** go to https://git-scm.com/download/win and install with the default options.
4. Open **PowerShell** (press the Windows key, type `PowerShell`, press Enter) and check:
   ```
   py -3.12 --version
   node --version
   git --version
   ```
   Each should print a version number. If one says "not recognized", restart the computer and
   try again.

### macOS
1. Open **Terminal** (press Command + Space, type `Terminal`, press Enter).
2. Install Homebrew (a tool installer) by pasting the command shown on https://brew.sh and
   pressing Enter. Follow what it prints, including the "Next steps" lines at the end.
3. Install the three tools:
   ```
   brew install python@3.12 node git
   ```
4. Check: `python3.12 --version`, `node --version`, `git --version`.

### Linux (Ubuntu/Debian)
```
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip make
```
For Node.js, follow the "Linux" instructions on https://nodejs.org (version 22 or newer).

> Python 3.11, 3.12 or 3.13 all work (3.12 is the tested version). Node.js 22 or newer.

---

## Part 2: Download the game

In Terminal (macOS/Linux) or PowerShell (Windows):

```
cd Desktop
git clone https://github.com/satcastic/the-holdout.git
cd the-holdout
```

Replace `satcastic/the-holdout` with the address of the repository you are downloading
(the green **Code** button on GitHub shows it). You now have a `the-holdout` folder on your
Desktop and your terminal is inside it.

---

## Part 3: Get your keys (full game only)

Skip this part for practice mode.

1. **Anthropic (the AI):** go to https://console.anthropic.com, sign up, add credit under
   **Settings -> Billing** (the minimum is enough; one game costs well under a dollar), then
   **API Keys -> Create Key**. Copy the key; it starts with `sk-ant-`. It is shown only once.
2. **Pinecone (the database):** go to https://app.pinecone.io, sign up for the free Starter
   plan, open **API Keys** and copy the key; it starts with `pcsk_`.

Keys are passwords. Never post them online or commit them to GitHub.

---

## Part 4: Create your settings file

Make a copy of the example settings and open it:

- **macOS / Linux:**
  ```
  cp .env.example .env
  open -e .env        # macOS; on Linux use: nano .env
  ```
- **Windows:**
  ```
  copy .env.example .env
  notepad .env
  ```

Then edit it:

- **Full game:** paste each key right after its `=` sign, with no spaces or quotes:
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  PINECONE_API_KEY=pcsk_...
  ```
  Be careful to put the Anthropic key (`sk-ant-`) and the Pinecone key (`pcsk_`) on the right lines.
- **Practice mode:** change these two lines instead (leave the keys empty):
  ```
  LLM_MODE=fake
  VECTOR_BACKEND=memory
  ```

Save and close. (The file name starts with a dot, so some file browsers hide it. That's normal.)

---

## Part 5: Install the game and load the case

### macOS / Linux
```
make install
make ingest
```

### Windows
```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
cd web
npm install
cd ..
.venv\Scripts\python -m src.ingest
```

Installing takes 1-3 minutes. The last command (`ingest`) uploads the 30 case files to Pinecone
and should end with `Namespace now holds 30 records`. If it shows fewer, wait a minute and run
it again; it's safe to repeat. In practice mode it just prints a note that nothing is stored;
that's expected.

---

## Part 6: Start the game (every time you play)

The game runs as two programs, each in its own terminal window.

**Window 1: the game server**

- macOS / Linux: `make api`
- Windows: `.venv\Scripts\python -m uvicorn src.api:app --port 8000`

Wait until you see `The Holdout API ready` and `Uvicorn running on http://127.0.0.1:8000`.
Leave this window open.

**Window 2: the game screen**

Open a second terminal window, go into the game folder again
(`cd Desktop/the-holdout` on macOS/Linux, `cd Desktop\the-holdout` on Windows), then:

- macOS / Linux: `make web`
- Windows: `cd web` then `npm run dev`

When it shows `Local: http://localhost:5173/`, open your web browser at
**http://localhost:5173** and click **Take the case**.

**To stop:** press **Control + C** in each window. Next time, repeat Part 6 only.

---

## How to play

Elena Voss, lead systems architect at Veridia AI, was found dead in Server Room 11-S. Four
people had reasons to silence her. You have **30 moves**.

- **Find evidence** with the buttons above the text box: **Ask forensics** (a good first move),
  **Request records** (emails, chats, door logs, cameras, receipts) and **Examine Server Room
  11-S**. Type something before pressing a button to make a specific request, for example
  "Lobby Turnstile exit log". New clues appear in the **Evidence locker** on the right.
- **Question a suspect:** click them on the left, type a question, press Enter. Suspects can
  lie, and what they say never counts as evidence.
- **Confront a suspect:** tick clues in the locker, then press **Present to [name]**. The right
  evidence can make people admit things.
- Some records only unlock after you've found earlier clues. Follow the trail.
- **Accuse:** use the red **Accuse** button, pick a suspect, explain your reasoning and tick
  your supporting clues. You get two wrong accusations. Score: right person 40, broken alibi 20,
  other suspects ruled out 20, motive 10, moves left 10.
- When the case closes you see your score and the full true story.

**No spoilers:** don't open `case/solution.json` if you want to solve it yourself.

---

## Troubleshooting

| You see | Do this |
|---|---|
| `make: command not found` (Windows) | Use the Windows commands in Parts 5 and 6; Windows has no `make`. |
| `python` / `py` / `node` "not recognized" | Re-run that installer (on Windows tick "Add to PATH"), then restart the computer. |
| `No such file or directory` / `No rule to make target` | You're not in the game folder. `cd` into `the-holdout` and run `ls` (or `dir` on Windows); you should see `Makefile` and `README.md`. |
| `requires ANTHROPIC_API_KEY` or `requires PINECONE_API_KEY` | A key is missing from `.env`, or use practice mode. |
| `401`, `invalid x-api-key`, `authentication` | A key is wrong or on the wrong line. Anthropic keys start `sk-ant-`, Pinecone keys `pcsk_`. After fixing `.env`, restart Window 1. |
| `credit balance is too low` | Add credit at console.anthropic.com -> Settings -> Billing. |
| Browser: "Could not reach the precinct" or "The line went dead" | Look at Window 1 for the error. Usually a key problem; fix `.env`, then stop (Control + C) and restart Window 1. |
| Browser page doesn't load | Window 2 isn't running; start it again. |
| `address already in use` | An old copy is still running. Close all terminal windows and redo Part 6. |
| "Slow down, detective" | Rate limit (20 messages per minute). Wait a minute. |

Changed `.env`? Always restart Window 1 afterwards: the server reads settings only when it starts.
