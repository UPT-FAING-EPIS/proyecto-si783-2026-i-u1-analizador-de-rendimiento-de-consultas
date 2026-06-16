# Extension VS Code

La extension `Query Analyzer` se distribuye como VSIX especifico por plataforma
y tambien se puede publicar en Visual Studio Marketplace.

## Instalacion por usuario

Desde Marketplace:

1. Abre VS Code.
2. Ve a Extensions.
3. Busca `Query Analyzer`.
4. Instala la extension del publisher `andre-carbajal`.

Desde GitHub Releases:

```bash
code --install-extension query-analyzer-linux-x64.vsix
```

Usa el VSIX de tu plataforma:

- `query-analyzer-linux-x64.vsix`
- `query-analyzer-darwin-arm64.vsix`
- `query-analyzer-win32-x64.vsix`

La extension incluye el binario `qa` y levanta la API local en segundo plano. El
usuario no necesita instalar Python, `uv`, ni ejecutar `uv run qa-api`.

## Modo API externo

Para desarrollo o entornos donde la API se administra por separado:

```json
{
  "queryAnalyzer.apiMode": "external",
  "queryAnalyzer.apiUrl": "http://localhost:8000"
}
```

En ese modo, levanta la API manualmente:

```bash
uv run qa-api
```

## Publicacion automatica

El workflow `.github/workflows/release.yml` genera VSIX por plataforma en cada
tag `v*`, los adjunta al GitHub Release y publica en Marketplace si existe el
secret `VSCE_PAT`.

Pasos para habilitar Marketplace:

1. Confirmar el publisher `andre-carbajal` en Visual Studio Marketplace.
2. Mantener `"publisher": "andre-carbajal"` en `integrations/vscode-query-analyzer/package.json`.
3. Crear un Personal Access Token compatible con `vsce`.
4. Guardarlo en GitHub Actions como secret `VSCE_PAT`.
5. Publicar un tag `v*`.

Si `VSCE_PAT` no existe, el release no falla por Marketplace; solo publica los
VSIX en GitHub Releases.
