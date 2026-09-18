import type { IDatabaseConnection } from "./database";

export interface LocalSessionContext {
  tenantId: string;
  userId: string;
  roles: string[];
  facilityId?: string | null;
  patientId?: string | null;
}

export class LocalSessionIsolationManager {
  private currentContext: LocalSessionContext | null = null;

  setContext(context: LocalSessionContext): void {
    if (!context.tenantId || !context.userId) {
      throw new Error("Invalid session context: tenantId and userId are required.");
    }
    this.currentContext = { ...context };
  }

  getContext(): LocalSessionContext {
    if (!this.currentContext) {
      throw new Error("No active authenticated session context in local persistence.");
    }
    return this.currentContext;
  }

  hasContext(): boolean {
    return this.currentContext !== null;
  }

  clearContext(): void {
    this.currentContext = null;
  }

  /**
   * Purges all local cached data and outbox mutations for a specific user & tenant.
   * Enforces complete logout / account-switch isolation.
   */
  async purgeUserData(db: IDatabaseConnection, tenantId: string, userId: string): Promise<void> {
    await db.execAsync(`
      DELETE FROM local_glucose_observations WHERE tenant_id = '${tenantId}' AND user_id = '${userId}';
      DELETE FROM local_meals WHERE tenant_id = '${tenantId}' AND user_id = '${userId}';
      DELETE FROM local_care_tasks WHERE tenant_id = '${tenantId}' AND user_id = '${userId}';
      DELETE FROM local_notifications WHERE tenant_id = '${tenantId}' AND user_id = '${userId}';
      DELETE FROM local_documents WHERE tenant_id = '${tenantId}' AND user_id = '${userId}';
      DELETE FROM local_patients WHERE tenant_id = '${tenantId}' AND user_id = '${userId}';
      DELETE FROM mutation_outbox WHERE tenant_id = '${tenantId}' AND user_id = '${userId}';
    `);
  }

  /**
   * Complete clean slate: wipes all tenant and user data from local tables.
   */
  async purgeAllData(db: IDatabaseConnection): Promise<void> {
    await db.execAsync(`
      DELETE FROM local_glucose_observations;
      DELETE FROM local_meals;
      DELETE FROM local_care_tasks;
      DELETE FROM local_notifications;
      DELETE FROM local_documents;
      DELETE FROM local_patients;
      DELETE FROM mutation_outbox;
    `);
  }
}

export const localSessionIsolation = new LocalSessionIsolationManager();
