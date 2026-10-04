import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QSlider, QScrollArea,
    QFileDialog, QMessageBox, QGroupBox, QFrame
)
from PySide6.QtCore import Qt, Signal
from services.tts_service import TTSService
from services.audio_player import AudioPlayerService
from core.gas_client import GASClient

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
        self.speaker_input.setFixedWidth(140)

        self.voice_combo = QComboBox()
        for v in voices:
            self.voice_combo.addItem(v["name"], v["id"])
        if default_voice:
            idx = self.voice_combo.findData(default_voice)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)

        self.split_btn = QPushButton("✂ 分割")
        self.split_btn.setProperty("class", "secondary")
        self.split_btn.setFixedWidth(70)
        self.split_btn.clicked.connect(self._on_split)

        self.del_btn = QPushButton("✕ 削除")
        self.del_btn.setProperty("class", "danger")
        self.del_btn.setFixedWidth(70)
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
    """TTS (音声合成) 画面"""
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self.tts = TTSService(output_dir=self.cfg.get("output_dir", "output"))
        self.player = AudioPlayerService(self)
        self.gas = GASClient(self.cfg.get("gas_url", ""))
        self.current_audio_path = None
        self.blocks = []

        self._init_ui()
        self._init_connections()

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
        self.engine_combo.addItem("🔊 Windows SAPI (標準・日本語/英語)", "sapi")
        self.engine_combo.addItem("⚡ Piper AI (高速ニューラル・多言語)", "piper")
        self.engine_combo.setFixedWidth(260)

        # 速度スライダー
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(-10, 10)
        self.speed_slider.setValue(self.cfg.get("default_sapi_rate", 0))
        self.speed_label = QLabel(f"速度: {self.speed_slider.value()}")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"速度: {v}"))

        # 音量スライダー
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self.cfg.get("default_sapi_volume", 100))
        self.vol_label = QLabel(f"音量: {self.vol_slider.value()}%")
        self.vol_slider.valueChanged.connect(lambda v: self.vol_label.setText(f"音量: {v}%"))

        set_layout.addWidget(QLabel("エンジン:"))
        set_layout.addWidget(self.engine_combo)
        set_layout.addWidget(self.speed_label)
        set_layout.addWidget(self.speed_slider)
        set_layout.addWidget(self.vol_label)
        set_layout.addWidget(self.vol_slider)
        main_layout.addWidget(settings_group)

        # ===== 対話エディター =====
        editor_group = QGroupBox("📝 対話エディター (Dialogue Editor)")
        editor_layout = QVBoxLayout(editor_group)
        editor_layout.setSpacing(8)

        # スクロールエリア
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

        # ブロック追加ボタン
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

        # ===== 音声プレイヤーバー =====
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

        # 初期ブロックの作成
        self.sapi_voices = self.tts.get_sapi_voices()
        default_voice = self.cfg.get("default_sapi_voice")
        self.add_block(default_voice=default_voice)

    def _init_connections(self):
        self.player.position_changed.connect(self._on_position_changed)
        self.player.duration_changed.connect(self._on_duration_changed)
        self.player.state_changed.connect(self._on_state_changed)

    def add_block(self, default_voice=None, speaker_name="", text="", insert_after=None):
        block = DialogueBlockWidget(
            voices=self.sapi_voices,
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
            # stretchの直前に挿入
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
        rate = self.speed_slider.value()
        vol = self.vol_slider.value()

        for b in block_data:
            b["rate"] = rate
            b["volume"] = vol

        self.status_label.setText("⏳ 音声を合成中...")
        self.generate_btn.setEnabled(False)

        try:
            out_path = self.tts.synthesize_dialogue(block_data, engine=engine)
            self.current_audio_path = out_path
            self.player.load(out_path)
            
            self.status_label.setText(f"✅ 合成完了: {out_path.name}")
            self.play_btn.setEnabled(True)
            self.seek_slider.setEnabled(True)
            self.save_pc_btn.setEnabled(True)
            self.save_drive_btn.setEnabled(True)
            
            # 自動再生
            self.player.play()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"合成失敗: {e}")
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
        voice_info = f"Desktop SAPI ({self.engine_combo.currentText()})"

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
        """STT等の外部からテキストを受け取ってブロックを作成"""
        self.add_block(text=text)
