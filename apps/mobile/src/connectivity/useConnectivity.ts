import { useState, useEffect } from "react";
import {
  connectivityService,
  type ConnectivityStatus,
} from "./connectivityService";

export function useConnectivity(): {
  status: ConnectivityStatus;
  isOnline: boolean;
  isOffline: boolean;
  isSyncing: boolean;
} {
  const [status, setStatus] = useState<ConnectivityStatus>(
    connectivityService.getStatus()
  );

  useEffect(() => {
    return connectivityService.subscribe((newStatus) => {
      setStatus(newStatus);
    });
  }, []);

  return {
    status,
    isOnline: status !== "OFFLINE",
    isOffline: status === "OFFLINE",
    isSyncing: status === "SYNCING",
  };
}
