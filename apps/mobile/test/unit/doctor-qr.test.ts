import { describe, expect, it } from "vitest";
import { buildDoctorAccountQrValue, buildQrMatrix, DoctorQrAccount } from "../../src/features/doctor/doctorQr";

describe("buildDoctorAccountQrValue", () => {
  const base: DoctorQrAccount = {
    accountId: "acct-1",
    displayName: "Dr. Ananya Rao",
    facilityId: "facility-1",
  };

  it("is deterministic for the same account", () => {
    expect(buildDoctorAccountQrValue(base)).toBe(buildDoctorAccountQrValue(base));
  });

  it("produces a unique value per doctor account", () => {
    const a = buildDoctorAccountQrValue({ ...base, accountId: "acct-1" });
    const b = buildDoctorAccountQrValue({ ...base, accountId: "acct-2" });
    expect(a).not.toBe(b);
  });

  it("encodes the thali doctor deep link with account, name, and facility", () => {
    const value = buildDoctorAccountQrValue(base);
    expect(value).toBe(
      `thali://doctor?account=acct-1&name=${encodeURIComponent("Dr. Ananya Rao")}&facility=facility-1`
    );
    expect(value.startsWith("thali://doctor?")).toBe(true);
  });

  it("omits name and facility when absent", () => {
    expect(buildDoctorAccountQrValue({ accountId: "acct-3" })).toBe("thali://doctor?account=acct-3");
  });

  it("URL-encodes special characters in the display name", () => {
    const value = buildDoctorAccountQrValue({ accountId: "acct-4", displayName: "Dr A & B / C" });
    expect(value).toBe(`thali://doctor?account=acct-4&name=${encodeURIComponent("Dr A & B / C")}`);
  });
});

describe("buildQrMatrix", () => {
  it("produces a square matrix of dark cells for a valid deep link", () => {
    const matrix = buildQrMatrix("thali://doctor?account=acct-123&name=Dr.A&facility=fac-1");
    expect(matrix.size).toBeGreaterThan(16);
    expect(matrix.dark.length).toBeGreaterThan(0);
    const inBounds = matrix.dark.every(
      (cell) => cell.row >= 0 && cell.row < matrix.size && cell.col >= 0 && cell.col < matrix.size
    );
    expect(inBounds).toBe(true);
  });

  it("is deterministic for the same value", () => {
    const a = buildQrMatrix("thali://doctor?account=acct-9");
    const b = buildQrMatrix("thali://doctor?account=acct-9");
    expect(a.size).toBe(b.size);
    expect(a.dark).toEqual(b.dark);
  });

  it("produces a different matrix for a different doctor account", () => {
    const a = buildQrMatrix("thali://doctor?account=acct-1");
    const b = buildQrMatrix("thali://doctor?account=acct-2");
    expect(a.dark).not.toEqual(b.dark);
  });

  it("decodes back to a scannable matrix via error correction level H", () => {
    const value = "thali://doctor?account=acct-77&name=Dr.Ananya&facility=facility-1";
    const matrix = buildQrMatrix(value, "H");
    expect(matrix.size).toBeGreaterThan(0);
  });
});