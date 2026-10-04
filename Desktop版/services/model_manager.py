import os
import requests
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread

MODEL_DEFINITIONS = {
    "kokoro_en": {
        "name": "Kokoro (英語・最高品質)",
        "files": [
            {
                "filename": "kokoro-v0_19.onnx",
                "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
                "size_mb": 86
            },
            {
                "filename": "voices.bin",
                "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin",
                "size_mb": 5.8
            }
        ]
    },
    "piper_ja": {
        "name": "Piper (日本語 - Hi-Fi Captain)",
        "files": [
            {
                "filename": "ja_JP-hi_fi_captain-medium.onnx",
                "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ja/ja_JP/hi_fi_captain/medium/ja_JP-hi_fi_captain-medium.onnx",
                "size_mb": 63
            },
            {
                "filename": "ja_JP-hi_fi_captain-medium.onnx.json",
                "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ja/ja_JP/hi_fi_captain/medium/ja_JP-hi_fi_captain-medium.onnx.json",
                "size_mb": 0.01
            }
        ]
    },
    "piper_en": {
        "name": "Piper (英語 - Lessac)",
        "files": [
            {
                "filename": "en_US-lessac-medium.onnx",
                "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
                "size_mb": 63
            },
            {
                "filename": "en_US-lessac-medium.onnx.json",
                "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
                "size_mb": 0.01
            }
        ]
    }
}


class ModelDownloadWorker(QThread):
    """モデルダウンロード用バックグラウンドスレッド"""
    progress = Signal(int, str)       # percent, status message
    finished = Signal(bool, str)      # success, message

    def __init__(self, model_key: str, models_dir: Path, parent=None):
        super().__init__(parent)
        self.model_key = model_key
        self.models_dir = Path(models_dir)
        self._is_cancelled = False

    def run(self):
        if self.model_key not in MODEL_DEFINITIONS:
            self.finished.emit(False, f"未定義のモデルキー: {self.model_key}")
            return

        info = MODEL_DEFINITIONS[self.model_key]
        self.models_dir.mkdir(parents=True, exist_ok=True)
        files = info["files"]

        total_files = len(files)
        for idx, f_info in enumerate(files):
            if self._is_cancelled:
                self.finished.emit(False, "ダウンロードがキャンセルされました")
                return

            filename = f_info["filename"]
            url = f_info["url"]
            dest_path = self.models_dir / filename

            self.progress.emit(
                int((idx / total_files) * 100),
                f"{filename} をダウンロード中 ({idx+1}/{total_files})..."
            )

            try:
                with requests.get(url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    total_bytes = int(r.headers.get("content-length", 0))
                    downloaded = 0
                    
                    with open(dest_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 64):
                            if self._is_cancelled:
                                return
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_bytes > 0:
                                    percent = int(((idx + downloaded / total_bytes) / total_files) * 100)
                                    mb_done = downloaded / (1024 * 1024)
                                    mb_total = total_bytes / (1024 * 1024)
                                    self.progress.emit(percent, f"{filename} ({mb_done:.1f}MB / {mb_total:.1f}MB)...")

            except Exception as e:
                # 失敗時は不完全なファイルを削除
                if dest_path.exists():
                    try:
                        dest_path.unlink()
                    except Exception:
                        pass
                self.finished.emit(False, f"{filename} のダウンロードに失敗しました: {e}")
                return

        self.progress.emit(100, "ダウンロード完了！")
        self.finished.emit(True, f"{info['name']} の準備が完了しました！")

    def cancel(self):
        self._is_cancelled = True


class ModelManager:
    """モデルファイルの有無確認・管理"""
    def __init__(self, models_dir: str | Path = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def is_model_installed(self, model_key: str) -> bool:
        if model_key not in MODEL_DEFINITIONS:
            return False
        info = MODEL_DEFINITIONS[model_key]
        for f in info["files"]:
            p = self.models_dir / f["filename"]
            if not p.exists() or p.stat().st_size == 0:
                return False
        return True

    def get_model_path(self, filename: str) -> Path:
        return self.models_dir / filename
