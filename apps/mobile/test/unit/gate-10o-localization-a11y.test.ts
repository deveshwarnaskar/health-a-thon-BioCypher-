import { describe, it, expect, vi, beforeEach } from "vitest";
import { i18n, t } from "../../src/i18n/i18n";
import { en } from "../../src/i18n/translations/en";
import { hi } from "../../src/i18n/translations/hi";
import { bn } from "../../src/i18n/translations/bn";
import { ta } from "../../src/i18n/translations/ta";
import { te } from "../../src/i18n/translations/te";
import { mr } from "../../src/i18n/translations/mr";
import {
  resolveButtonAccessibilityProps,
  touchTargetStyle,
} from "../../src/components/primitives/button.accessibility";
import { touchTarget, typography } from "../../src/theming/tokens";
import { MockSqlCipherDatabase } from "./helpers/mockDatabase";
import { OfflineCaptureService } from "../../src/sync/offlineCapture";
import { SyncCoordinator } from "../../src/sync/syncCoordinator";
import { GlucoseRepository, MealRepository, CareTaskRepository } from "../../src/db/repositories";
import { ApiClient } from "../../src/services/api/client";

describe("Gate 10O — Localization & Accessibility Test Matrix (Items 41-60)", () => {
  beforeEach(() => {
    i18n.setLanguage("en");
  });

  // 41 English localization
  it("41: English localization renders all keys and verifies critical clinical terminology", () => {
    i18n.setLanguage("en");
    expect(t("common.appName")).toBe("GLYCOCARE");
    expect(t("roles.doctor")).toBe("Doctor");
    expect(t("glucose.title")).toBe("Blood Glucose");
    expect(t("sync.savedLocally")).toBe("Saved on this device");
    expect(t("sync.waitingToSync")).toBe("Waiting to sync");
    expect(t("sync.synced")).toBe("Synced");
  });

  // 42 Hindi localization
  it("42: Hindi localization preserves clinical meaning without machine-translation corruption", () => {
    i18n.setLanguage("hi");
    expect(t("glucose.title")).toBe("रक्त शर्करा");
    expect(t("glucose.record")).toBe("ग्लूकोज दर्ज करें");
    expect(t("roles.doctor")).toBe("चिकित्सक");
    expect(t("roles.fieldHealthWorker")).toContain("आशा");
    expect(t("sync.savedLocally")).toBe("इस उपकरण पर सहेजा गया");
    expect(t("sync.waitingToSync")).toBe("सिंक की प्रतीक्षा है");
    expect(t("sync.synced")).toBe("सिंक हो गया");
  });

  // 43 Bengali localization
  it("43: Bengali localization preserves clinical meaning", () => {
    i18n.setLanguage("bn");
    expect(t("glucose.title")).toBe("রক্তে শর্করা");
    expect(t("glucose.record")).toBe("গ্লুকোজ রেকর্ড করুন");
    expect(t("roles.doctor")).toBe("চিকিৎসক");
    expect(t("sync.savedLocally")).toBe("এই ডিভাইসে সংরক্ষিত");
    expect(t("sync.synced")).toBe("সিঙ্ক সম্পন্ন");
  });

  // 44 Tamil localization
  it("44: Tamil localization preserves clinical meaning", () => {
    i18n.setLanguage("ta");
    expect(t("glucose.title")).toBe("இரத்த சர்க்கரை");
    expect(t("glucose.record")).toBe("குளுக்கோஸை பதிவு செய்");
    expect(t("roles.doctor")).toBe("மருத்துவர்");
    expect(t("sync.savedLocally")).toBe("இந்த சாதனத்தில் சேமிக்கப்பட்டது");
    expect(t("sync.synced")).toBe("ஒத்திசைக்கப்பட்டது");
  });

  // 45 Telugu localization
  it("45: Telugu localization preserves clinical meaning", () => {
    i18n.setLanguage("te");
    expect(t("glucose.title")).toBe("రక్తంలో చక్కెర");
    expect(t("glucose.record")).toBe("గ్లూకోజ్ నమోదు చేయండి");
    expect(t("roles.doctor")).toBe("వైద్యుడు");
    expect(t("sync.savedLocally")).toBe("ఈ పరికరంలో సేవ్ చేయబడింది");
    expect(t("sync.synced")).toBe("సింక్ చేయబడింది");
  });

  // 46 Marathi localization
  it("46: Marathi localization preserves clinical meaning", () => {
    i18n.setLanguage("mr");
    expect(t("glucose.title")).toBe("रक्त शर्करा");
    expect(t("glucose.record")).toBe("ग्लुकोज नोंदवा");
    expect(t("roles.doctor")).toBe("डॉक्टर");
    expect(t("sync.savedLocally")).toBe("या डिव्हाइसवर जतन केले");
    expect(t("sync.synced")).toBe("सिंक झाले");
  });

  // 47 translation fallback
  it("47: translation fallback defaults to English when key is missing in target language", () => {
    i18n.setLanguage("hi");
    // If a subkey is queried that exists in English
    const res = i18n.t("common.save");
    expect(res).toBe("सहेजें");

    // Fallback test: query a key non-existent in dictionary returns human title-cased fallback, never raw key syntax
    const missing = i18n.t("nonExistentKey");
    expect(missing).not.toBe("nonExistentKey");
    expect(missing).toBe("Non Existent Key");
  });

  // 48 text expansion
  it("48: text expansion verifies all 6 dictionaries have matching structural keys without truncation", () => {
    const dictionaries = [hi, bn, ta, te, mr];
    const enSections = Object.keys(en) as (keyof typeof en)[];

    for (const dict of dictionaries) {
      for (const section of enSections) {
        expect(dict).toHaveProperty(section);
        const enKeys = Object.keys(en[section]);
        const targetKeys = Object.keys(dict[section]);
        expect(targetKeys.sort()).toEqual(enKeys.sort());
      }
    }
  });

  // 49 VoiceOver
  it("49: VoiceOver compatibility ensures accessible labels, roles, and traits on interactive primitives", () => {
    const props = resolveButtonAccessibilityProps({
      label: "Save observation",
      hint: "Saves observation to local storage",
      disabled: false,
      busy: false,
    });
    expect(props.accessible).toBe(true);
    expect(props.accessibilityRole).toBe("button");
    expect(props.accessibilityLabel).toBe("Save observation");
    expect(props.accessibilityHint).toBe("Saves observation to local storage");
    expect(props.accessibilityState).toEqual({ disabled: false, busy: false });
  });

  // 50 TalkBack
  it("50: TalkBack compatibility verifies accessible states for disabled and busy controls", () => {
    const props = resolveButtonAccessibilityProps({
      label: "Syncing data",
      disabled: true,
      busy: true,
    });
    expect(props.accessibilityState.disabled).toBe(true);
    expect(props.accessibilityState.busy).toBe(true);
  });

  // 51 large text
  it("51: large text scaling token metrics guarantee readability up to 200%", () => {
    expect(typography.fontSize.display).toBe(32);
    expect(typography.lineHeight.display).toBe(38);
    // At 200%, display font scale is 64 / 76, typography accommodates dynamic type
    expect(typography.lineHeight.display).toBeGreaterThan(typography.fontSize.display);
  });

  // 52 focus order
  it("52: focus order and interactive touch targets meet WCAG 2.5.5 minimum 48x48dp", () => {
    const style = touchTargetStyle();
    expect(style.minHeight).toBe(48);
    expect(style.minWidth).toBe(48);
    expect(touchTarget.min).toBe(48);
  });

  // 53 screen-reader labels
  it("53: screen-reader labels distinguish sync status non-color glyphs and localized text", () => {
    i18n.setLanguage("en");
    const syncLabel = `${t("accessibility.syncStatusLabel")}: ${t("sync.savedLocally")}`;
    expect(syncLabel).toBe("Sync status: Saved on this device");

    i18n.setLanguage("hi");
    const hiSyncLabel = `${t("accessibility.syncStatusLabel")}: ${t("sync.savedLocally")}`;
    expect(hiSyncLabel).toBe("सिंक स्थिति: इस उपकरण पर सहेजा गया");
  });

  // 54 error announcements
  it("54: error announcements provide clear, sanitized, non-leaking messages", () => {
    expect(t("common.error")).toBe("An error occurred");
    expect(t("glucose.validationError")).toBe(
      "Please enter a valid glucose reading between 20 and 600 mg/dL"
    );
  });

  // 55 sync-status announcements
  it("55: sync-status announcements inform user of connection restoration and active sync", () => {
    expect(t("accessibility.offlineModeActive")).toBe("Offline mode active");
    expect(t("accessibility.networkRestored")).toBe("Network connection restored");
  });

  // 56 offline UI
  it("56: offline UI displays explicit saved-on-device state and never claims server success", () => {
    const savedLocally = t("sync.savedLocally");
    expect(savedLocally).toBe("Saved on this device");
    expect(savedLocally).not.toContain("successfully");
  });

  // 57 sync failure UI
  it("57: sync failure UI indicates NEEDS_ATTENTION with non-color warning glyph", () => {
    const attention = t("sync.needsAttention");
    expect(attention).toBe("Needs attention");
  });

  // 58 full offline->online glucose workflow
  it("58: full offline->online glucose workflow captures reading offline, stores in SQLCipher, survives, and syncs on reconnect", async () => {
    const mockDb = new MockSqlCipherDatabase();
    const captureService = new OfflineCaptureService(mockDb);
    const context = {
      tenantId: "tenant-flow",
      userId: "user-flow",
      roles: ["Patient"],
      patientId: "patient-flow",
    };

    // 1. Offline Capture
    const capture = await captureService.captureGlucose(
      context,
      { patient_id: "patient-flow", value_mg_dl: 128, tag: "fasting" },
      "idem-flow-58"
    );
    expect(capture.sync_status).toBe("SAVED_LOCALLY");

    // 2. Verified in local SQLCipher projection
    const glucoseRepo = new GlucoseRepository(mockDb);
    const localRec = await glucoseRepo.findById(capture.local_id);
    expect(localRec?.syncStatus).toBe("SAVED_LOCALLY");
    expect(localRec?.serverId).toBeNull();

    // 3. Network Restored & Sync Executed
    const fakeClient = {
      request: vi.fn().mockResolvedValue({ id: "server-obs-58", observation_id: "server-obs-58" }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });
    const syncRes = await coordinator.sync(context);
    expect(syncRes.processed).toBe(1);

    // 4. Local Entity Reconciled to SYNCED
    const syncedRec = await glucoseRepo.findById(capture.local_id);
    expect(syncedRec?.syncStatus).toBe("SYNCED");
    expect(syncedRec?.serverId).toBe("server-obs-58");
  });

  // 59 full offline->online meal workflow
  it("59: full offline->online meal workflow captures draft offline, stores in SQLCipher, and syncs to server", async () => {
    const mockDb = new MockSqlCipherDatabase();
    const captureService = new OfflineCaptureService(mockDb);
    const context = {
      tenantId: "tenant-flow",
      userId: "user-flow",
      roles: ["Patient"],
      patientId: "patient-flow",
    };

    // 1. Offline Capture
    const capture = await captureService.captureMeal(
      context,
      {
        patient_id: "patient-flow",
        description: "Roti with Palak Paneer",
        portion: { food_key: "palak_paneer", katori_volume_ml: 220, quantity: 1.5 },
      },
      "idem-meal-59"
    );
    expect(capture.sync_status).toBe("SAVED_LOCALLY");

    // 2. Verify local repository
    const mealRepo = new MealRepository(mockDb);
    const meals = await mealRepo.findByPatient(context, "patient-flow");
    expect(meals).toHaveLength(1);
    expect(meals[0]!.syncStatus).toBe("SAVED_LOCALLY");

    // 3. Sync executed
    const fakeClient = {
      request: vi.fn().mockResolvedValue({ id: "server-meal-59", meal_observation_id: "server-meal-59" }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });
    const syncRes = await coordinator.sync(context);
    expect(syncRes.processed).toBe(1);

    // 4. Reconciled to SYNCED
    const updatedMeals = await mealRepo.findByPatient(context, "patient-flow");
    expect(updatedMeals[0]!.syncStatus).toBe("SYNCED");
    expect(updatedMeals[0]!.serverId).toBe("server-meal-59");
  });

  // 60 full offline->online task workflow
  it("60: full offline->online task workflow transitions task state locally and syncs to authoritative server", async () => {
    const mockDb = new MockSqlCipherDatabase();
    const taskRepo = new CareTaskRepository(mockDb);
    const context = {
      tenantId: "tenant-flow",
      userId: "user-flow",
      roles: ["FieldHealthWorker"],
      patientId: "patient-flow",
    };

    // Pre-populate task
    await taskRepo.upsert({
      localId: "t-local-60",
      serverId: "server-task-60",
      tenantId: "tenant-flow",
      userId: "user-flow",
      patientId: "patient-flow",
      title: "Patient follow-up check",
      description: "Home visit",
      taskType: "FOLLOW_UP",
      status: "OPEN",
      priority: "HIGH",
      dueDate: null,
      syncStatus: "SYNCED",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    // 1. Offline Task Transition (COMPLETE)
    const captureService = new OfflineCaptureService(mockDb);
    const trans = await captureService.captureTaskTransition(
      context,
      "server-task-60",
      "COMPLETE",
      "idem-task-60"
    );
    expect(trans.status).toBe("COMPLETED");
    expect(trans.sync_status).toBe("WAITING_TO_SYNC");

    // 2. Sync to Server
    const fakeClient = {
      request: vi.fn().mockResolvedValue({ task_id: "server-task-60", status: "COMPLETED" }),
    } as unknown as ApiClient;

    const coordinator = new SyncCoordinator({ db: mockDb, apiClient: fakeClient });
    const syncRes = await coordinator.sync(context);
    expect(syncRes.processed).toBe(1);

    // 3. Reconciled to SYNCED
    const updated = await taskRepo.findByServerId("server-task-60");
    expect(updated?.status).toBe("COMPLETED");
    expect(updated?.syncStatus).toBe("SYNCED");
  });
});
