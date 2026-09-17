import { createContext } from "react";
import { AuthVerifyResponse } from "../contracts";

export interface AuthContextType {
  user: AuthVerifyResponse | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  error: string | null;
  login: () => Promise<void>;
  logout: () => void;
  verifySession: () => Promise<void>;
  handleOidcCallback: (code: string, state: string) => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
