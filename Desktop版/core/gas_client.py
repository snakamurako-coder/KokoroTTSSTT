import os
import base64
import json
import requests
from pathlib import Path

class GASClient:
    """Google Apps Script (GAS) 連携クライアント"""
    def __init__(self, gas_url: str):
        self.gas_url = gas_url

    def upload_audio(self, audio_path: str | Path, text: str, voice_model: str, settings: str = "Desktop版") -> dict:
        """
        ローカルの音声ファイルをBase64エンコードし、GASエンドポイントに送信してGoogle Driveに保存する
        """
        path = Path(audio_path)
        if not path.exists():
            return {"status": "error", "message": f"ファイルが見つかりません: {path}"}

        ext = path.suffix.lstrip(".").lower()
        if ext == "wav":
            format_type = "wav"
        elif ext == "mp3":
            format_type = "mp3"
        else:
            format_type = "webm"

        try:
            with open(path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "text": text,
                "voiceModel": voice_model,
                "settings": settings,
                "audioBase64": b64_data,
                "format": format_type
            }

            headers = {"Content-Type": "text/plain;charset=utf-8"}
            response = requests.post(self.gas_url, data=json.dumps(payload), headers=headers, timeout=30)
            
            if response.status_code == 200:
                try:
                    res_json = response.json()
                    return res_json
                except Exception:
                    return {"status": "success", "message": "保存されました", "raw": response.text}
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}
