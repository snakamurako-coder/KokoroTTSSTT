from pathlib import Path
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

class AudioPlayerService(QObject):
    """QtMultimedia を利用した音声再生サービス"""
    position_changed = Signal(int)     # 再生位置 (ms)
    duration_changed = Signal(int)     # 総再生時間 (ms)
    state_changed = Signal(bool)        # 再生中フラグ (True: プレイ中, False: 停止中)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self.player.positionChanged.connect(self.position_changed.emit)
        self.player.durationChanged.connect(self.duration_changed.emit)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)

    def load(self, file_path: str | Path):
        url = QUrl.fromLocalFile(str(file_path))
        self.player.setSource(url)

    def play(self):
        dur = self.player.duration()
        pos = self.player.position()
        if dur > 0 and pos >= dur:
            self.player.setPosition(0)
        self.player.play()

    def restart(self):
        """最初から再生"""
        self.player.setPosition(0)
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

    def unload(self):
        """再生を停止し、ファイル参照を完全に解放する"""
        self.player.stop()
        self.player.setSource(QUrl())

    def set_position(self, ms: int):
        self.player.setPosition(ms)

    def set_volume(self, volume_percent: int):
        # 0.0 〜 1.0 にスケーリング
        self.audio_output.setVolume(max(0.0, min(1.0, volume_percent / 100.0)))

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def _on_playback_state_changed(self, state):
        self.state_changed.emit(state == QMediaPlayer.PlaybackState.PlayingState)
