from __future__ import annotations

import json

from claire_continuity.core import ContinuityWorkspace


def main() -> None:
    result = ContinuityWorkspace().create_demo(admit_to_are=True)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
