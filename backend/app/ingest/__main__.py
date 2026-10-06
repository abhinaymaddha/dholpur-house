"""Load transcripts into Postgres.

    python -m app.ingest "<Telegram export folder>"        # messages*.html
    python -m app.ingest path/to/messages.jsonl
    python -m app.ingest --seed                            # the data committed in backend/seed/
    python -m app.ingest --write-seed "<export folder>"    # refresh backend/seed/ from a new export
"""

import sys
from pathlib import Path

from .parse import parse_export
from .pipeline import SEED_FILE, run_ingest, write_messages

if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--seed"]:
        run_ingest(SEED_FILE)
    elif len(args) == 2 and args[0] == "--write-seed":
        msgs = parse_export(Path(args[1]).expanduser())
        write_messages(msgs, SEED_FILE)
        print(f"wrote {len(msgs)} messages to {SEED_FILE}")
    elif len(args) == 1 and not args[0].startswith("-"):
        run_ingest(Path(args[0]).expanduser())
    else:
        sys.exit(__doc__)
