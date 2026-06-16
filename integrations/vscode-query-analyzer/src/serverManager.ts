import { spawn, ChildProcessWithoutNullStreams } from "node:child_process";
import * as fs from "node:fs";
import * as net from "node:net";
import * as path from "node:path";

export type ApiMode = "managed" | "external";
export type SupportedTarget = "win32-x64" | "linux-x64" | "darwin-arm64";

export interface OutputChannelLike {
  appendLine(value: string): void;
}

export interface ApiConfigurationLike {
  get<T>(section: string, defaultValue: T): T;
}

const READY_TIMEOUT_MS = 15_000;
const READY_INTERVAL_MS = 250;

export class ServerManager {
  private process: ChildProcessWithoutNullStreams | undefined;
  private apiUrl: string | undefined;

  constructor(
    private readonly extensionPath: string,
    private readonly output: OutputChannelLike,
    private readonly fetchImpl: typeof fetch = fetch
  ) {}

  async getManagedApiUrl(): Promise<string> {
    if (this.process && this.apiUrl && !this.process.killed) {
      return this.apiUrl;
    }

    const executablePath = resolveBundledExecutablePath(this.extensionPath);
    const port = await findAvailablePort();
    const apiUrl = `http://127.0.0.1:${port}`;

    this.output.appendLine(`Starting Query Analyzer API: ${executablePath} api --port ${port}`);
    this.process = spawn(executablePath, ["api", "--host", "127.0.0.1", "--port", String(port)], {
      cwd: this.extensionPath,
      windowsHide: true
    });
    this.apiUrl = apiUrl;

    this.process.stdout.on("data", (chunk: Buffer) => {
      this.output.appendLine(`[qa-api] ${chunk.toString().trimEnd()}`);
    });
    this.process.stderr.on("data", (chunk: Buffer) => {
      this.output.appendLine(`[qa-api] ${chunk.toString().trimEnd()}`);
    });
    this.process.once("exit", (code, signal) => {
      this.output.appendLine(`Query Analyzer API exited with code=${code ?? "-"} signal=${signal ?? "-"}.`);
      this.process = undefined;
      this.apiUrl = undefined;
    });

    try {
      await waitForReadiness(apiUrl, this.fetchImpl);
      return apiUrl;
    } catch (error) {
      this.dispose();
      throw error;
    }
  }

  dispose(): void {
    if (this.process && !this.process.killed) {
      this.output.appendLine("Stopping Query Analyzer API.");
      this.process.kill();
    }
    this.process = undefined;
    this.apiUrl = undefined;
  }
}

export async function resolveApiUrl(
  config: ApiConfigurationLike,
  serverManager: ServerManager
): Promise<string> {
  const mode = config.get<ApiMode>("apiMode", "managed");
  if (mode === "external") {
    return config.get<string>("apiUrl", "http://localhost:8000");
  }

  return serverManager.getManagedApiUrl();
}

export function resolveTargetPlatform(
  platform: NodeJS.Platform = process.platform,
  arch: string = process.arch
): SupportedTarget | undefined {
  if (platform === "win32" && arch === "x64") {
    return "win32-x64";
  }
  if (platform === "linux" && arch === "x64") {
    return "linux-x64";
  }
  if (platform === "darwin" && arch === "arm64") {
    return "darwin-arm64";
  }
  return undefined;
}

export function resolveBundledExecutablePath(extensionPath: string): string {
  const target = resolveTargetPlatform();
  if (!target) {
    throw new Error(
      `Managed Query Analyzer API is not bundled for ${process.platform}-${process.arch}. ` +
        "Set queryAnalyzer.apiMode to external and configure queryAnalyzer.apiUrl."
    );
  }

  const executablePath = buildBundledExecutablePath(extensionPath, target);
  if (!fs.existsSync(executablePath)) {
    throw new Error(
      `Bundled Query Analyzer executable was not found at ${executablePath}. ` +
        "Install the platform-specific VSIX or set queryAnalyzer.apiMode to external."
    );
  }

  return executablePath;
}

export function buildBundledExecutablePath(extensionPath: string, target: SupportedTarget): string {
  const executableName = target.startsWith("win32") ? "qa.exe" : "qa";
  return path.join(extensionPath, "bin", executableName);
}

export async function findAvailablePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => {
        if (typeof address === "object" && address) {
          resolve(address.port);
        } else {
          reject(new Error("Could not allocate a local port for Query Analyzer API."));
        }
      });
    });
  });
}

async function waitForReadiness(apiUrl: string, fetchImpl: typeof fetch): Promise<void> {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  let lastError: unknown;

  while (Date.now() < deadline) {
    try {
      const response = await fetchImpl(`${apiUrl}/openapi.json`);
      if (response.ok) {
        return;
      }
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }

    await sleep(READY_INTERVAL_MS);
  }

  const message = lastError instanceof Error ? lastError.message : String(lastError ?? "timeout");
  throw new Error(`Query Analyzer API did not become ready at ${apiUrl}: ${message}`);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
