# Query Analyzer

Analyze selected SQL directly from Visual Studio Code.

## Usage

1. Select a SQL query in the editor.
2. Right-click and choose **Query Analyzer: Analizar Rendimiento**.
3. Choose or create a database profile.
4. Review the factual execution plan immediately; AI analysis appears later when `QA_AI_*` is configured.

By default, the extension starts the bundled Query Analyzer API automatically. You do not need to run
`uv run qa-api` when installing the platform-specific VSIX from a release or from the Marketplace.

## External API Mode

For development or remote API usage, set:

```json
{
  "queryAnalyzer.apiMode": "external",
  "queryAnalyzer.apiUrl": "http://localhost:8000"
}
```

Then start the API manually with:

```bash
uv run qa-api
```

## Install from VSIX

Download the VSIX that matches your operating system from the project release and install it:

```bash
code --install-extension query-analyzer-*.vsix
```
