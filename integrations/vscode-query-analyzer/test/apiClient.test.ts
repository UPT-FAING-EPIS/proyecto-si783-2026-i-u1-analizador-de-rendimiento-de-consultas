import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAiAnalyzeUrl,
  buildAnalyzePayload,
  buildAnalyzeUrl,
  renderAnalysisHtml
} from "../src/apiClient";
import {
  buildProfileDescription,
  defaultPortForEngine,
  profilesFromConfig,
  upsertProfile
} from "../src/profiles";

test("buildAnalyzeUrl appends the analyzer explain endpoint", () => {
  assert.equal(
    buildAnalyzeUrl("http://localhost:8000/"),
    "http://localhost:8000/api/v1/analyzer/explain"
  );
});

test("buildAiAnalyzeUrl appends the analyzer ai endpoint", () => {
  assert.equal(buildAiAnalyzeUrl("http://localhost:8000/"), "http://localhost:8000/api/v1/analyzer/ai");
});

test("buildAnalyzePayload preserves the selected query and connection", () => {
  const connection = { engine: "postgresql", database: "query_analyzer" };

  assert.deepEqual(buildAnalyzePayload("SELECT 1", connection), {
    connection,
    query: "SELECT 1"
  });
});

test("renderAnalysisHtml escapes API content", () => {
  const html = renderAnalysisHtml({
    success: false,
    engine: "sqlite",
    error: "<script>alert(1)</script>"
  });

  assert.match(html, /Analisis fallido/);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
});

test("renderAnalysisHtml shows AI analysis and readable metrics", () => {
  const html = renderAnalysisHtml({
    success: true,
    engine: "postgresql",
    execution_time_ms: 12.3456,
    plan_summary: "Seq Scan on alumnos",
    ai_analysis: {
      summary: "La consulta hace una lectura secuencial.",
      observations: ["Lee la tabla alumnos."],
      recommendations: ["Crea un indice si filtras por una columna frecuente."],
      suggested_query: "SELECT id, nombres FROM alumnos;"
    },
    metrics: {
      planning_time_ms: 7.288,
      execution_time_ms: 1.065,
      node_count: 1,
      scan_nodes: [
        {
          "Node Type": "Seq Scan",
          "Relation Name": "alumnos",
          "Actual Rows": 31,
          "Actual Total Time": 0.832,
          "Total Cost": 11
        }
      ]
    },
    raw_plan: { Plan: { "Node Type": "Seq Scan" } }
  });

  assert.match(html, /Analisis con IA/);
  assert.match(html, /La consulta hace una lectura secuencial/);
  assert.match(html, /Metricas clave/);
  assert.match(html, /Planning Time Ms/);
  assert.match(html, /Nodos de lectura/);
  assert.match(html, /alumnos/);
  assert.match(html, /Ver datos tecnicos completos/);
});

test("renderAnalysisHtml shows async AI loading state before AI result arrives", () => {
  const html = renderAnalysisHtml({
    success: true,
    engine: "postgresql",
    query: "SELECT 1",
    plan_summary: "Result"
  });

  assert.match(html, /Generando analisis con IA en segundo plano/);
});

test("profilesFromConfig returns sorted named profiles", () => {
  assert.deepEqual(
    profilesFromConfig({
      prod: { engine: "postgresql", database: "query_analyzer" },
      local: { engine: "sqlite", database: ":memory:" }
    }),
    [
      { name: "local", connection: { engine: "sqlite", database: ":memory:" } },
      { name: "prod", connection: { engine: "postgresql", database: "query_analyzer" } }
    ]
  );
});

test("upsertProfile preserves existing profiles", () => {
  assert.deepEqual(
    upsertProfile(
      { local: { engine: "sqlite", database: ":memory:" } },
      { name: "pg", connection: { engine: "postgresql", database: "query_analyzer" } }
    ),
    {
      local: { engine: "sqlite", database: ":memory:" },
      pg: { engine: "postgresql", database: "query_analyzer" }
    }
  );
});

test("defaultPortForEngine knows common engines", () => {
  assert.equal(defaultPortForEngine("postgresql"), 5432);
  assert.equal(defaultPortForEngine("sqlite"), undefined);
});

test("buildProfileDescription summarizes the connection", () => {
  assert.equal(
    buildProfileDescription({
      name: "pg",
      connection: {
        engine: "postgresql",
        host: "localhost",
        port: 5432,
        database: "query_analyzer"
      }
    }),
    "postgresql - localhost:5432 - query_analyzer"
  );
});
