import qrcodeFactory from "qrcode-generator";

export type DoctorQrAccount = {
  accountId: string;
  displayName?: string | null;
  facilityId?: string | null;
};

export const DOCTOR_QR_SCHEME = "thali";

export function buildDoctorAccountQrValue(account: DoctorQrAccount): string {
  const query: string[] = [`account=${encodeURIComponent(account.accountId)}`];
  if (account.displayName) {
    query.push(`name=${encodeURIComponent(account.displayName)}`);
  }
  if (account.facilityId) {
    query.push(`facility=${encodeURIComponent(account.facilityId)}`);
  }
  return `${DOCTOR_QR_SCHEME}://doctor?${query.join("&")}`;
}

/**
 * Parse a doctor account QR value back into its structured account id + the
 * optional display name / facility id that `buildDoctorAccountQrValue` packed
 * in. Returns null when the value is not a doctor QR (wrong scheme, missing
 * host, or absent account).
 *
 * Pure TS, no dependencies — mirrors (not hard-copies) the backend's own
 * `thali://doctor?account=...` QR contract so a scanned/pasted URI resolves
 * to exactly the clinician_user_id the v2 clinician-links endpoints expect.
 */
export function parseDoctorAccountQrValue(value: string): DoctorQrAccount | null {
  const trimmed = value.trim();
  if (!trimmed.toLowerCase().startsWith(`${DOCTOR_QR_SCHEME}://doctor`)) {
    return null;
  }
  const queryIndex = trimmed.indexOf("?");
  if (queryIndex === -1) {
    return null;
  }
  const params = new URLSearchParams(trimmed.slice(queryIndex + 1));
  const accountId = params.get("account");
  if (!accountId) {
    return null;
  }
  const displayName = params.get("name") || undefined;
  const facilityId = params.get("facility") || undefined;
  return { accountId, displayName, facilityId };
}

export function isDoctorAccountQrValue(value: string): boolean {
  return parseDoctorAccountQrValue(value) !== null;
}

export type QrEcl = "L" | "M" | "Q" | "H";

export type QrMatrix = {
  size: number;
  dark: readonly { row: number; col: number }[];
};

export function buildQrMatrix(value: string, ecl: QrEcl = "H"): QrMatrix {
  const qr = qrcodeFactory(0, ecl);
  qr.addData(value);
  qr.make();
  const size = qr.getModuleCount();
  const dark: { row: number; col: number }[] = [];
  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      if (qr.isDark(row, col)) dark.push({ row, col });
    }
  }
  return { size, dark };
}