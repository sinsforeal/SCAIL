# B-Zombie bench seed saves

Ten SQLite saves (10.6 MB) that bench runs and scene batches start from, so the bench can be run without first replaying days.

- `start/save.db` (4 files: three Momoka bases and `cl3v2_s_tomoe`): the empty save a run boots from. 0 messages, default kv rows only.
- `day1_end/save.db` and `day2_end/save.db` for `gr2_b_s3_momoka`, `gr2_b_s4_momoka`, `gr_b_s5_momoka`: the day checkpoints that `scene_batch`, `inject_batch` and `removal_batch` branch from. Bench days are virtual (2026-10-26 to 10-28).
- `arm.json` and `harness/<snapshot>.json` beside each save: the small sidecars the harness reads with a snapshot.

Provenance: every save was made by the bench itself. A run boots an empty save (`bzombie/arms/s/make_run.py`), and snapshots are sqlite backups of that run's own store. "Him" in the day checkpoints is the simulated user replaying a script (`him_via: script`); his lines are model-written, not a real person's messages. `manifest.json` lists each file with size, sha256, the run it came from and how it was made.

Checked before publishing (tools/public_bench_dbs.py in the private tree): every text column was compared against the owner's real saves and the simulated-user profile; 0 hits on messages, replies, profile sentences, paths and names, raw bytes, URLs, embeddings and dates. Titles the model picked were confirmed as its own picks (its input said the user's list was unknown).

Not included: the simulated-user style profile (built from real messages), the Tomoe day checkpoints (made with that profile), scratch branch saves, and per-run `config.json` (rebuild with the bench's `new` command; the stored ones hold machine paths). There is no install command yet: copy a base folder into `var/runs/<run>/` and point the harness at it.
