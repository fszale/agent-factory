import { describe, it, expect } from "vitest";
import {
  FactoryApiError,
  FactoryClient,
  errorCodeForStatus,
  defaultMessageForStatus,
  extractErrorMessage,
} from "@/lib/agent-factory/client";

function makeFetchOk(body: unknown, status = 200): typeof fetch {
  return (async () =>
    new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    })) as unknown as typeof fetch;
}

function makeFetchError(status: number, body: unknown): typeof fetch {
  return (async () =>
    new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    })) as unknown as typeof fetch;
}

function makeFetchThrow(err: unknown): typeof fetch {
  return (async () => {
    throw err;
  }) as unknown as typeof fetch;
}

describe("FactoryClient construction", () => {
  it("requires baseUrl and apiKey", () => {
    expect(() => new FactoryClient({ baseUrl: "", apiKey: "x" })).toThrow();
    expect(() => new FactoryClient({ baseUrl: "https://x", apiKey: "" })).toThrow();
  });

  it("normalizes trailing slashes in baseUrl", async () => {
    let called = "";
    const fetchSpy: typeof fetch = (async (url: any) => {
      called = String(url);
      return new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } });
    }) as unknown as typeof fetch;
    const client = new FactoryClient({
      baseUrl: "https://api.example.com///",
      apiKey: "k",
      fetchImpl: fetchSpy,
    });
    await client.listTwins();
    expect(called).toBe("https://api.example.com/twins");
  });
});

describe("FactoryClient request handling", () => {
  it("sends API key headers and parses JSON response", async () => {
    let receivedHeaders: Headers | undefined;
    const fetchSpy: typeof fetch = (async (_url: any, init: any) => {
      receivedHeaders = new Headers(init?.headers);
      return new Response(JSON.stringify([{ id: "t1" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;
    const client = new FactoryClient({
      baseUrl: "https://api.example.com",
      apiKey: "secret",
      fetchImpl: fetchSpy,
    });
    const result = await client.listTwins();
    expect(result).toEqual([{ id: "t1" }]);
    expect(receivedHeaders?.get("X-API-Key")).toBe("secret");
    expect(receivedHeaders?.get("Authorization")).toBe("Bearer secret");
  });

  it("throws FactoryApiError with code 'unauthorized' on 401", async () => {
    const client = new FactoryClient({
      baseUrl: "https://api.example.com",
      apiKey: "k",
      fetchImpl: makeFetchError(401, { detail: "bad key" }),
    });
    await expect(client.listTwins()).rejects.toMatchObject({
      name: "FactoryApiError",
      status: 401,
      code: "unauthorized",
      message: "bad key",
    });
  });

  it("throws FactoryApiError with code 'not_found' on 404", async () => {
    const client = new FactoryClient({
      baseUrl: "https://api.example.com",
      apiKey: "k",
      fetchImpl: makeFetchError(404, { detail: "missing" }),
    });
    await expect(client.getTwin("nope")).rejects.toMatchObject({
      status: 404,
      code: "not_found",
    });
  });

  it("throws FactoryApiError with code 'server_error' on 500", async () => {
    const client = new FactoryClient({
      baseUrl: "https://api.example.com",
      apiKey: "k",
      fetchImpl: makeFetchError(500, { detail: "boom" }),
    });
    await expect(client.listTwins()).rejects.toMatchObject({
      status: 500,
      code: "server_error",
    });
  });

  it("throws FactoryApiError with code 'network_error' when fetch throws", async () => {
    const client = new FactoryClient({
      baseUrl: "https://api.example.com",
      apiKey: "k",
      fetchImpl: makeFetchThrow(new TypeError("network down")),
    });
    await expect(client.listTwins()).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });

  it("returns a default message when error body is empty", async () => {
    const client = new FactoryClient({
      baseUrl: "https://api.example.com",
      apiKey: "k",
      fetchImpl: makeFetchError(403, ""),
    });
    await expect(client.listTwins()).rejects.toMatchObject({
      status: 403,
      code: "forbidden",
      message: "Forbidden: this API key does not have access.",
    });
  });

  it("encodes query parameters and skips empty ones", async () => {
    let calledUrl = "";
    const fetchSpy: typeof fetch = (async (url: any) => {
      calledUrl = String(url);
      return new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 50 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;
    const client = new FactoryClient({
      baseUrl: "https://api.example.com",
      apiKey: "k",
      fetchImpl: fetchSpy,
    });
    await client.listAudit({ twin_id: "twin-1", action: undefined, page: 2, page_size: 20 });
    expect(calledUrl).toContain("twin_id=twin-1");
    expect(calledUrl).toContain("page=2");
    expect(calledUrl).toContain("page_size=20");
    expect(calledUrl).not.toContain("action=");
  });

  it("handles non-JSON error body gracefully", async () => {
    const client = new FactoryClient({
      baseUrl: "https://api.example.com",
      apiKey: "k",
      fetchImpl: makeFetchOk("oops not json", 502),
    });
    await expect(client.listTwins()).rejects.toMatchObject({
      status: 502,
      code: "server_error",
    });
  });
});

describe("error helpers", () => {
  it("classifies status codes correctly", () => {
    expect(errorCodeForStatus(0)).toBe("network_error");
    expect(errorCodeForStatus(401)).toBe("unauthorized");
    expect(errorCodeForStatus(404)).toBe("not_found");
    expect(errorCodeForStatus(409)).toBe("conflict");
    expect(errorCodeForStatus(422)).toBe("unprocessable_entity");
    expect(errorCodeForStatus(429)).toBe("rate_limited");
    expect(errorCodeForStatus(500)).toBe("server_error");
    expect(errorCodeForStatus(418)).toBe("client_error");
  });

  it("extracts error messages from various shapes", () => {
    expect(extractErrorMessage({ detail: "a" })).toBe("a");
    expect(extractErrorMessage({ message: "b" })).toBe("b");
    expect(extractErrorMessage({ error: "c" })).toBe("c");
    expect(extractErrorMessage({ detail: [{ msg: "validation failed" }] })).toBe(
      "validation failed",
    );
    expect(extractErrorMessage(null)).toBeNull();
    expect(extractErrorMessage("string body")).toBeNull();
  });

  it("provides sane default messages", () => {
    expect(defaultMessageForStatus(401)).toMatch(/API key/i);
    expect(defaultMessageForStatus(503)).toMatch(/Server error/i);
  });
});

describe("FactoryApiError", () => {
  it("retains status, code, and message", () => {
    const err = new FactoryApiError({ status: 404, code: "not_found", message: "x" });
    expect(err.status).toBe(404);
    expect(err.code).toBe("not_found");
    expect(err.message).toBe("x");
    expect(err).toBeInstanceOf(Error);
  });
});
