import os
import asyncio
from pathlib import Path
from typing import Optional, Callable
from PySide6.QtCore import QObject, Signal, QThread

try:
    import winrt.windows.media.speechrecognition as winrt_sr
    HAS_WINRT_STT = True
except ImportError:
    HAS_WINRT_STT = False

try:
    import speech_recognition as py_sr
    HAS_PY_SR = True
except ImportError:
    HAS_PY_SR = False


class STTService:
    """音声認識 (STT) 統合サービス"""

    def __init__(self):
        self._recognizer = None

    def transcribe_file(self, file_path: str | Path, language: str = "ja-JP") -> str:
        """
        WAV音声ファイルから文字起こしを行う
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"音声ファイルが見つかりません: {file_path}")

        if not HAS_PY_SR:
            raise RuntimeError("speech_recognition ライブラリが利用できません")

        r = py_sr.Recognizer()
        with py_sr.AudioFile(str(file_path)) as source:
            audio_data = r.record(source)

        try:
            # Google Web Speech API (無料・キー不要)
            text = r.recognize_google(audio_data, language=language)
            return text
        except py_sr.UnknownValueError:
            return "（音声を認識できませんでした）"
        except py_sr.RequestError as e:
            raise RuntimeError(f"音声認識サービス接続エラー: {e}")


class WinRTMicWorker(QThread):
    """Windows 11 ネイティブマイク音声認識ワーカー (WinRT)"""
    text_recognized = Signal(str)
    status_changed = Signal(str)
    error_occurred = Signal(str)
    finished_listening = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False

    def run(self):
        if not HAS_WINRT_STT:
            self.error_occurred.emit("WinRT SpeechRecognition が利用できません")
            return

        self._is_running = True
        self.status_changed.emit("マイク準備中...")

        async def _listen():
            try:
                recognizer = winrt_sr.SpeechRecognizer()
                await recognizer.compile_constraints_async()
                
                self.status_changed.emit("🎤 音声を聞き取っています...（話し終えると自動認識）")
                
                # 単一セッションの認識 (UIスレッドをブロックしない)
                result = await recognizer.recognize_async()
                
                if result.status == winrt_sr.SpeechRecognitionResultStatus.SUCCESS:
                    text = result.text
                    if text:
                        self.text_recognized.emit(text)
                    else:
                        self.text_recognized.emit("（無音または認識不能）")
                else:
                    self.status_changed.emit(f"認識終了 (ステータス: {result.status})")
            except Exception as e:
                self.error_occurred.emit(f"音声認識エラー: {e}")
            finally:
                self.finished_listening.emit()

        asyncio.run(_listen())

    def stop(self):
        self._is_running = False
