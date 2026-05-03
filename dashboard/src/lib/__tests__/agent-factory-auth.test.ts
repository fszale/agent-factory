import { describe, it, expect, beforeEach } from "vitest";
import {
  API_KEY_STORAGE_KEY,
  BASE_URL_STORAGE_KEY,
  clearCredentials,
  isValidBaseUrl,
  loadCredentials,
  normalizeBaseUrl,
  saveCredentials,
} from "@/lib/agent-factory/auth";

describe("normalizeBaseUrl", () => {
  it("strips trailing slashes", () => {
    expect(normalizeBaseUrl("https://api.example.com/")).toBe("https://api.example.com");
    expect(normalizeBaseUrl("https://api.example.com///")).toBe("https://api.example.com");
    expect(normalizeBaseUrl("  https://api.example.com  ")).toBe("https://api.example.com");
  });
});

describe("isValidBaseUrl", () => {
  it("accepts http/https URLs", () => {
    expect(isValidBaseUrl("https://api.example.com")).toBe(true);
    expect(isValidBaseUrl("http://localhost:8000")).toBe(true);
  });

  it("rejects empty / non-http URLs", () => {
    expect(isValidBaseUrl("")).toBe(false);
    expect(isValidBaseUrl("ftp://x")).toBe(false);
    expect(isValidBaseUrl("not-a-url")).toBe(false);
  });
});

describe("credential storage", () => {
  beforeEach(() => {
    if (typeof window !== "undefined") {
      window.localStorage.clear();
    }
  });

  it("returns null when no credentials are set", () => {
    expect(loadCredentials()).toBeNull();
  });

  it("returns null when only one half is set", () => {
    window.localStorage.setItem(API_KEY_STORAGE_KEY, "key");
    expect(loadCredentials()).toBeNull();
    window.localStorage.removeItem(API_KEY_STORAGE_KEY);
    window.localStorage.setItem(BASE_URL_STORAGE_KEY, "https://x");
    expect(loadCredentials()).toBeNull();
  });

  it("round-trips saved credentials", () => {
    saveCredentials({ apiKey: "secret-key", baseUrl: "https://api.example.com/" });
    expect(loadCredentials()).toEqual({
      apiKey: "secret-key",
      baseUrl: "https://api.example.com",
    });
  });

  it("clearCredentials removes saved values", () => {
    saveCredentials({ apiKey: "k", baseUrl: "https://x" });
    clearCredentials();
    expect(loadCredentials()).toBeNull();
  });
});
