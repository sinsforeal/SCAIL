# secerts

This directory holds this fork's API keys. Everything in it except this file is
gitignored, so a key placed here is never committed.

Put the OpenRouter key here as plain text:

    F:\REPS2\SCAILV4\secerts\openrouter.txt

`config_momoka.json` reads it by the relative path `secerts/openrouter.txt`
(the `api.openrouter_key_file` setting), so no key needs to be pasted into any
tracked file. If a key must be inline in a config for a test, keep it out of git
by placing it in this directory and referencing it by path instead.

The Minimax speech key lives outside this tree, in `F:\REPS2\minimax\config.json`
(`api_key`), the same file SCAIL uses.
