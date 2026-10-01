const FOLDER_NAME = 'Kokoro TTS Output';
const SHEET_NAME = 'Kokoro TTS History';

function setupEnvironment() {
  const props = PropertiesService.getScriptProperties();
  
  // 1. フォルダの取得・作成
  let folderId = props.getProperty('FOLDER_ID');
  let folder;
  if (folderId) {
    try {
      folder = DriveApp.getFolderById(folderId);
    } catch (e) {
      folder = null;
    }
  }
  if (!folder) {
    const folders = DriveApp.getFoldersByName(FOLDER_NAME);
    if (folders.hasNext()) {
      folder = folders.next();
    } else {
      folder = DriveApp.createFolder(FOLDER_NAME);
    }
    props.setProperty('FOLDER_ID', folder.getId());
  }

  // 2. スプレッドシートの取得・作成
  let sheetId = props.getProperty('SHEET_ID');
  let ss;
  if (sheetId) {
    try {
      ss = SpreadsheetApp.openById(sheetId);
    } catch (e) {
      ss = null;
    }
  }
  if (!ss) {
    const files = folder.getFilesByName(SHEET_NAME);
    if (files.hasNext()) {
      ss = SpreadsheetApp.open(files.next());
    } else {
      ss = SpreadsheetApp.create(SHEET_NAME);
      // 作成したスプレッドシートをフォルダに移動
      const file = DriveApp.getFileById(ss.getId());
      file.moveTo(folder);
      
      // ヘッダー行を設定
      const sheet = ss.getSheets()[0];
      sheet.appendRow(['生成日時', 'テキスト', '音声モデル', '音声ファイルURL', '設定']);
      sheet.setFrozenRows(1);
    }
    props.setProperty('SHEET_ID', ss.getId());
  }
  
  return { folder, ss };
}

function doPost(e) {
  try {
    // リクエストのパース
    const data = JSON.parse(e.postData.contents);
    const text = data.text || 'テキストなし';
    const voiceModel = data.voiceModel || '不明';
    const settings = data.settings || '不明';
    const audioBase64 = data.audioBase64;
    
    if (!audioBase64) {
      throw new Error("音声データが空です");
    }

    // 環境（フォルダ・シート）の準備
    const { folder, ss } = setupEnvironment();
    
    // 音声ファイルの保存
    const decodedAudio = Utilities.base64Decode(audioBase64);
    const format = data.format || 'webm';
    let mimeType = 'audio/webm';
    if (format === 'wav') mimeType = 'audio/wav';
    else if (format === 'mp3') mimeType = 'audio/mp3';
    
    const fileName = `speech_${new Date().toISOString().replace(/[:.]/g, '-')}.${format}`;
    const blob = Utilities.newBlob(decodedAudio, mimeType, fileName);
    const file = folder.createFile(blob);
    const fileUrl = file.getUrl();
    
    // スプレッドシートへの記録
    const sheet = ss.getSheets()[0];
    sheet.appendRow([new Date(), text, voiceModel, fileUrl, settings]);
    
    // 成功レスポンスを返す（CORS対応のためにJSONで返す）
    return ContentService.createTextOutput(JSON.stringify({ 
      status: 'success', 
      url: fileUrl 
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    // エラーレスポンス
    return ContentService.createTextOutput(JSON.stringify({ 
      status: 'error', 
      message: error.toString() 
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

// GETリクエスト時のフォールバック処理
function doGet(e) {
  return ContentService.createTextOutput("This is an API endpoint for Kokoro TTS Studio. Please send a POST request with data.");
}