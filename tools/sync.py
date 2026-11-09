#!/usr/bin/env python3
"""Copy common/*.py into every skill folder so each skill installs on its own.

    python3 tools/sync.py          # copy
    python3 tools/sync.py --check  # exit 1 if any copy differs (the tests run this)
"""

import glob
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMON = sorted(glob.glob(os.path.join(ROOT, "common", "*.py")))


def main(argv):
    bad = []
    for d in sorted(x for x in glob.glob(os.path.join(ROOT, "etf-*")) if os.path.isdir(x)):
        for src in COMMON:
            dst = os.path.join(d, os.path.basename(src))
            same = os.path.exists(dst) and open(src, "rb").read() == open(dst, "rb").read()
            if "--check" in argv:
                if not same:
                    bad.append(os.path.relpath(dst, ROOT))
            elif not same:
                shutil.copyfile(src, dst)
                print("updated %s" % os.path.relpath(dst, ROOT))
    if bad:
        print("out of date: %s (run python3 tools/sync.py)" % ", ".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
