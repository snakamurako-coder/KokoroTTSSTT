import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QSlider, QScrollArea,
    QFileDialog, QMessageBox, QGroupBox, QFrame, QDialog,
    QProgressBar
)
from PySide6.QtCore import Qt, Signal
from services.tts_service import TTSService
from services.audio_player import AudioPlayerService
from services.model_manager import ModelManager, ModelDownloadWorker
from core.gas_client import GASClient


class ModelDownloadDialog(QDialog):
    """モデルダウンロード進行ダイアログ"""
    def __init__(self, model_key: str, models_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI音声モデルのダウンロード")
        self.setFixedSize(440, 180)
        self.setStyleSheet("background-color: #0f172a; color: #f8fafc;")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.info_label = QLabel("モデルのダウンロード準備中...")
        self.info_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                text-align: center;
                height: 22px;
                background-color: #1e293b;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.status_detail = QLabel("接続中...")
        self.status_detail.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self.status_detail)

        self.cancel_btn = QPushButton("キャンセル")
        self.cancel_btn.setProperty("class", "secondary")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

        self.worker = ModelDownloadWorker(model_key, models_dir, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, percent, msg):
        self.progress_bar.setValue(percent)
        self.status_detail.setText(msg)

    def _on_finished(self, success, msg):
        if success:
            QMessageBox.information(self, "完了", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "失敗", msg)
            self.reject()

    def _on_cancel(self):
        self.worker.cancel()
        self.reject()


class DialogueBlockWidget(QFrame):
    """対話ブロックウィジェット"""
    split_requested = Signal(object, int)  # (self, cursor_position)
    delete_requested = Signal(object)      # (self)

    def __init__(self, voices, default_voice=None, speaker_name="", text="", parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ヘッダーコントロール
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.speaker_input = QLineEdit()
        self.speaker_input.setPlaceholderText("話者名 (任意)")
        self.speaker_input.setText(speaker_name)
        self.speaker_input.setFixedWidth(130)

        self.voice_combo = QComboBox()
        self.set_voices(voices, default_voice)

        self.split_btn = QPushButton("✂ 分割")
        self.split_btn.setProperty("class", "secondary")
        self.split_btn.setFixedWidth(65)
        self.split_btn.clicked.connect(self._on_split)

        self.del_btn = QPushButton("✕ 削除")
        self.del_btn.setProperty("class", "danger")
        self.del_btn.setFixedWidth(65)
        self.del_btn.clicked.connect(lambda: self.delete_requested.emit(self))

        header_layout.addWidget(QLabel("話者:"))
        header_layout.addWidget(self.speaker_input)
        header_layout.addWidget(QLabel("音声:"))
        header_layout.addWidget(self.voice_combo, 1)
        header_layout.addWidget(self.split_btn)
        header_layout.addWidget(self.del_btn)
        layout.addLayout(header_layout)

        # テキスト入力欄
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("ここにテキストを入力...")
        self.text_edit.setText(text)
        self.text_edit.setFixedHeight(75)
        layout.addWidget(self.text_edit)

    def set_voices(self, voices, default_voice=None):
        prev = self.voice_combo.currentData()
        self.voice_combo.clear()
        for v in voices:
            self.voice_combo.addItem(v["name"], v["id"])
        
        target = default_voice or prev
        if target:
            idx = self.voice_combo.findData(target)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)

    def _on_split(self):
        cursor = self.text_edit.textCursor()
        pos = cursor.position()
        self.split_requested.emit(self, pos)

    def get_data(self):
        return {
            "speaker": self.speaker_input.text().strip(),
            "voice": self.voice_combo.currentData(),
            "voice_name": self.voice_combo.currentText(),
            "text": self.text_edit.toPlainText().strip()
        }


class TTSPage(QWidget):
    """TTS (音声合成) 画面: Kokoro, Piper, SAPI"""
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self.tts = TTSService(
            output_dir=self.cfg.get("output_dir", "output"),
            models_dir=self.cfg.get("piper_model_dir", "models")
        )
        self.player = AudioPlayerService(self)
        self.gas = GASClient(self.cfg.get("gas_url", ""))
        self.current_audio_path = None
        self.blocks = []

        self._init_ui()
        self._init_connections()
        self._on_engine_changed()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # ===== 上部設定パネル =====
        settings_group = QGroupBox("⚙ 音声エンジン & パラメーター設定")
        set_layout = QHBoxLayout(settings_group)
        set_layout.setSpacing(16)

        # エンジン選択
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("🎵 Kokoro (英語専用・最高品質 AI)", "kokoro")
        self.engine_combo.addItem("⚡ Piper (日本語/英語・高速ローカル AI)", "piper")
        self.engine_combo.addItem("🔊 Windows SAPI (標準搭載・即座利用)", "sapi")
        self.engine_combo.setFixedWidth(290)
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)

        # モデルDLボタン (必要な場合のみ表示)
        self.download_model_btn = QPushButton("⬇ モデルDL")
        self.download_model_btn.setProperty("class", "teal")
        self.download_model_btn.setFixedWidth(100)
        self.download_model_btn.setVisible(False)
        self.download_model_btn.clicked.connect(self._on_download_model)

        # 速度スライダー (0.5x 〜 2.0x)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(5, 20)
        self.speed_slider.setValue(10)
        self.speed_label = QLabel("速度: 1.0x")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"速度: {v/10.0:.1f}x"))

        set_layout.addWidget(QLabel("エンジン:"))
        set_layout.addWidget(self.engine_combo)
        set_layout.addWidget(self.download_model_btn)
        set_layout.addWidget(self.speed_label)
        set_layout.addWidget(self.speed_slider)
        main_layout.addWidget(settings_group)

        # ===== エンジン別ヒントバナー =====
        self.hint_banner = QLabel("")
        self.hint_banner.setStyleSheet("""
            background: rgba(139, 92, 246, 0.15);
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 8px;
            padding: 8px 12px;
            color: #cbd5e1;
            font-size: 12px;
        """)
        main_layout.addWidget(self.hint_banner)

        # ===== 対話エディター =====
        editor_group = QGroupBox("📝 対話エディター (Dialogue Editor)")
        editor_layout = QVBoxLayout(editor_group)
        editor_layout.setSpacing(8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.blocks_container = QWidget()
        self.blocks_layout = QVBoxLayout(self.blocks_container)
        self.blocks_layout.setContentsMargins(0, 0, 0, 0)
        self.blocks_layout.setSpacing(8)
        self.blocks_layout.addStretch()
        self.scroll_area.setWidget(self.blocks_container)

        editor_layout.addWidget(self.scroll_area, 1)

        self.add_block_btn = QPushButton("＋ 新しい対話ブロックを追加")
        self.add_block_btn.setProperty("class", "secondary")
        self.add_block_btn.clicked.connect(lambda: self.add_block())
        editor_layout.addWidget(self.add_block_btn)

        main_layout.addWidget(editor_group, 1)

        # ===== 操作ボタンエリア =====
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.generate_btn = QPushButton("🎵 音声を合成する")
        self.generate_btn.setFixedHeight(44)
        self.generate_btn.clicked.connect(self._on_generate)

        self.save_pc_btn = QPushButton("💾 パソコンに保存 (WAV)")
        self.save_pc_btn.setProperty("class", "secondary")
        self.save_pc_btn.setFixedHeight(44)
        self.save_pc_btn.setEnabled(False)
        self.save_pc_btn.clicked.connect(self._on_save_pc)

        self.save_drive_btn = QPushButton("☁ Google Drive に保存")
        self.save_drive_btn.setProperty("class", "teal")
        self.save_drive_btn.setFixedHeight(44)
        self.save_drive_btn.setEnabled(False)
        self.save_drive_btn.clicked.connect(self._on_save_drive)

        btn_layout.addWidget(self.generate_btn, 2)
        btn_layout.addWidget(self.save_pc_btn, 1)
        btn_layout.addWidget(self.save_drive_btn, 1)
        main_layout.addLayout(btn_layout)

        # ===== 音声プレイヤー =====
        player_group = QGroupBox("🎧 再生プレイヤー")
        player_layout = QHBoxLayout(player_group)
        player_layout.setSpacing(12)

        self.play_btn = QPushButton("▶ 再生")
        self.play_btn.setFixedWidth(90)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._on_toggle_play)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self.player.set_position)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(95)
        self.time_label.setAlignment(Qt.AlignCenter)

        self.status_label = QLabel("待機中")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")

        player_layout.addWidget(self.play_btn)
        player_layout.addWidget(self.seek_slider, 1)
        player_layout.addWidget(self.time_label)
        main_layout.addWidget(player_group)
        main_layout.addWidget(self.status_label)

        # 初期ブロックを1つ作成
        self.add_block()

    def _init_connections(self):
        self.player.position_changed.connect(self._on_position_changed)
        self.player.duration_changed.connect(self._on_duration_changed)
        self.player.state_changed.connect(self._on_state_changed)

    def _on_engine_changed(self):
        engine = self.engine_combo.currentData()
        voices = self.tts.get_voices_for_engine(engine)
        
        # 既存ブロックのボイス一覧を同期更新
        for b in self.blocks:
            b.set_voices(voices)

        # ヒント文とモデルダウンロードボタンの表示判定
        if engine == "kokoro":
            installed = self.tts.model_manager.is_model_installed("kokoro_en")
            self.download_model_btn.setVisible(not installed)
            if installed:
                self.hint_banner.setText("✨ Kokoro (英語専用・最高品質 AI): ローカル ONNX 推論モデル準備完了！英語テキストを入力してください。")
                self.hint_banner.setStyleSheet("background: rgba(139, 92, 246, 0.15); border: 1px solid #8b5cf6; border-radius: 8px; padding: 8px 12px; color: #e2e8f0; font-size: 12px;")
            else:
                self.hint_banner.setText("⚠ Kokoro モデルが未ダウンロードです。「⬇ モデルDL」ボタンを押してダウンロードしてください (約92MB)。")
                self.hint_banner.setStyleSheet("background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 8px; padding: 8px 12px; color: #fca5a5; font-size: 12px;")

        elif engine == "piper":
            installed_ja = self.tts.model_manager.is_model_installed("piper_ja")
            installed_en = self.tts.model_manager.is_model_installed("piper_en")
            self.download_model_btn.setVisible(not (installed_ja and installed_en))
            
            if installed_ja and installed_en:
                self.hint_banner.setText("⚡ Piper (日本語/英語・高速ローカル AI): 日本語・英語の両モデル準備完了！直接ローカルで高速合成します。")
                self.hint_banner.setStyleSheet("background: rgba(20, 184, 166, 0.15); border: 1px solid #14b8a6; border-radius: 8px; padding: 8px 12px; color: #e2e8f0; font-size: 12px;")
            else:
                self.hint_banner.setText("⚠ Piper の音声モデルが未ダウンロードです。「⬇ モデルDL」ボタンを押して取得してください。")
                self.hint_banner.setStyleSheet("background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 8px; padding: 8px 12px; color: #fca5a5; font-size: 12px;")

        else: # sapi
            self.download_model_btn.setVisible(False)
            self.hint_banner.setText("🔊 Windows SAPI (標準搭載): 事前ダウンロード不要！OS内蔵の日本語 (Haruka) / 英語 (Zira) で即座に読み上げます。")
            self.hint_banner.setStyleSheet("background: rgba(245, 158, 11, 0.15); border: 1px solid #f59e0b; border-radius: 8px; padding: 8px 12px; color: #e2e8f0; font-size: 12px;")

    def _on_download_model(self):
        engine = self.engine_combo.currentData()
        if engine == "kokoro":
            dlg = ModelDownloadDialog("kokoro_en", self.tts.models_dir, self)
            dlg.exec()
        elif engine == "piper":
            if not self.tts.model_manager.is_model_installed("piper_ja"):
                dlg = ModelDownloadDialog("piper_ja", self.tts.models_dir, self)
                dlg.exec()
            if not self.tts.model_manager.is_model_installed("piper_en"):
                dlg = ModelDownloadDialog("piper_en", self.tts.models_dir, self)
                dlg.exec()
        self._on_engine_changed()

    def add_block(self, default_voice=None, speaker_name="", text="", insert_after=None):
        engine = self.engine_combo.currentData()
        voices = self.tts.get_voices_for_engine(engine)
        
        block = DialogueBlockWidget(
            voices=voices,
            default_voice=default_voice,
            speaker_name=speaker_name,
            text=text
        )
        block.split_requested.connect(self._on_split_block)
        block.delete_requested.connect(self._on_delete_block)

        if insert_after and insert_after in self.blocks:
            idx = self.blocks.index(insert_after)
            self.blocks.insert(idx + 1, block)
            self.blocks_layout.insertWidget(idx + 1, block)
        else:
            self.blocks.append(block)
            self.blocks_layout.insertWidget(len(self.blocks) - 1, block)

        return block

    def _on_split_block(self, target_block, cursor_pos):
        data = target_block.get_data()
        full_text = target_block.text_edit.toPlainText()
        
        text_before = full_text[:cursor_pos]
        text_after = full_text[cursor_pos:].strip()
        
        target_block.text_edit.setPlainText(text_before)
        self.add_block(
            default_voice=data["voice"],
            speaker_name=data["speaker"],
            text=text_after,
            insert_after=target_block
        )

    def _on_delete_block(self, target_block):
        if len(self.blocks) <= 1:
            QMessageBox.warning(self, "警告", "最低1つのブロックが必要です。")
            return
        self.blocks.remove(target_block)
        target_block.deleteLater()

    def _on_generate(self):
        block_data = [b.get_data() for b in self.blocks if b.get_data()["text"]]
        if not block_data:
            QMessageBox.warning(self, "警告", "テキストを入力してください。")
            return

        engine = self.engine_combo.currentData()
        speed_factor = self.speed_slider.value() / 10.0

        # モデル有無の事前チェック
        if engine == "kokoro" and not self.tts.model_manager.is_model_installed("kokoro_en"):
            QMessageBox.warning(self, "モデル未ダウンロード", "Kokoro モデルがダウンロードされていません。「⬇ モデルDL」ボタンからダウンロードしてください。")
            return
        if engine == "piper":
            for b in block_data:
                m_key = b["voice"] or "piper_ja"
                if not self.tts.model_manager.is_model_installed(m_key):
                    QMessageBox.warning(self, "モデル未ダウンロード", f"Piper モデル ({m_key}) がダウンロードされていません。「⬇ モデルDL」ボタンからダウンロードしてください。")
                    return

        self.status_label.setText("⏳ 音声を合成中...")
        self.generate_btn.setEnabled(False)

        try:
            out_path = self.tts.synthesize_dialogue(block_data, engine=engine, speed=speed_factor)
            self.current_audio_path = out_path
            self.player.load(out_path)
            
            self.status_label.setText(f"✅ 合成完了: {out_path.name}")
            self.play_btn.setEnabled(True)
            self.seek_slider.setEnabled(True)
            self.save_pc_btn.setEnabled(True)
            self.save_drive_btn.setEnabled(True)
            
            self.player.play()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"合成失敗:\n{e}")
            self.status_label.setText(f"❌ エラー: {e}")
        finally:
            self.generate_btn.setEnabled(True)

    def _on_save_pc(self):
        if not self.current_audio_path or not self.current_audio_path.exists():
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "音声を保存", f"speech_{self.current_audio_path.name}", "WAVファイル (*.wav)")
        if save_path:
            import shutil
            shutil.copy2(self.current_audio_path, save_path)
            QMessageBox.information(self, "成功", f"保存しました:\n{save_path}")

    def _on_save_drive(self):
        if not self.current_audio_path or not self.current_audio_path.exists():
            return

        full_text = "\n".join([f"[{b.get_data()['speaker'] or '話者'}] {b.get_data()['text']}" for b in self.blocks if b.get_data()['text']])
        voice_info = f"Desktop ({self.engine_combo.currentText()})"

        self.status_label.setText("☁ Google Drive にアップロード中...")
        self.save_drive_btn.setEnabled(False)

        res = self.gas.upload_audio(self.current_audio_path, full_text, voice_info)
        self.save_drive_btn.setEnabled(True)

        if res.get("status") == "success":
            url = res.get("url", "")
            msg = "✅ Google Drive に正常に保存されました！"
            if url:
                msg += f"\n\nURL: {url}"
            QMessageBox.information(self, "Google Drive 保存完了", msg)
            self.status_label.setText("✅ Google Drive 保存完了！")
        else:
            err = res.get("message", "不明なエラー")
            QMessageBox.critical(self, "保存失敗", f"Google Driveへの保存に失敗しました:\n{err}")
            self.status_label.setText(f"❌ Google Drive 保存失敗: {err}")

    def _on_toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def _on_state_changed(self, is_playing):
        self.play_btn.setText("⏸ 一時停止" if is_playing else "▶ 再生")

    def _on_duration_changed(self, duration_ms):
        self.seek_slider.setRange(0, duration_ms)
        self._update_time_label(self.player.player.position(), duration_ms)

    def _on_position_changed(self, pos_ms):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(pos_ms)
        self._update_time_label(pos_ms, self.seek_slider.maximum())

    def _update_time_label(self, cur_ms, total_ms):
        cur_sec = cur_ms // 1000
        tot_sec = total_ms // 1000
        self.time_label.setText(f"{cur_sec//60:02d}:{cur_sec%60:02d} / {tot_sec//60:02d}:{tot_sec%60:02d}")

    def insert_external_text(self, text: str):
        self.add_block(text=text)
