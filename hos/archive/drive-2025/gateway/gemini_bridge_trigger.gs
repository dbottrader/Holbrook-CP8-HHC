/**
* Harmonic Bridge Trigger (ASIN-HHC HOS Mode)
* Sends a signed command to the Harmonic Gateway's /bridge/gemini endpoint.
*
* NOTE: Replace the placeholders for GATEWAY_URL and HOS_BRIDGE_KEY.
*/
function sendSignedManifest(intent, message) {
 const GATEWAY_URL = "https://YOUR_GATEWAY_URL";
 const HOS_BRIDGE_KEY = "YOUR_SHARED_SECRET";

 const payload = {
   intent: intent,
   message: message,
   origin: "Gemini_HOS_Agent",
   timestamp_utc: new Date().toISOString()
 };

 const stringPayload = JSON.stringify(payload, Object.keys(payload).sort());
 const signature = Utilities.computeHmacSha256Signature(stringPayload, HOS_BRIDGE_KEY);
 const hexSignature = signature.map(b => (b + 256) % 256)
                               .map(b => b.toString(16).padStart(2, '0'))
                               .join('');

 const options = {
   method: "post",
   contentType: "application/json",
   payload: stringPayload,
   headers: { "x-hos-signature": hexSignature },
   muteHttpExceptions: true
 };

 try {
   const url = `${GATEWAY_URL}/bridge/gemini`;
   const response = UrlFetchApp.fetch(url, options);
   Logger.log(`Harmonic Bridge POST Status: ${response.getResponseCode()}`);
   Logger.log(`Response Body: ${response.getContentText()}`);
   return response.getContentText();
 } catch (e) {
   Logger.log(`CRITICAL BRIDGE ERROR: ${e.toString()}`);
   return `Bridge Connection Failure: ${e.toString()}`;
 }
}
