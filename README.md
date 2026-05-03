# Query Analyzer

[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue)](https://www.python.org/)
[![uv](https://img.shields.io/badge/Package%20Manager-uv-orange)](https://github.com/astral-sh/uv)

Analizador de rendimiento de consultas para SQL, NoSQL y TimeSeries con interfaz TUI en terminal.

## Que puedes hacer

- Analizar planes de ejecucion y detectar anti-patrones de rendimiento.
- Trabajar con multiples motores desde una sola herramienta CLI/TUI.
- Obtener recomendaciones de optimizacion orientadas al motor.

## Motores soportados

### SQL

- PostgreSQL
- MySQL
- SQLite
- CockroachDB
- YugabyteDB

### NoSQL

- MongoDB
- DynamoDB

### TimeSeries y grafos

- InfluxDB
- Neo4j

Para detalles de DynamoDB, revisa `docs/adapters/DYNAMODB.md`.

## Instalacion

La forma recomendada es instalar por package manager (Homebrew, Scoop o Snap). Como alternativa, puedes
instalar con binarios de GitHub Releases o ejecutar desde codigo fuente.

### Opcion A (recomendada): Instalacion por package manager

Cada release `v*` publica automaticamente el paquete `qa` via JReleaser.

#### Homebrew (macOS/Linux)

```bash
brew tap andre-carbajal/tap
brew install qa
qa --help
```

#### Scoop (Windows)

```powershell
scoop bucket add andre https://github.com/andre-carbajal/scoop-bucket.git
scoop install qa
qa --help
```

#### Snap (Linux)

```bash
sudo snap install qa
qa --help
```

### Opcion B: Instalar binario desde GitHub Releases

En cada tag `v*` se publican estos artefactos:

- `qa-linux-amd64.tar.gz`
- `qa-linux-arm64.tar.gz`
- `qa-macos-arm64.zip`
- `qa-windows-amd64.zip`

#### Linux (amd64/arm64)

```bash
tar -xzf qa-linux-amd64.tar.gz
chmod +x bin/qa
sudo mv bin/qa /usr/local/bin/qa
qa --help
```

Para ARM64, reemplaza el archivo por `qa-linux-arm64.tar.gz`.

#### macOS (arm64)

```bash
unzip qa-macos-arm64.zip
chmod +x bin/qa
sudo mv bin/qa /usr/local/bin/qa
qa --help
```

#### Windows (amd64)

1. Descomprime `qa-windows-amd64.zip`.
2. Ubica `qa.exe` dentro de `qa-<version>/bin/`.
3. Agrega esa carpeta al `PATH` o ejecuta el binario directamente.

PowerShell (ejecucion directa):

```powershell
.\qa-0.1.0\bin\qa.exe --help
```

### Opcion C: Ejecutar desde codigo fuente

Requisitos:

- Python 3.14+
- uv

```bash
git clone https://github.com/UPT-FAING-EPIS/proyecto-si783-2026-i-u1-analizador-de-rendimiento-de-consultas.git
cd proyecto-si783-2026-i-u1-analizador-de-rendimiento-de-consultas
uv sync
uv run query_analyzer
```

Tambien puedes usar:

```bash
python -m query_analyzer
```

## Canales de distribucion

El pipeline de release publica automaticamente en estos canales:

- Homebrew Tap: `andre-carbajal/tap`
- Scoop Bucket: `andre` (`https://github.com/andre-carbajal/scoop-bucket`)
- Snapcraft: paquete `qa`

## Uso rapido

```bash
qa --help
```

Si lo ejecutas desde fuente:

```bash
uv run query_analyzer --help
```

## Entorno opcional con Docker

Si quieres levantar servicios de base de datos locales para pruebas:

```bash
cp .env.example .env
make up
make health
```

Servicios incluidos: PostgreSQL, MySQL, MongoDB, Redis, InfluxDB, Neo4j y CockroachDB.

Para apagar:

```bash
make down
```

## Releases

El workflow `.github/workflows/release.yml` se ejecuta automaticamente cuando haces push de un tag `v*`.

- Construye binarios por plataforma con PyInstaller.
- Publica artefactos de release.
- Publica y actualiza package managers via JReleaser.

Comandos de instalacion por canal:

```bash
# Homebrew
brew tap andre-carbajal/tap
brew install qa
```

```bash
# Snap
sudo snap install qa
```

```powershell
# Scoop
scoop bucket add andre https://github.com/andre-carbajal/scoop-bucket.git
scoop install qa
```

## Para desarrolladores

Si quieres contribuir, revisa `CONTRIBUTING.md` para setup, pruebas, estilo de codigo y flujo de PRs.
