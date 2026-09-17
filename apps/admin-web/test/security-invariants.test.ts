import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

function getAllSourceFiles(dir: string): string[] {
  let results: string[] = [];
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    if (stat && stat.isDirectory()) {
      results = results.concat(getAllSourceFiles(filePath));
    } else if (filePath.endsWith(".ts") || filePath.endsWith(".tsx")) {
      results.push(filePath);
    }
  }
  return results;
}

describe("Gate 10K-W Security Invariants", () => {
  const srcDir = path.resolve(__dirname, "../src");
  const sourceFiles = getAllSourceFiles(srcDir);

  it("never calls /api/v1 endpoints", () => {
    for (const file of sourceFiles) {
      const content = fs.readFileSync(file, "utf-8");
      expect(content).not.toMatch(/\/api\/v1/);
    }
  });

  it("never calls clinical observation, meal, or medication endpoints", () => {
    const forbiddenPatterns = [
      /\/api\/v2\/patients\/[^/]+\/observations/,
      /\/api\/v2\/patients\/[^/]+\/meals/,
      /\/api\/v2\/patients\/[^/]+\/medications/,
      /\/api\/v2\/clinical/,
      /\/api\/v2\/ai/,
    ];

    for (const file of sourceFiles) {
      const content = fs.readFileSync(file, "utf-8");
      for (const pattern of forbiddenPatterns) {
        expect(content).not.toMatch(pattern);
      }
    }
  });

  it("contains no hardcoded client secrets, private keys, or passwords", () => {
    const secretPatterns = [
      /client_secret\s*[:=]\s*["'][^"']+["']/,
      /-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----/,
      /password\s*[:=]\s*["'][^"']+["']/,
    ];

    for (const file of sourceFiles) {
      const content = fs.readFileSync(file, "utf-8");
      for (const pattern of secretPatterns) {
        expect(content).not.toMatch(pattern);
      }
    }
  });

  it("does not introduce arbitrary or elevated roles beyond canonical roles", () => {
    const forbiddenRoles = ["facility_admin", "system_admin", "super_admin"];
    for (const file of sourceFiles) {
      const content = fs.readFileSync(file, "utf-8");
      for (const role of forbiddenRoles) {
        expect(content).not.toContain(`"${role}"`);
        expect(content).not.toContain(`'${role}'`);
      }
    }
  });

  it("ensures all mutations send Idempotency-Key", () => {
    const apiClientFile = path.resolve(srcDir, "api/client.ts");
    const content = fs.readFileSync(apiClientFile, "utf-8");
    expect(content).toContain('headers.set("Idempotency-Key", window.crypto.randomUUID())');
  });

  it("ensures all responses invoke assertNoClinicalFields", () => {
    const apiClientFile = path.resolve(srcDir, "api/client.ts");
    const content = fs.readFileSync(apiClientFile, "utf-8");
    expect(content).toContain("assertNoClinicalFields(rawJson)");
  });
});
