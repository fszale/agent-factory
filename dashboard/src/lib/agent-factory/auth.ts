export const API_KEY_STORAGE_KEY = "agent-factory.apiKey";
export const BASE_URL_STORAGE_KEY = "agent-factory.baseUrl";

export interface FactoryCredentials {
  apiKey: string;
  baseUrl: string;
}

function safeStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadCredentials(): FactoryCredentials | null {
  const storage = safeStorage();
  if (!storage) return null;
  const apiKey = storage.getItem(API_KEY_STORAGE_KEY)?.trim() ?? "";
  const baseUrl = storage.getItem(BASE_URL_STORAGE_KEY)?.trim() ?? "";
  if (!apiKey || !baseUrl) return null;
  return { apiKey, baseUrl: normalizeBaseUrl(baseUrl) };
}

export function saveCredentials(creds: FactoryCredentials): void {
  const storage = safeStorage();
  if (!storage) return;
  storage.setItem(API_KEY_STORAGE_KEY, creds.apiKey.trim());
  storage.setItem(BASE_URL_STORAGE_KEY, normalizeBaseUrl(creds.baseUrl));
}

export function clearCredentials(): void {
  const storage = safeStorage();
  if (!storage) return;
  storage.removeItem(API_KEY_STORAGE_KEY);
  storage.removeItem(BASE_URL_STORAGE_KEY);
}

export function normalizeBaseUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/g, "");
  return trimmed;
}

export function isValidBaseUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}
