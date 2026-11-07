"""Bounded, read-only perceptual comparison. Similarity never authorizes deletion."""

import io
import os
import shutil
import subprocess
import time
from pathlib import Path

from .common import fingerprint
from .errors import APIError

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_TYPES = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}


def difference_hash(image):
    from PIL import ImageOps

    image = ImageOps.exif_transpose(image).convert("L").resize((9, 8))
    pixels = list(image.getdata())
    return sum(
        (pixels[y * 9 + x] > pixels[y * 9 + x + 1]) << (y * 8 + x)
        for y in range(8)
        for x in range(8)
    )


def distance(left, right):
    return bin(left ^ right).count("1")


def video_hash(path):
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    duration = float(probe.stdout.strip())
    if not 0 < duration < 86400:
        raise ValueError("Unsupported video duration")
    from PIL import Image

    hashes = []
    for fraction in (0.2, 0.5, 0.8):
        frame = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-ss",
                str(duration * fraction),
                "-i",
                path,
                "-frames:v",
                "1",
                "-vf",
                "scale=9:8",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-",
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )
        with Image.open(io.BytesIO(frame.stdout)) as image:
            hashes.append(difference_hash(image))
    return duration, hashes


def scan(files, cancelled=None, progress=None, limit=500):
    try:
        from PIL import Image
    except ImportError as exc:
        raise APIError(
            400,
            'Install the optional media extra: python3 -m pip install "mac-deep-cleaner[media]". Video comparison also needs ffmpeg and ffprobe.',
        ) from exc
    videos = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    records, pairs, errors = [], [], []
    candidates = sorted(
        {f[0] for f in files if Path(f[0]).suffix.lower() in IMAGE_TYPES | VIDEO_TYPES}
    )
    started = time.monotonic()
    for index, path in enumerate(candidates[:limit]):
        if cancelled and cancelled.is_set():
            break
        if time.monotonic() - started > 180:
            errors.append("Time limit reached; results are partial.")
            break
        if progress:
            progress(f"Comparing media {index + 1}/{min(limit, len(candidates))}")
        before = fingerprint(path)
        if (
            not before
            or Path(path).resolve() != Path(path)
            or os.path.getsize(path) > 20_000_000_000
        ):
            continue
        kind = "video" if Path(path).suffix.lower() in VIDEO_TYPES else "image"
        if kind == "video" and not videos:
            continue
        try:
            if kind == "image":
                with Image.open(path) as image:
                    hashes, duration = [difference_hash(image)], 0
            else:
                duration, hashes = video_hash(path)
            if before != fingerprint(path):
                continue
        except (
            OSError,
            ValueError,
            subprocess.SubprocessError,
            Image.DecompressionBombError,
        ) as exc:
            errors.append(Path(path).name + ": " + type(exc).__name__)
            continue
        record = {
            "path": path,
            "kind": kind,
            "size": before[3],
            "duration": duration,
            "hashes": hashes,
        }
        for previous in records:
            if previous["kind"] != kind or (
                kind == "video" and abs(previous["duration"] - duration) > max(1, duration * 0.05)
            ):
                continue
            distances = [distance(a, b) for a, b in zip(previous["hashes"], hashes)]
            if max(distances) <= 6 and len(pairs) < 300:
                pairs.append(
                    {
                        "left": previous["path"],
                        "right": path,
                        "kind": kind,
                        "score": round(100 * (1 - sum(distances) / (64 * len(distances)))),
                        "reason": "Perceptual dHash similarity"
                        + (" across three frames and matching duration" if kind == "video" else ""),
                        "review_only": True,
                    }
                )
        records.append(record)
    return {
        "pairs": pairs,
        "checked": len(records),
        "candidates": len(candidates),
        "limit": limit,
        "partial": len(candidates) > limit or bool(errors),
        "errors": errors[:30],
        "video_available": videos,
        "notice": "Visual similarity is not proof of duplication. Compare originals before removing anything. Only files above the storage scan size threshold are included.",
    }
