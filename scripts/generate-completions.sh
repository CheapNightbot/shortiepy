#!/bin/bash
# Generate shell completions for shortiepy

echo "✨ Generating completions..."

_SHORTIEPY_COMPLETE=bash_source shortiepy > shortiepy/completions/shortiepy.bash
_SHORTIEPY_COMPLETE=zsh_source shortiepy > shortiepy/completions/shortiepy.zsh
_SHORTIEPY_COMPLETE=fish_source shortiepy > shortiepy/completions/shortiepy.fish

echo "🌸 Done! Completions updated."
