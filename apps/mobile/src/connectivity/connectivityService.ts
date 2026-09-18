export type ConnectivityStatus =
  | "ONLINE"
  | "OFFLINE"
  | "SYNCING"
  | "SYNC_ERROR"
  | "PENDING";

export type ConnectivityListener = (status: ConnectivityStatus) => void;

export class ConnectivityService {
  private status: ConnectivityStatus = "ONLINE";
  private listeners = new Set<ConnectivityListener>();
  private scheduledRetryTimer: ReturnType<typeof setTimeout> | null = null;
  private onReconnectCallback?: () => Promise<void>;

  constructor(initialStatus: ConnectivityStatus = "ONLINE") {
    this.status = initialStatus;
  }

  getStatus(): ConnectivityStatus {
    return this.status;
  }

  isOnline(): boolean {
    return this.status !== "OFFLINE";
  }

  setStatus(newStatus: ConnectivityStatus): void {
    if (this.status === newStatus) return;

    const previous = this.status;
    this.status = newStatus;
    this.notifyListeners();

    // On transition from OFFLINE -> ONLINE, fire reconnect callback
    if (previous === "OFFLINE" && newStatus === "ONLINE" && this.onReconnectCallback) {
      void this.onReconnectCallback();
    }
  }

  setOnReconnect(callback: () => Promise<void>): void {
    this.onReconnectCallback = callback;
  }

  subscribe(listener: ConnectivityListener): () => void {
    this.listeners.add(listener);
    listener(this.status);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Schedules a controlled retry timer for the earliest next_retry_at.
   * INVARIANT: Never uses blind setInterval(() => retryEverything(), ...).
   */
  scheduleControlledRetry(delayMs: number, onRetry: () => Promise<void>): void {
    if (this.scheduledRetryTimer) {
      clearTimeout(this.scheduledRetryTimer);
      this.scheduledRetryTimer = null;
    }

    if (delayMs <= 0) {
      void onRetry();
      return;
    }

    this.scheduledRetryTimer = setTimeout(() => {
      this.scheduledRetryTimer = null;
      if (this.isOnline()) {
        void onRetry();
      }
    }, delayMs);
  }

  cancelScheduledRetry(): void {
    if (this.scheduledRetryTimer) {
      clearTimeout(this.scheduledRetryTimer);
      this.scheduledRetryTimer = null;
    }
  }

  private notifyListeners(): void {
    for (const listener of this.listeners) {
      try {
        listener(this.status);
      } catch {
        // Listener errors should not interrupt connectivity state propagation
      }
    }
  }
}

export const connectivityService = new ConnectivityService();
