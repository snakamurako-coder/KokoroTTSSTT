import os
import re
import unicodedata
import wave
import io
from pathlib import Path
from typing import List, Dict, Any, Optional

CENTURY_MAP = {
    '10': 'ten', '11': 'eleven', '12': 'twelve', '13': 'thirteen',
    '14': 'fourteen', '15': 'fifteen', '16': 'sixteen', '17': 'seventeen',
    '18': 'eighteen', '19': 'nineteen', '20': 'twenty', '21': 'twenty one'
}

DECADE_MAP = {
    '00': 'hundreds', '10': 'tens', '20': 'twenties', '30': 'thirties',
    '40': 'forties', '50': 'fifties', '60': 'sixties', '70': 'seventies',
    '80': 'eighties', '90': 'nineties'
}

# 単位略語 → (単数形, 複数形)。Kokoro/espeak は kg 等を字母読みにするため事前展開する。
UNIT_MAP = {
    # Length
    'km': ('kilometer', 'kilometers'),
    'cm': ('centimeter', 'centimeters'),
    'mm': ('millimeter', 'millimeters'),
    'm': ('meter', 'meters'),
    'mi': ('mile', 'miles'),
    'ft': ('foot', 'feet'),
    'in': ('inch', 'inches'),
    'yd': ('yard', 'yards'),
    # Mass
    'kg': ('kilogram', 'kilograms'),
    'mg': ('milligram', 'milligrams'),
    'g': ('gram', 'grams'),
    'lb': ('pound', 'pounds'),
    'lbs': ('pound', 'pounds'),
    'oz': ('ounce', 'ounces'),
    # Volume
    'ml': ('milliliter', 'milliliters'),
    'l': ('liter', 'liters'),
    'gal': ('gallon', 'gallons'),
    # Speed
    'mph': ('mile per hour', 'miles per hour'),
    'kph': ('kilometer per hour', 'kilometers per hour'),
    'kmh': ('kilometer per hour', 'kilometers per hour'),
    'km/h': ('kilometer per hour', 'kilometers per hour'),
    'm/s': ('meter per second', 'meters per second'),
    # Data
    'tb': ('terabyte', 'terabytes'),
    'gb': ('gigabyte', 'gigabytes'),
    'mb': ('megabyte', 'megabytes'),
    'kb': ('kilobyte', 'kilobytes'),
    # Frequency / power
    'ghz': ('gigahertz', 'gigahertz'),
    'mhz': ('megahertz', 'megahertz'),
    'khz': ('kilohertz', 'kilohertz'),
    'hz': ('hertz', 'hertz'),
    'kw': ('kilowatt', 'kilowatts'),
    'w': ('watt', 'watts'),
    # Time
    'ms': ('millisecond', 'milliseconds'),
    'sec': ('second', 'seconds'),
    'hrs': ('hour', 'hours'),
    'hr': ('hour', 'hours'),
}

# 単独でも一般英単語になり得る単位。数字に密着した場合のみ展開する (例: 5m, 2in)。
_AMBIGUOUS_UNITS = frozenset({'in', 'm', 'g', 'l', 'w'})

# 4桁西暦の Spoken form 用
_YEAR_ONES = (
    '', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'
)
_YEAR_TEENS = (
    'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
    'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'
)
_YEAR_TENS = (
    '', '', 'twenty', 'thirty', 'forty', 'fifty',
    'sixty', 'seventy', 'eighty', 'ninety'
)

# 年号の強い文脈前置詞
_YEAR_PREPS = (
    r'in|since|until|till|by|from|during|before|after|around|about'
)

# 直前にあると年号扱いしない語 (room 1998 等)
_YEAR_EXCLUDE_PREFIX = (
    r'room|page|flight|highway|apt|apartment|suite|gate|channel|'
    r'isbn|number|no\.?|nr\.?|code|id|pin|#|\$|£|€|¥'
)

# 直後にあると数量扱い（年号にしない）
_YEAR_EXCLUDE_SUFFIX = (
    r'people|persons|users|dollars?|yen|times|copies|items|units|'
    r'soldiers|troops|men|women|children|students|employees|years'
)

# 年号として扱う範囲 (2桁+2桁読みが自然な西暦)
_YEAR_MIN, _YEAR_MAX = 1100, 2199

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
from services.audio_converter import AudioConverter


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

        # 起動時に過去の未保存一時ファイルを全自動廃棄
        self.cleanup_output_dir()

    def cleanup_output_dir(self):
        """output ディレクトリ内の未保存・作業用音声ファイルを全削除（自動廃棄）"""
        if not self.output_dir.exists():
            return
        for file in self.output_dir.iterdir():
            if file.is_file() and file.name != ".gitkeep":
                try:
                    file.unlink()
                except Exception:
                    pass

    # -------------------------------------------------------------
    # ボイスリスト取得
    # -------------------------------------------------------------
    def get_voices_for_engine(self, engine: str) -> List[Dict[str, str]]:
        if engine == "kokoro":
            return [
                {"id": "af", "name": "🇺🇸 女性 (Heart / Default・最高品質)"},
                {"id": "af_bella", "name": "🇺🇸 女性 (Bella)"},
                {"id": "af_nicole", "name": "🇺🇸 女性 (Nicole)"},
                {"id": "af_sky", "name": "🇺🇸 女性 (Sky・高め)"},
                {"id": "af_sarah", "name": "🇺🇸 女性 (Sarah)"},
                {"id": "am_adam", "name": "🇺🇸 男性 (Adam・標準)"},
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

    def synthesize_kokoro(self, text: str, voice_name: str = "af", speed: float = 1.0, output_path: Optional[str | Path] = None) -> Path:
        kokoro = self.get_kokoro()
        if output_path is None:
            output_path = self.output_dir / f"kokoro_{os.urandom(4).hex()}.wav"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # エイリアス変換 & 安全なフォールバック
        actual_voice = voice_name
        if actual_voice == "af_heart" or not actual_voice:
            actual_voice = "af"

        available = kokoro.get_voices()
        if actual_voice not in available:
            actual_voice = "af" if "af" in available else available[0]

        # 年代・単位略語などを自然な英語読みに事前正規化
        processed_text = self.normalize_english_for_tts(text)

        samples, sample_rate = kokoro.create(processed_text, voice=actual_voice, speed=speed, lang="en-us")
        sf.write(str(output_path), samples, sample_rate)
        return output_path

    @classmethod
    def normalize_english_for_tts(cls, text: str) -> str:
        """英語 TTS 向けの事前正規化（全角半角化・年代・西暦・単位略語）。"""
        if not text:
            return text
        text = unicodedata.normalize('NFKC', text)
        text = cls.normalize_english_decades(text)
        text = cls.normalize_english_years(text)
        text = cls.normalize_english_units(text)
        return text

    @staticmethod
    def _two_digit_words(n: int) -> str:
        """0–99 を英語単語に。0 は空文字。"""
        if n <= 0:
            return ''
        if n < 10:
            return _YEAR_ONES[n]
        if n < 20:
            return _YEAR_TEENS[n - 10]
        tens, ones = divmod(n, 10)
        if ones == 0:
            return _YEAR_TENS[tens]
        return f'{_YEAR_TENS[tens]} {_YEAR_ONES[ones]}'

    @classmethod
    def year_to_spoken(cls, year: int | str) -> str:
        """
        4桁西暦を year-style 読みに変換する。
        例: 1998 → nineteen ninety eight / 1905 → nineteen oh five / 2000 → two thousand
        """
        try:
            y = int(year)
        except (TypeError, ValueError):
            return str(year)

        if y == 2000:
            return 'two thousand'

        left, right = divmod(y, 100)
        left_words = cls._two_digit_words(left)
        if not left_words:
            return str(y)

        if right == 0:
            return f'{left_words} hundred'
        if right < 10:
            return f'{left_words} oh {_YEAR_ONES[right]}'
        return f'{left_words} {cls._two_digit_words(right)}'

    @classmethod
    def _is_plausible_year(cls, year: int | str) -> bool:
        try:
            y = int(year)
        except (TypeError, ValueError):
            return False
        return _YEAR_MIN <= y <= _YEAR_MAX

    @classmethod
    def normalize_english_years(cls, text: str) -> str:
        """
        文脈上の4桁西暦を nineteen ninety eight 形式に展開する。
        Kokoro が one thousand nine hundred ... と誤読するのを防ぐ。

        判定（強い文脈優先）:
        1. between A and B / from A to B
        2. 前置詞 + YYYY（in/since/until/…）
        3. (the) year YYYY
        4. the YYYY
        5. (YYYY) / YYYY–YYYY 範囲
        6. 単独 YYYY（1100–2199）※ room/page/flight 等の直後は除外
        """
        if not text:
            return text

        def spoken(m_year: str) -> str:
            return cls.year_to_spoken(m_year)

        def _followed_by_quantity(after: str) -> bool:
            return bool(re.match(rf'(?i)\s+(?:{_YEAR_EXCLUDE_SUFFIX})\b', after))

        # 1. between 1998 and 2001 / from 1998 to 2005（元の大文字小文字を維持）
        def repl_between(m):
            a, b = m.group(1), m.group(2)
            if cls._is_plausible_year(a) and cls._is_plausible_year(b):
                return m.group(0).replace(a, spoken(a), 1).replace(b, spoken(b), 1)
            return m.group(0)

        def repl_from_to(m):
            a, b = m.group(1), m.group(2)
            if cls._is_plausible_year(a) and cls._is_plausible_year(b):
                return m.group(0).replace(a, spoken(a), 1).replace(b, spoken(b), 1)
            return m.group(0)

        text = re.sub(
            r'\bbetween\s+(\d{4})\s+and\s+(\d{4})\b',
            repl_between,
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r'\bfrom\s+(\d{4})\s+to\s+(\d{4})\b',
            repl_from_to,
            text,
            flags=re.IGNORECASE,
        )

        # 2. 前置詞 + YYYY（および AD/BC/CE/BCE）※直後が people 等ならスキップ
        def repl_prep(m):
            year = m.group(2)
            if not cls._is_plausible_year(year):
                return m.group(0)
            after = text[m.end():]
            if _followed_by_quantity(after):
                return m.group(0)
            return m.group(0).replace(year, spoken(year), 1)

        text = re.sub(
            rf'\b({_YEAR_PREPS})\s+(\d{{4}})(\s*(?:AD|BC|CE|BCE))?\b',
            repl_prep,
            text,
            flags=re.IGNORECASE,
        )

        # 3. (the) year 1998
        def repl_year_kw(m):
            year = m.group(2)
            if not cls._is_plausible_year(year):
                return m.group(0)
            return m.group(0).replace(year, spoken(year), 1)

        text = re.sub(
            r'\b((?:the\s+)?year\s+)(\d{4})\b',
            repl_year_kw,
            text,
            flags=re.IGNORECASE,
        )

        # 4. the 1998 (election 等)
        def repl_the(m):
            year = m.group(1)
            if not cls._is_plausible_year(year):
                return m.group(0)
            return m.group(0).replace(year, spoken(year), 1)

        text = re.sub(r'\bthe\s+(\d{4})\b', repl_the, text, flags=re.IGNORECASE)

        # 5a. 範囲 1998-2005 / 1998–2005
        def repl_range(m):
            a, b = m.group(1), m.group(2)
            if cls._is_plausible_year(a) and cls._is_plausible_year(b):
                return f'{spoken(a)} to {spoken(b)}'
            return m.group(0)

        text = re.sub(r'\b(\d{4})\s*[-–—]\s*(\d{4})\b', repl_range, text)

        # 5b. 括弧 (1998)
        def repl_paren(m):
            year = m.group(1)
            if not cls._is_plausible_year(year):
                return m.group(0)
            return f'({spoken(year)})'

        text = re.sub(r'\((\d{4})\)', repl_paren, text)

        # 6. 単独 YYYY（除外プレフィックス／数量サフィックスはスキップ）
        def repl_bare(m):
            year = m.group(1)
            if not cls._is_plausible_year(year):
                return m.group(0)
            start, end = m.start(), m.end()
            prefix = text[:start]
            after = text[end:]
            if re.search(rf'(?i)(?:{_YEAR_EXCLUDE_PREFIX})\s*$', prefix):
                return m.group(0)
            if start > 0 and text[start - 1] in '$£€¥#':
                return m.group(0)
            if _followed_by_quantity(after):
                return m.group(0)
            return spoken(year)

        text = re.sub(r'\b(\d{4})\b', repl_bare, text)

        return text

    @staticmethod
    def normalize_english_decades(text: str) -> str:
        """
        英語の年代表記 (例: 1980s, 1980's, '80s, '80's, 2000s 等) を
        自然な発音 (例: nineteen eighties, eighties, two thousands 等) に事前正規化する。
        Kokoro などのエンジンが末尾の s / 's を脱落させて年号 (1980) と誤読する現象を防ぐ。
        """
        if not text:
            return text

        # 1. 4桁の年代: 1980s, 1980's, 1980s', 2000s, 2000's 等
        def replace_4digit(m):
            cent = m.group(1)
            dec = m.group(2)
            if cent == '20' and dec == '00':
                return 'two thousands'
            cent_word = CENTURY_MAP.get(cent, cent)
            dec_word = DECADE_MAP.get(dec, dec + 's')
            return f'{cent_word} {dec_word}'

        text = re.sub(r'\b(1[0-9]|20|21)([0-9]0)[\'’]?[sS][\'’]?\b', replace_4digit, text)

        # 2. 2桁の年代: '80s, '80's, 80s, 80's, 80s' 等
        def replace_2digit(m):
            dec = m.group(1)
            if dec == '00':
                return 'two thousands'
            return DECADE_MAP.get(dec, dec + 's')

        text = re.sub(r'(?:[\'’]|\b)([0-9]0)[\'’]?[sS][\'’]?\b', replace_2digit, text)

        return text

    @staticmethod
    def normalize_english_units(text: str) -> str:
        """
        単位略語 (kg, km, cm 等) を Spoken form に展開する。
        Kokoro / espeak は略語を字母読み (ケー・ジー等) にしがちなので、数字付き数量を事前変換する。
        """
        if not text:
            return text

        unambiguous = sorted(
            (u for u in UNIT_MAP if u not in _AMBIGUOUS_UNITS),
            key=len,
            reverse=True,
        )
        ambiguous = sorted(_AMBIGUOUS_UNITS, key=len, reverse=True)

        def _spoken(number: str, unit_key: str) -> str:
            singular, plural = UNIT_MAP[unit_key]
            # 素の "1" のみ単数。1.0 や 1,000 は複数読みが自然。
            form = singular if number == '1' else plural
            return f'{number} {form}'

        def replace_unambiguous(m):
            return _spoken(m.group(1), m.group(2).lower())

        def replace_ambiguous(m):
            return _spoken(m.group(1), m.group(2).lower())

        # 数字と単位の間に空白があってもよい (5 kg, 5kg)
        unit_alt = '|'.join(re.escape(u) for u in unambiguous)
        text = re.sub(
            rf'(\d+(?:[.,]\d+)*)\s*({unit_alt})\b',
            replace_unambiguous,
            text,
            flags=re.IGNORECASE,
        )

        # 曖昧単位は数字に密着のみ (5m OK / 1 in 5 の in は触らない)
        amb_alt = '|'.join(re.escape(u) for u in ambiguous)
        text = re.sub(
            rf'(\d+(?:[.,]\d+)*)({amb_alt})\b',
            replace_ambiguous,
            text,
            flags=re.IGNORECASE,
        )

        # 温度: 25°C / 98.6°F / 25℃
        def replace_temp(m):
            number = m.group(1)
            scale = m.group(2).upper()
            if scale == 'C':
                return f'{number} degrees Celsius'
            return f'{number} degrees Fahrenheit'

        text = re.sub(
            r'(\d+(?:[.,]\d+)*)\s*°\s*([CcFf])\b',
            replace_temp,
            text,
        )
        text = re.sub(
            r'(\d+(?:[.,]\d+)*)\s*([℃℉])',
            lambda m: (
                f'{m.group(1)} degrees Celsius'
                if m.group(2) == '℃'
                else f'{m.group(1)} degrees Fahrenheit'
            ),
            text,
        )

        return text

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

        if model_key == "piper_en":
            text = self.normalize_english_for_tts(text)

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
    # 文区切り・特定記号による無音挿入（アプリ側制御）
    # -------------------------------------------------------------
    @staticmethod
    def split_text_for_pauses(
        text: str,
        *,
        sentence_pause_sec: float = 0.5,
        pause_marker: str = "/",
        marker_pause_sec: float = 0.3,
    ) -> List[tuple]:
        """
        文末 (. ? !) と特定記号ランの直後でテキストを分割し、
        [(読み上げテキスト, 直後の無音秒), ...] を返す。

        - 文末記号は読み上げテキストに残す（イントネーション用）。
        - 特定記号（デフォルト /）は読み上げから除去する。
        - // はマーカー無音が2回分（2倍）。/// は3倍、以下同様。
        - 小数点 (3.14) のピリオドでは分割しない。
        - 末尾セグメントの直後無音は 0（ブロック間無音は呼び出し側で付与）。
        """
        if not text:
            return []

        marker = pause_marker if pause_marker else "/"
        sentence_pause_sec = max(0.0, float(sentence_pause_sec))
        marker_pause_sec = max(0.0, float(marker_pause_sec))

        segments: List[tuple] = []
        buf: List[str] = []
        i = 0
        n = len(text)

        def flush_with_pause(pause: float):
            seg = "".join(buf).strip()
            buf.clear()
            if seg:
                segments.append((seg, pause))
            elif segments and pause > 0:
                prev_text, prev_pause = segments[-1]
                segments[-1] = (prev_text, prev_pause + pause)

        while i < n:
            if marker and text.startswith(marker, i):
                count = 0
                while text.startswith(marker, i):
                    count += 1
                    i += len(marker)
                flush_with_pause(round(marker_pause_sec * count, 1))
                continue

            ch = text[i]
            if ch in ".?!":
                # 小数: 数字.数字 は文末にしない
                if (
                    ch == "."
                    and i > 0
                    and text[i - 1].isdigit()
                    and i + 1 < n
                    and text[i + 1].isdigit()
                ):
                    buf.append(ch)
                    i += 1
                    continue

                while i < n and text[i] in ".?!":
                    buf.append(text[i])
                    i += 1
                # 閉じ引用などがあればセグメントに含める
                while i < n and text[i] in "\"'」』）)]":
                    buf.append(text[i])
                    i += 1
                flush_with_pause(sentence_pause_sec)
                continue

            buf.append(ch)
            i += 1

        flush_with_pause(0.0)

        if segments:
            last_text, _ = segments[-1]
            segments[-1] = (last_text, 0.0)

        return segments

    # -------------------------------------------------------------
    # 対話台本の結合合成 (Dialogue Synthesize & Merge)
    # -------------------------------------------------------------
    def synthesize_dialogue(
        self,
        blocks: List[Dict[str, Any]],
        engine: str = "sapi",
        speed: float = 1.0,
        silence_sec: float = 0.3,
        format_type: str = "wav",
        sample_rate: int = 24000,
        channels: int = 1,
        bitrate_kbps: int = 128,
        output_path: Optional[str | Path] = None,
        pause_control_enabled: bool = False,
        sentence_pause_sec: float = 0.5,
        pause_marker: str = "/",
        marker_pause_sec: float = 0.3,
    ) -> Path:
        if not blocks:
            raise ValueError("対話ブロックが空です")

        ext = format_type.lower()
        if output_path is None:
            output_path = self.output_dir / f"dialogue_{os.urandom(4).hex()}.{ext}"
        output_path = Path(output_path)

        temp_wavs: List[Path] = []
        # 各 WAV の直後に入れる無音秒（最後は通常 0）
        gap_after: List[float] = []
        raw_combined_wav = self.output_dir / f"_temp_combined_{os.urandom(4).hex()}.wav"

        def _synth_one(text: str, voice_id: str, temp_path: Path):
            if engine == "kokoro":
                self.synthesize_kokoro(text, voice_name=voice_id or "af_heart", speed=speed, output_path=temp_path)
            elif engine == "piper":
                self.synthesize_piper(text, model_key=voice_id or "piper_ja", output_path=temp_path)
            else:
                rate_val = int((speed - 1.0) * 10)
                self.synthesize_sapi(text, voice_name=voice_id, rate=rate_val, volume=100, output_path=temp_path)

        try:
            nonempty_blocks = [(i, b) for i, b in enumerate(blocks) if b.get("text", "").strip()]
            for bi, (i, b) in enumerate(nonempty_blocks):
                text = b.get("text", "").strip()
                v_id = b.get("voice", "")
                is_last_block = bi == len(nonempty_blocks) - 1

                if pause_control_enabled:
                    parts = self.split_text_for_pauses(
                        text,
                        sentence_pause_sec=sentence_pause_sec,
                        pause_marker=pause_marker,
                        marker_pause_sec=marker_pause_sec,
                    )
                    if not parts:
                        continue
                    for j, (seg_text, pause_after) in enumerate(parts):
                        if not seg_text.strip():
                            continue
                        temp_path = self.output_dir / f"_temp_block_{i}_{j}_{os.urandom(4).hex()}.wav"
                        _synth_one(seg_text, v_id, temp_path)
                        temp_wavs.append(temp_path)
                        # ブロック末尾セグメントの後は、次ブロックがあるときだけブロック間無音を加算
                        if j == len(parts) - 1 and not is_last_block:
                            gap_after.append(pause_after + silence_sec)
                        else:
                            gap_after.append(pause_after)
                else:
                    temp_path = self.output_dir / f"_temp_block_{i}_{os.urandom(4).hex()}.wav"
                    _synth_one(text, v_id, temp_path)
                    temp_wavs.append(temp_path)
                    gap_after.append(0.0 if is_last_block else silence_sec)

            if not temp_wavs:
                raise ValueError("合成可能なテキストブロックがありませんでした")

            # gap_after は wav と同数。末尾の無音は結合時に使わない
            silence_gaps = gap_after[:-1] if len(gap_after) > 1 else []

            self.merge_wavs(temp_wavs, raw_combined_wav, silence_sec=silence_sec, silence_gaps=silence_gaps)

            AudioConverter.convert(
                input_wav=raw_combined_wav,
                output_path=output_path,
                format_type=format_type,
                sample_rate=sample_rate,
                channels=channels,
                bitrate_kbps=bitrate_kbps
            )

        finally:
            for p in temp_wavs:
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
            try:
                if raw_combined_wav.exists():
                    raw_combined_wav.unlink()
            except Exception:
                pass

        return output_path

    @staticmethod
    def merge_wavs(
        wav_paths: List[Path],
        output_path: Path,
        silence_sec: float = 0.3,
        silence_gaps: Optional[List[float]] = None,
    ):
        """複数のWAVを結合。silence_gaps があれば各境界の無音秒を個別指定。"""
        if not wav_paths:
            return

        with wave.open(str(wav_paths[0]), "rb") as first_wav:
            params = first_wav.getparams()
            sample_rate = params.framerate
            n_channels = params.nchannels
            sampwidth = params.sampwidth

        def _silence_bytes(sec: float) -> bytes:
            if sec <= 0:
                return b""
            frames = int(sample_rate * sec)
            return b"\x00" * (frames * n_channels * sampwidth)

        with wave.open(str(output_path), "wb") as out_wav:
            out_wav.setparams(params)
            for idx, p in enumerate(wav_paths):
                with wave.open(str(p), "rb") as w:
                    out_wav.writeframes(w.readframes(w.getnframes()))
                if idx < len(wav_paths) - 1:
                    if silence_gaps is not None and idx < len(silence_gaps):
                        gap = silence_gaps[idx]
                    else:
                        gap = silence_sec
                    silence_data = _silence_bytes(gap)
                    if silence_data:
                        out_wav.writeframes(silence_data)
