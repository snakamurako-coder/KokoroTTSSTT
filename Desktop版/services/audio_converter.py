import os
import subprocess
from pathlib import Path
from typing import Optional

try:
    import imageio_ffmpeg
    HAS_FFMPEG = True
except ImportError:
    HAS_FFMPEG = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False


class AudioConverter:
    """音声リサンプリング・チャンネル変換・エンコード (WAV / MP3 / WebM)"""

    @staticmethod
    def get_ffmpeg_exe() -> Optional[str]:
        if HAS_FFMPEG:
            try:
                return imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                pass
        return None

    @classmethod
    def convert(
        cls,
        input_wav: Path,
        output_path: Path,
        format_type: str = "wav",      # "wav", "mp3", "webm"
        sample_rate: int = 24000,      # 16000, 22050, 24000, 44100
        channels: int = 1,             # 1 (mono), 2 (stereo)
        bitrate_kbps: int = 128        # 64, 128, 192, 256, 320
    ) -> Path:
        """
        音声を指定のフォーマット・サンプルレート・チャンネル・ビットレートにエンコード
        """
        input_wav = Path(input_wav)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        format_type = format_type.lower()

        ffmpeg_exe = cls.get_ffmpeg_exe()

        if ffmpeg_exe:
            # FFmpeg を使用した高音質エンコード
            cmd = [
                ffmpeg_exe, "-y",
                "-i", str(input_wav),
                "-ar", str(sample_rate),
                "-ac", str(channels)
            ]

            if format_type == "mp3":
                cmd.extend(["-b:a", f"{bitrate_kbps}k", str(output_path)])
            elif format_type == "webm":
                # Opus コーデックで WebM 音声コンテナを作成
                cmd.extend(["-c:a", "libopus", "-b:a", f"{bitrate_kbps}k", str(output_path)])
            else: # wav
                cmd.append(str(output_path))

            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return output_path

        elif HAS_SOUNDFILE:
            # FFmpeg が無い場合の soundfile フォールバック
            data, sr = sf.read(str(input_wav))
            # チャンネル調整
            if channels == 1 and data.ndim > 1:
                data = data.mean(axis=1)
            elif channels == 2 and data.ndim == 1:
                import numpy as np
                data = np.column_stack((data, data))

            if format_type == "mp3":
                sf.write(str(output_path), data, sample_rate, format="MP3")
            else:
                sf.write(str(output_path), data, sample_rate, format="WAV")
            return output_path

        else:
            raise RuntimeError("音声変換ツール (FFmpeg / soundfile) が利用できません")
