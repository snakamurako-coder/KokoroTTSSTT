from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QStatusBar, QLabel
from PySide6.QtCore import Qt
from ui.tts_page import TTSPage
from ui.stt_page import STTPage
from ui.settings_page import SettingsPage

class MainWindow(QMainWindow):
    """デスクトップ版メインウィンドウ"""
    def __init__(self, config_manager):
        super().__init__()
        self.cfg = config_manager

        self.setWindowTitle("Kokoro TTS & STT Studio (Desktop)")
        self.resize(980, 720)
        self.setMinimumSize(800, 600)

        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # ===== タブウィジェット =====
        self.tabs = QTabWidget()
        
        self.tts_page = TTSPage(self.cfg, self)
        self.stt_page = STTPage(self.cfg, self)
        self.settings_page = SettingsPage(self.cfg, self)

        # STT -> TTS への連携シグナル
        self.stt_page.send_to_tts_requested.connect(self._handle_send_to_tts)

        self.tabs.addTab(self.tts_page, "🎵 音声合成 (TTS Studio)")
        self.tabs.addTab(self.stt_page, "🎙️ 音声認識 (STT Studio)")
        self.tabs.addTab(self.settings_page, "⚙️ 設定 & クラウド連携")

        main_layout.addWidget(self.tabs)

        # ===== ステータスバー =====
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        status_info = QLabel("Snapdragon Copilot+ PC (ARM64 Windows 11) 最適化モード | Python 3.14 + PySide6")
        status_info.setStyleSheet("color: #64748b; font-size: 11px; padding-right: 12px;")
        status_bar.addPermanentWidget(status_info)
        status_bar.showMessage("準備完了", 4000)

    def _handle_send_to_tts(self, text: str):
        """STTから送られたテキストをTTSに追加し、TTSタブへ自動切り替え"""
        self.tts_page.insert_external_text(text)
        self.tabs.setCurrentIndex(0)

    def closeEvent(self, event):
        """アプリ終了時に未保存の一時音声ファイルをすべて自動破棄"""
        if hasattr(self, "tts_page"):
            self.tts_page.cleanup()
        event.accept()
