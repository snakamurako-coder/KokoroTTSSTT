# ローカル開発環境レポート (Local Development Environment)

本ドキュメントは、ローカルマシン上のシステム環境、開発ランタイム、インストール済みライブラリ、および既存アプリの設計パターンをまとめたものです。新しいアプリを開発する際のベース情報として活用してください。

---

## 1. マシン・OS・ハードウェア仕様

| 項目 | 詳細情報 | 備考 |
| :--- | :--- | :--- |
| **OS** | Windows 11 (Build 26200 / 64-bit) | Microsoft Windows NT 10.0.26200.0 |
| **CPU / SoC** | **Qualcomm Snapdragon (ARMv8 64-bit)** | Copilot+ PC / ARM Windows マシン |
| **GPU** | 内蔵 Qualcomm Adreno (NVIDIA GPU なし) | CUDA 非対応。AI推論は ONNX Runtime (CPU/DirectML) や軽量モデルが最適 |
| **プロジェクト基準パス** | `C:\Users\enhan\コード開発\Projects\` | 全プロジェクトの親ディレクトリ |
| **現行ワークスペース** | `C:\Users\enhan\コード開発\Projects\AutomatedSaiten` | |

---

## 2. 開発ランタイム & ツール

| ツール | バージョン | 実行パス / 備考 |
| :--- | :--- | :--- |
| **Python** | **3.14.6** (AMD64) | `C:\Users\enhan\AppData\Local\Python\pythoncore-3.14-64\python.exe`<br>※`py -3` コマンドで起動可能 |
| **pip** | **26.1.2** | `python -m pip` |
| **Node.js** | **v24.11.1** | `C:\Program Files\nodejs\node.exe` |
| **npm** | **11.6.2** | `C:\Program Files\nodejs\npm.cmd` |
| **Git** | **2.52.0.windows.1** | システム PATH 登録済み |

---

## 3. インストール済み主要 Python ライブラリ

現在のグローバル環境にインストールされており、追加セットアップなしで即座に利用可能な主要ライブラリです。

### ① GUI / デスクトップアプリケーション
* **`PySide6` (6.11.1)**: Qt for Python 公式バインディング。モダンで高機能なデスクトップ GUI を構築可能。
* **`sv_ttk` (2.6.1)**: Tkinter 用の Sun Valley モダンテーマ（ダーク/ライト対応）。
* **`windnd` (1.0.7)**: Windows エクスプローラーからのファイルドラッグ＆ドロップ対応。

### ② 音声・AI・OCR
* **`piper-tts` (1.8.0)**: 高速・軽量なローカルテキスト読み上げ (TTS) エンジン。
* **`winrt-Windows.Media.SpeechRecognition` (3.2.1)**: Windows 11 標準の高精度・オフライン音声認識 API。
* **`SpeechRecognition` (3.17.0)**: 多様な音声認識エンジンラッパー。
* **`sounddevice` (0.5.5) / `SoundCard` (0.4.6)**: リアルタイム音声入出力・録音・再生。
* **`onnxruntime` (1.30.0)**: 機械学習・ディープラーニングモデルの高速推論エンジン。
* **`pytesseract` (0.3.13)**: Tesseract OCR ラッパー。

### ③ 画像処理・ドキュメント操作・データ解析
* **`opencv-python` (5.0.0.93)**: 画像処理・コンピュータビジョン。
* **`Pillow` (12.3.0)**: 画像加工・フォーマット変換。
* **`PyMuPDF` (`fitz` 1.28.0)**: PDF の高速レンダリング・テキスト抽出・画像変換。
* **`python-docx` (1.2.0)**: Word (.docx) ファイルの生成・編集。
* **`openpyxl` (3.1.5)**: Excel (.xlsx) ファイルの読み書き。
* **`pandas` (3.0.3)** / **`numpy` (2.5.0)**: データフレーム操作・数値計算。

### ④ Web / ネットワーク / システム
* **`Flask` (3.1.3)** / **`flask-cors` (6.0.5)**: 軽量 Web アプリケーション / ローカル API サーバー。
* **`requests` (2.34.2)**: HTTP 通信クライアント。
* **`pywin32` (312)**: Windows OS API への低レベルアクセス。

---

## 4. 既存プロジェクト（AutomatedSaiten）のアーキテクチャ構成

新規アプリを作る際の設計テンプレートとして参考になります。

```text
Projects/AutomatedSaiten/
├── desktop/                      # Python デスクトップアプリ本体
│   ├── main.py                   # エントリーポイント
│   ├── launch.bat                # ワンクリック起動バッチ
│   ├── config.py / config.json   # ユーザー設定・パス等の永続化
│   ├── constants.py              # アプリ共通定数
│   ├── requirements.txt          # 依存パッケージ定義
│   ├── models/                   # データ構造クラス (Student, ExamData 等)
│   ├── services/                 # ロジック層 (音声認識, OCR, PDF処理, 音声合成)
│   ├── ui_qt/                    # PySide6 UI 層
│   │   ├── main_window.py        # メインウィンドウ
│   │   ├── components/           # 再利用可能なUI部品
│   │   └── pages/                # 各画面 (初期設定, 手動採点, レポート等)
│   └── data/                     # アプリ内ローカルキャッシュ・ログ
├── index.html                    # Web UI / 採点画面 (HTML/JS)
├── code.gs                       # Google Apps Script (バックエンド連携)
└── .clasp.json                   # GAS同期設定
```

### 起動スクリプト (`launch.bat`) のパターン
```bat
@echo off
chcp 65001 >nul
title <アプリ名>
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 main.py
) else (
    python main.py
)

if errorlevel 1 (
    echo.
    echo Failed to start. If packages are missing, run:
    echo   py -3 -m pip install -r requirements.txt
    echo.
    pause
)
```

---

## 5. 新規アプリ開発における留意点と推奨アプローチ

1. **Snapdragon (ARM64 Windows) 特有の留意点**:
   - ディスクリート NVIDIA GPU がないため、**CUDA 前提のライブラリ（GPU版 PyTorch など）は動作しません**。
   - モデルのローカル推論には **ONNX Runtime (CPU)** や、**Windows 標準の WinRT API**、**軽量モデル (Piper-TTS 等)** を採用するのが安定・高速です。
2. **プロジェクトの作成場所**:
   - `C:\Users\enhan\コード開発\Projects\<新しいアプリ名>` 配下に作成することを推奨します。
3. **開発環境の分離 (venv)**:
   - 今回のように共通ライブラリをそのまま使う場合はグローバル Python (`py -3`) で直接動かせますが、ライブラリのバージョン衝突を防ぎたい場合は以下のように個別 venv を作成することも可能です：
     ```powershell
     py -3 -m venv venv
     .\venv\Scripts\activate
     ```
