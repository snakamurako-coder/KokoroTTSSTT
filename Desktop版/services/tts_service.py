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


class TTSService:
    """TTS (音声合成) 統合サービス"""
    
    def __init__(self, output_dir: str | Path = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sapi_voice = None
        self._piper_cache: Dict[str, Any] = {}

    # -------------------------------------------------------------
    # Windows SAPI 音声合成 (標準搭載)
    # -------------------------------------------------------------
    def get_sapi_voices(self) -> List[Dict[str, str]]:
        """Windows SAPI で利用可能な音声一覧を取得"""
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

    def synthesize_sapi(self, text: str, voice_name: Optional[str] = None, rate: int = 0, volume: int = 100, output_path: Optional[str | Path] = None) -> Path:
        """
        SAPI でテキストを WAV ファイルに合成
        :param text: 読み上げテキスト
        :param voice_name: 音声名 (例: "Microsoft Haruka Desktop - Japanese")
        :param rate: 速度 (-10 〜 +10)
        :param volume: 音量 (0 〜 100)
        :param output_path: 出力先パス
        """
        if not HAS_SAPI:
            raise RuntimeError("win32com (SAPI) が利用できません")

        if output_path is None:
            output_path = self.output_dir / f"sapi_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        voice = win32com.client.Dispatch("SAPI.SpVoice")
        
        # 音声選択
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
        # SSFMCreateForWrite = 3
        stream.Open(str(output_path), 3)
        voice.AudioOutputStream = stream
        voice.Speak(text)
        stream.Close()

        return output_path

    # -------------------------------------------------------------
    # Piper AI TTS 音声合成 (高速ニューラルTTS)
    # -------------------------------------------------------------
    def get_piper_voice(self, model_path: str | Path, config_path: Optional[str | Path] = None) -> Any:
        """PiperVoice モデルのロード (キャッシュ付き)"""
        if not HAS_PIPER:
            raise RuntimeError("piper-tts が利用できません")

        model_path = str(model_path)
        if model_path in self._piper_cache:
            return self._piper_cache[model_path]

        config_path = str(config_path) if config_path else None
        voice = PiperVoice.load(model_path, config_path=config_path, use_cuda=False)
        self._piper_cache[model_path] = voice
        return voice

    def synthesize_piper(self, text: str, model_path: str | Path, config_path: Optional[str | Path] = None, output_path: Optional[str | Path] = None) -> Path:
        """
        Piper でテキストを WAV ファイルに合成
        """
        if not HAS_PIPER:
            raise RuntimeError("piper-tts が利用できません")

        if output_path is None:
            output_path = self.output_dir / f"piper_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        voice = self.get_piper_voice(model_path, config_path)
        with wave.open(str(output_path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)

        return output_path

    # -------------------------------------------------------------
    # 対話台本の結合合成 (Dialogue Synthesize & Merge)
    # -------------------------------------------------------------
    def synthesize_dialogue(self, blocks: List[Dict[str, Any]], engine: str = "sapi", silence_sec: float = 0.3, output_path: Optional[str | Path] = None) -> Path:
        """
        複数ブロックの対話テキストを話者ごとに合成し、無音を挟んで1つのWAVにマージする
        blocks: [ {"speaker": "...", "voice": "...", "text": "...", "rate": 0, "volume": 100}, ... ]
        """
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
                
                if engine == "piper":
                    model_path = b.get("model_path")
                    if not model_path or not os.path.exists(model_path):
                        raise FileNotFoundError(f"Piperモデルファイルが見つかりません: {model_path}")
                    self.synthesize_piper(text, model_path, output_path=temp_path)
                else: # SAPI
                    v_name = b.get("voice")
                    rate = b.get("rate", 0)
                    vol = b.get("volume", 100)
                    self.synthesize_sapi(text, voice_name=v_name, rate=rate, volume=vol, output_path=temp_path)

                temp_wavs.append(temp_path)

            if not temp_wavs:
                raise ValueError("合成可能なテキストブロックがありませんでした")

            # WAVファイルを結合
            self.merge_wavs(temp_wavs, output_path, silence_sec=silence_sec)

        finally:
            # 一時ファイルの削除
            for p in temp_wavs:
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass

        return output_path

    @staticmethod
    def merge_wavs(wav_paths: List[Path], output_path: Path, silence_sec: float = 0.3):
        """複数のWAVファイルを結合（サンプリングレート・チャンネルを第1ファイルに統一）"""
        if not wav_paths:
            return

        with wave.open(str(wav_paths[0]), "rb") as first_wav:
            params = first_wav.getparams()
            sample_rate = params.framerate
            n_channels = params.nchannels
            sampwidth = params.sampwidth

        # 無音フレームデータの作成
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
