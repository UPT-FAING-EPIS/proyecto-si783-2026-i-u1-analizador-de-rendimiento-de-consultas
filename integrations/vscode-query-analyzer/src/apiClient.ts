export type ConnectionPayload = Record<string, unknown>;

export interface AnalyzePayload {
  connection: ConnectionPayload;
  query: string;
}

export interface AIAnalyzePayload {
  plan_json: unknown;
  query: string;
  engine: string;
}

export interface AnalyzeResponse {
  success: boolean;
  engine?: string;
  query?: string;
  execution_time_ms?: number | null;
  plan_summary?: string | null;
  ai_analysis?: AIAnalysis | null;
  metrics?: Record<string, unknown>;
  raw_plan?: unknown;
  error?: string | null;
}

export interface AIAnalyzeResponse extends AIAnalysis {
  success: boolean;
  error?: string | null;
}

export interface AIAnalysis {
  summary: string;
  observations?: string[];
  recommendations?: string[];
  suggested_query?: string | null;
  raw_response?: string | null;
}

export function buildAnalyzeUrl(baseUrl: string): string {
  const normalized = baseUrl.trim().replace(/\/+$/, "");
  return `${normalized}/api/v1/analyzer/explain`;
}

export function buildAiAnalyzeUrl(baseUrl: string): string {
  const normalized = baseUrl.trim().replace(/\/+$/, "");
  return `${normalized}/api/v1/analyzer/ai`;
}

export function buildAnalyzePayload(query: string, connection: ConnectionPayload): AnalyzePayload {
  return {
    connection,
    query
  };
}

export async function postAnalyze(
  baseUrl: string,
  payload: AnalyzePayload,
  fetchImpl: typeof fetch = fetch
): Promise<AnalyzeResponse> {
  const response = await fetchImpl(buildAnalyzeUrl(baseUrl), {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  const body = (await response.json()) as AnalyzeResponse;
  if (!response.ok) {
    return {
      success: false,
      error: body.error ?? `HTTP ${response.status}`
    };
  }

  return body;
}

export async function postAiAnalyze(
  baseUrl: string,
  payload: AIAnalyzePayload,
  fetchImpl: typeof fetch = fetch
): Promise<AIAnalyzeResponse> {
  const response = await fetchImpl(buildAiAnalyzeUrl(baseUrl), {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  const body = (await response.json()) as AIAnalyzeResponse;
  if (!response.ok) {
    return {
      success: false,
      summary: "",
      error: body.error ?? `HTTP ${response.status}`
    };
  }

  return body;
}

export function renderAnalysisHtml(result: AnalyzeResponse): string {
  const statusClass = result.success ? "success" : "error";
  const statusText = result.success ? "Analisis completado" : "Analisis fallido";
  const summary = result.plan_summary ?? "No plan summary returned.";
  const error = result.error ? `<section><h2>Error</h2><pre>${escapeHtml(result.error)}</pre></section>` : "";
  const rawDetails = JSON.stringify(
    {
      metrics: result.metrics ?? {},
      raw_plan: result.raw_plan ?? {}
    },
    null,
    2
  );

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { color: var(--vscode-foreground); font-family: var(--vscode-font-family); padding: 20px; }
    h1, h2, h3 { font-weight: 600; }
    h1 { margin-top: 0; }
    section { margin: 22px 0; }
    .status { border-left: 4px solid; padding: 8px 12px; margin-bottom: 16px; }
    .success { border-color: var(--vscode-testing-iconPassed); }
    .error { border-color: var(--vscode-testing-iconFailed); }
    .muted { color: var(--vscode-descriptionForeground); }
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; }
    .metric { background: var(--vscode-textCodeBlock-background); border: 1px solid var(--vscode-panel-border); padding: 10px; }
    .metric-label { color: var(--vscode-descriptionForeground); font-size: 12px; }
    .metric-value { font-size: 18px; margin-top: 4px; }
    ul { padding-left: 20px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid var(--vscode-panel-border); padding: 6px; text-align: left; }
    th { color: var(--vscode-descriptionForeground); font-weight: 600; }
    pre { background: var(--vscode-textCodeBlock-background); overflow: auto; padding: 12px; white-space: pre-wrap; }
    code { font-family: var(--vscode-editor-font-family); }
    details { background: var(--vscode-textCodeBlock-background); padding: 10px 12px; }
    summary { cursor: pointer; font-weight: 600; }
  </style>
  <title>Query Analyzer</title>
</head>
<body>
  <h1>Query Analyzer</h1>
  <div class="status ${statusClass}">
    <strong>${statusText}</strong>
    <div>${escapeHtml(result.engine ?? "unknown engine")}</div>
    <div>${formatExecutionTime(result.execution_time_ms)}</div>
  </div>
  ${error}
  ${renderAiAnalysis(result)}
  <section>
    <h2>Plan Summary</h2>
    <pre>${escapeHtml(summary)}</pre>
  </section>
  ${renderMetrics(result.metrics ?? {})}
  ${renderScanNodes(result.metrics ?? {})}
  <section>
    <details>
      <summary>Ver datos tecnicos completos</summary>
      <pre><code>${escapeHtml(rawDetails)}</code></pre>
    </details>
  </section>
</body>
</html>`;
}

function formatExecutionTime(value: number | null | undefined): string {
  return typeof value === "number" ? `${value.toFixed(2)} ms` : "No execution time returned";
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderAiAnalysis(result: AnalyzeResponse): string {
  if (result.success && result.ai_analysis === undefined) {
    return `<section>
      <h2>Analisis con IA</h2>
      <p class="muted">Generando analisis con IA en segundo plano...</p>
    </section>`;
  }

  if (result.ai_analysis === null) {
    return `<section>
      <h2>Analisis con IA</h2>
      <p class="muted">No hay analisis de IA disponible para este resultado.</p>
    </section>`;
  }

  if (!result.ai_analysis) {
    return "";
  }

  const observations = renderList(result.ai_analysis.observations ?? []);
  const recommendations = renderList(result.ai_analysis.recommendations ?? []);
  const suggestedQuery = result.ai_analysis.suggested_query
    ? `<h3>Consulta sugerida</h3><pre><code>${escapeHtml(result.ai_analysis.suggested_query)}</code></pre>`
    : "";

  return `<section>
    <h2>Analisis con IA</h2>
    <p>${escapeHtml(result.ai_analysis.summary)}</p>
    ${observations ? `<h3>Observaciones</h3>${observations}` : ""}
    ${recommendations ? `<h3>Recomendaciones</h3>${recommendations}` : ""}
    ${suggestedQuery}
  </section>`;
}

function renderList(items: string[]): string {
  if (!items.length) {
    return "";
  }

  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderMetrics(metrics: Record<string, unknown>): string {
  const scalarMetrics = Object.entries(metrics).filter(([, value]) => isScalar(value));

  if (!scalarMetrics.length) {
    return `<section><h2>Metricas</h2><p class="muted">No se devolvieron metricas.</p></section>`;
  }

  return `<section>
    <h2>Metricas clave</h2>
    <div class="metric-grid">
      ${scalarMetrics
        .map(
          ([key, value]) => `<div class="metric">
            <div class="metric-label">${escapeHtml(formatMetricLabel(key))}</div>
            <div class="metric-value">${escapeHtml(formatMetricValue(value))}</div>
          </div>`
        )
        .join("")}
    </div>
  </section>`;
}

function renderScanNodes(metrics: Record<string, unknown>): string {
  const scanNodes = Array.isArray(metrics.scan_nodes) ? metrics.scan_nodes : [];
  const rows = scanNodes.filter((node): node is Record<string, unknown> => isRecord(node));

  if (!rows.length) {
    return "";
  }

  return `<section>
    <h2>Nodos de lectura</h2>
    <table>
      <thead>
        <tr>
          <th>Tipo</th>
          <th>Relacion</th>
          <th>Filas</th>
          <th>Tiempo</th>
          <th>Costo</th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map(
            (node) => `<tr>
              <td>${escapeHtml(String(node["Node Type"] ?? node.type ?? "-"))}</td>
              <td>${escapeHtml(String(node["Relation Name"] ?? node.relation ?? "-"))}</td>
              <td>${escapeHtml(String(node["Actual Rows"] ?? node.actual_rows ?? "-"))}</td>
              <td>${escapeHtml(String(node["Actual Total Time"] ?? node.actual_time ?? "-"))}</td>
              <td>${escapeHtml(String(node["Total Cost"] ?? node.cost ?? "-"))}</td>
            </tr>`
          )
          .join("")}
      </tbody>
    </table>
  </section>`;
}

function isScalar(value: unknown): boolean {
  return ["string", "number", "boolean"].includes(typeof value) || value === null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatMetricLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatMetricValue(value: unknown): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }

  return String(value);
}
