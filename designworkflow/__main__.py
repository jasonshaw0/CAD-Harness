"""Keep previous checkout commands working during the repository migration."""

import sys

from cadharness.cli import main

args = sys.argv[1:]
raise SystemExit(main(args if args and args[0] == "studio" else ["design", *args]))
