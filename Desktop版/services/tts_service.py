import os
import wave
import io
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import win32com.client
    HAS_SAPI = True
except ImportError:
    HAS_SAPI = False

try:
    from piper import PiperVoice
    HAS_PIPER = True
except ImportError:
    HAS_PIPER = False

try:
    from kokoro_onnx import Kokoro
    import soundfile as sf
    HAS_KOKORO = True
except ImportError:
    HAS_KOKORO = False

from services.model_manager import ModelManager


class TTSService:
    """TTS (音声合成) 統合サービス: Kokoro, Piper, SAPI"""

    def __init__(self, output_dir: str | Path = "output", models_dir: str | Path = "models"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.model_manager = ModelManager(self.models_dir)
        self._piper_cache: Dict[str, Any] = {}
        self._kokoro_instance = None

    # -------------------------------------------------------------
    # ボイスリスト取得
    # -------------------------------------------------------------
    def get_voices_for_engine(self, engine: str) -> List[Dict[str, str]]:
        if engine == "kokoro":
            return [
                {"id": "af_heart", "name": "🇺🇸 女性 (Heart・最高品質・標準)"},
                {"id": "af_bella", "name": "🇺🇸 女性 (Bella)"},
                {"id": "af_nicole", "name": "🇺🇸 女性 (Nicole)"},
                {"id": "af_sky", "name": "🇺🇸 女性 (Sky・高め)"},
                {"id": "af_sarah", "name": "🇺🇸 女性 (Sarah)"},
                {"id": "af_nova", "name": "🇺🇸 女性 (Nova)"},
                {"id": "am_adam", "name": "🇺🇸 男性 (Adam・標準)"},
                {"id": "am_echo", "name": "🇺🇸 男性 (Echo)"},
                {"id": "am_eric", "name": "🇺🇸 男性 (Eric)"},
                {"id": "am_onyx", "name": "🇺🇸 男性 (Onyx・低音)"},
                {"id": "am_michael", "name": "🇺🇸 男性 (Michael)"},
                {"id": "bf_emma", "name": "🇬🇧 女性 (Emma・英国)"},
                {"id": "bf_isabella", "name": "🇬🇧 女性 (Isabella・英国)"},
                {"id": "bm_george", "name": "🇬🇧 男性 (George・英国)"},
                {"id": "bm_lewis", "name": "🇬🇧 男性 (Lewis・英国)"},
            ]
        elif engine == "piper":
            return [
                {"id": "piper_ja", "name": "🇯🇵 日本語 - Hi-Fi Captain (クリア・自然)"},
                {"id": "piper_en", "name": "🇺🇸 英語 - Lessac (標準・明瞭)"},
            ]
        else: # sapi
            return self.get_sapi_voices()

    def get_sapi_voices(self) -> List[Dict[str, str]]:
        if not HAS_SAPI:
            return []
        voices = []
        try:
            voice_engine = win32com.client.Dispatch("SAPI.SpVoice")
            tokens = voice_engine.GetVoices()
            for i in range(tokens.Count):
                token = tokens.Item(i)
                desc = token.GetDescription()
                voices.append({"id": desc, "name": desc})
        except Exception as e:
            print(f"SAPI音声一覧取得エラー: {e}")
        return voices

    # -------------------------------------------------------------
    # ① Kokoro (英語専用・ローカルONNXニューラル推論)
    # -------------------------------------------------------------
    def get_kokoro(self) -> Any:
        if not HAS_KOKORO:
            raise RuntimeError("kokoro-onnx または soundfile がインストールされていません")

        if self._kokoro_instance is not None:
            return self._kokoro_instance

        model_path = self.models_dir / "kokoro-v0_19.onnx"
        voices_path = self.models_dir / "voices.bin"
        if not model_path.exists() or not voices_path.exists():
            raise FileNotFoundError(
                "Kokoro のモデルファイルが見つかりません。\n"
                "設定画面またはダイアログからモデルをダウンロードしてください。"
            )

        self._kokoro_instance = Kokoro(str(model_path), str(voices_path))
        return self._kokoro_instance

    def synthesize_kokoro(self, text: str, voice_name: str = "af_heart", speed: float = 1.0, output_path: Optional[str | Path] = None) -> Path:
        kokoro = self.get_kokoro()
        if output_path is None:
            output_path = self.output_dir / f"kokoro_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        samples, sample_rate = kokoro.create(text, voice=voice_name, speed=speed, lang="en-us")
        sf.write(str(output_path), samples, sample_rate)
        return output_path

    # -------------------------------------------------------------
    # ② Piper (日本語・英語・ローカルPiperVoice)
    # -------------------------------------------------------------
    def get_piper_voice(self, model_key: str) -> Any:
        if not HAS_PIPER:
            raise RuntimeError("piper-tts が利用できません")

        if model_key == "piper_ja":
            onnx_name = "ja_JP-hi_fi_captain-medium.onnx"
        else: # piper_en
            onnx_name = "en_US-lessac-medium.onnx"

        model_path = self.models_dir / onnx_name
        config_path = self.models_dir / f"{onnx_name}.json"

        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper モデルファイルが見つかりません: {onnx_name}\n"
                "設定画面またはダイアログからモデルをダウンロードしてください。"
            )

        str_path = str(model_path)
        if str_path in self._piper_cache:
            return self._piper_cache[str_path]

        voice = PiperVoice.load(str_path, config_path=str(config_path) if config_path.exists() else None, use_cuda=False)
        self._piper_cache[str_path] = voice
        return voice

    def synthesize_piper(self, text: str, model_key: str = "piper_ja", output_path: Optional[str | Path] = None) -> Path:
        if not HAS_PIPER:
            raise RuntimeError("piper-tts が利用できません")

        if output_path is None:
            output_path = self.output_dir / f"piper_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        voice = self.get_piper_voice(model_key)
        with wave.open(str(output_path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)

        return output_path

    # -------------------------------------------------------------
    # ③ Windows SAPI (OS標準・即座利用)
    # -------------------------------------------------------------
    def synthesize_sapi(self, text: str, voice_name: Optional[str] = None, rate: int = 0, volume: int = 100, output_path: Optional[str | Path] = None) -> Path:
        if not HAS_SAPI:
            raise RuntimeError("win32com (SAPI) が利用できません")

        if output_path is None:
            output_path = self.output_dir / f"sapi_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        voice = win32com.client.Dispatch("SAPI.SpVoice")
        if voice_name:
            tokens = voice.GetVoices()
            for i in range(tokens.Count):
                t = tokens.Item(i)
                if t.GetDescription() == voice_name:
                    voice.Voice = t
                    break

        voice.Rate = max(-10, min(10, rate))
        voice.Volume = max(0, min(100, volume))

        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(str(output_path), 3) # SSFMCreateForWrite
        voice.AudioOutputStream = stream
        voice.Speak(text)
        stream.Close()

        return output_path

    # -------------------------------------------------------------
    # 対話台本の結合合成 (Dialogue Synthesize & Merge)
    # -------------------------------------------------------------
    def synthesize_dialogue(self, blocks: List[Dict[str, Any]], engine: str = "sapi", speed: float = 1.0, silence_sec: float = 0.3, output_path: Optional[str | Path] = None) -> Path:
        if not blocks:
            raise ValueError("対話ブロックが空です")

        if output_path is None:
            output_path = self.output_dir / f"dialogue_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)

        temp_wavs: List[Path] = []
        try:
            for i, b in enumerate(blocks):
                text = b.get("text", "").strip()
                if not text:
                    continue

                temp_path = self.output_dir / f"_temp_block_{i}_{os.urandom(4).hex()}.wav"
                v_id = b.get("voice", "")

                if engine == "kokoro":
                    self.synthesize_kokoro(text, voice_name=v_id or "af_heart", speed=speed, output_path=temp_path)
                elif engine == "piper":
                    self.synthesize_piper(text, model_key=v_id or "piper_ja", output_path=temp_path)
                else: # sapi
                    rate_val = int((speed - 1.0) * 10) # 1.0 -> 0, 0.5 -> -5, 2.0 -> 10
                    self.synthesize_sapi(text, voice_name=v_id, rate=rate_val, volume=100, output_path=temp_path)

                temp_wavs.append(temp_path)

            if not temp_wavs:
                raise ValueError("合成可能なテキストブロックがありませんでした")

            # WAVファイルを結合
            self.merge_wavs(temp_wavs, output_path, silence_sec=silence_sec)

        finally:
            for p in temp_wavs:
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass

        return output_path

    @staticmethod
    def merge_wavs(wav_paths: List[Path], output_path: Path, silence_sec: float = 0.3):
        """複数のWAVファイルをリサンプリング・チャンネル統一して結合"""
        if not wav_paths:
            return

        with wave.open(str(wav_paths[0]), "rb") as first_wav:
            params = first_wav.getparams()
            sample_rate = params.framerate
            n_channels = params.nchannels
            sampwidth = params.sampwidth

        silence_frames_count = int(sample_rate * silence_sec)
        silence_data = b"\x00" * (silence_frames_count * n_channels * sampwidth)

        with wave.open(str(output_path), "wb") as out_wav:
            out_wav.setparams(params)
            for idx, p in enumerate(wav_paths):
                with wave.open(str(p), "rb") as w:
                    frames = w.readframes(w.getnframes())
                    out_wav.writeframes(frames)
                if idx < len(wav_paths) - 1 and silence_sec > 0:
                    out_wav.writeframes(silence_data)
