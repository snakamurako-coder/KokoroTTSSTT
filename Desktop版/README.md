# Kokoro TTS & STT Studio (Desktop版)

Windows 11 (ARM64 Snapdragon / Copilot+ PC) 環境に最適化された、デスクトップネイティブの**音声合成 (TTS) ＆ 音声認識 (STT) 統合スタジオ**です。

---

## 🚀 起動方法

### ① ワンクリック起動 (おすすめ)
フォルダ内の **`launch.bat`** をダブルクリックするだけで起動します。

### ② コマンドラインからの起動
```powershell
cd "c:\Users\enhan\コード開発\Projects\KokoroTTSSTT\Desktop版"
py -3 main.py
```

---

## ✨ 主な機能

### 1. 🎵 音声合成 (TTS Studio)
* **Windows SAPI 音声合成**:
  * 外部モデルのダウンロード不要で、起動直後から即座に利用可能。
  * **Microsoft Haruka (日本語)**、**Microsoft Zira (英語)** など、OS内蔵の自然な音声を自動検出して使用。
  * 速度・音量の細かい調整対応。
* **対話エディター (Dialogue Editor)**:
  * 複数ブロック（話者、音声、テキスト）を組み合わせた対話スクリプトの作成。
  * カーソル位置での「✂ 分割」や「✕ 削除」に対応。
  * 連続合成し、無音ギャップ（0.3秒）を自動挿入して1つの高音質 WAV ファイルに結合。
* **高音質プレイヤー**:
  * QtMultimedia (Direct WASAPI) による低遅延・高音質なプレビュー再生。
  * シークバーによる任意位置へのスキップ再生。
* **ファイル保存 & Google Drive 連携**:
  * ローカルへの WAV 書き出し。
  * ワンクリックで Google Drive へアップロード＆スプレッドシート履歴に自動記録（GAS API 連携）。

### 2. 🎙️ 音声認識 (STT Studio)
* **Windows 11 Native WinRT 音声認識**:
  * Snapdragon Copilot+ PC に最適化された Windows 11 標準オフライン音声認識 API を採用。
  * マイクに向かって話すだけで、リアルタイム・高精度にテキストへ変換。
* **音声ファイルからの文字起こし**:
  * 録音済み WAV ファイルを選択して一括文字起こし。
* **テキスト活用 & TTS連携**:
  * クリップボードへのワンクリックコピー。
  * テキストファイル (.txt) 保存。
  * **「➡ TTS対話エディターに転送」**: 認識したテキストをそのままTTSの対話エディターに送信し、自動で新しいセリフブロックとして読み上げ可能！

### 3. ⚙️ 設定 & クラウド連携
* Google Apps Script (GAS) Web API の URL 設定と接続テスト。
* 音声ファイルのデフォルト出力先ディレクトリの変更。

---

## 🛠️ 開発環境情報
* **OS**: Windows 11 (Snapdragon ARM64)
* **GUIフレームワーク**: PySide6 (Qt 6.11.1)
* **オーディオ**: QtMultimedia, Windows SAPI (pywin32), Piper-TTS
* **音声認識**: WinRT SpeechRecognition, SpeechRecognition
