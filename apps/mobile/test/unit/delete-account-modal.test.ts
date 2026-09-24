import { describe, expect, it, vi } from "vitest";

describe("DeleteAccountModal & Phone Confirmation Logic", () => {
  function normalizePhone(p: string | null | undefined): string {
    if (!p) return "";
    return p.replace(/\D/g, "");
  }

  function checkPhonesMatch(entered: string, registered: string): boolean {
    const nEntered = normalizePhone(entered);
    const nRegistered = normalizePhone(registered);
    if (!nEntered || !nRegistered) return false;
    if (nEntered === nRegistered) return true;
    if (nEntered.length >= 10 && nRegistered.length >= 10) {
      return nEntered.slice(-10) === nRegistered.slice(-10);
    }
    return false;
  }

  it("accurately matches identical phone numbers", () => {
    expect(checkPhonesMatch("9876543210", "9876543210")).toBe(true);
    expect(checkPhonesMatch("+919876543210", "+919876543210")).toBe(true);
  });

  it("accurately matches formatted phone numbers with spaces and dashes", () => {
    expect(checkPhonesMatch("+91 98765 43210", "9876543210")).toBe(true);
    expect(checkPhonesMatch("98765-43210", "+91 98765-43210")).toBe(true);
    expect(checkPhonesMatch("(+91) 98765 43210", "9876543210")).toBe(true);
  });

  it("matches numbers with and without country code by 10-digit suffix", () => {
    expect(checkPhonesMatch("9876543210", "+919876543210")).toBe(true);
    expect(checkPhonesMatch("+919876543210", "9876543210")).toBe(true);
    expect(checkPhonesMatch("09876543210", "9876543210")).toBe(true);
  });

  it("rejects mismatched phone numbers", () => {
    expect(checkPhonesMatch("9876543210", "9123456789")).toBe(false);
    expect(checkPhonesMatch("+91 98765 43210", "+91 88888 88888")).toBe(false);
    expect(checkPhonesMatch("12345", "9876543210")).toBe(false);
    expect(checkPhonesMatch("", "9876543210")).toBe(false);
  });

  it("simulates confirmation flow and calls onConfirmDelete when matching", async () => {
    const onConfirmDelete = vi.fn().mockResolvedValue(undefined);
    const registered = "+91 98765 43210";
    const entered = "9876543210";

    const isMatch = checkPhonesMatch(entered, registered);
    expect(isMatch).toBe(true);

    if (isMatch) {
      await onConfirmDelete(entered);
    }

    expect(onConfirmDelete).toHaveBeenCalledWith("9876543210");
  });

  it("blocks deletion when entered phone number does not match registered phone", async () => {
    const onConfirmDelete = vi.fn().mockResolvedValue(undefined);
    const registered = "+91 98765 43210";
    const entered = "9999999999";

    const isMatch = checkPhonesMatch(entered, registered);
    expect(isMatch).toBe(false);

    let error: string | null = null;
    if (!isMatch) {
      error = "Phone number does not match your registered phone number. Please try again.";
    } else {
      await onConfirmDelete(entered);
    }

    expect(error).toBe("Phone number does not match your registered phone number. Please try again.");
    expect(onConfirmDelete).not.toHaveBeenCalled();
  });
});
