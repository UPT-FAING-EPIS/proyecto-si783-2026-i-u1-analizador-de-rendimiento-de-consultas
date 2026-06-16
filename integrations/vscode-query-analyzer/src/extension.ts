import * as vscode from "vscode";

import {
  ConnectionPayload,
  buildAnalyzePayload,
  postAnalyze,
  postAiAnalyze,
  renderAnalysisHtml
} from "./apiClient";
import {
  ProfilesConfig,
  SUPPORTED_ENGINES,
  QueryAnalyzerProfile,
  buildProfileDescription,
  defaultPortForEngine,
  profilesFromConfig,
  upsertProfile
} from "./profiles";
import { resolveApiUrl, ServerManager } from "./serverManager";

const PASSWORD_PREFIX = "queryAnalyzer.profilePassword.";
let serverManager: ServerManager | undefined;

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel("Query Analyzer");
  serverManager = new ServerManager(context.extensionPath, output);

  const disposable = vscode.commands.registerCommand("query-analyzer.analyze", async () => {
    const editor = vscode.window.activeTextEditor;
    const selectedText = editor?.document.getText(editor.selection).trim();

    if (!selectedText) {
      vscode.window.showWarningMessage("Select a SQL query before running Query Analyzer.");
      return;
    }

    const config = vscode.workspace.getConfiguration("queryAnalyzer");
    const profile = await selectProfile(config, context);

    if (!profile) {
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      "queryAnalyzerResults",
      "Query Analyzer",
      vscode.ViewColumn.Beside,
      { enableScripts: false }
    );

    panel.webview.html = renderAnalysisHtml({
      success: true,
      plan_summary: "Analyzing selected query..."
    });

    try {
      const apiUrl = await resolveApiUrl(config, serverManager!);
      const result = await postAnalyze(
        apiUrl,
        buildAnalyzePayload(selectedText, profile.connection)
      );
      panel.webview.html = renderAnalysisHtml(result);

      if (result.success && (result.raw_plan || result.plan_summary) && result.engine) {
        void renderAiAnalysisWhenReady(panel, apiUrl, result);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      panel.webview.html = renderAnalysisHtml({
        success: false,
        error: `Could not start or reach Query Analyzer API: ${message}`
      });
      output.show(true);
    }
  });

  context.subscriptions.push(disposable, output, { dispose: () => serverManager?.dispose() });
}

export function deactivate(): void {
  serverManager?.dispose();
}

async function renderAiAnalysisWhenReady(
  panel: vscode.WebviewPanel,
  apiUrl: string,
  result: Awaited<ReturnType<typeof postAnalyze>>
): Promise<void> {
  try {
    const aiResult = await postAiAnalyze(apiUrl, {
      plan_json: result.raw_plan ?? result.plan_summary ?? "No plan available",
      query: result.query ?? "",
      engine: result.engine ?? ""
    });

    panel.webview.html = renderAnalysisHtml({
      ...result,
      ai_analysis: aiResult.success
        ? {
            summary: aiResult.summary,
            observations: aiResult.observations ?? [],
            recommendations: aiResult.recommendations ?? [],
            suggested_query: aiResult.suggested_query ?? null,
            raw_response: aiResult.raw_response ?? null
          }
        : null
    });
  } catch {
    panel.webview.html = renderAnalysisHtml({
      ...result,
      ai_analysis: null
    });
  }
}

async function selectProfile(
  config: vscode.WorkspaceConfiguration,
  context: vscode.ExtensionContext
): Promise<QueryAnalyzerProfile | undefined> {
  const configuredProfiles = config.get<ProfilesConfig>("profiles", {});
  const profiles = await withStoredPasswords(profilesFromConfig(configuredProfiles), context);

  if (profiles.length === 0) {
    const create = "Create Query Analyzer profile";
    const selected = await vscode.window.showInformationMessage(
      "No Query Analyzer profiles configured.",
      create
    );
    return selected === create ? createProfile(config, context, configuredProfiles) : undefined;
  }

  const defaultProfile = config.get<string>("defaultProfile", "");
  const createLabel = "$(add) Create new profile";
  const items = [
    ...profiles.map((profile) => ({
      label: profile.name === defaultProfile ? `$(star-full) ${profile.name}` : profile.name,
      description: buildProfileDescription(profile),
      profile
    })),
    {
      label: createLabel,
      description: "Add a database connection profile",
      profile: undefined
    }
  ];

  const selected = await vscode.window.showQuickPick(items, {
    placeHolder: "Choose the Query Analyzer profile for this analysis"
  });

  if (!selected) {
    return undefined;
  }

  if (!selected.profile) {
    return createProfile(config, context, configuredProfiles);
  }

  return selected.profile;
}

async function withStoredPasswords(
  profiles: QueryAnalyzerProfile[],
  context: vscode.ExtensionContext
): Promise<QueryAnalyzerProfile[]> {
  const resolved: QueryAnalyzerProfile[] = [];

  for (const profile of profiles) {
    const password = await context.secrets.get(`${PASSWORD_PREFIX}${profile.name}`);
    resolved.push({
      ...profile,
      connection: password ? { ...profile.connection, password } : profile.connection
    });
  }

  return resolved;
}

async function createProfile(
  config: vscode.WorkspaceConfiguration,
  context: vscode.ExtensionContext,
  configuredProfiles: ProfilesConfig
): Promise<QueryAnalyzerProfile | undefined> {
  const name = await vscode.window.showInputBox({
    title: "Query Analyzer Profile",
    prompt: "Profile name",
    validateInput: (value) => {
      if (!value.trim()) {
        return "Profile name is required.";
      }
      if (configuredProfiles[value.trim()]) {
        return "A profile with this name already exists.";
      }
      return undefined;
    }
  });

  if (!name) {
    return undefined;
  }

  const engine = await vscode.window.showQuickPick([...SUPPORTED_ENGINES], {
    title: "Query Analyzer Profile",
    placeHolder: "Database engine"
  });

  if (!engine) {
    return undefined;
  }

  const database = await vscode.window.showInputBox({
    title: "Query Analyzer Profile",
    prompt: engine === "sqlite" ? "SQLite database path or :memory:" : "Database name",
    value: engine === "sqlite" ? ":memory:" : ""
  });

  if (database === undefined) {
    return undefined;
  }

  const connection: ConnectionPayload = {
    engine,
    database
  };

  if (engine !== "sqlite") {
    const host = await vscode.window.showInputBox({
      title: "Query Analyzer Profile",
      prompt: "Host",
      value: "localhost"
    });

    if (host === undefined) {
      return undefined;
    }

    const defaultPort = defaultPortForEngine(engine);
    const port = await vscode.window.showInputBox({
      title: "Query Analyzer Profile",
      prompt: "Port",
      value: defaultPort ? String(defaultPort) : "",
      validateInput: (value) => {
        if (!value.trim()) {
          return undefined;
        }
        const parsed = Number(value);
        return Number.isInteger(parsed) && parsed > 0 && parsed <= 65535
          ? undefined
          : "Port must be a number between 1 and 65535.";
      }
    });

    if (port === undefined) {
      return undefined;
    }

    const username = await vscode.window.showInputBox({
      title: "Query Analyzer Profile",
      prompt: "Username (optional)"
    });

    if (username === undefined) {
      return undefined;
    }

    const password = await vscode.window.showInputBox({
      title: "Query Analyzer Profile",
      prompt: "Password (optional, stored in VS Code SecretStorage)",
      password: true
    });

    if (password === undefined) {
      return undefined;
    }

    connection.host = host;
    if (port.trim()) {
      connection.port = Number(port);
    }
    if (username.trim()) {
      connection.username = username;
    }
    if (password) {
      await context.secrets.store(`${PASSWORD_PREFIX}${name.trim()}`, password);
      connection.password = password;
    }
  }

  const profile = {
    name: name.trim(),
    connection
  };
  const target = vscode.workspace.workspaceFolders
    ? vscode.ConfigurationTarget.Workspace
    : vscode.ConfigurationTarget.Global;

  await config.update("profiles", upsertProfile(configuredProfiles, profile), target);
  await config.update("defaultProfile", profile.name, target);

  vscode.window.showInformationMessage(`Query Analyzer profile '${profile.name}' created.`);
  return profile;
}
