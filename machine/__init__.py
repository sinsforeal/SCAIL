"""His machine, which belongs to neither character.

One collector per machine (`collector.py`, its own process, started by
talkapp.cmd) writes the telemetry feed and the two small files that say what
is in front of him right now; `monitor_client.py` is what a bot reads them
with. Nothing in here knows which character is asking.
"""
