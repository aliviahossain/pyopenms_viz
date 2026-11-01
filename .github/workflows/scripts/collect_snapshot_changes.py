#!/usr/bin/env python3
"""
Collect the snapshots changed by `pytest --snapshot-update` into a folder that CI uploads as an artifact.
For changed matplotlib snapshots (png) an old | new | changed pixels image is also written for visual review.
"""
import argparse
import shutil
import subprocess
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def changed_snapshots(snapshot_dir):
    """Return (modified or new files, deleted files) under snapshot_dir compared to HEAD."""
    status = git("status", "--porcelain", "--untracked-files=all", "--", snapshot_dir).decode()
    changed, deleted = [], []
    for line in status.splitlines():
        code, path = line[:2], line[3:].strip('"')
        (deleted if "D" in code else changed).append(path)
    return changed, deleted


def side_by_side(old_png, new_png):
    old = Image.open(BytesIO(old_png)).convert("RGB")
    new = Image.open(new_png).convert("RGB")
    width, height = max(old.width, new.width), max(old.height, new.height)
    canvas = Image.new("RGB", (width * 3, height), "white")
    canvas.paste(old, (0, 0))
    canvas.paste(new, (width, 0))
    if old.size == new.size:
        diff = np.any(np.asarray(old) != np.asarray(new), axis=2)
        canvas.paste(
            Image.fromarray(np.where(diff[..., None], [255, 0, 0], [255, 255, 255]).astype(np.uint8)),
            (width * 2, 0),
        )
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", default="test/__snapshots__")
    parser.add_argument("--out", default="snapshot-changes")
    args = parser.parse_args()

    out = Path(args.out)
    changed, deleted = changed_snapshots(args.snapshots)
    for path in changed:
        target = out / "snapshots" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if path.endswith(".png"):
            try:
                old_png = git("show", f"HEAD:{path}")
            except subprocess.CalledProcessError:
                continue  # new snapshot, nothing to compare against
            image = out / "side_by_side" / path
            image.parent.mkdir(parents=True, exist_ok=True)
            side_by_side(old_png, path).save(image)

    if changed or deleted:
        out.mkdir(parents=True, exist_ok=True)
        (out / "README.txt").write_text(
            "Snapshots regenerated with `pytest --snapshot-update` on this PR.\n"
            "snapshots/: changed or new snapshot files, at their paths in the repository\n"
            "side_by_side/: old | new | changed pixels (red) for each changed matplotlib snapshot\n\n"
            "Changed or new:\n" + "".join(f"  {p}\n" for p in changed)
            + "Deleted:\n" + "".join(f"  {p}\n" for p in deleted)
        )
    print(f"{len(changed)} changed or new snapshots, {len(deleted)} deleted")


if __name__ == "__main__":
    main()
