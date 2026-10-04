import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QApplication
)
from PySide6.QtCore import Qt, Signal
from services.stt_service import STTService, WinRTMicWorker

class STTPage(QWidget):
    """STT (音声認識) 画面"""
    send_to_tts_requested = Signal(str)  # テキストをTTS画面に送るシグナル

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self.stt = STTService()
        self.mic_worker = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # ===== 音声入力コントロール =====
        control_group = QGroupBox("🎙️ 音声入力ソースの選択")
        ctrl_layout = QHBoxLayout(control_group)
        ctrl_layout.setSpacing(14)

        self.mic_btn = QPushButton("🎤 マイク音声認識を開始 (Windows 11 Native)")
        self.mic_btn.setFixedHeight(46)
        self.mic_btn.clicked.connect(self._on_toggle_mic)

        self.file_btn = QPushButton("📁 音声ファイルを選択して文字起こし (.wav)")
        self.file_btn.setProperty("class", "secondary")
        self.file_btn.setFixedHeight(46)
        self.file_btn.clicked.connect(self._on_transcribe_file)

        ctrl_layout.addWidget(self.mic_btn, 1)
        ctrl_layout.addWidget(self.file_btn, 1)
        main_layout.addWidget(control_group)

        # ===== ステータスインジケーター =====
        self.status_box = QLabel("マイクまたは音声ファイルを選択してください。")
        self.status_box.setStyleSheet("""
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 10px 14px;
            color: #94a3b8;
            font-size: 13px;
        """)
        main_layout.addWidget(self.status_box)

        # ===== 文字起こし結果エディター =====
        result_group = QGroupBox("📄 文字起こし結果 (編集・コピー可能)")
        res_layout = QVBoxLayout(result_group)

        self.transcript_edit = QTextEdit()
        self.transcript_edit.setPlaceholderText("認識されたテキストがここに表示されます...")
        self.transcript_edit.setStyleSheet("font-size: 14px; line-height: 1.6;")
        res_layout.addWidget(self.transcript_edit)

        main_layout.addWidget(result_group, 1)

        # ===== アクションボタン =====
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        self.copy_btn = QPushButton("📋 クリップボードにコピー")
        self.copy_btn.setProperty("class", "secondary")
        self.copy_btn.setFixedHeight(42)
        self.copy_btn.clicked.connect(self._on_copy)

        self.save_txt_btn = QPushButton("💾 テキスト保存 (.txt)")
        self.save_txt_btn.setProperty("class", "secondary")
        self.save_txt_btn.setFixedHeight(42)
        self.save_txt_btn.clicked.connect(self._on_save_txt)

        self.send_tts_btn = QPushButton("➡ TTS対話エディターに転送")
        self.send_tts_btn.setProperty("class", "teal")
        self.send_tts_btn.setFixedHeight(42)
        self.send_tts_btn.clicked.connect(self._on_send_to_tts)

        self.clear_btn = QPushButton("🗑 クリア")
        self.clear_btn.setProperty("class", "danger")
        self.clear_btn.setFixedWidth(90)
        self.clear_btn.setFixedHeight(42)
        self.clear_btn.clicked.connect(lambda: self.transcript_edit.clear())

        action_layout.addWidget(self.copy_btn)
        action_layout.addWidget(self.save_txt_btn)
        action_layout.addWidget(self.send_tts_btn)
        action_layout.addWidget(self.clear_btn)
        main_layout.addLayout(action_layout)

    def _on_toggle_mic(self):
        if self.mic_worker and self.mic_worker.isRunning():
            self.mic_worker.stop()
            self.mic_btn.setText("🎤 マイク音声認識を開始 (Windows 11 Native)")
            self.status_box.setText("⏹ 音声認識を停止しました。")
            return

        self.mic_worker = WinRTMicWorker(self)
        self.mic_worker.status_changed.connect(self.status_box.setText)
        self.mic_worker.text_recognized.connect(self._on_text_recognized)
        self.mic_worker.error_occurred.connect(self._on_error)
        self.mic_worker.finished_listening.connect(self._on_finished_listening)

        self.mic_btn.setText("⏹ 録音・認識を停止")
        self.mic_worker.start()

    def _on_text_recognized(self, text):
        current = self.transcript_edit.toPlainText().strip()
        if current:
            new_text = current + "\n" + text
        else:
            new_text = text
        self.transcript_edit.setPlainText(new_text)
        self.status_box.setText("✅ 認識成功！テキストを追加しました。")

    def _on_finished_listening(self):
        self.mic_btn.setText("🎤 マイク音声認識を開始 (Windows 11 Native)")

    def _on_error(self, err_msg):
        self.status_box.setText(f"❌ {err_msg}")
        QMessageBox.warning(self, "音声認識エラー", err_msg)
        self.mic_btn.setText("🎤 マイク音声認識を開始 (Windows 11 Native)")

    def _on_transcribe_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "音声ファイルを選択", "", "音声ファイル (*.wav *.flac)")
        if not file_path:
            return

        self.status_box.setText("⏳ 音声ファイルを文字起こし中...")
        QApplication.processEvents()

        try:
            text = self.stt.transcribe_file(file_path, language="ja-JP")
            current = self.transcript_edit.toPlainText().strip()
            if current:
                self.transcript_edit.setPlainText(current + "\n" + text)
            else:
                self.transcript_edit.setPlainText(text)
            self.status_box.setText(f"✅ ファイル文字起こし完了: {Path(file_path).name}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"文字起こし失敗: {e}")
            self.status_box.setText(f"❌ エラー: {e}")

    def _on_copy(self):
        text = self.transcript_edit.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "コピー完了", "クリップボードにコピーしました。")

    def _on_save_txt(self):
        text = self.transcript_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "保存するテキストがありません。")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "テキストファイルを保存", "transcript.txt", "テキストファイル (*.txt)")
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(text)
                QMessageBox.information(self, "保存完了", f"保存しました:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"保存に失敗しました: {e}")

    def _on_send_to_tts(self):
        text = self.transcript_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "転送するテキストがありません。")
            return
        self.send_to_tts_requested.emit(text)
        QMessageBox.information(self, "転送完了", "TTS対話エディターに新しいブロックとして転送しました！")
