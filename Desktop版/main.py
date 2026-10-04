import sys
import os
from pathlib import Path

# カレントディレクトリをパスに追加
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from core.config_manager import ConfigManager
from ui.main_window import MainWindow
from ui.styles import DARK_THEME_QSS

def main():
    # Windows 高DPIスケール対応
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    # QtMultimedia の FFmpeg デバッグログ出力を抑制
    os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg=false;qt.multimedia.*=false"

    app = QApplication(sys.argv)
    app.setApplicationName("KokoroTTSSTT-Desktop")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_THEME_QSS)

    # 設定ロード
    config = ConfigManager(BASE_DIR / "config.json")

    # メインウィンドウ表示
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
