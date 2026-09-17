"""Media extraction boundary and degradation tests; no model downloads needed."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1] / "llamaindex_rag"
sys.path.insert(0, str(BACKEND))
import media_extract as media

try:
    from PIL import Image
except ImportError:
    Image = None


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "upload.mp4"
        self.source.write_bytes(b"synthetic fixture")
        self.artifacts = self.root / "artifacts"
        self.progress = []

    def tearDown(self):
        self.temporary.cleanup()

    def progress_callback(self, value, message):
        self.progress.append((value, message))

    def video_metadata(self, duration=20, has_audio=False):
        return {"duration_seconds": duration, "width": 640, "height": 360, "has_audio": has_audio}

    def fake_ffmpeg(self, argv, timeout):
        Path(argv[-1]).write_bytes(b"decoded fixture")
        return b""

    def test_frame_times_never_seek_beyond_end(self):
        for duration in (0.0001, 0.001, 0.01, 0.2, 1, 10, 300):
            for count in (1, 6, 24):
                times = media._frame_times(duration, count)
                self.assertLessEqual(len(times), count)
                self.assertEqual(times[0], 0)
                self.assertEqual(times, sorted(set(times)))
                self.assertTrue(all(0 <= time < duration for time in times))

    def test_probe_rejects_video_over_limit(self):
        data = {"streams": [{"codec_type": "video", "width": 640, "height": 360}], "format": {"duration": "300.1"}}
        with patch.object(media, "_run_media", return_value=json.dumps(data).encode()):
            with patch.dict(os.environ, {"VIDEO_MAX_SECONDS": "300"}):
                with self.assertRaisesRegex(media.MediaExtractionError, "超过当前 300 秒"):
                    media._probe_video(self.source)

    def test_probe_accepts_container_duration_when_stream_duration_unavailable(self):
        data = {"streams": [{"codec_type": "video", "width": 640, "height": 360, "duration": "N/A"}], "format": {"duration": "20.5"}}
        with patch.object(media, "_run_media", return_value=json.dumps(data).encode()):
            self.assertEqual(media._probe_video(self.source)["duration_seconds"], 20.5)

    def test_probe_rejects_non_finite_duration(self):
        data = {"streams": [{"codec_type": "video", "width": 640, "height": 360}], "format": {"duration": "NaN"}}
        with patch.object(media, "_run_media", return_value=json.dumps(data).encode()):
            with self.assertRaises(media.MediaExtractionError):
                media._probe_video(self.source)

    def test_probe_rejects_audio_only_and_oversized_video(self):
        for streams in ([{"codec_type": "audio"}], [{"codec_type": "video", "width": 100000, "height": 100000}]):
            data = {"streams": streams, "format": {"duration": "20"}}
            with patch.object(media, "_run_media", return_value=json.dumps(data).encode()):
                with self.assertRaises(media.MediaExtractionError):
                    media._probe_video(self.source)

    def test_caption_rejects_empty_and_repeated_output(self):
        for text in ("", "none", "11111111111", "检查设备" * 20, None):
            with self.assertRaises(media.MediaExtractionError):
                media._clean_caption(text)
        self.assertEqual(media._clean_caption("<think>猜测型号</think>图中可见红色阀门和蓝色管道。"), "图中可见红色阀门和蓝色管道。")

    def test_caption_checkpoint_only_reused_for_same_image_and_model(self):
        image = self.root / "frame.jpg"
        image.write_bytes(b"first-image")
        cache = self.root / "caption.json"
        caption = "图中可见红色阀门，旁边标注关闭。"
        def response(*args, **kwargs):
            return io.BytesIO(json.dumps({"message": {"content": caption}}).encode())
        with patch.object(media.urllib.request, "urlopen", side_effect=response) as request:
            media._caption(image, cache)
            media._caption(image, cache)
            self.assertEqual(request.call_count, 1)
            image.write_bytes(b"different-image")
            media._caption(image, cache)
            self.assertEqual(request.call_count, 2)
            with patch.dict(os.environ, {"VISION_MODEL": "different-local-model"}):
                media._caption(image, cache)
            self.assertEqual(request.call_count, 3)

    @unittest.skipIf(Image is None, "Pillow required")
    def test_image_orientation_resize_and_alpha_are_applied(self):
        source = self.root / "equipment.png"
        Image.new("RGBA", (2400, 1600), (255, 0, 0, 0)).save(source)
        with patch.object(media, "_caption", return_value="画面为浅色背景，未见清晰设备文字。"):
            result = media.extract_media(source, "equipment.png", self.artifacts, self.progress_callback)
        self.assertEqual(result.metadata["width"], 2400)
        self.assertEqual(result.chunks[0].metadata["media_type"], "image")
        with Image.open(self.artifacts / "thumbnail.jpg") as thumbnail:
            self.assertEqual(thumbnail.mode, "RGB")
            self.assertLessEqual(max(thumbnail.size), 1280)
            self.assertTrue(all(channel > 245 for channel in thumbnail.getpixel((0, 0))))
        self.assertEqual(self.progress[-1][0], 75)

    @unittest.skipIf(Image is None, "Pillow required")
    def test_exif_rotation_preserves_display_orientation(self):
        source = self.root / "rotated.jpg"
        original = Image.new("RGB", (60, 30), "blue")
        exif = Image.Exif()
        exif[274] = 6
        original.save(source, exif=exif)
        details = media._prepare_image(source, self.root / "thumbnail.jpg")
        self.assertEqual((details["width"], details["height"]), (30, 60))

    @unittest.skipIf(Image is None, "Pillow required")
    def test_invalid_image_is_rejected_before_model_call(self):
        with patch.object(media, "_caption") as caption:
            with self.assertRaises(media.MediaExtractionError):
                media.extract_media(self.source, "disguised.png", self.artifacts, self.progress_callback)
            caption.assert_not_called()

    def test_silent_video_has_timestamp_sources_and_explicit_coverage_warning(self):
        with patch.object(media, "_probe_video", return_value=self.video_metadata()), \
                patch.object(media, "_run_media", side_effect=self.fake_ffmpeg), \
                patch.object(media, "_caption", return_value="画面中可见操作人员正在转动红色阀门。"):
            result = media.extract_media(self.source, "training.mp4", self.artifacts, self.progress_callback)
        self.assertTrue(result.chunks)
        self.assertTrue(all(chunk.metadata["source_kind"] == "visual" for chunk in result.chunks))
        self.assertTrue(all(0 <= chunk.metadata["start_seconds"] < 20 for chunk in result.chunks))
        self.assertTrue(any("仅采样" in warning for warning in result.metadata["warnings"]))
        self.assertTrue(any("没有音轨" in warning for warning in result.metadata["warnings"]))
        self.assertTrue((self.artifacts / "thumbnail.jpg").is_file())

    def test_failed_speech_keeps_visuals_and_removes_temporary_audio(self):
        with patch.object(media, "_probe_video", return_value=self.video_metadata(has_audio=True)), \
                patch.object(media, "_run_media", side_effect=self.fake_ffmpeg), \
                patch.object(media, "_caption", return_value="画面中可见操作人员正在转动红色阀门。"), \
                patch.object(media, "_speech_chunks", side_effect=RuntimeError("internal path /secret")), \
                self.assertLogs(media._logger, level="ERROR"):
            result = media.extract_media(self.source, "training.mp4", self.artifacts, self.progress_callback)
        self.assertTrue(result.chunks)
        self.assertEqual(result.metadata["speech_chunk_count"], 0)
        self.assertTrue(any("语音未完成" in warning for warning in result.metadata["warnings"]))
        self.assertNotIn("/secret", json.dumps(result.metadata))
        self.assertFalse((self.artifacts / "audio.wav").exists())

    def test_failed_vision_can_fall_back_to_speech_with_warning(self):
        speech = media.MediaChunk("先关闭电源，再检查指示灯。", {"media_type": "video", "source_kind": "audio", "start_seconds": 0, "end_seconds": 3})
        with patch.object(media, "_probe_video", return_value=self.video_metadata(has_audio=True)), \
                patch.object(media, "_run_media", side_effect=self.fake_ffmpeg), \
                patch.object(media, "_caption", side_effect=media.MediaExtractionError("测试视觉错误")), \
                patch.object(media, "_speech_chunks", return_value=[speech]):
            result = media.extract_media(self.source, "training.mp4", self.artifacts, self.progress_callback)
        self.assertEqual(result.chunks, [speech])
        self.assertEqual(result.metadata["frame_count"], 0)
        self.assertTrue(any("画面处理失败" in warning for warning in result.metadata["warnings"]))

    def test_video_without_any_content_fails(self):
        with patch.object(media, "_probe_video", return_value=self.video_metadata()), \
                patch.object(media, "_run_media", side_effect=self.fake_ffmpeg), \
                patch.object(media, "_caption", side_effect=media.MediaExtractionError("无可用内容")):
            with self.assertRaisesRegex(media.MediaExtractionError, "未提取到可用内容"):
                media.extract_media(self.source, "training.mp4", self.artifacts, self.progress_callback)

    def test_speech_word_timestamps_split_a_long_silent_gap(self):
        words = [types.SimpleNamespace(start=0.0, end=0.5, word="Step one."),
                 types.SimpleNamespace(start=0.5, end=2.0, word=" Close the blue valve."),
                 types.SimpleNamespace(start=5.0, end=5.5, word=" Step two."),
                 types.SimpleNamespace(start=5.5, end=7.2, word=" Press the green button.")]
        segment = types.SimpleNamespace(start=0, end=7.2, text="both steps", words=words)
        spans = media._speech_spans(segment)
        self.assertEqual(len(spans), 2)
        self.assertEqual(spans[0][:2], (0, 2))
        self.assertEqual(spans[1][:2], (5, 7.2))
        self.assertIn("green button", spans[1][2])

    def test_speech_groups_preserve_time_ranges_and_ignore_invalid_segments(self):
        model_path = self.root / "model"
        model_path.mkdir()
        (model_path / "model.bin").write_bytes(b"local model")
        audio = self.root / "audio.wav"
        audio.write_bytes(b"local audio")
        raw = [(0, 5, "关闭电源。"), (6, 10, "检查指示灯。"), (31, 35, "拆卸外壳。"),
               (-5, -1, "无效时间。"), (float("nan"), 20, "无效数字。"), (39, 50, "清理过滤器。")]
        segments = [types.SimpleNamespace(start=start, end=end, text=text) for start, end, text in raw]
        class FakeWhisperModel:
            def __init__(self, *args, **kwargs):
                self.kwargs = kwargs
            def transcribe(self, *args, **kwargs):
                return iter(segments), None
        with patch.dict(os.environ, {"WHISPER_MODEL_PATH": str(model_path)}), \
                patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=FakeWhisperModel)}):
            chunks = media._speech_chunks(audio, 40, self.root / "speech.json", "training.mp4")
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].metadata["start_seconds"], 0)
        self.assertEqual(chunks[0].metadata["end_seconds"], 10)
        self.assertEqual(chunks[1].metadata["start_seconds"], 31)
        self.assertEqual(chunks[1].metadata["end_seconds"], 35)
        self.assertEqual(chunks[2].metadata["start_seconds"], 39)
        self.assertEqual(chunks[2].metadata["end_seconds"], 40)
        self.assertNotIn("无效", "".join(chunk.text for chunk in chunks))


if __name__ == "__main__":
    unittest.main(verbosity=2)
