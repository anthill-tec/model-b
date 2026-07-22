"""``python -m modelb_axi`` entrypoint — delegates to the CLI."""

import sys

from modelb_axi.cli import main

sys.exit(main())
