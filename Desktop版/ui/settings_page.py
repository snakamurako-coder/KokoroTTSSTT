import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QMessageBox, QGroupBox
)
import requests

class SettingsPage(QWidget):
    """設定画面"""
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # ===== Google Apps Script (GAS) 連携設定 =====
        gas_group = QGroupBox("☁ Google Drive / スプレッドシート連携設定")
        gas_layout = QVBoxLayout(gas_group)
        gas_layout.setSpacing(12)

        desc = QLabel(
            "Google Apps Script の Web アプリケーション URL を設定します。\n"
            "合成音声や文字起こし履歴を自動で Google Drive にアップロードし、スプレッドシートに記録できます。"
        )
        desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        desc.setWordWrap(True)
        gas_layout.addWidget(desc)

        url_layout = QHBoxLayout()
        self.gas_url_input = QLineEdit()
        self.gas_url_input.setText(self.cfg.get("gas_url", ""))
        self.gas_url_input.setPlaceholderText("https://script.google.com/macros/s/.../exec")
        
        self.test_btn = QPushButton("接続テスト")
        self.test_btn.setProperty("class", "secondary")
        self.test_btn.setFixedWidth(100)
        self.test_btn.clicked.connect(self._test_gas_connection)

        url_layout.addWidget(QLabel("GAS URL:"))
        url_layout.addWidget(self.gas_url_input, 1)
        url_layout.addWidget(self.test_btn)
        gas_layout.addLayout(url_layout)

        self.gas_status_label = QLabel("")
        self.gas_status_label.setStyleSheet("font-size: 12px;")
        gas_layout.addWidget(self.gas_status_label)

        layout.addWidget(gas_group)

        # ===== 保存先ディレクトリ設定 =====
        dir_group = QGroupBox("📁 出力ディレクトリ設定")
        dir_layout = QHBoxLayout(dir_group)

        self.dir_input = QLineEdit()
        self.dir_input.setText(str(Path(self.cfg.get("output_dir", "output")).resolve()))

        self.browse_btn = QPushButton("参照...")
        self.browse_btn.setProperty("class", "secondary")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self._browse_dir)

        dir_layout.addWidget(QLabel("出力先:"))
        dir_layout.addWidget(self.dir_input, 1)
        dir_layout.addWidget(self.browse_btn)

        layout.addWidget(dir_group)

        # ===== システム環境情報 =====
        info_group = QGroupBox("💻 動作環境情報 (Copilot+ PC / Snapdragon ARM64)")
        info_layout = QVBoxLayout(info_group)
        
        info_text = (
            "• OS: Windows 11 (ARMv8 64-bit)\n"
            "• Python: 3.14 (AMD64 Emulated Runtime)\n"
            "• 音声合成 (TTS): Windows SAPI (Microsoft Haruka / Zira) & Piper-TTS (ONNX)\n"
            "• 音声認識 (STT): Windows 11 Native WinRT SpeechRecognition (Offline Native)\n"
            "• オーディオエンジン: QtMultimedia (Direct WASAPI)"
        )
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.6;")
        info_layout.addWidget(info_label)

        layout.addWidget(info_group)
        layout.addStretch()

        # ===== 保存ボタン =====
        self.save_btn = QPushButton("設定を保存する")
        self.save_btn.setFixedHeight(44)
        self.save_btn.clicked.connect(self._save_settings)
        layout.addWidget(self.save_btn)

    def _test_gas_connection(self):
        url = self.gas_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "エラー", "URLを入力してください。")
            return

        self.gas_status_label.setText("接続確認中...")
        try:
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                self.gas_status_label.setText("✅ 接続成功！GASエンドポイントが正常に応答しています。")
                self.gas_status_label.setStyleSheet("color: #10b981;")
            else:
                self.gas_status_label.setText(f"⚠ 接続応答: HTTP {res.status_code}")
                self.gas_status_label.setStyleSheet("color: #f59e0b;")
        except Exception as e:
            self.gas_status_label.setText(f"❌ 接続失敗: {e}")
            self.gas_status_label.setStyleSheet("color: #ef4444;")

    def _browse_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "出力ディレクトリを選択", self.dir_input.text())
        if dir_path:
            self.dir_input.setText(dir_path)

    def _save_settings(self):
        self.cfg.set("gas_url", self.gas_url_input.text().strip())
        self.cfg.set("output_dir", self.dir_input.text().strip())
        QMessageBox.information(self, "保存完了", "設定を保存しました。")
