import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  clearCredentials as clearCreds,
  loadCredentials,
  saveCredentials,
  type FactoryCredentials,
} from "@/lib/agent-factory/auth";
import { FactoryClient } from "@/lib/agent-factory/client";

interface CredentialsContextValue {
  credentials: FactoryCredentials | null;
  client: FactoryClient | null;
  isReady: boolean;
  setCredentials: (creds: FactoryCredentials) => void;
  clearCredentials: () => void;
}

const CredentialsContext = createContext<CredentialsContextValue | null>(null);

export function CredentialsProvider({ children }: { children: React.ReactNode }) {
  const [credentials, setCreds] = useState<FactoryCredentials | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setCreds(loadCredentials());
    setHydrated(true);
  }, []);

  const setCredentials = useCallback((creds: FactoryCredentials) => {
    saveCredentials(creds);
    setCreds({ apiKey: creds.apiKey.trim(), baseUrl: creds.baseUrl.replace(/\/+$/, "") });
  }, []);

  const clearCredentials = useCallback(() => {
    clearCreds();
    setCreds(null);
  }, []);

  const client = useMemo(() => {
    if (!credentials) return null;
    try {
      return new FactoryClient({ baseUrl: credentials.baseUrl, apiKey: credentials.apiKey });
    } catch {
      return null;
    }
  }, [credentials]);

  const value: CredentialsContextValue = {
    credentials,
    client,
    isReady: hydrated,
    setCredentials,
    clearCredentials,
  };

  return <CredentialsContext.Provider value={value}>{children}</CredentialsContext.Provider>;
}

export function useCredentials(): CredentialsContextValue {
  const ctx = useContext(CredentialsContext);
  if (!ctx) throw new Error("useCredentials must be used within CredentialsProvider");
  return ctx;
}
