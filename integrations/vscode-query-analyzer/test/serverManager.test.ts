import assert from "node:assert/strict";
import test from "node:test";

import {
  ServerManager,
  buildBundledExecutablePath,
  findAvailablePort,
  resolveApiUrl,
  resolveTargetPlatform
} from "../src/serverManager";

test("resolveTargetPlatform maps supported release targets", () => {
  assert.equal(resolveTargetPlatform("win32", "x64"), "win32-x64");
  assert.equal(resolveTargetPlatform("linux", "x64"), "linux-x64");
  assert.equal(resolveTargetPlatform("darwin", "arm64"), "darwin-arm64");
  assert.equal(resolveTargetPlatform("darwin", "x64"), undefined);
});

test("buildBundledExecutablePath chooses the platform executable name", () => {
  assert.match(buildBundledExecutablePath("/ext", "win32-x64"), /bin[\\/]qa\.exe$/);
  assert.match(buildBundledExecutablePath("/ext", "linux-x64"), /bin[\\/]qa$/);
});

test("findAvailablePort returns a bindable local port", async () => {
  const port = await findAvailablePort();

  assert.equal(Number.isInteger(port), true);
  assert.equal(port > 0, true);
});

test("resolveApiUrl returns external URL when configured", async () => {
  const server = {
    getManagedApiUrl: async () => "http://127.0.0.1:9999"
  } as ServerManager;
  const config = {
    get<T>(key: string, fallback: T): T {
      return (key === "apiMode" ? "external" : "http://example.test:8000") as T;
    }
  };

  assert.equal(await resolveApiUrl(config, server), "http://example.test:8000");
});

test("resolveApiUrl starts managed server by default", async () => {
  const server = {
    getManagedApiUrl: async () => "http://127.0.0.1:8765"
  } as ServerManager;
  const config = {
    get<T>(_key: string, fallback: T): T {
      return fallback;
    }
  };

  assert.equal(await resolveApiUrl(config, server), "http://127.0.0.1:8765");
});
