#!/usr/bin/env python3
"""Generate fictional Chinese internal content assets for the multimodal RAG demo.

Requires Pillow, PyMuPDF and FFmpeg (available in the backend Docker image).
The font and optional narration are local files. No network or AI calls are made.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

import pymupdf
from PIL import Image, ImageDraw, ImageFont

INK = "#193A37"
GREEN = "#315E4B"
PAPER = "#F5F0E5"
GOLD = "#DFB865"
MUTED = "#66736A"
FOOTER = "内部演示资料 · 虚构"


def run(argv: list[str]) -> bytes:
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-3000:])
    return result.stdout


class Canvas:
    def __init__(self, size: tuple[int, int], font_path: Path):
        self.image = Image.new("RGB", size, PAPER)
        self.draw = ImageDraw.Draw(self.image)
        self.font_path = str(font_path)

    def text(self, position, text, size=32, fill=INK, max_width=None):
        font = ImageFont.truetype(self.font_path, size)
        while max_width and self.draw.textbbox((0, 0), text, font=font)[2] > max_width and size > 12:
            size -= 1
            font = ImageFont.truetype(self.font_path, size)
        self.draw.text(position, text, font=font, fill=fill)


def poster(font_path: Path, company: str) -> Image.Image:
    canvas = Canvas((1600, 1000), font_path)
    d = canvas.draw
    d.rectangle((0, 0, 1600, 20), fill=GREEN)
    canvas.text((90, 72), company, 32, max_width=1050)
    canvas.text((1332, 76), "09 / 2026", 24)
    d.line((90, 140, 1510, 140), fill="#C7D0BE", width=2)
    canvas.text((90, 196), "城市漫游·郑州篇", 43, GREEN)
    canvas.text((85, 273), "周末去散步", 112, max_width=1400)
    canvas.text((92, 424), "把熟悉的城市，走成新的故事。", 34, MUTED)
    # A stylized city park illustration made of simple vector-like shapes.
    d.ellipse((1004, 213, 1374, 583), fill=GOLD)
    d.rectangle((0, 560, 1600, 850), fill="#D6DDC7")
    for x, top, width in [(35, 582, 150), (211, 510, 90), (335, 555, 130),
                           (512, 484, 100), (1200, 522, 125), (1390, 466, 163)]:
        d.rectangle((x, top, x + width, 734), fill="#809A86")
        for wx in range(x + 20, x + width - 10, 32):
            for wy in range(top + 28, 710, 38):
                d.rectangle((wx, wy, wx + 9, wy + 15), fill="#D6DDC7")
    d.polygon([(0, 756), (480, 627), (1058, 658), (1600, 714), (1600, 850), (0, 850)], fill=GREEN)
    d.polygon([(600, 850), (767, 699), (931, 674), (1020, 674), (872, 718), (778, 850)], fill="#E6D3A9")
    for x, y, scale in [(230, 677, 1.0), (1310, 675, 1.2), (1110, 705, .65)]:
        d.line((x, y, x, y - int(102 * scale)), fill=INK, width=max(5, int(10 * scale)))
        r = int(57 * scale)
        d.ellipse((x - r, y - 168 * scale, x + r, y - 55 * scale), fill="#234B3F")
    d.line((803, 765, 797, 810), fill=INK, width=8)
    d.line((803, 765, 826, 805), fill=INK, width=8)
    d.line((808, 734, 803, 773), fill=INK, width=15)
    d.ellipse((796, 711, 818, 733), fill=INK)
    canvas.text((92, 889), "60-90 秒城市短片", 30)
    canvas.text((580, 889), "每周三 19:30", 30)
    canvas.text((1118, 891), "封面提案 · 01", 27)
    canvas.text((92, 953), FOOTER, 19, MUTED)
    return canvas.image


def training_slide(step: int, font_path: Path, company: str) -> Image.Image:
    canvas = Canvas((1600, 900), font_path)
    d = canvas.draw
    d.rectangle((0, 0, 1600, 14), fill=GREEN)
    canvas.text((74, 50), company + " / 拍摄流程培训", 28, max_width=1240)
    canvas.text((1410, 50), f"0{step} / 02", 26)
    d.line((74, 108, 1526, 108), fill="#C7D0BE", width=2)
    canvas.text((74, 146), "城市漫游 · 开拍前的两件事", 29, MUTED)
    title = "第一步：检查收音和电量" if step == 1 else "第二步：拍摄15秒开场口播"
    canvas.text((70, 223), title, 73, max_width=1450)
    d.rounded_rectangle((74, 372, 1526, 746), radius=30, fill="#E0E5D6")
    if step == 1:
        # Microphone + check symbol and a full battery are recognizable at a glance.
        d.rounded_rectangle((222, 430, 299, 563), radius=37, fill=GREEN)
        d.arc((187, 452, 332, 601), 0, 180, fill=GREEN, width=10)
        d.line((260, 600, 260, 647), fill=GREEN, width=10)
        d.line((218, 651, 305, 651), fill=GREEN, width=10)
        d.rounded_rectangle((724, 450, 976, 574), radius=12, outline=GREEN, width=10)
        d.rectangle((978, 485, 999, 539), fill=GREEN)
        for x in (746, 817, 888):
            d.rectangle((x, 473, x + 53, 551), fill=GREEN)
        canvas.text((118, 682), "先试录，再听回放", 34)
        canvas.text((733, 612), "确认电池已充满", 34)
        canvas.text((1114, 462), "检查清单", 33, GREEN)
        canvas.text((1114, 524), "收音清晰", 34)
        canvas.text((1114, 582), "电量充足", 34)
    else:
        d.rounded_rectangle((183, 423, 520, 660), radius=20, fill=GREEN)
        d.polygon([(520, 488), (594, 445), (594, 638), (520, 596)], fill=GREEN)
        d.ellipse((312, 450, 388, 526), fill=PAPER)
        d.rounded_rectangle((267, 545, 433, 638), radius=53, fill=PAPER)
        canvas.text((714, 442), "15 秒", 83, GREEN)
        canvas.text((720, 566), "介绍地点 + 本期看点", 39)
        canvas.text((720, 635), "看镜头，语速自然", 33, MUTED)
    canvas.text((74, 795), "先完成第一步，再开始第二步。", 27, MUTED)
    canvas.text((1220, 837), FOOTER, 20, MUTED, max_width=305)
    return canvas.image


def rgb(color):
    return tuple(int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))


def create_pdf(path: Path, company: str, preview_dir: Path):
    # Built-in CJK font avoids depending on TTC subfont selection in PDF engines.
    # Text stays selectable and searchable; the poster remains a separate asset.
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        page.draw_rect(page.rect, color=None, fill=rgb(PAPER))
        page.draw_rect(pymupdf.Rect(0, 0, 595, 10), color=None, fill=rgb(GREEN))

        def text(x, y, value, size=13, color=INK):
            page.insert_text((x, y), value, fontname="china-s", fontsize=size, color=rgb(color))

        def wrap(x, y, value, width=500, size=12, line_height=22):
            # Each Chinese glyph occupies at most one em in the chosen font.
            limit = max(1, int(width / size))
            for start in range(0, len(value), limit):
                text(x, y, value[start:start + limit], size)
                y += line_height
            return y

        text(44, 53, company, min(15, 500 / len(company)), GREEN)
        text(44, 108, "城市漫游封面规范", 27)
        text(44, 141, "栏目视觉规范 / 2026 年 9 月 / 版本 1.0", 11, MUTED)
        page.draw_line((44, 164), (551, 164), color=rgb("#C7D0BE"), width=1)
        y = 203
        sections = [
            ("01  标题与品牌", ["主标题使用“周末去散步”，副标题使用“城市漫游·郑州篇”。",
                           "左上角标注工作室名称，右下角标注“封面提案 · 01”。"]),
            ("02  画面与配色", ["封面提案画布为 1600 × 1000 像素。主色为森林绿 #315E4B，",
                           "底色为米白 #F5F0E5，点缀色为暖金 #DFB865。",
                           "使用城市公园插画，标题与背景保持清晰对比。"]),
            ("03  平台适配", ["发布平台为微信公众号、百家号和今日头条。按各平台发布页面",
                           "裁切封面，保持主标题、人物和品牌名称完整，发布前预览。"]),
            ("04  审核与交付", ["封面初审由陈晨负责，终审由林晓负责。未经终审不得发布。",
                           "交付 PNG 文件，文件名包含栏目、选题、日期和版本号。"]),
        ]
        for title, paragraphs in sections:
            text(44, y, title, 16, GREEN)
            y += 30
            for paragraph in paragraphs:
                y = wrap(44, y, paragraph)
            y += 28
        page.draw_line((44, 782), (551, 782), color=rgb("#C7D0BE"), width=1)
        text(44, 810, FOOTER, 10, MUTED)
        text(522, 810, "1 / 1", 10, MUTED)
        document.set_metadata({"title": "城市漫游封面规范", "author": company,
                               "subject": "自媒体企业内部演示资料（虚构）"})
        document.save(path, garbage=4, deflate=True)
    with pymupdf.open(path) as result:
        extracted = "\n".join(page.get_text() for page in result)
        for expected in ("城市漫游封面规范", "陈晨", "林晓", "315E4B", "1600"):
            if expected not in extracted:
                raise RuntimeError(f"PDF text verification failed: {expected}")
        result[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(preview_dir / "cover-spec-page-1.png")


def create(output: Path, font_path: Path, company: str, narration: Path | None):
    output = output.resolve()
    font_path = font_path.resolve()
    if not font_path.is_file():
        raise ValueError("--font must point to a readable local Chinese font")
    if narration and not narration.is_file():
        raise ValueError("--narration must point to a readable local audio file")
    if not company.strip() or len(company) > 40 or any(ord(c) < 32 for c in company):
        raise ValueError("--company must contain 1-40 printable characters")
    output.mkdir(parents=True, exist_ok=True)
    preview = output / ".build"
    preview.mkdir(exist_ok=True)
    names = {
        "document": "01_九月城市漫游选题方案.txt",
        "pdf": "02_城市漫游封面规范.pdf",
        "image": "03_城市漫游封面提案.png",
        "video": "04_拍摄流程培训.mp4",
    }
    text_document = f"""{company}｜九月城市漫游选题方案

栏目名称：城市漫游
本期主题：郑州周末散步
项目负责人：林晓
执行编辑：陈晨

一、选题目标
用短片和图文记录郑州适合周末散步的城市空间，让读者发现身边的生活细节。
本期封面主标题为“周末去散步”，副标题为“城市漫游·郑州篇”。

二、内容与发布
每条成片时长为60-90秒。图文包含路线介绍、沿途看点和拍摄说明。
固定发布时间为每周三19:30。
发布平台为微信公众号、百家号和今日头条。

三、生产流程
陈晨整理选题与脚本；拍摄人员先检查收音和电量，再拍摄15秒开场口播。
剪辑完成后，由陈晨初审，再交林晓终审；两级审核完成后才能发布。
封面由陈晨初审、林晓终审，配色与排版遵循《城市漫游封面规范》。

四、素材归档
每个选题按“文案、封面、原始视频、成片”四类归档。
文件命名建议：栏目_选题_日期_版本。例如：城市漫游_郑州周末散步_20260916_v01。
发布后保留终审版本，并记录平台、发布时间、链接和素材授权来源。

{FOOTER}
"""
    (output / names["document"]).write_text(text_document, encoding="utf-8")
    poster(font_path, company).save(output / names["image"], optimize=True)
    create_pdf(output / names["pdf"], company, preview)
    slides = []
    for step in (1, 2):
        path = preview / f"training-step-{step}.png"
        training_slide(step, font_path, company).save(path)
        slides.append(path)
    concat = preview / "slides.txt"
    concat.write_text("file 'training-step-1.png'\nduration 6\nfile 'training-step-2.png'\nduration 6\nfile 'training-step-2.png'\n", encoding="utf-8")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
               "-safe", "0", "-i", str(concat)]
    if narration:
        command += ["-i", str(narration.resolve()), "-map", "0:v:0", "-map", "1:a:0", "-af", "apad"]
    command += ["-vf", "fps=12", "-t", "12", "-c:v", "libx264", "-preset", "fast",
                "-pix_fmt", "yuv420p"]
    command += ["-c:a", "aac", "-ar", "16000", "-ac", "1"] if narration else ["-an"]
    command += ["-movflags", "+faststart", str(output / names["video"])]
    run(command)
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_entries",
                           "stream=codec_type:format=duration", "-of", "json", str(output / names["video"])]))
    if abs(float(probe["format"]["duration"]) - 12) > .15:
        raise RuntimeError("Training video must be 12 seconds long")
    stream_types = {stream["codec_type"] for stream in probe["streams"]}
    if "video" not in stream_types or bool(narration) != ("audio" in stream_types):
        raise RuntimeError("Unexpected video/audio tracks")
    manifest = {
        "company": company,
        "library_name": "企业数字资产 AI 管理平台",
        "purpose": "虚构的自媒体企业内部资料，用于演示文档、图片和视频管理及问答",
        "files": names,
        "assets": [
            {"file_name": names["document"], "media_type": "document", "expected_facts":
             ["城市漫游", "郑州周末散步", "负责人林晓", "每周三19:30", "60-90秒", "陈晨初审，林晓终审"]},
            {"file_name": names["pdf"], "media_type": "document", "expected_facts":
             ["森林绿 #315E4B", "1600 × 1000", "微信公众号、百家号和今日头条"], "pages": 1, "has_text_layer": True},
            {"file_name": names["image"], "media_type": "image", "expected_facts":
             ["周末去散步", "城市漫游·郑州篇", company, "城市公园插画"]},
            {"file_name": names["video"], "media_type": "video", "expected_facts":
             ["第一步：检查收音和电量", "第二步：拍摄15秒开场口播"], "duration_seconds": 12,
             "scenes": [{"start_seconds": 0, "end_seconds": 6, "step": "检查收音和电量"},
                        {"start_seconds": 6, "end_seconds": 12, "step": "拍摄15秒开场口播"}]},
        ],
        "video_duration_seconds": float(probe["format"]["duration"]),
        "video_has_audio": "audio" in stream_types,
        "narration": "本地提供的中文旁白" if narration else "无旁白；视频含清晰中文字幕",
        "sample_questions": ["城市漫游由谁负责，每周什么时候发布？",
                             "城市漫游封面的主色和尺寸是什么？",
                             "周末去散步封面上画了什么？",
                             "拍摄培训视频里，检查收音和电量之后要做什么？"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True, help="Readable local Chinese TTF, OTF or TTC font")
    parser.add_argument("--company", default="星河内容工作室", help="Fictional company display name")
    parser.add_argument("--narration", type=Path, help="Optional local Chinese narration; omitted means silent captions")
    args = parser.parse_args()
    create(args.output, args.font, args.company, args.narration)
