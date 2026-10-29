#!/usr/bin/env python3
"""Sample a video into labeled PNG contact sheets for visual review.

Requires FFmpeg on PATH and Pillow. See video_contact_sheet.README.md.
"""

import argparse
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return number


def nonnegative_float(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative finite number")
    return number


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def time_label(seconds):
    hours, remainder = divmod(round(seconds * 10), 36000)
    minutes, tenths = divmod(remainder, 600)
    whole_seconds, tenth = divmod(tenths, 10)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{tenth}"


def font():
    for name in ("consola.ttf", "DejaVuSansMono.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, 18)
        except OSError:
            pass
    return ImageFont.load_default()


def sample_video(video, temp_dir, *, every, width, start, duration):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    if start:
        command += ["-ss", str(start)]
    command += ["-i", str(video)]
    if duration is not None:
        command += ["-t", str(duration)]
    command += ["-an", "-vf", f"fps=1/{every},scale={width}:-2", "-q:v", "3",
                str(temp_dir / "frame_%06d.jpg")]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("ffmpeg could not read the video:\n" + result.stderr.strip())
    frames = sorted(temp_dir.glob("frame_*.jpg"))
    if not frames:
        raise RuntimeError("ffmpeg produced no frames; check the video and time range")
    return frames


def sheet_paths(output, count):
    if count == 1:
        return [output]
    return [output.with_name(f"{output.stem}_{page:03d}.png")
            for page in range(1, count + 1)]


def make_sheet(frames, output, *, cols, width, cell_height, first_index, every, start):
    gap, label_height = 8, 28
    rows = math.ceil(len(frames) / cols)
    sheet_width = cols * width + (cols + 1) * gap
    sheet_height = rows * (cell_height + label_height) + (rows + 1) * gap
    canvas = Image.new("RGB", (sheet_width, sheet_height), "#202027")
    draw = ImageDraw.Draw(canvas)
    label_font = font()
    for position, path in enumerate(frames):
        row, col = divmod(position, cols)
        x = gap + col * (width + gap)
        y = gap + row * (cell_height + label_height + gap)
        with Image.open(path) as source:
            image = ImageOps.contain(source.convert("RGB"), (width, cell_height),
                                     Image.Resampling.LANCZOS)
        canvas.paste(image, (x + (width - image.width) // 2,
                             y + (cell_height - image.height) // 2))
        at = start + (first_index + position) * every
        draw.text((x + 4, y + cell_height + 3), time_label(at),
                  fill="white", font=label_font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return sheet_width, sheet_height


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make timestamped contact sheets from a video.")
    parser.add_argument("video", type=Path, help="input video, such as an MKV or MP4")
    parser.add_argument("--out", required=True, type=Path,
                        help="output PNG; multiple sheets get _001, _002, ... suffixes")
    parser.add_argument("--every", type=positive_float, default=2.0,
                        help="seconds between samples (default: 2)")
    parser.add_argument("--cols", type=positive_int, default=4,
                        help="columns per sheet (default: 4)")
    parser.add_argument("--rows", type=positive_int, default=4,
                        help="maximum rows per sheet (default: 4)")
    parser.add_argument("--width", type=positive_int, default=640,
                        help="width of each screenshot in pixels (default: 640)")
    parser.add_argument("--start", type=nonnegative_float, default=0.0,
                        help="start time in seconds (default: 0)")
    parser.add_argument("--duration", type=positive_float,
                        help="inspect only this many seconds after --start")
    parser.add_argument("--overwrite", action="store_true",
                        help="replace contact sheets at the destination")
    args = parser.parse_args(argv)

    if not args.video.is_file():
        parser.error(f"video does not exist: {args.video}")
    if args.out.suffix.lower() != ".png":
        parser.error("--out must end in .png")
    if shutil.which("ffmpeg") is None:
        parser.error("ffmpeg is not on PATH")

    with tempfile.TemporaryDirectory(prefix="video_contact_sheet_") as temporary:
        frames = sample_video(args.video, Path(temporary), every=args.every,
                              width=args.width, start=args.start,
                              duration=args.duration)
        per_sheet = args.cols * args.rows
        outputs = sheet_paths(args.out, math.ceil(len(frames) / per_sheet))
        existing = [path for path in outputs if path.exists()]
        if existing and not args.overwrite:
            parser.error(f"output exists: {existing[0]} (use --overwrite to replace it)")
        with Image.open(frames[0]) as first:
            cell_height = first.height
        for page, output in enumerate(outputs):
            first_index = page * per_sheet
            selected = frames[first_index:first_index + per_sheet]
            dimensions = make_sheet(selected, output, cols=args.cols,
                                    width=args.width, cell_height=cell_height,
                                    first_index=first_index, every=args.every,
                                    start=args.start)
            print(f"{output.resolve()}  {dimensions[0]}x{dimensions[1]}  "
                  f"{len(selected)} frames  "
                  f"{time_label(args.start + first_index * args.every)} to "
                  f"{time_label(args.start + (first_index + len(selected) - 1) * args.every)}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="backslashreplace")
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"video contact sheet: {exc}", file=sys.stderr)
        raise SystemExit(1)
