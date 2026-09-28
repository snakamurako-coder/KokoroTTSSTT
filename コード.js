function doGet() {
  // index.html を読み込んでWebアプリとして出力する
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Kokoro TTS Studio')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}