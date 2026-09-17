#!/usr/bin/env python3
"""Generate synthetic media for a real image/video/scanned-PDF RAG smoke test.

Run inside the backend Docker image (Pillow, PyMuPDF and FFmpeg are required):
  python tests/create_media_fixtures.py --output /tmp/rag-test-media
Generated files are test data and must not be committed to the repository.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont


def run(argv):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=120, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-3000:])
    return result.stdout


def font(size, font_path=None):
    candidates = ([font_path] if font_path else []) + [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def card(step=None, font_path=None):
    image = Image.new("RGB", (1280, 720), "#f3f7fc")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1280, 74), fill="#172f50")
    draw.text((48, 22), "SYNTHETIC EQUIPMENT TRAINING", fill="white", font=font(30, font_path))
    draw.text((48, 102), "WIDGET ZX-17", fill="#13263f", font=font(66, font_path))
    draw.text((48, 190), "Maximum pressure: 0.6 MPa", fill="#13263f", font=font(45, font_path))
    if step:
        draw.rounded_rectangle((38, 262, 1242, 360), radius=14, fill="#ffffff")
        label = "STEP 1: CLOSE THE BLUE VALVE" if step == 1 else "STEP 2: PRESS THE GREEN BUTTON"
        draw.text((60, 291), label, fill="#163451", font=font(43, font_path))
    else:
        draw.text((48, 282), "Step 1: Close the blue valve.", fill="#174e87", font=font(41, font_path))
        draw.text((48, 342), "Step 2: Press the green button.", fill="#16602e", font=font(41, font_path))
    # The panel is intentionally a diagram, never a photograph of real equipment.
    draw.rounded_rectangle((72, 430, 525, 620), radius=20, fill="#e1edfb", outline="#8fb0d4", width=3)
    draw.line((110, 525, 485, 525), fill="#7ea3c9", width=38)
    draw.ellipse((240, 465, 355, 580), fill="#1976cf", outline="#064c8f", width=6)
    draw.line((250, 478, 345, 568), fill="white", width=12)
    draw.text((157, 643), "BLUE VALVE", fill="#134f86", font=font(30, font_path))
    draw.rounded_rectangle((750, 430, 1170, 620), radius=20, fill="#e2f1e5", outline="#89b296", width=3)
    draw.ellipse((903, 472, 1017, 586), fill="#17a653", outline="#096731", width=7)
    draw.text((825, 643), "GREEN BUTTON", fill="#136b36", font=font(30, font_path))
    if step == 1:
        draw.polygon([(305, 385), (275, 415), (292, 415), (292, 450), (316, 450), (316, 415), (333, 415)], fill="#d16b0c")
    elif step == 2:
        draw.polygon([(960, 385), (930, 415), (948, 415), (948, 450), (972, 450), (972, 415), (990, 415)], fill="#d16b0c")
    return image


def create(output: Path, narration: Path | None = None, font_path: str | None = None):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    equipment = output / "equipment-card.png"
    first, second = output / "video-step-1.png", output / "video-step-2.png"
    card(font_path=font_path).save(equipment)
    card(1, font_path).save(first)
    card(2, font_path).save(second)
    scanned = output / "scanned-card.pdf"
    with Image.open(first) as page_one, Image.open(second) as page_two:
        page_one.convert("RGB").save(scanned, "PDF", resolution=110,
                                     save_all=True, append_images=[page_two.convert("RGB")])
    audio = output / "narration.wav"
    if narration:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(narration.resolve()),
             "-vn", "-af", "apad", "-t", "10", "-ar", "16000", "-ac", "1", str(audio)])
    else:
        stages = []
        for number, words in ((1, "Step one. Close the blue valve."),
                              (2, "Step two. Press the green button.")):
            stage = output / f"speech-step-{number}.wav"
            # Static text is passed as a single argv entry; no shell or external TTS.
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                 "-i", f"flite=text={words}:voice=slt", "-af", "apad", "-t", "5",
                 "-ar", "16000", "-ac", "1", str(stage)])
            stages.append(stage)
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(stages[0]),
             "-i", str(stages[1]), "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
             "-map", "[a]", str(audio)])
    concat = output / "video-slides.txt"
    concat.write_text("file 'video-step-1.png'\nduration 5\nfile 'video-step-2.png'\nduration 5\nfile 'video-step-2.png'\n", encoding="utf-8")
    video = output / "training-demo.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat), "-i", str(audio), "-vf", "fps=10", "-t", "10", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(video)])
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration",
                           "-of", "json", str(video)]))
    assert {stream["codec_type"] for stream in probe["streams"]} == {"audio", "video"}
    assert abs(float(probe["format"]["duration"]) - 10) < 0.1
    import pymupdf
    with pymupdf.open(scanned) as document:
        assert len(document) == 2
        assert all(not page.get_text().strip() for page in document), "PDF must have no text layer"
    manifest = {
        "purpose": "Entirely fictional fixtures for multimodal RAG integration testing",
        "files": {"image": equipment.name, "video": video.name, "scanned_pdf": scanned.name},
        "video_duration_seconds": float(probe["format"]["duration"]),
        "video_has_audio": True,
        "pdf_pages": 2,
        "pdf_has_text_layer": False,
        "expected_facts": ["WIDGET ZX-17", "Maximum pressure: 0.6 MPa", "Step 1: Close the blue valve.",
                           "Step 2: Press the green button."],
        "expected_video_scenes": [{"start_seconds": 0, "end_seconds": 5, "step": "Close the blue valve"},
                                  {"start_seconds": 5, "end_seconds": 10, "step": "Press the green button"}],
        "narration": "supplied local audio" if narration else "local FFmpeg flite English synthesis",
    }
    (output / "fixture-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--narration", type=Path, help="Optional existing local audio; otherwise FFmpeg flite is used")
    parser.add_argument("--font", help="Optional local TrueType font path")
    args = parser.parse_args()
    create(args.output, args.narration, args.font)
