---
title: "pyenv Python on macOS needs explicit flag for loadable sqlite extensions"
category: configuration-fixes
tags: [pyenv, python, sqlite, sqlite-vec, macos, tcl-tk, memory-layer]
module: memory
symptom: "sqlite3.Connection has no attribute 'enable_load_extension' when loading sqlite-vec"
root_cause: "pyenv compiles Python without --enable-loadable-sqlite-extensions by default; also tcl-tk 9 breaks the 3.12.0 tkinter build on macOS 26"
---

## Problem

Loading `sqlite-vec` (or any sqlite loadable extension) from a pyenv-installed Python fails with:

```
AttributeError: 'sqlite3.Connection' object has no attribute 'enable_load_extension'
```

pyenv's `python-build` does not pass `--enable-loadable-sqlite-extensions` by default. Homebrew Python does. The memory layer (`skills/memory/scripts/memory.py`) hits this whenever the active Python is a pyenv Python without that flag.

## Fix

Rebuild the pyenv Python with the flag. On macOS with Xcode 26 / macOS 26, the `_tkinter.c` compile also breaks against Homebrew's tcl-tk 9 — install `tcl-tk@8` and pass `TCLTK_LIBS`/`TCLTK_CFLAGS` so python-build finds it correctly. Passing `-ltcl8.6 -ltk8.6` inside `PYTHON_CONFIGURE_OPTS` fails because the env var gets word-split and `configure` sees the library flags as unknown options.

```bash
# 1. One-time dep
brew install tcl-tk@8

# 2. Snapshot virtualenvs (pyenv install -f is safe for envs/ but belt-and-suspenders)
SNAP="$HOME/.pyenv-3.12.0-backup-$(date +%s)"
mkdir -p "$SNAP"
tar -cf "$SNAP/envs.tar" -C "$HOME/.pyenv/versions/3.12.0" envs

# 3. Rebuild with flags set as env vars (NOT inside PYTHON_CONFIGURE_OPTS)
TCLTK="/opt/homebrew/opt/tcl-tk@8"
SQLITE="$(brew --prefix sqlite3)"
export LDFLAGS="-L${SQLITE}/lib -L${TCLTK}/lib"
export CPPFLAGS="-I${SQLITE}/include -I${TCLTK}/include"
export PKG_CONFIG_PATH="${TCLTK}/lib/pkgconfig"
export TCLTK_CFLAGS="-I${TCLTK}/include"
export TCLTK_LIBS="-L${TCLTK}/lib -ltcl8.6 -ltk8.6"
export PATH="${TCLTK}/bin:$PATH"
export PYTHON_CONFIGURE_OPTS="--enable-loadable-sqlite-extensions"
pyenv install 3.12.0 -f

# 4. Verify
~/.pyenv/versions/3.12.0/bin/python3 -c "import sqlite3; sqlite3.connect(':memory:').enable_load_extension(True); print('OK')"
```

## Gotchas

- **Do NOT** put `--with-tcltk-libs="-L... -ltcl8.6 -ltk8.6"` inside `PYTHON_CONFIGURE_OPTS` — the shell splits on spaces and `configure` rejects `-ltcl8.6` as an unrecognized option. Use the dedicated `TCLTK_LIBS` env var instead.
- `pyenv install 3.12.0 -f` preserves everything under `~/.pyenv/versions/3.12.0/envs/` (virtualenvs are separate dirs), so existing envs survive.
- `tk==0.1.0` in a `pip freeze` is a dummy PyPI package, not real tkinter — does not indicate tkinter usage.
