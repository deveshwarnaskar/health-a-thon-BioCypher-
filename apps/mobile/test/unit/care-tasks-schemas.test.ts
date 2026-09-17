import { describe, expect, it } from "vitest";
import {
  careTaskStatusSchema,
  careTaskResponseSchema,
  careTaskListResponseSchema,
  createCareTaskRequestSchema,
  startCareTaskResponseSchema,
  completeCareTaskResponseSchema,
  reassignCareTaskRequestSchema,
  reassignCareTaskResponseSchema,
  type CareTaskResponse,
  type CareTaskListResponse,
} from "../../src/services/schemas/tasks";
import { can, capabilitiesForRole } from "../../src/authz/capabilities";

describe("Gate 10J-M Care Task Schemas & Authorization Contracts", () => {
  const validUUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  const validWorkerUUID = "e4a21190-3cb8-47e2-861f-998811223344";

  describe("Care Task Status Schema", () => {
    it("accepts canonical status values: open, in_progress, completed, cancelled", () => {
      expect(careTaskStatusSchema.parse("open")).toBe("open");
      expect(careTaskStatusSchema.parse("in_progress")).toBe("in_progress");
      expect(careTaskStatusSchema.parse("completed")).toBe("completed");
      expect(careTaskStatusSchema.parse("cancelled")).toBe("cancelled");
    });

    it("rejects invalid status values", () => {
      expect(() => careTaskStatusSchema.parse("pending")).toThrow();
      expect(() => careTaskStatusSchema.parse("closed")).toThrow();
      expect(() => careTaskStatusSchema.parse("ARCHIVED")).toThrow();
      expect(() => careTaskStatusSchema.parse("")).toThrow();
    });
  });

  describe("Care Task Response Schema", () => {
    const validTask: CareTaskResponse = {
      care_task_id: "ct-001",
      patient_id: validUUID,
      assigned_to_user_id: validWorkerUUID,
      description: "Home visit: check capillary blood glucose and observe lunch portion.",
      status: "open",
      due_at: "2026-09-18T10:00:00Z",
      created_at: "2026-09-17T08:00:00Z",
      completed_at: null,
    };

    it("parses valid complete care task response", () => {
      const parsed = careTaskResponseSchema.parse(validTask);
      expect(parsed).toEqual(validTask);
      expect(parsed.care_task_id).toBe("ct-001");
      expect(parsed.status).toBe("open");
    });

    it("parses task response with null optional fields", () => {
      const minimalTask = {
        care_task_id: "ct-002",
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "Routine checkup",
        status: "in_progress",
        due_at: null,
        created_at: "2026-09-17T08:00:00Z",
        completed_at: null,
      };

      const parsed = careTaskResponseSchema.parse(minimalTask);
      expect(parsed.care_task_id).toBe("ct-002");
      expect(parsed.due_at).toBeNull();
    });

    it("rejects task response missing required fields", () => {
      expect(() =>
        careTaskResponseSchema.parse({
          description: "Missing ID",
          status: "open",
          patient_id: validUUID,
        })
      ).toThrow();

      expect(() =>
        careTaskResponseSchema.parse({
          care_task_id: "ct-003",
          patient_id: validUUID,
          assigned_to_user_id: validWorkerUUID,
          description: "Missing status",
          created_at: "2026-09-17T08:00:00Z",
        })
      ).toThrow();
    });

    it("rejects unknown keys due to strict validation", () => {
      expect(() =>
        careTaskResponseSchema.parse({
          ...validTask,
          extra_key: "not-allowed",
        })
      ).toThrow();
    });
  });

  describe("Care Task List Response Schema", () => {
    const listPayload: CareTaskListResponse = {
      patient_id: validUUID,
      task_count: 1,
      items: [
        {
          care_task_id: "ct-001",
          patient_id: validUUID,
          assigned_to_user_id: validWorkerUUID,
          description: "Home visit",
          status: "open",
          due_at: "2026-09-18T10:00:00Z",
          created_at: "2026-09-17T08:00:00Z",
          completed_at: null,
        },
      ],
    };

    it("parses valid task list response", () => {
      const parsed = careTaskListResponseSchema.parse(listPayload);
      expect(parsed.task_count).toBe(1);
      expect(parsed.items).toHaveLength(1);
      expect(parsed.items[0]?.care_task_id).toBe("ct-001");
    });

    it("allows null patient_id in facility-wide task list", () => {
      const parsed = careTaskListResponseSchema.parse({
        patient_id: null,
        task_count: 0,
        items: [],
      });
      expect(parsed.patient_id).toBeNull();
      expect(parsed.task_count).toBe(0);
      expect(parsed.items).toEqual([]);
    });

    it("rejects task list missing items array", () => {
      expect(() =>
        careTaskListResponseSchema.parse({
          task_count: 0,
        })
      ).toThrow();
    });
  });

  describe("Create Care Task Request Schema", () => {
    it("parses valid creation payload", () => {
      const validPayload = {
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "Visit home and measure capillary blood glucose.",
        due_at: "2026-09-20T14:00:00Z",
      };

      const parsed = createCareTaskRequestSchema.parse(validPayload);
      expect(parsed.patient_id).toBe(validUUID);
      expect(parsed.assigned_to_user_id).toBe(validWorkerUUID);
      expect(parsed.description).toBe("Visit home and measure capillary blood glucose.");
      expect(parsed.due_at).toBe("2026-09-20T14:00:00Z");
    });

    it("parses valid creation payload without optional due_at", () => {
      const payloadWithoutDue = {
        patient_id: validUUID,
        assigned_to_user_id: validWorkerUUID,
        description: "Follow-up phone consultation",
      };

      const parsed = createCareTaskRequestSchema.parse(payloadWithoutDue);
      expect(parsed.description).toBe("Follow-up phone consultation");
      expect(parsed.due_at).toBeUndefined();
    });

    it("rejects empty description", () => {
      expect(() =>
        createCareTaskRequestSchema.parse({
          patient_id: validUUID,
          assigned_to_user_id: validWorkerUUID,
          description: "",
        })
      ).toThrow();
    });

    it("rejects missing patient_id or assigned_to_user_id", () => {
      expect(() =>
        createCareTaskRequestSchema.parse({
          assigned_to_user_id: validWorkerUUID,
          description: "Missing patient",
        })
      ).toThrow();

      expect(() =>
        createCareTaskRequestSchema.parse({
          patient_id: validUUID,
          description: "Missing assignee",
        })
      ).toThrow();
    });
  });

  describe("Lifecycle Mutation Response Schemas", () => {
    it("parses startCareTaskResponseSchema", () => {
      const parsed = startCareTaskResponseSchema.parse({
        care_task_id: "ct-001",
        status: "in_progress",
      });
      expect(parsed.care_task_id).toBe("ct-001");
      expect(parsed.status).toBe("in_progress");
    });

    it("parses completeCareTaskResponseSchema", () => {
      const parsed = completeCareTaskResponseSchema.parse({
        care_task_id: "ct-001",
        status: "completed",
        completed_at: "2026-09-17T12:00:00Z",
      });
      expect(parsed.status).toBe("completed");
      expect(parsed.completed_at).toBe("2026-09-17T12:00:00Z");
    });

    it("parses reassignCareTaskRequestSchema and Response", () => {
      const reqParsed = reassignCareTaskRequestSchema.parse({
        new_user_id: validWorkerUUID,
      });
      expect(reqParsed.new_user_id).toBe(validWorkerUUID);

      const resParsed = reassignCareTaskResponseSchema.parse({
        care_task_id: "ct-001",
        assigned_to_user_id: validWorkerUUID,
        status: "open",
      });
      expect(resParsed.assigned_to_user_id).toBe(validWorkerUUID);
    });
  });

  describe("Role Capabilities for Care Tasks", () => {
    it("grants READ_CARE_TASKS, START_CARE_TASK, COMPLETE_CARE_TASK to FieldHealthWorker", () => {
      expect(can("FieldHealthWorker", "READ_CARE_TASKS")).toBe(true);
      expect(can("FieldHealthWorker", "START_CARE_TASK")).toBe(true);
      expect(can("FieldHealthWorker", "COMPLETE_CARE_TASK")).toBe(true);
      expect(can("FieldHealthWorker", "READ_ASSIGNED_TASKS")).toBe(true);
      expect(can("FieldHealthWorker", "START_ASSIGNED_TASK")).toBe(true);
      expect(can("FieldHealthWorker", "COMPLETE_ASSIGNED_TASK")).toBe(true);
      expect(can("FieldHealthWorker", "CREATE_CARE_TASK")).toBe(false);
      expect(can("FieldHealthWorker", "REASSIGN_CARE_TASK")).toBe(false);
    });

    it("grants READ_CARE_TASKS, CREATE_CARE_TASK, REASSIGN_CARE_TASK to CareCoordinator", () => {
      expect(can("CareCoordinator", "READ_CARE_TASKS")).toBe(true);
      expect(can("CareCoordinator", "CREATE_CARE_TASK")).toBe(true);
      expect(can("CareCoordinator", "REASSIGN_CARE_TASK")).toBe(true);
      expect(can("CareCoordinator", "START_CARE_TASK")).toBe(true);
      expect(can("CareCoordinator", "COMPLETE_CARE_TASK")).toBe(true);
    });

    it("grants READ_CARE_TASKS to Doctor, Nurse, Dietitian", () => {
      expect(can("Doctor", "READ_CARE_TASKS")).toBe(true);
      expect(can("Nurse", "READ_CARE_TASKS")).toBe(true);
      expect(can("Dietitian", "READ_CARE_TASKS")).toBe(true);
    });

    it("denies care task capabilities to Patient and Caregiver", () => {
      expect(can("Patient", "READ_CARE_TASKS")).toBe(false);
      expect(can("Patient", "CREATE_CARE_TASK")).toBe(false);
      expect(can("Caregiver", "READ_CARE_TASKS")).toBe(false);
      expect(can("Caregiver", "CREATE_CARE_TASK")).toBe(false);
    });

    it("lists expected capability counts for roles", () => {
      const fhwCaps = capabilitiesForRole("FieldHealthWorker");
      expect(fhwCaps).toContain("READ_CARE_TASKS");
      expect(fhwCaps).toContain("START_CARE_TASK");
      expect(fhwCaps).toContain("COMPLETE_CARE_TASK");

      const coordCaps = capabilitiesForRole("CareCoordinator");
      expect(coordCaps).toContain("CREATE_CARE_TASK");
      expect(coordCaps).toContain("REASSIGN_CARE_TASK");
    });
  });
});
