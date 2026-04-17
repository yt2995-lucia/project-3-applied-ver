// =============================================================================
// Google Apps Script — DataScope A/B Study Data Receiver
// =============================================================================
//
// SETUP:
//   1. Open your Google Sheet
//   2. Extensions → Apps Script → paste this entire file
//   3. Deploy → New Deployment → Web App
//      - Execute as: Me
//      - Who has access: Anyone
//   4. Copy the deployment URL into app.R (SHEETS_URL variable)
//
// The script writes one row per participant submission to the first sheet.
// =============================================================================

var SHEET_NAME = "Sheet1";

var COLUMNS = [
  "session_id",
  "participant_id",
  "group",
  "n_tasks_done",
  "total_time_sec",
  "t1_done", "t1_time_s",
  "t2_done", "t2_time_s",
  "t3_done", "t3_time_s",
  "t4_done", "t4_time_s",
  "t5_done", "t5_time_s",
  "prior_experience",
  "tasks_hard_to_understand",
  "timestamp"
];

function doPost(e) {
  try {
    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME);

    // Create sheet and header row if it doesn't exist yet
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow(COLUMNS);
    }

    // Parse the JSON body sent from the Shiny app
    var payload = JSON.parse(e.postData.contents);

    // Handle both single object and array-of-one
    var record = Array.isArray(payload) ? payload[0] : payload;

    // Build a row in the same order as COLUMNS
    var row = COLUMNS.map(function(col) {
      var val = record[col];
      if (val === null || val === undefined) return "";
      return val;
    });

    sheet.appendRow(row);

    return ContentService
      .createTextOutput(JSON.stringify({ status: "ok" }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: "error", message: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Optional: GET handler for testing the deployment is live
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: "live" }))
    .setMimeType(ContentService.MimeType.JSON);
}
