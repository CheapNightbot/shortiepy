# shortiepy 🌸

Your local URL shortener (˶˘ ³˘)♡

- 🔒 100% offline - no data leaves your machine
- 🌈 Cross-platform (Linux/macOS/Windows)
- 📋 Auto-copies short URLs to clipboard
- 🎀 Pastel colors & kaomojis everywhere!

## Installation

- **Using `pipx`** [Recommended]

Follow instructions to install `pipx` here: [pipx.pypa.io/stable/installation](https://pipx.pypa.io/stable/installation/) and after installing `pipx` in your system, install `shortiepy`:

```bash
pipx install shortiepy
```

- **Using `pip`**

```bash
pip install shortiepy
```

## Usage

- **Add a URL**

```bash
shortiepy add https://example.com
```

- **Start server**

```bash
shortiepy serve  # will run in forground
# OR
shortiepy start  # will run in background
```

- **View docs**

```bash
shortiepy docs
```

## Shell Completion

Get tab-completion with **one command**:

```bash
shortiepy completion
```

> Restart your shell or reload config (`source ~/.bashrc` for bash OR `source ~/.zshrc` for zsh).
> Fish users: no restart needed!

That's it! Works for bash, zsh, and fish.

## Why

For some reason, when I’m working on things or trying to learn something new, my browser ends up filled with tons of tabs—which makes my laptop-chan angry ~ ₍^.  ̫.^₎

I don’t want to close them or bookmark them. I tried manually copying URLs into a `.txt` file, but then I wished there was a simple way to turn long links into short ones I could use later.

I didn’t want to send anything online, and existing self-hosted URL shorteners felt like overkill for such a small need.

So I made this: a minimal, local-only URL shortener. It started as a single script file and isn’t perfect—but it just works! ~ ദ്ദി/ᐠ｡‸｡ᐟ\


## For Developers

Want to tinker with `shortiepy` or contribute? Here's how to set it up locally:

- Clone the repository locally and change the directory into it:

```bash
git clone https://github.com/CheapNightbot/shortiepy.git && cd shortiepy
```

- Install `shortiepy`:

```bash
# Create a virtual environment (keeps things clean!)
python -m venv .venv

# Activate it
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate     # Windows

# Install in editable mode (changes reflect instantly!)
pip install -e .
```

Now you can run `shortiepy` from anywhere in your terminal!
Made a change? It’ll work immediately—no reinstall needed!

### Updating Shell Completions

If you modify CLI commands or options, regenerate completions:

```bash
./scripts/generate-completions.sh
```

> This updates the files in `shortiepy/completions/` directory.
