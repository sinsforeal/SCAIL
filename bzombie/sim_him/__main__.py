"""python -m bzombie.sim_him profile <tomoe|momoka>   builds var/bzombie/profiles/<character>.json (one Claude call)."""
import sys

from . import profile

if len(sys.argv) == 3 and sys.argv[1] == "profile":
    p = profile.build(sys.argv[2])
    print("profile written; keys:", sorted(p))
else:
    print(__doc__)
