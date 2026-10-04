import os
import json
from pathlib import Path

DEFAULT_CONFIG = {
    "gas_url": "https://script.google.com/a/macros/yamagataps.jp/s/AKfycbxmVamqNrYxfTYhR3JquN1mksZZqbzpY94qGm9BNJqlNnPZiGkj4-2XgwXfkraL2ytfgw/exec",
    "default_engine": "sapi",
    "default_sapi_voice": "Microsoft Haruka Desktop - Japanese",
    "default_sapi_rate": 0,
    "default_sapi_volume": 100,
    "piper_model_dir": "models",
    "piper_default_model": "en_US-lessac-medium",
    "auto_save_drive": False,
    "output_dir": "output"
}

class ConfigManager:
    def __init__(self, config_path: str | Path | None = None):
        if config_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            self.config_path = base_dir / "config.json"
        else:
            self.config_path = Path(config_path)
            
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception as e:
                print(f"設定読み込みエラー: {e}")

    def save(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"設定保存エラー: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()
