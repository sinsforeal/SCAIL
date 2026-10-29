# Video contact sheets

`video_contact_sheet.py` samples a video into timestamped screenshot grids.
Use it to inspect motion, dialogue changes and brief visual bugs without
opening each frame separately. It does not change the source video.

## Requirements

- Python with Pillow (`from PIL import Image` must work).
- `ffmpeg` on `PATH`. The workspace's Windows installation provides it at
  `C:\ffmpeg\bin\ffmpeg.exe`.

## Use

From the repository root in PowerShell:

```powershell
python tools/video_contact_sheet.py 'F:\Videos\2026-09-18 13-32-07.mkv' --out "$env:TEMP\backlog-review.png"
```

This takes one frame every two seconds, at 640 pixels wide, and places up to
16 frames on each 4-column × 4-row sheet. Each frame has a video time label.
For a short video the output is exactly the `--out` path. Longer videos write
`backlog-review_001.png`, `backlog-review_002.png`, and so on.

Choose a denser sample or inspect only one span:

```powershell
python tools/video_contact_sheet.py 'F:\Videos\clip.mkv' --out "$env:TEMP\clip.png" --every 0.5 --start 12 --duration 8 --cols 4 --rows 4 --width 480
```

The script will not replace an existing sheet unless you pass `--overwrite`.
It makes a temporary directory for sampled JPEGs and removes them after the
PNG sheets are written. Use `--help` for all options.

For agents: call `tools.view_image` on the printed absolute PNG path to review
the grid. If a moment needs closer inspection, rerun with a smaller `--every`
and a narrow `--start`/`--duration` span. The time labels are nominal sample
positions; seek and frame timing can differ slightly for variable-frame-rate
video. Keep generated sheets in a temporary or report directory unless the
user asks to track them.
