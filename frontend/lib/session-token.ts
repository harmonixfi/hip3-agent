/**
 * HMAC-SHA256(password, password) as lowercase hex.
 * Must match Node `createHmac("sha256", password).update(password).digest("hex")`
 * in `app/login/actions.ts` (Edge middleware cannot use Node `crypto`).
 */
export async function makeSessionToken(password: string): Promise<string> {
  const enc = new TextEncoder();
  const keyData = enc.encode(password);
  const messageData = enc.encode(password);
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyData,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, messageData);
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
