<center>

![./media/logo-upt.png](./media/logo-upt.png)

**UNIVERSIDAD PRIVADA DE TACNA**

**FACULTAD DE INGENIERÍA**

**Escuela Profesional de Ingeniería de Sistemas**

**Proyecto *Analizador de Rendimiento de Consultas***

Curso: *Base de Datos II*

Docente: *Mag. Patrick Cuadros Quiroga*

Integrantes:

***Carbajal Vargas, Andre Alejandro (2023077287)***

***Yupa Gómez, Fátima Sofía (2023076618)***

**Tacna – Perú**

***2026***

</center>

---

| CONTROL DE VERSIONES | | | | | |
|:---:|:---|:---|:---|:---|:---|
| Versión | Hecha por | Revisada por | Aprobada por | Fecha | Motivo |
| 1.0 | Andre Carbajal Vargas, Fátima Yupa Gómez | Patrick Cuadros Quiroga | Patrick Cuadros Quiroga | 2026-04 | Versión Original |

---

**Sistema *Query Performance Analyzer***

**Documento de Visión**

**Versión *1.0***

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## ÍNDICE GENERAL

1. [Introducción](#1-introducción)
   - 1.1 Propósito
   - 1.2 Alcance
   - 1.3 Definiciones, Siglas y Abreviaturas
   - 1.4 Referencias
   - 1.5 Visión General

2. [Posicionamiento](#2-posicionamiento)
   - 2.1 Oportunidad de negocio
   - 2.2 Definición del problema

3. [Descripción de Interesados y Usuarios](#3-descripción-de-interesados-y-usuarios)
   - 3.1 Resumen de los interesados
   - 3.2 Resumen de los usuarios
   - 3.3 Entorno de usuario
   - 3.4 Perfiles de los interesados
   - 3.5 Perfiles de los usuarios
   - 3.6 Necesidades de los interesados y usuarios

4. [Vista General del Producto](#4-vista-general-del-producto)
   - 4.1 Perspectiva del producto
   - 4.2 Resumen de capacidades
   - 4.3 Suposiciones y dependencias
   - 4.4 Costos y precios
   - 4.5 Licenciamiento e instalación

5. [Características del Producto](#5-características-del-producto)

6. [Restricciones](#6-restricciones)

7. [Rangos de Calidad](#7-rangos-de-calidad)

8. [Precedencia y Prioridad](#8-precedencia-y-prioridad)

9. [Otros Requerimientos del Producto](#9-otros-requerimientos-del-producto)

[Conclusiones](#conclusiones)

[Recomendaciones](#recomendaciones)

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## 1. Introducción

### 1.1 Propósito

Este documento presenta la **visión estratégica** del **Query Performance Analyzer**, una herramienta de software de código abierto orientada a desarrolladores y administradores de bases de datos. El propósito es establecer un entendimiento compartido de los objetivos, características, restricciones y estándares de calidad del proyecto entre todos los interesados.

### 1.2 Alcance

El proyecto abarca el desarrollo de una herramienta unificada que:

- **Soporta 13 motores de bases de datos:** PostgreSQL, MySQL, SQLite, MongoDB, Redis, Neo4j, InfluxDB, CockroachDB, YugabyteDB, TimescaleDB, DynamoDB, Cassandra y Elasticsearch.
- **Se entrega en dos modalidades:** CLI (Command Line Interface) mediante `qa analyze` y TUI (Terminal User Interface) interactiva con editor de queries, visualizador de plan de ejecución e historial.
- **Se implementa en 33 issues distribuidos en 5 milestones (v0–v4)** durante ~16 semanas de desarrollo.
- **Funciona completamente offline** sin dependencias de servicios en la nube ni datos que salgan de la máquina del usuario.

**No está en el alcance:**
- Soporte a motores no listados sin una contribución de la comunidad.
- Modificación automática de estructuras de base de datos (solo análisis y recomendaciones).
- Herramientas visuales avanzadas (el proyecto es estrictamente terminal).

### 1.3 Definiciones, Siglas y Abreviaturas

| Término | Definición |
|---------|-----------|
| **TUI** | Terminal User Interface — Interfaz de usuario completamente en terminal |
| **CLI** | Command Line Interface — Interfaz de línea de comandos |
| **EXPLAIN** | Comando SQL para obtener el plan de ejecución de una query |
| **Seq Scan** | Sequential Scan — Escaneo secuencial de todos los registros de una tabla (ineficiente) |
| **Index Scan** | Escaneo de tabla usando un índice (eficiente) |
| **Anti-patrón** | Patrón de query reconocidamente subóptimo (full table scan, nested loop costoso, etc.) |
| **BaseAdapter** | Clase abstracta que define el contrato común de todos los drivers de motores |
| **QueryAnalysisReport** | Estructura de datos que normaliza el resultado del análisis independiente del motor |
| **Plan de ejecución** | Árbol de operaciones que el motor ejecuta para resolver una query |
| **DBA** | Database Administrator — Administrador de base de datos |
| **Scoring (0–100)** | Métrica de calidad de la query donde 100 es óptimo |

### 1.4 Referencias

- **BACKLOG.md:** Roadmap detallado con 33 issues, milestones v0–v4 y criterios de aceptación medibles.
- **FD01-Informe-Factibilidad.md:** Análisis técnico, económico, legal, social y ambiental del proyecto.
- **Documentación oficial de motores:** PostgreSQL EXPLAIN, MySQL EXPLAIN FORMAT=JSON, MongoDB executionStats, etc.
- **Stack tecnológico:** Documentación de Textual, Rich, Typer, Pydantic, pytest, Docker.

### 1.5 Visión General

**Declaración de visión:** *"Query Performance Analyzer es una herramienta unificada, gratuita y de código abierto que automatiza el análisis de rendimiento de consultas en múltiples motores de bases de datos, eliminando la fragmentación actual de herramientas especializadas y proporcionando recomendaciones concretas y accionables en menos de 1 minuto por consulta."*

**Diferenciadores clave:**
- Una única interfaz para 13 motores (vs 13 herramientas diferentes actualmente).
- Recomendaciones con SQL/comandos exactos listos para copiar y ejecutar.
- Historial persistente para medir el impacto objetivo de optimizaciones.
- Completamente offline y sin dependencias de cloud o suscripciones.
- Arquitectura extensible que invita contribuciones de la comunidad.

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## 2. Posicionamiento

### 2.1 Oportunidad de Negocio

**Situación del mercado:**
- Estudios de la industria (Percona, 2023) indican que más del 60% de problemas de rendimiento en aplicaciones web tienen origen en consultas de base de datos subóptimas.
- El mercado de herramientas de optimización de bases de datos incluye soluciones comerciales ($69–$500/año por usuario): DataGrip, pgAdmin Pro, MySQL Workbench Pro, TablePlus, Redgate Monitor.
- No existe una herramienta unificada, de código abierto y orientada a terminal que cubra múltiples motores.

**Oportunidad:**
- Demanda de desarrolladores y pequeñas/medianas empresas que necesitan análisis de rendimiento sin inversión en licencias comerciales.
- Mercado de startups y proyectos open source que requieren herramientas gratuitas.
- Educación: herramienta que simultáneamente diagnostica y enseña conceptos de internals de bases de datos.

**Ventaja competitiva:**
- Gratuito vs $250–$500/año de alternativas comerciales.
- Multi-motor en una interfaz vs especialización en un solo motor.
- Funcionamiento offline vs dependencia de cloud.

### 2.2 Definición del Problema

**Problema actual:**
Un desarrollador que trabaja con múltiples motores de bases de datos enfrenta un proceso manual ineficiente cada vez que necesita diagnosticar una query lenta:

1. **Fragmentación de herramientas:** Debe recordar la sintaxis exacta de `EXPLAIN` para cada motor y su versión específica.
2. **Interpretación manual:** Debe entender formatos heterogéneos: árbol JSON (PostgreSQL), tablas (MySQL), texto con opcodes (SQLite), stages (MongoDB).
3. **Brecha de conocimiento:** Interpretar correctamente requiere conocimiento especializado (qué es un Seq Scan, cuándo el planificador se equivoca, significado de `Using filesort`).
4. **Sin automatización:** No existe detección automática de anti-patrones reconocidos.
5. **Sin trazabilidad:** No hay forma de medir objetivamente el impacto de optimizaciones.

**Síntomas:**
- 30–60 minutos por consulta analizada.
- Alto riesgo de decisiones de optimización erróneas por falta de conocimiento.
- Consultas lentas llegan a producción sin análisis previo.
- Desarrolladores generalistas no disponen de herramientas comparables a las de DBAs especializados.

**Impacto:**
- Incidentes de rendimiento en producción (downtime, experiencia degradada del usuario).
- Costos innecesarios en infraestructura cloud por consultas ineficientes.
- Brecha de conocimiento entre desarrolladores y DBAs.

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## 3. Descripción de Interesados y Usuarios

### 3.1 Resumen de los Interesados

| Interesado | Rol | Interés Principal |
|-----------|-----|-------------------|
| **Desarrollador (estudiante)** | Creador del proyecto | Completar proyecto, adquirir conocimiento profundo en internals de BD, crear portafolio |
| **Docente asesor** | Supervisor académico | Evaluar calidad técnica, originalidad, cumplimiento de requisitos |
| **Comunidad open source** | Usuarios y colaboradores | Disponer de herramienta gratuita, contribuir nuevos drivers |
| **Universidad Privada de Tacna** | Institución académica | Validar que proyecto cumple requisitos, contribuir a formación de estudiantes |

### 3.2 Resumen de los Usuarios

| Segmento | Descripción | Tamaño estimado |
|----------|-------------|-----------------|
| **Desarrolladores de software** | Desarrolladores full-stack, backend engineers que trabajan con múltiples BD | Alto (millones) |
| **DBAs (Administradores de BD)** | Especialistas que administran infraestructura de BD en producción | Medio (miles) |
| **Startups y proyectos open source** | Equipos pequeños sin presupuesto para herramientas comerciales | Alto (miles) |
| **Comunidad académica** | Estudiantes de Ingeniería en Sistemas aprendiendo internals de BD | Medio (miles) |

### 3.3 Entorno de Usuario

- **Máquina local:** Computadora personal o laptop del desarrollador/DBA.
- **Sistema Operativo:** Linux (Ubuntu 22.04+), macOS 13+, Windows 11 (WSL2).
- **Contexto de uso:** Terminal del desarrollador, integrado en flujos de trabajo diarios, potencialmente en pipelines CI/CD.
- **Requisitos:** Python 3.12, acceso a credenciales de BD (proporcionadas por usuario), conexión a internet solo para instalar (después funciona offline).

### 3.4 Perfiles de los Interesados

**Desarrollador (Estudiante):**
- Edad: ~22 años
- Conocimiento: Nivel intermedio–avanzado en Python, bases de datos (curso actual), Git
- Motivación: Completar proyecto académico, aprender internals, crear herramienta útil para comunidad
- Expectativa: Documentación clara, criterios de aceptación medibles, libertad de diseño arquitectónico

**Docente Asesor:**
- Rol: Evaluador, mentor, guía en decisiones técnicas
- Expectativa: Proyecto original, código de calidad profesional, documentación académica rigurosa, contribución al aprendizaje

**Colaborador Open Source (futuro):**
- Motivación: Agregar soporte a motor específico, mejorar feature existente, corrección de bugs
- Expectativa: Proceso de contribución claro (docs/adding-a-driver.md), issue template útil, CI/CD que valide calidad

### 3.5 Perfiles de los Usuarios

**Usuario Principiante:**
- Perfil: Developer junior sin experiencia en optimización de BD
- Objetivo: Aprender qué significa un Seq Scan, por qué es lento, cómo solucionarlo
- Expectativa: Recomendaciones claras en lenguaje natural con SQL concreto

**Usuario Intermedio:**
- Perfil: Developer senior o DBA que quiere optimizar queries de forma sistemática
- Objetivo: Comparar performance antes/después, justificar decisiones de optimización con datos
- Expectativa: Historial persistente, scoring reproducible, exportación de reportes

**Usuario Avanzado:**
- Perfil: DBA en producción o DevOps/SRE que integra en pipelines
- Objetivo: Identificar bulk queries lentas, automatizar detección de anti-patrones en CI/CD
- Expectativa: Soporte para integración programática, export JSON, análisis batch

### 3.6 Necesidades de los Interesados y Usuarios

| Interesado/Usuario | Necesidad | Cómo lo resuelve Query Performance Analyzer |
|---------|-----------|------|
| Developer | Analizar query lenta sin expertise de DBA | Recomendación automática en lenguaje natural |
| DBA | Identificar queries lentas en producción | `get_slow_queries()` + análisis automático |
| Dev junior | Aprender internals de BD | Explicación de anti-patrones + SQL de solución |
| Startup | Herramienta de análisis sin costo | 100% gratuito, open source, sin suscripción |
| DevOps/SRE | Integración en CI/CD | CLI + export JSON para automatización |
| Comunidad | Herramienta extensible | Patrón Adapter + docs contributing |

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## 4. Vista General del Producto

### 4.1 Perspectiva del Producto

El **Query Performance Analyzer** es una aplicación de escritorio/terminal que se ejecuta localmente en la máquina del usuario sin requerir servidor, cloud, ni conexión a internet continua.

**Arquitectura en 4 capas:**

```
┌─────────────────────────────────────────────────┐
│  CAPA DE PRESENTACIÓN (v2, v3)                  │
│  CLI: qa analyze --profile local-postgres "..."│
│  TUI: Editor interactivo + Visualizador de plan│
├─────────────────────────────────────────────────┤
│  CAPA CORE (v1, v2)                             │
│  AntiPatternDetector + RecommendationEngine    │
│  QueryAnalysisReport (normalización)            │
├─────────────────────────────────────────────────┤
│  CAPA ABSTRACCIÓN (v0)                          │
│  BaseAdapter (contrato común)                   │
│  AdapterRegistry (factory de drivers)           │
├─────────────────────────────────────────────────┤
│  CAPA DRIVERS (v1, v2)                          │
│  13 Adapters específicos por motor              │
└─────────────────────────────────────────────────┘
```

**Almacenamiento local:**
- `~/.query-analyzer/config.yaml`: Perfiles de conexión (credenciales del usuario)
- `~/.query-analyzer/history.db`: Historial de análisis (queries ejecutadas, scores, recomendaciones)

**Funcionamiento completamente offline:** Una vez instalado, no requiere conexión a internet ni servicios externos.

### 4.2 Resumen de Capacidades

| Capacidad | Descripción | Milestone |
|----------|-------------|-----------|
| **Análisis de plan de ejecución** | Parsea EXPLAIN de 13 motores, normaliza a árbol común | v1–v2 |
| **Detección de anti-patrones** | Identifica automáticamente 7+ patrones subóptimos | v1 |
| **Recomendaciones accionables** | Genera SQL/comando exacto listo para copiar y ejecutar | v1–v2 |
| **Scoring 0–100** | Métrica reproducible de calidad de query | v1 |
| **Gestión de perfiles** | Guardar múltiples conexiones a diferentes BD | v0 |
| **CLI principal** | Comando `qa analyze` con soporte de output (rich/json/markdown) | v2 |
| **TUI interactiva** | Editor de queries, visualizador de plan, historial | v3 |
| **Historial persistente** | Compara antes/después de optimizaciones | v3 |
| **Panel de queries lentas** | Muestra queries más costosas del motor | v3 |
| **Exportación** | JSON y Markdown para documentación/reportes | v4 |

### 4.3 Suposiciones y Dependencias

**Suposiciones:**
- El usuario tiene Python 3.12+ instalado en su máquina.
- El usuario dispone de credenciales válidas para conectarse a las BD que quiere analizar.
- El proyecto se distribuirá como paquete PyPI, instalable con `pip install query-analyzer`.
- El usuario tiene acceso a `docker` y `docker-compose` para desarrollo local (opcional para usuario final).

**Dependencias técnicas (todas open source):**
- **Python 3.12:** Lenguaje principal
- **Textual 0.47+:** Framework para TUI
- **Rich 13+:** Output enriquecido en terminal
- **Typer 0.9+:** CLI framework
- **Pydantic v2:** Validación de configuración
- **PyYAML:** Parseo de config.yaml
- **psycopg2-binary, pymysql, pymongo, redis-py, etc.:** Drivers específicos por motor
- **pytest, Ruff, Black, mypy:** Testing y calidad de código
- **Docker (desarrollo):** Entorno reproducible con todos los motores

**Dependencias externas (ninguna):** La herramienta NO depende de:
- Servicios cloud (AWS, GCP, Azure)
- APIs externas
- Servidores web o microservicios
- Suscripciones comerciales

### 4.4 Costos y Precios

| Concepto | Costo al usuario final |
|----------|----------------------|
| **Herramienta** | S/. 0 (completamente gratuito) |
| **Distribución (PyPI)** | S/. 0 (PyPI es gratuito) |
| **Soporte/mantenimiento** | S/. 0 (mantenimiento comunitario) |
| **Alternativas comerciales (DataGrip, pgAdmin Pro)** | S/. 250–720/año |
| **Ahorro anual por usuario** | S/. 250–720 |

**Modelo de negocio:** El proyecto es de código abierto, financiado por el tiempo del estudiante como parte de su formación académica. No persigue monetización.

### 4.5 Licenciamiento e Instalación

**Licencia:** MIT (permisiva, permite uso comercial y modificación)

**Compatibilidad de dependencias:**
- 100% de las dependencias tienen licencias open source compatibles con MIT.
- El proyecto puede ser usado sin restricción legal en contextos académicos, comerciales y open source.

**Instalación para usuario final:**
```bash
# Opción 1: pip
pip install query-analyzer

# Opción 2: uv (recomendado)
uv tool install query-analyzer

# Uso inmediato
qa analyze --help
```

**Instalación para desarrolladores:**
```bash
git clone https://github.com/usuario/query-analyzer.git
cd query-analyzer
uv sync
uv run qa --help
```

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## 5. Características del Producto

El proyecto se entrega en **5 milestones con 33 issues progresivos**:

| Milestone | Descripción | Issues | Días | Features entregadas |
|-----------|-------------|--------|------|---------------------|
| **v0 — Setup** | Arquitectura base y entorno | #1–#5 | 4.0 d | Estructura proyecto, BaseAdapter, configuración, Docker, registry |
| **v1 — SQL** | Drivers SQL + core engine | #6–#13 | 13.0 d | PostgreSQL, MySQL, SQLite, anti-patrones, recomendaciones, tests SQL |
| **v2 — NoSQL + CLI** | Drivers NoSQL + comando principal | #14–#22 | 15.5 d | MongoDB, Redis, Neo4j, InfluxDB, DynamoDB, Cassandra, Elasticsearch, `qa analyze` |
| **v3 — TUI** | Interfaz terminal interactiva | #23–#27 | 9.0 d | Editor, visualizador plan, historial, comparación, queries lentas |
| **v4 — Release** | Testing, docs, publicación | #28–#33 | 7.5 d | Tests 80%+, docs, README, release v1.0.0 en PyPI |

**Total: 33 features en ~52 días (~16 semanas a 3–4 h/día)**

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## 6. Restricciones

| Restricción | Descripción | Impacto de mitigación |
|------------|-------------|----------------------|
| **Dedicación parcial** | Estudiante con dedicación de 3–4 h/día; imprevistos académicos pueden extender timeline | Milestones v0–v1 priorizados; v3 (TUI) puede ser reducida sin comprometer funcionalidad core |
| **Heterogeneidad de motores** | Cada motor retorna EXPLAIN en formato distinto; normalización compleja | Parsers encapsulados en cada Adapter; BaseAdapter define solo contrato de salida |
| **Compatibilidad de versiones** | `EXPLAIN` varía entre MySQL 5.7–8.0, InfluxDB 1.x–2.x, etc. | Tests contra versiones LTS; detección de versión en `get_engine_info()` |
| **Motores sin plan formal** | Redis, DynamoDB, Cassandra no tienen EXPLAIN equivalente | Análisis limitado a patrones estáticos; documentación clara del alcance |
| **Alcance de 13 motores** | Profundidad vs amplitud: implementar 13 drivers con mismo nivel es difícil | PostgreSQL, MySQL, MongoDB = "primera clase"; otros = "experimental" en v1.0.0 |
| **Seguridad de credenciales** | Passwords nunca deben aparecer en logs, output, historial | Enmascaramiento en todo output; variables de entorno; sin serialización de config completa |
| **Cambios de API en drivers** | pymongo, neo4j, elasticsearch-py cambian API entre versiones mayores | Versiones fijas en `pyproject.toml`; `uv.lock` para reproducibilidad; tests en CI detectan roturas |

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## 7. Rangos de Calidad

| Atributo de Calidad | Métrica | Target | Herramienta |
|-------------------|--------|--------|------------|
| **Cobertura de tests** | % de código ejecutado por tests | ≥ 80% | pytest-cov |
| **Tipado estático** | Errores de tipo | 0 errores en modo `strict` | mypy |
| **Calidad de código** | Warnings de linter | 0 warnings | Ruff |
| **Formateo consistente** | Estilo de código uniforme | Black (determinista) | Black |
| **Documentación** | Docstrings en módulos públicos | 100% | PEP 257 |
| **Reproducibilidad** | Consistencia de entorno | Idéntico en cualquier máquina | uv.lock |
| **Rendimiento de análisis** | Tiempo para analizar query | < 1 segundo | Benchmarks en CI |
| **Scoring reproducible** | Misma query = mismo score | 100% consistencia | Tests determinísticos |
| **Compatibilidad multiplataforma** | Ejecución en Linux, macOS, Windows (WSL2) | 100% funcional | CI en GitHub Actions |

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## 8. Precedencia y Prioridad

**Secuencia obligatoria (sin excepciones):**
```
v0 (Setup) → v1 (Drivers SQL + Core) → v2 (Drivers NoSQL + CLI) → v3/v4 (TUI + Release)
```

**Priorización dentro de v1 (Drivers SQL):**
1. PostgreSQL (#6) — Motor más documentado, output JSON detallado
2. MySQL (#7) — Motor más usado en producción web
3. SQLite (#8) — Desarrollo offline sin Docker
4. Anti-patrones (#9) — Capacidad core del proyecto

**Priorización dentro de v2 (Drivers NoSQL):**
1. MongoDB (#14) — SQL-like, output estructurado
2. Redis (#15) — Patrones diferentes, SLOWLOG
3. Neo4j (#16) — Lenguaje Cypher distinto
4. InfluxDB (#17), DynamoDB (#19), Cassandra (#20), Elasticsearch (#21) — Según disponibilidad

**Clasificación de Features:**

| Prioridad | Descripción | Ejemplos | Garantizado en v1.0.0 |
|----------|-------------|----------|----------------------|
| **Crítica** | Bloquea release, sin ella el proyecto no funciona | BaseAdapter, PostSQL + MySQL drivers, anti-patrones, CLI | ✅ SÍ |
| **Alta** | Core functionality, entrega valor inmediato | SQLite driver, TUI básica, historial | ✅ SÍ (v1.0.0) |
| **Media** | Enhancement, mejora la experiencia | Neo4j, Redis drivers | ✅ Probablemente |
| **Baja** | Nice-to-have, post release | DynamoDB, Elasticsearch en profundidad | ❌ No (v1.1+) |

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## 9. Otros Requerimientos del Producto

### 9.1 Estándares Legales

- **Licencia del proyecto:** MIT — compatible con 100% de dependencias
- **Cumplimiento de privacidad:** RGPD (Unión Europea) — datos nunca salen de máquina del usuario
- **Cumplimiento de privacidad:** Ley Nº 29733 (Perú) — Ley de Protección de Datos Personales
  - Dato: Las credenciales y queries analizadas permanecen EXCLUSIVAMENTE en `~/.query-analyzer/` del usuario
  - No hay recopilación centralizada, transmisión a servidores, ni procesamiento en cloud
- **Auditoría de dependencias:** `uv pip audit` pre-release para vulnerabilidades conocidas
- **Propiedad intelectual:** Código 100% original del estudiante, sin conflictos

### 9.2 Estándares de Comunicación

- **Documentación técnica:** Markdown en `/docs` con ejemplos ejecutables
- **README.md:** Demo GIF con asciinema, tabla de motores soportados, quickstart 3 comandos
- **Docstrings:** PEP 257, con ejemplos de uso en cada módulo público
- **Mensajes de error:** Claros, descriptivos, con sugerencias de solución (no solo "Error")
- **Issues en GitHub:** Criterios de aceptación medibles y verificables
- **Commits:** Conventional Commits (feat:, fix:, docs:, test:, chore:)
- **Pull Requests:** Template con descripción, cambios, testing manual, screenshots si aplica

### 9.3 Estándares de Cumplimiento de Plataforma

- **Python:** Versión 3.12 LTS mínimo (soporte extendido hasta 2028)
- **Sistemas Operativos:** 
  - Linux: Ubuntu 22.04 LTS o similar
  - macOS: 13+ (Intel y Apple Silicon)
  - Windows: Windows 11 con WSL2
- **Versionado:** Semantic Versioning (MAJOR.MINOR.PATCH)
  - v0.x: Desarrollo (puede romper API)
  - v1.0.0+: Estable, compatible (mantenimiento a largo plazo)
- **Distribución:** PyPI como fuente oficial
- **CI/CD:** GitHub Actions en cada PR (tests, linter, type check, coverage)

### 9.4 Estándares de Calidad y Seguridad

**Seguridad de credenciales:**
- ❌ Passwords **NUNCA** en:
  - Logs de ejecución
  - Output de consola
  - Archivo de historial
  - Git (`.gitignore` incluye `config.yaml`)
- ✅ Almacenamiento seguro:
  - Credenciales en variables de entorno o interpoladas con `${VAR}` en config
  - Enmascaramiento automático en cualquier output (mostrar `***` en lugar de password)

**Validación de entrada:**
- Todas las entradas de usuario (conexión, query) validadas con Pydantic
- Mensajes de error descriptivos que guíen al usuario

**Testing:**
- ≥ 80% cobertura de código con pytest-cov
- Tests unitarios (no requieren BD real) y tests de integración (con Docker)
- Separación clara de `tests/unit/` y `tests/integration/`

**Compatibilidad de dependencias:**
- Versiones fijas en `pyproject.toml` (e.g., `psycopg2-binary>=2.9.0,<3.0`)
- `uv.lock` para reproducibilidad exacta del entorno
- Pre-release audit: `uv pip audit` detecta vulnerabilidades

**Entorno reproducible:**
- `docker-compose.yml` con todos los motores versiones LTS
- Cualquier persona puede ejecutar `make up` y replicar el entorno de desarrollo

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## Conclusiones

El **Query Performance Analyzer** es un proyecto **viable, factible y de alto valor** que:

1. **Resuelve un problema real:** 60%+ de problemas de rendimiento en apps web vienen de queries subóptimas, y no existe una herramienta unificada que los diagnostique automáticamente.

2. **Es técnicamente factible:** 100% de tecnologías requeridas son open source, gratuitas y ampliamente adoptadas. La arquitectura en capas con patrón de adaptadores escala a múltiples motores.

3. **Es económicamente rentable:** 
   - B/C = 2.20 (2.20 soles de beneficio por sol invertido)
   - VAN = S/. 11,026.09 en 3 años
   - TIR = 88% (supera ampliamente costo de capital del 12%)

4. **Es completamente accesible:**
   - Gratuito (vs $250–$720/año de alternativas comerciales)
   - 100% open source (MIT license)
   - Sin dependencias de cloud ni suscripciones
   - Funciona offline

5. **Aporta valor educativo:**
   - Herramienta de aprendizaje simultáneamente (recomendaciones explican conceptos)
   - Profundo conocimiento de internals de 13 motores distintos
   - Portafolio técnico profesional para estudiante

6. **Invita extensión comunitaria:**
   - Patrón de adaptadores facilita agregar nuevos motores
   - Documentación clara para contribuidores
   - Proyecto académico con potencial de herramienta profesional

---

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

## Recomendaciones

1. **Proceder con desarrollo inmediato:** Los indicadores de factibilidad son positivos. Se recomienda iniciar con el milestone v0 (Setup y arquitectura base) dentro de la semana.

2. **Priorizar milestones v0–v1:** Asegurar que PostgreSQL, MySQL, SQLite y el detector de anti-patrones estén funcionales y testeados antes de avanzar a v2 (NoSQL).

3. **Gestión del timeline:** Si imprevistos académicos comprimen el tiempo disponible:
   - **Plan A (ideal):** Completar v0–v3 (CLI + TUI, 52 días)
   - **Plan B (si tiempo insuficiente):** Completar v0–v2 (CLI sin TUI, 32.5 días) — la funcionalidad core CLI es más valiosa que la TUI
   - **Plan C (mínimo viable):** Completar v0–v1 + CLI parcial (PostgreSQL, MySQL) — 20+ días, entregable funcional

4. **Documentación temprana:** Redactar documentos académicos (este FD02, metodología, arquitectura) en paralelo al código, no al final. Facilita validación de progreso.

5. **Testing desde el inicio:** Escribir tests unitarios junto con cada driver (TDD). Evita acumulación de tests al final (v4).

6. **Integración CI/CD temprana:** Configurar GitHub Actions en v0 para que tests se ejecuten automáticamente. Detecta problemas rápidamente.

7. **Comunicación con docente:** Reportes biweekly de progreso, validación de decisiones arquitectónicas, identificación temprana de riesgos.

---

**Documento de Visión elaborado y validado.**

Firma del Docente Asesor: ___________________________

Fecha: ___________________________
