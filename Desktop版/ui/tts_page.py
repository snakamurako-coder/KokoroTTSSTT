import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QSlider, QScrollArea,
    QFileDialog, QMessageBox, QGroupBox, QFrame, QDialog,
    QProgressBar, QCheckBox, QStyle, QStyleOptionSlider,
    QDoubleSpinBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer
from services.tts_service import TTSService
from services.audio_player import AudioPlayerService
from services.model_manager import ModelManager, ModelDownloadWorker
from core.gas_client import GASClient


class SeekSlider(QSlider):
    """クリック位置へ即座にジャンプ＆ドラッグ可能なシークバー"""
    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def _val_from_pos(self, x: float) -> int:
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        handle_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderHandle, self
        )
        hw = handle_rect.width()
        span = max(1, self.width() - hw)
        pos = int(x - hw / 2)
        val = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), pos, span)
        return max(self.minimum(), min(self.maximum(), val))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.maximum() > self.minimum() and self.isEnabled():
            val = self._val_from_pos(event.position().x())
            self.setValue(val)
            self.sliderMoved.emit(val)
            self.setSliderDown(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown() and (event.buttons() & Qt.MouseButton.LeftButton):
            val = self._val_from_pos(event.position().x())
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.isSliderDown():
            val = self._val_from_pos(event.position().x())
            self.setValue(val)
            self.setSliderDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ModelDownloadDialog(QDialog):
    """モデルダウンロード進行ダイアログ"""
    def __init__(self, model_key: str, models_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI音声モデルのダウンロード")
        self.setFixedSize(450, 185)
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
            elif self.voice_combo.count() > 0:
                self.voice_combo.setCurrentIndex(0)
        elif self.voice_combo.count() > 0:
            self.voice_combo.setCurrentIndex(0)

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
    """TTS (音声合成) 画面: Kokoro, Piper, SAPI (音質コントロール & WAV/MP3/WebM保存対応)"""
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
        # ページ全体を縦スクロール可能に（詳細パラメーター展開で潰れないように）
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.page_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        self.content_widget = QWidget()
        self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # ===== 上部設定パネル =====
        settings_group = QGroupBox("⚙ 音声エンジン & フォーマット設定")
        settings_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        set_layout = QVBoxLayout(settings_group)
        set_layout.setContentsMargins(12, 18, 12, 12)
        set_layout.setSpacing(12)

        # 1行目: エンジン・フォーマット・速度
        row1 = QHBoxLayout()
        row1.setSpacing(14)

        self.engine_combo = QComboBox()
        self.engine_combo.addItem("🎵 Kokoro (英語専用・最高品質 AI)", "kokoro")
        self.engine_combo.addItem("⚡ Piper (日本語/英語・高速ローカル AI)", "piper")
        self.engine_combo.addItem("🔊 Windows SAPI (標準搭載・即座利用)", "sapi")
        self.engine_combo.setFixedWidth(280)
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)

        self.download_model_btn = QPushButton("⬇ モデルDL")
        self.download_model_btn.setProperty("class", "teal")
        self.download_model_btn.setFixedWidth(95)
        self.download_model_btn.setVisible(False)
        self.download_model_btn.clicked.connect(self._on_download_model)

        self.format_combo = QComboBox()
        self.format_combo.addItem("WAV (高音質・非圧縮)", "wav")
        self.format_combo.addItem("MP3 (軽量・高音質・汎用)", "mp3")
        self.format_combo.addItem("WebM (Opus高圧縮・Web標準)", "webm")
        self.format_combo.setFixedWidth(210)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(5, 20)
        self.speed_slider.setValue(10)
        self.speed_label = QLabel("速度: 1.0x")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"速度: {v/10.0:.1f}x"))

        row1.addWidget(QLabel("エンジン:"))
        row1.addWidget(self.engine_combo)
        row1.addWidget(self.download_model_btn)
        row1.addWidget(QLabel("形式:"))
        row1.addWidget(self.format_combo)
        row1.addWidget(self.speed_label)
        row1.addWidget(self.speed_slider, 1)
        set_layout.addLayout(row1)

        # 2行目: 詳細音質パラメーター (トグル開閉)
        self.advanced_check = QCheckBox("詳細パラメーター (音質・チャンネル・ビットレート) を設定")
        self.advanced_check.setStyleSheet("color: #a78bfa; font-weight: bold; font-size: 12px;")
        self.advanced_check.toggled.connect(self._toggle_advanced_settings)
        set_layout.addWidget(self.advanced_check)

        self.advanced_frame = QFrame()
        self.advanced_frame.setObjectName("advancedFrame")
        self.advanced_frame.setStyleSheet("""
            QFrame#advancedFrame {
                background: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
        """)
        self.advanced_frame.setVisible(False)
        self.advanced_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.advanced_frame.setMinimumHeight(0)

        adv_layout = QVBoxLayout(self.advanced_frame)
        adv_layout.setContentsMargins(14, 14, 14, 14)
        adv_layout.setSpacing(16)

        # --- 音質行 ---
        quality_row = QHBoxLayout()
        quality_row.setSpacing(16)

        self.sr_combo = QComboBox()
        self.sr_combo.addItem("44.1 kHz (高音質CD標準)", 44100)
        self.sr_combo.addItem("24.0 kHz (Kokoro標準)", 24000)
        self.sr_combo.addItem("22.05 kHz (Piper標準)", 22050)
        self.sr_combo.addItem("16.0 kHz (軽量・音声標準)", 16000)
        self.sr_combo.setCurrentIndex(1)  # 24kHz

        self.ch_combo = QComboBox()
        self.ch_combo.addItem("モノラル (1ch)", 1)
        self.ch_combo.addItem("ステレオ (2ch)", 2)

        self.br_combo = QComboBox()
        self.br_combo.addItem("192 kbps (高音質)", 192)
        self.br_combo.addItem("128 kbps (標準・推奨)", 128)
        self.br_combo.addItem("256 kbps (最高品質)", 256)
        self.br_combo.addItem("64 kbps (超軽量)", 64)
        self.br_combo.setCurrentIndex(1)  # 128 kbps

        quality_row.addWidget(QLabel("サンプルレート:"))
        quality_row.addWidget(self.sr_combo)
        quality_row.addWidget(QLabel("チャンネル:"))
        quality_row.addWidget(self.ch_combo)
        quality_row.addWidget(QLabel("ビットレート:"))
        quality_row.addWidget(self.br_combo)
        quality_row.addStretch()
        adv_layout.addLayout(quality_row)

        # --- 空白時間指定 ---
        self.pause_check = QCheckBox("空白時間指定（文末・特定記号の後に無音を挿入）")
        self.pause_check.setStyleSheet("color: #c4b5fd; font-weight: bold; font-size: 13px; min-height: 24px;")
        self.pause_check.setChecked(False)
        self.pause_check.setMinimumHeight(28)
        self.pause_check.toggled.connect(self._toggle_pause_controls)
        adv_layout.addWidget(self.pause_check)

        self.pause_controls = QFrame()
        self.pause_controls.setObjectName("pauseControls")
        self.pause_controls.setStyleSheet("""
            QFrame#pauseControls {
                background: rgba(139, 92, 246, 0.08);
                border: 1px solid rgba(139, 92, 246, 0.25);
                border-radius: 8px;
            }
            QFrame#pauseControls QLabel {
                color: #e2e8f0;
                font-size: 13px;
                min-height: 22px;
            }
        """)
        self.pause_controls.setVisible(False)
        self.pause_controls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        pause_layout = QVBoxLayout(self.pause_controls)
        pause_layout.setContentsMargins(14, 14, 14, 14)
        pause_layout.setSpacing(14)

        # 縦積みにして狭い幅でも潰れないようにする
        sentence_lbl = QLabel("文末 (. ? !) の後")
        sentence_lbl.setStyleSheet("font-weight: 600;")
        pause_layout.addWidget(sentence_lbl)
        self.sentence_pause_spin = QDoubleSpinBox()
        self.sentence_pause_spin.setRange(0.1, 2.0)
        self.sentence_pause_spin.setSingleStep(0.1)
        self.sentence_pause_spin.setDecimals(1)
        self.sentence_pause_spin.setValue(0.5)
        self.sentence_pause_spin.setSuffix(" 秒")
        self.sentence_pause_spin.setMinimumHeight(40)
        self.sentence_pause_spin.setMaximumWidth(160)
        pause_layout.addWidget(self.sentence_pause_spin)

        marker_lbl = QLabel("特定記号（連続で倍数: // = 2倍）")
        marker_lbl.setStyleSheet("font-weight: 600;")
        pause_layout.addWidget(marker_lbl)
        marker_row = QHBoxLayout()
        marker_row.setSpacing(12)
        self.pause_marker_edit = QLineEdit("/")
        self.pause_marker_edit.setMaxLength(8)
        self.pause_marker_edit.setMinimumWidth(72)
        self.pause_marker_edit.setMaximumWidth(96)
        self.pause_marker_edit.setMinimumHeight(40)
        self.pause_marker_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pause_marker_edit.setToolTip("文中の区切り記号。連続すると無音が倍数になります（例: // = 2倍）")
        marker_row.addWidget(self.pause_marker_edit)
        after_lbl = QLabel("の後")
        marker_row.addWidget(after_lbl)
        self.marker_pause_spin = QDoubleSpinBox()
        self.marker_pause_spin.setRange(0.1, 2.0)
        self.marker_pause_spin.setSingleStep(0.1)
        self.marker_pause_spin.setDecimals(1)
        self.marker_pause_spin.setValue(0.3)
        self.marker_pause_spin.setSuffix(" 秒")
        self.marker_pause_spin.setMinimumHeight(40)
        self.marker_pause_spin.setMaximumWidth(160)
        marker_row.addWidget(self.marker_pause_spin)
        marker_row.addStretch()
        pause_layout.addLayout(marker_row)

        pause_hint = QLabel(
            "オフ時は従来どおり（ブロック間 0.3 秒のみ）。\n"
            "オン時は文を分割して合成し、指定無音を挿入します。特定記号自体は読み上げません。"
        )
        pause_hint.setWordWrap(True)
        pause_hint.setMinimumHeight(48)
        pause_hint.setStyleSheet("color: #94a3b8; font-size: 12px;")
        pause_layout.addWidget(pause_hint)

        adv_layout.addWidget(self.pause_controls)
        set_layout.addWidget(self.advanced_frame)

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
        editor_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        editor_group.setMinimumHeight(320)
        editor_layout = QVBoxLayout(editor_group)
        editor_layout.setContentsMargins(12, 18, 12, 12)
        editor_layout.setSpacing(8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(240)
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

        # stretch しない（ページ全体スクロールで高さを確保）
        main_layout.addWidget(editor_group, 0)

        # ===== 操作ボタンエリア =====
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.generate_btn = QPushButton("🎵 音声を合成する")
        self.generate_btn.setFixedHeight(44)
        self.generate_btn.clicked.connect(self._on_generate)

        self.save_pc_btn = QPushButton("💾 パソコンに保存 (.wav)")
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
        player_layout.setSpacing(10)

        self.restart_btn = QPushButton("⏮ 最初から")
        self.restart_btn.setProperty("class", "secondary")
        self.restart_btn.setFixedWidth(95)
        self.restart_btn.setEnabled(False)
        self.restart_btn.setToolTip("音声を最初から再生します")
        self.restart_btn.clicked.connect(self._on_restart_play)

        self.play_btn = QPushButton("▶ 再生")
        self.play_btn.setFixedWidth(90)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._on_toggle_play)

        self.seek_slider = SeekSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(95)
        self.time_label.setAlignment(Qt.AlignCenter)

        self.status_label = QLabel("待機中")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")

        player_layout.addWidget(self.restart_btn)
        player_layout.addWidget(self.play_btn)
        player_layout.addWidget(self.seek_slider, 1)
        player_layout.addWidget(self.time_label)
        player_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        main_layout.addWidget(player_group)
        main_layout.addWidget(self.status_label)
        main_layout.addStretch(0)

        self.page_scroll.setWidget(self.content_widget)
        root.addWidget(self.page_scroll)

        # 初期ブロックを1つ作成
        self.add_block()
        self._refresh_page_scroll()

    def _refresh_page_scroll(self):
        """詳細パネル開閉後にコンテンツ高さを再計算し、ページ縦スクロールを有効化する。"""
        if not hasattr(self, "content_widget"):
            return
        layout = self.content_widget.layout()
        if layout is not None:
            layout.activate()
            # 表示中ウィジェットの推奨高さを合算（非表示は sizeHint に含まれにくいので個別加算）
            needed = layout.contentsMargins().top() + layout.contentsMargins().bottom()
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item is None:
                    continue
                w = item.widget()
                if w is not None:
                    if w.isVisibleTo(self.content_widget):
                        needed += max(w.sizeHint().height(), w.minimumHeight())
                    continue
                sp = item.spacerItem()
                if sp is not None:
                    needed += sp.sizeHint().height()
                elif item.layout() is not None:
                    needed += item.layout().sizeHint().height()
                needed += layout.spacing()
            self.content_widget.setMinimumHeight(max(needed + 32, 480))
        self.content_widget.adjustSize()
        self.content_widget.updateGeometry()
        self.page_scroll.updateGeometry()

    def _init_connections(self):
        self.player.position_changed.connect(self._on_position_changed)
        self.player.duration_changed.connect(self._on_duration_changed)
        self.player.state_changed.connect(self._on_state_changed)
        self.seek_slider.sliderMoved.connect(self._on_slider_moved)
        self.seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self.seek_slider.sliderReleased.connect(self._on_slider_released)

    def _toggle_advanced_settings(self, checked):
        self.advanced_frame.setVisible(checked)
        # レイアウト確定後に高さ再計算（即時だと sizeHint が古いことがある）
        QTimer.singleShot(0, self._refresh_page_scroll)

    def _toggle_pause_controls(self, checked):
        self.pause_controls.setVisible(checked)
        QTimer.singleShot(0, self._refresh_page_scroll)

    def _on_format_changed(self):
        ext = self.format_combo.currentData()
        self.save_pc_btn.setText(f"💾 パソコンに保存 (.{ext})")

    def _on_engine_changed(self):
        engine = self.engine_combo.currentData()
        voices = self.tts.get_voices_for_engine(engine)
        
        for b in self.blocks:
            b.set_voices(voices)

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
        format_type = self.format_combo.currentData()
        speed_factor = self.speed_slider.value() / 10.0
        sample_rate = self.sr_combo.currentData()
        channels = self.ch_combo.currentData()
        bitrate_kbps = self.br_combo.currentData()

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

        self.status_label.setText(f"⏳ 音声を合成＆ {format_type.upper()} にエンコード中...")
        self.generate_btn.setEnabled(False)

        # 前回の未保存一時音声があれば破棄
        if self.current_audio_path and self.current_audio_path.exists():
            try:
                self.player.unload()
                self.current_audio_path.unlink()
            except Exception:
                pass
            self.current_audio_path = None

        try:
            pause_on = self.pause_check.isChecked()
            marker = self.pause_marker_edit.text().strip() or "/"
            out_path = self.tts.synthesize_dialogue(
                block_data,
                engine=engine,
                speed=speed_factor,
                format_type=format_type,
                sample_rate=sample_rate,
                channels=channels,
                bitrate_kbps=bitrate_kbps,
                pause_control_enabled=pause_on,
                sentence_pause_sec=self.sentence_pause_spin.value(),
                pause_marker=marker,
                marker_pause_sec=self.marker_pause_spin.value(),
            )
            self.current_audio_path = out_path
            self.player.load(out_path)
            
            self.status_label.setText(f"✅ 合成・エンコード完了: {out_path.name} ({sample_rate}Hz, {channels}ch, {bitrate_kbps}kbps)")
            self.play_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
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
        ext = self.format_combo.currentData()
        filter_str = f"{ext.upper()}ファイル (*.{ext})"
        save_path, _ = QFileDialog.getSaveFileName(self, "音声を保存", f"speech_{self.current_audio_path.name}", filter_str)
        if save_path:
            import shutil
            shutil.copy2(self.current_audio_path, save_path)
            QMessageBox.information(self, "成功", f"保存しました:\n{save_path}")

    def _on_save_drive(self):
        if not self.current_audio_path or not self.current_audio_path.exists():
            return

        ext = self.format_combo.currentData()
        sr = self.sr_combo.currentData()
        ch = "ステレオ" if self.ch_combo.currentData() == 2 else "モノラル"
        br = self.br_combo.currentData()
        
        full_text = "\n".join([f"[{b.get_data()['speaker'] or '話者'}] {b.get_data()['text']}" for b in self.blocks if b.get_data()['text']])
        voice_info = f"Desktop ({self.engine_combo.currentText()})"
        settings_info = f"エンジン: {self.engine_combo.currentText()}, 形式: {ext.upper()}, SR: {sr}Hz, チャンネル: {ch}, BR: {br}kbps"

        self.status_label.setText("☁ Google Drive にアップロード中...")
        self.save_drive_btn.setEnabled(False)

        res = self.gas.upload_audio(self.current_audio_path, full_text, voice_info, settings=settings_info)
        self.save_drive_btn.setEnabled(True)

        if res.get("status") == "success":
            url = res.get("url", "")
            msg = f"✅ Google Drive に正常に保存されました！ (形式: {ext.upper()})"
            if url:
                msg += f"\n\nURL: {url}"
            QMessageBox.information(self, "Google Drive 保存完了", msg)
            self.status_label.setText(f"✅ Google Drive 保存完了！ ({ext.upper()})")
        else:
            err = res.get("message", "不明なエラー")
            QMessageBox.critical(self, "保存失敗", f"Google Driveへの保存に失敗しました:\n{err}")
            self.status_label.setText(f"❌ Google Drive 保存失敗: {err}")

    def _on_restart_play(self):
        self.player.restart()
        self.seek_slider.setValue(0)
        self._update_time_label(0, self.seek_slider.maximum())

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

    def _on_slider_moved(self, pos_ms):
        self._update_time_label(pos_ms, self.seek_slider.maximum())

    def _on_slider_pressed(self):
        self._was_playing_before_seek = self.player.is_playing()
        if self._was_playing_before_seek:
            self.player.pause()
        self.player.set_position(self.seek_slider.value())
        self._update_time_label(self.seek_slider.value(), self.seek_slider.maximum())

    def _on_slider_released(self):
        self.player.set_position(self.seek_slider.value())
        self._update_time_label(self.seek_slider.value(), self.seek_slider.maximum())
        if getattr(self, "_was_playing_before_seek", False):
            self.player.play()
            self._was_playing_before_seek = False

    def _update_time_label(self, cur_ms, total_ms):
        cur_sec = cur_ms // 1000
        tot_sec = total_ms // 1000
        self.time_label.setText(f"{cur_sec//60:02d}:{cur_sec%60:02d} / {tot_sec//60:02d}:{tot_sec%60:02d}")

    def insert_external_text(self, text: str):
        self.add_block(text=text)

    def cleanup(self):
        """アプリ終了時等に未保存の一時音声ファイルをすべて破棄"""
        try:
            self.player.unload()
        except Exception:
            pass
        self.tts.cleanup_output_dir()
        self.current_audio_path = None
