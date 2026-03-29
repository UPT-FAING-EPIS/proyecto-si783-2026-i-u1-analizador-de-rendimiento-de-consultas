<center>

![logo UPT](./media/logo-upt.png)

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

Sistema *Query Performance Analyzer*

Informe de Factibilidad

Versión *1.0*

| CONTROL DE VERSIONES | | | | | |
|:---:|:---|:---|:---|:---|:---|
| Versión | Hecha por | Revisada por | Aprobada por | Fecha | Motivo |
| 1.0 | {Estudiante} | {Docente} | {Docente} | 2025 | Versión Original |

---

## ÍNDICE GENERAL

1. [Descripción del Proyecto](#1-descripción-del-proyecto)
2. [Riesgos](#2-riesgos)
3. [Análisis de la Situación Actual](#3-análisis-de-la-situación-actual)
4. [Estudio de Factibilidad](#4-estudio-de-factibilidad)
   - 4.1 [Factibilidad Técnica](#41-factibilidad-técnica)
   - 4.2 [Factibilidad Económica](#42-factibilidad-económica)
   - 4.3 [Factibilidad Operativa](#43-factibilidad-operativa)
   - 4.4 [Factibilidad Legal](#44-factibilidad-legal)
   - 4.5 [Factibilidad Social](#45-factibilidad-social)
   - 4.6 [Factibilidad Ambiental](#46-factibilidad-ambiental)
5. [Análisis Financiero](#5-análisis-financiero)
6. [Conclusiones](#6-conclusiones)

## Informe de Factibilidad

## 1. Descripción del Proyecto

### 1.1. Nombre del proyecto

**Query Performance Analyzer** — Herramienta TUI/CLI multi-motor para análisis de rendimiento de consultas en bases de datos.

### 1.2. Duración del proyecto

| Elemento | Detalle |
|---|---|
| Fecha de inicio | Milestone v0 — Setup y arquitectura base |
| Fecha de término estimada | Milestone v4 — Release v1.0.0 en PyPI |
| Total de issues planificados | 33 issues distribuidos en 5 milestones |
| Estimación total de desarrollo | ~52 días (~16 semanas a ritmo de 3–4 horas/día) |
| Metodología | Desarrollo incremental por fases con tablero Kanban en GitHub Projects |

#### Distribución de fases y esfuerzo

| Milestone | Descripción | Issues | Días estimados |
|---|---|:---:|:---:|
| **v0** | Setup, arquitectura base y entorno de desarrollo | #1–#5 | 4.0 d |
| **v1** | Drivers SQL + motor de análisis y detección de anti-patrones | #6–#13 | 13.0 d |
| **v2** | Drivers NoSQL, NewSQL y especializados + CLI | #14–#22 | 15.5 d |
| **v3** | Interfaz TUI completa con Textual | #23–#27 | 9.0 d |
| **v4** | Testing, documentación y release v1.0.0 | #28–#33 | 7.5 d |
| **Total** | | **33** | **~52 días** |

### 1.3. Descripción

El **Query Performance Analyzer** es una herramienta de software de código abierto orientada a desarrolladores y administradores de bases de datos que necesitan diagnosticar y optimizar el rendimiento de sus consultas. El proyecto surge como una iniciativa académica individual con proyección a convertirse en una herramienta de uso profesional publicada en PyPI.

La herramienta funciona como una **interfaz de usuario en terminal (TUI)** y como **herramienta de línea de comandos (CLI)**, permitiendo al usuario conectarse a múltiples motores de bases de datos, ejecutar el análisis del plan de ejecución de una consulta y recibir recomendaciones concretas y accionables, incluyendo sentencias SQL o comandos listos para aplicar.

El contexto en el que se desarrolla el proyecto es el de la creciente adopción de múltiples motores de bases de datos (SQL, NoSQL, grafos, series de tiempo, columnar) en entornos de desarrollo modernos, donde los desarrolladores frecuentemente carecen de herramientas unificadas para analizar el rendimiento de consultas sin necesidad de cambiar de entorno o instalar software adicional por cada motor.

La herramienta se distingue por los siguientes atributos:

- **Soporte multi-motor:** cubre 13 motores de bases de datos en una sola interfaz, desde PostgreSQL y MySQL hasta MongoDB, Redis, Neo4j, Elasticsearch, InfluxDB, Cassandra, DynamoDB, CockroachDB, YugabyteDB, TimescaleDB y SQLite.
- **Arquitectura de adaptadores:** diseñada desde el origen para que agregar soporte a un nuevo motor requiera únicamente implementar una interfaz común (`BaseAdapter`), sin modificar el código existente.
- **Análisis inteligente:** detecta automáticamente anti-patrones conocidos (full table scans, estimaciones de filas incorrectas, nested loops costosos, comandos O(N) bloqueantes, `ALLOW FILTERING`, entre otros) y genera recomendaciones con el SQL concreto para resolver el problema.
- **Interfaz sin fricción:** al funcionar completamente en terminal, se integra con cualquier flujo de trabajo de desarrollo sin depender de un navegador, interfaz gráfica o conexión a servicios en la nube.
- **Gestión moderna de paquetes:** usa `uv` (Astral) como gestor de entornos y dependencias, garantizando reproducibilidad exacta del entorno de desarrollo con un único archivo `uv.lock`.

### 1.4. Objetivos

#### 1.4.1. Objetivo General

Desarrollar una herramienta TUI/CLI de código abierto en Python que permita analizar el rendimiento de consultas en múltiples motores de bases de datos, detectar anti-patrones de forma automática y generar recomendaciones concretas de optimización, consolidando el conocimiento práctico en internals de bases de datos adquirido durante el proceso de desarrollo.

#### 1.4.2. Objetivos Específicos

| # | Objetivo específico | Milestone | Issues | Logro esperado |
|---|---|:---:|---|---|
| OE1 | Diseñar e implementar la arquitectura base del sistema: estructura del proyecto con `uv`, contrato `BaseAdapter`, sistema de perfiles de conexión, entorno Docker y registro de adaptadores | v0 | #1, #2, #3, #4, #5 | El repositorio está operativo. `uv sync` instala todo sin errores. El contrato de adaptadores está definido y verificado con tipado estático. |
| OE2 | Implementar los drivers para los seis motores SQL y el motor de detección de anti-patrones con recomendaciones accionables | v1 | #6, #7, #8, #9, #10, #11, #12, #13 | Los drivers de PostgreSQL, MySQL, SQLite, CockroachDB, YugabyteDB y TimescaleDB producen `QueryAnalysisReport` normalizados. El detector identifica al menos 7 anti-patrones con SQL concreto como recomendación. |
| OE3 | Ampliar el soporte a motores NoSQL, de grafos, series de tiempo y cloud, e implementar el comando CLI principal `qa analyze` | v2 | #14–#22 | Los drivers de MongoDB, Redis, Neo4j, InfluxDB, DynamoDB, Cassandra y Elasticsearch están operativos. `uv run qa analyze --profile <nombre> "<query>"` funciona para todos los motores soportados. |
| OE4 | Desarrollar la interfaz TUI completa con editor de queries, visualizador del árbol del plan de ejecución, historial de análisis y panel de queries lentas | v3 | #23, #24, #25, #26, #27 | El usuario puede completar un ciclo completo (seleccionar perfil → escribir query → ver árbol → comparar con historial → exportar reporte) sin abandonar la terminal. |
| OE5 | Publicar la herramienta en PyPI con suite de tests de cobertura >= 80%, documentación completa y pipeline CI/CD automatizado | v4 | #28, #29, #30, #31, #32, #33 | `pip install query-analyzer` disponible públicamente. GitHub Actions ejecuta tests en cada PR. El README incluye demo GIF y tabla de motores soportados. |

---

## 2. Riesgos

Los siguientes riesgos han sido identificados como factores que podrían afectar el éxito del proyecto:

| # | Riesgo | Milestone afectado | Probabilidad | Impacto | Estrategia de mitigación |
|---|---|:---:|:---:|:---:|---|
| R1 | **Heterogeneidad de formatos de EXPLAIN:** cada motor retorna el plan de ejecución en formato distinto (árbol JSON multinivel, tabla relacional, texto plano con opcodes), dificultando la normalización al modelo `QueryAnalysisReport`. | v1–v2 | Alta | Alto | Parsers específicos por motor encapsulados dentro de cada `Adapter`. El `BaseAdapter` define el contrato de salida, no el proceso de parseo interno. |
| R2 | **Motores NoSQL sin plan de ejecución formal:** Redis, DynamoDB y Cassandra no tienen un equivalente directo a `EXPLAIN`, limitando el análisis a patrones estáticos del comando recibido. | v2 | Alta | Medio | Documentar claramente el alcance de análisis por motor en el README. Enfocarse en los anti-patrones de mayor impacto para cada motor: `SLOWLOG` (Redis), `Scan vs Query` (DynamoDB), `ALLOW FILTERING` (Cassandra). |
| R3 | **Compatibilidad de versiones de motores:** las APIs de profiling cambian entre versiones mayores. `EXPLAIN FORMAT=JSON` varía entre MySQL 5.7 y MySQL 8.0; `EXPLAIN ANALYZE` en Flux varía entre InfluxDB 1.x y 2.x. | v1–v2 | Media | Alto | Testear contra versiones LTS de cada motor en Docker. Detectar versión del motor en `get_engine_info()` y ramificar el parser según corresponda. |
| R4 | **Estimación de 52 días excedida:** como proyecto individual con dedicación parcial (3–4 h/día), imprevistos académicos pueden extender la duración real más allá de las ~16 semanas estimadas. | Todas | Media | Alto | Los issues de mayor valor (PostgreSQL en v1 + CLI en v2) están priorizados en los primeros milestones. Si el tiempo es insuficiente, v3 (TUI) puede reducirse sin comprometer la funcionalidad core entregable via CLI. |
| R5 | **Complejidad de la TUI con Textual (v3):** construir interfaces reactivas y asíncronas en terminal tiene una curva de aprendizaje considerable para un desarrollador que la usa por primera vez. | v3 | Media | Medio | La funcionalidad CLI completa (`qa analyze`, `qa profile`, `qa engines`) queda operativa al final de v2. La TUI de v3 es un enhancement que agrega valor pero no bloquea la funcionalidad principal. |
| R6 | **Alcance de 13 motores resulta en implementaciones superficiales:** implementar y testear 13 drivers con la misma profundidad puede comprometer la calidad del análisis en los motores menos prioritarios. | v2 | Media | Medio | PostgreSQL, MySQL, SQLite y MongoDB son drivers de primera clase con análisis profundo (v1–v2). Los demás pueden marcarse como "soporte experimental" en la v1.0.0 y mejorarse en versiones posteriores. |
| R7 | **Fuga de credenciales de base de datos:** un error de implementación podría exponer passwords en logs, output de consola o en el archivo de historial. | v0–v2 | Baja | Crítico | Enmascarar passwords en todo output desde el issue #3. Nunca serializar `ConnectionConfig` completo en logs ni en `history.db`. Usar variables de entorno para credenciales en lugar de valores en texto plano en `config.yaml`. |
| R8 | **Cambios de API en drivers de terceros:** `pymongo`, `neo4j`, `elasticsearch-py` realizan cambios de API en versiones mayores que pueden romper los adapters. | v2 | Baja | Medio | Fijar versiones mínimas y máximas en `pyproject.toml`. Usar `uv lock` para garantizar reproducibilidad exacta. Los tests de integración en CI detectarán roturas antes de la release. |

---

## 3. Análisis de la Situación Actual

### 3.1. Planteamiento del Problema

#### Antecedentes

El rendimiento de las consultas a bases de datos es uno de los factores que más impacto tiene en la experiencia del usuario final de las aplicaciones modernas. Estudios de la industria (Percona, 2023) indican que más del 60% de los problemas de rendimiento en aplicaciones web tienen su origen en consultas de base de datos subóptimas: full table scans por ausencia de índices, estimaciones incorrectas del planificador de consultas, anti-patrones como N+1 queries, o uso incorrecto de operaciones costosas propias de cada motor (como `ALLOW FILTERING` en Cassandra o `KEYS *` en Redis).

A pesar de que todos los motores de bases de datos maduros ofrecen mecanismos de análisis del plan de ejecución (`EXPLAIN`, `PROFILE`, `.explain()`, `_profile`, `SLOWLOG`), su uso sistemático entre desarrolladores es bajo por las siguientes razones:

- La sintaxis y el formato de salida es radicalmente diferente entre motores, requiriendo que el desarrollador aprenda herramientas distintas para cada uno.
- Las herramientas de análisis existentes son mayoritariamente visuales (pgAdmin, MySQL Workbench, MongoDB Compass, DataGrip) y no se integran con flujos de trabajo basados en terminal o con pipelines de CI/CD.
- Interpretar un plan de ejecución correctamente requiere conocimiento especializado (entender qué es un Seq Scan, cuándo el planificador toma una decisión equivocada, qué significa `Using filesort`, etc.) que los desarrolladores generalistas frecuentemente no poseen.
- No existe una herramienta unificada, de código abierto y orientada a terminal, que cubra múltiples motores bajo una misma interfaz.

#### Situación Actual

Actualmente, un desarrollador que trabaja con múltiples motores de bases de datos debe seguir un proceso manual ineficiente para cada motor:

1. Recordar o buscar la sintaxis exacta de `EXPLAIN` para el motor específico y su versión.
2. Interpretar manualmente la salida: árbol JSON multinivel (PostgreSQL), tabla con columnas `type`, `key`, `Extra` (MySQL), texto con opcodes (SQLite), árbol de stages (MongoDB), o lista de comandos con tiempos (Redis `SLOWLOG GET`).
3. Identificar si existe un Seq Scan, un `type=ALL`, un `COLLSCAN`, un `ALLOW FILTERING`, un `CartesianProduct` en Neo4j o una query Flux sin filtro de tiempo en InfluxDB.
4. Buscar en la documentación de cada motor qué significa el término encontrado y qué acción correctiva aplicar.
5. Aplicar la corrección y volver a ejecutar el `EXPLAIN` manualmente para verificar que el anti-patrón fue resuelto.
6. Cambiar de herramienta para cada motor, perdiendo el contexto y el flujo de trabajo.

Este proceso consume entre 30 y 60 minutos por consulta analizada, es propenso a errores por falta de conocimiento especializado, y se repite para cada motor de forma independiente.

#### Problemática que resuelve el proyecto

El **Query Performance Analyzer** centraliza y automatiza este proceso al proveer:

- Una única interfaz (CLI/TUI) para analizar consultas en cualquier motor soportado, con la misma experiencia de usuario.
- Traducción automática del plan de ejecución a warnings en lenguaje natural, con el nombre real de la tabla o colección afectada.
- Recomendaciones concretas con el SQL o comando exacto listo para ejecutar (`CREATE INDEX`, `ANALYZE`, `SCAN 0 MATCH ... COUNT 100` en lugar de `KEYS *`).
- Un sistema de scoring (0–100) y un historial persistente que permiten medir objetivamente el impacto de cada optimización aplicada.

### 3.2. Consideraciones de Hardware y Software

#### Hardware disponible y requerido

| Componente | Mínimo (usuario final) | Recomendado (desarrollo con Docker) |
|---|---|---|
| CPU | Dual-core 1.8 GHz | Quad-core 2.5 GHz o superior |
| RAM | 256 MB (solo la herramienta) | 8 GB (para correr múltiples motores en Docker simultáneamente) |
| Almacenamiento | < 100 MB instalada con dependencias | 30 GB (imágenes Docker de todos los motores de bases de datos) |
| Sistema Operativo | Linux, macOS o Windows (WSL2) | Linux Ubuntu 22.04 LTS o macOS |
| Python | 3.12 o superior | 3.12 LTS |
| Red | Acceso a la base de datos objetivo | Acceso a internet para descarga de dependencias e imágenes Docker |

No se requiere ningún servidor dedicado, infraestructura cloud ni hardware especializado para el desarrollo o el uso de la herramienta.

#### Software seleccionado para la implementación

| Categoría | Tecnología seleccionada | Justificación técnica |
|---|---|---|
| Lenguaje de programación | Python 3.12 | Mayor ecosistema de drivers para bases de datos. Tipado estático moderno. Soporte LTS. |
| Gestor de paquetes y entornos | `uv` (Astral) | Reemplaza `pip` + `venv` + `pip-tools` en un solo binario. Hasta 100x más rápido que pip. Reproducibilidad exacta con `uv.lock`. Adoptado rápidamente como estándar de la industria en 2024–2025. |
| Framework TUI | Textual 0.47+ | Framework moderno para TUI con soporte de widgets reactivos, CSS-like styling y testing headless. |
| Output enriquecido en terminal | Rich 13+ | Librería de referencia para output con colores, tablas, paneles y árboles en terminal. Usada internamente por `pip`, `pytest` y `uv`. |
| CLI | Typer 0.9+ | Usa el sistema de tipos de Python como definición de la interfaz CLI. Sin configuración adicional. |
| Validación de modelos | Pydantic v2 | Validación de `ConnectionConfig` con mensajes de error descriptivos. Serialización JSON nativa. |
| Configuración | PyYAML | Formato YAML para perfiles de conexión con interpolación de variables de entorno (`${VAR}`). |
| Testing | pytest + pytest-cov | Framework estándar de Python con soporte de markers para separar tests unitarios de integración. |
| Calidad de código | Ruff + Black + mypy | Ruff reemplaza flake8 + isort con velocidad superior. Black para formateo determinista. mypy para tipado estático. |
| Containerización | Docker + Docker Compose | Entorno reproducible con todos los motores de bases de datos para desarrollo local y tests de integración. |
| CI/CD | GitHub Actions | Pipeline automático usando `astral-sh/setup-uv@v3` con servicios Docker para tests de integración en cada PR. |
| Control de versiones | Git + GitHub Projects | Repositorio `@analizador-de-dependencias` con tablero Kanban de 5 columnas y 33 issues con criterios de aceptación detallados. |
| Distribución pública | PyPI | Publicación del paquete instalable con `pip install query-analyzer` o `uv tool install query-analyzer`. |

#### Drivers de bases de datos utilizados por fase

| Milestone | Motor | Tipo | Driver Python |
|:---:|---|---|---|
| v1 | PostgreSQL 16 | SQL relacional | psycopg2-binary |
| v1 | MySQL 8 / MariaDB 10 | SQL relacional | pymysql |
| v1 | SQLite | SQL embebido | sqlite3 (stdlib) |
| v1 | CockroachDB | NewSQL | psycopg2-binary |
| v1 | YugabyteDB | NewSQL | psycopg2-binary |
| v1 | TimescaleDB | SQL + Time-series | psycopg2-binary |
| v2 | MongoDB 7 | Documental NoSQL | pymongo |
| v2 | Redis 7 | Key-Value NoSQL | redis-py |
| v2 | Neo4j 5 | Grafos | neo4j (oficial) |
| v2 | InfluxDB 2 | Series de tiempo | influxdb-client |
| v2 | DynamoDB | Cloud NoSQL | boto3 |
| v2 | Cassandra / ScyllaDB | Columnar | cassandra-driver |
| v2 | Elasticsearch 8 | Búsqueda full-text | elasticsearch-py |

---

## 4. Estudio de Factibilidad

El presente estudio de factibilidad fue elaborado para determinar si el proyecto es viable desde las perspectivas técnica, económica, operativa, legal, social y ambiental. La evaluación fue realizada durante el milestone v0 y aprobada por el docente asesor.

### 4.1. Factibilidad Técnica

El estudio de viabilidad técnica evalúa los recursos tecnológicos disponibles y su aplicabilidad a las necesidades del proyecto.

#### Evaluación de la arquitectura

El sistema se estructura en cuatro capas desarrolladas progresivamente a lo largo de los cinco milestones:

| Capa | Responsabilidad | Tecnología | Milestone |
|---|---|---|:---:|
| Presentación | TUI interactiva + CLI | Textual + Typer + Rich | v3 / v2 |
| Núcleo (Core) | Motor de análisis, scoring y recomendaciones | Python puro + Pydantic | v0–v1 |
| Abstracción | `BaseAdapter` + `AdapterRegistry` | ABC + decoradores Python | v0 |
| Drivers | 13 adaptadores de motores de bases de datos | Drivers específicos por motor | v1–v2 |

Esta separación permite desarrollar y testear cada componente en forma independiente, y garantiza que agregar soporte a un nuevo motor en el futuro no requiera modificar ninguna de las capas superiores.

#### Evaluación por componente técnico

| Componente | Tecnología | Disponible y gratuito | Factibilidad |
|---|---|:---:|:---:|
| TUI interactiva | Textual 0.47+ | ✅ PyPI | ✅ Factible |
| CLI principal | Typer + Rich | ✅ PyPI | ✅ Factible |
| BaseAdapter (patrón Adapter) | Python ABC estándar | ✅ Stdlib | ✅ Factible |
| AdapterRegistry (patrón Registry) | Decoradores Python | ✅ Stdlib | ✅ Factible |
| Sistema de configuración | PyYAML + Pydantic v2 | ✅ PyPI | ✅ Factible |
| Parser EXPLAIN PostgreSQL (JSON árbol) | psycopg2 | ✅ PyPI | ✅ Factible |
| Parser EXPLAIN MySQL (tabla) | pymysql | ✅ PyPI | ✅ Factible |
| Parser EXPLAIN SQLite (texto) | sqlite3 stdlib | ✅ Stdlib | ✅ Factible |
| Driver MongoDB (executionStats) | pymongo | ✅ PyPI | ✅ Factible |
| Driver Redis (SLOWLOG) | redis-py | ✅ PyPI | ✅ Factible |
| Driver Neo4j (PROFILE Cypher) | neo4j oficial | ✅ PyPI | ✅ Factible |
| Driver InfluxDB (EXPLAIN ANALYZE Flux) | influxdb-client | ✅ PyPI | ✅ Factible |
| Driver DynamoDB | boto3 | ✅ PyPI | ✅ Factible |
| Driver Cassandra | cassandra-driver | ✅ PyPI | ✅ Factible |
| Driver Elasticsearch (_profile API) | elasticsearch-py | ✅ PyPI | ✅ Factible |
| Historial de análisis | SQLite local (stdlib) | ✅ Stdlib | ✅ Factible |
| Entorno de desarrollo | Docker + uv | ✅ Gratuito | ✅ Factible |
| Tests de integración en CI | GitHub Actions + Docker services | ✅ Gratuito | ✅ Factible |

**Conclusión técnica:** el proyecto es **técnicamente factible**. El 100% de las tecnologías requeridas son de código abierto, gratuitas y están disponibles. La arquitectura en capas con el patrón de adaptadores es la solución técnica más apropiada para gestionar la heterogeneidad de 13 motores. El plan de milestones progresivos (comenzar con PostgreSQL como motor más documentado en v1, avanzar a motores NoSQL en v2) gestiona la curva de aprendizaje de forma controlada.

### 4.2. Factibilidad Económica

#### 4.2.1. Costos Generales
No se registran gastos significativos en materiales fisicos o impresiones durante el desarrollo del proyecto.

#### 4.2.2. Costos Operativos Durante el Desarrollo

La duración estimada del proyecto es de aproximadamente 4 meses (~16 semanas).

| Concepto | Meses | Costo mensual (S/.) | Costo total (S/.) |
|---|:---:|:---:|:---:|
| Servicio de internet | 4 | 40.00 | 160.00 |
| Energía eléctrica (equipo de cómputo) | 4 | 25.00 | 100.00 |
| **Total costos operativos** | | | **260.00** |

#### 4.2.3. Costos del Ambiente

| Concepto | Licencia | Costo (S/.) |
|---|---|:---:|
| Python 3.12 | PSF License (open source) | 0.00 |
| `uv` — gestor de paquetes y entornos | MIT / Apache 2.0 | 0.00 |
| Textual, Rich, Typer, Pydantic, PyYAML | MIT | 0.00 |
| psycopg2, pymysql, pymongo, redis-py, neo4j, influxdb-client, boto3, cassandra-driver, elasticsearch-py | Apache 2.0 / LGPL / MIT | 0.00 |
| pytest, Ruff, Black, mypy | MIT | 0.00 |
| Docker Desktop | Gratuito (uso personal/académico) | 0.00 |
| GitHub — repositorio + Actions + Projects | Gratuito (plan Free, 2,000 min/mes) | 0.00 |
| PyPI — publicación del paquete | Gratuito | 0.00 |
| IDE (VS Code u otro) | Gratuito | 0.00 |
| **Total costos del ambiente** | | **0.00** |

> El 100% del stack tecnológico del proyecto es de código abierto y gratuito. Esto incluye el sistema de CI/CD, el gestor de paquetes, todos los frameworks de desarrollo y las herramientas de calidad de código.

#### 4.2.4. Costos de Personal

El proyecto es desarrollado por un único estudiante. Se valoriza el tiempo invertido a una tarifa de practicante de desarrollo de software:

| Rol | Fase | Días estimados | Horas estimadas | Valor hora (S/.) | Costo (S/.) |
|---|---|:---:|:---:|:---:|:---:|
| Desarrollador | v0 — Setup | 4.0 d | 30 h | 15.00 | 450.00 |
| Desarrollador | v1 — Drivers SQL | 13.0 d | 97.5 h | 15.00 | 1,462.50 |
| Desarrollador | v2 — Drivers NoSQL + CLI | 15.5 d | 116.3 h | 15.00 | 1,744.50 |
| Desarrollador | v3 — TUI | 9.0 d | 67.5 h | 15.00 | 1,012.50 |
| Desarrollador | v4 — Testing + Release | 7.5 d | 56.3 h | 15.00 | 844.50 |
| Investigación / aprendizaje (20% adicional) | Todas | — | 73.5 h | 15.00 | 1,102.50 |
| **Total costos de personal** | | **49 d** | **441 h** | | **6,616.50** |

> Se incluye un 20% adicional por tiempo de investigación de internals de cada motor de base de datos, parte esencial e incorporada en el proceso de aprendizaje del proyecto.

#### 4.2.5. Costos Totales del Desarrollo del Sistema

| Categoría | Costo (S/.) | % del total |
|---|:---:|:---:|
| Costos Generales | 0.00 | 0% |
| Costos Operativos | 260.00 | 3.7% |
| Costos del Ambiente | 0.00 | 0% |
| Costos de Personal (incluye investigación) | 6,616.50 | 96.3% |
| **TOTAL** | **7,106.50** | **100%** |

**Forma de financiamiento:** el proyecto es autofinanciado por el estudiante como parte de sus estudios de pregrado. No requiere financiamiento externo ni inversión institucional.

### 4.3. Factibilidad Operativa

#### Beneficios del producto

**Beneficios directos para usuarios:**

- **Reducción de tiempo de análisis:** el proceso manual de analizar una consulta (ejecutar `EXPLAIN`, interpretar la salida, buscar en documentación) toma de 30 a 60 minutos. Con la herramienta, el mismo análisis toma menos de 1 minuto.
- **Eliminación de fragmentación de herramientas:** un único comando reemplaza el conocimiento de la sintaxis de `EXPLAIN` de 13 motores diferentes.
- **Recomendaciones accionables con SQL concreto:** el SQL o comando exacto de la corrección elimina la ambigüedad del diagnóstico (`CREATE INDEX CONCURRENTLY ON orders(status)` en lugar de "considera agregar un índice").
- **Historial cuantificable de optimizaciones:** el score 0–100 y el historial persistente permiten medir el impacto real de cada optimización con datos concretos.
- **Funcionamiento completamente offline:** no depende de servicios externos, APIs en la nube ni conexión a internet una vez instalado.

**Capacidad de mantenimiento:**

- Agregar soporte a un nuevo motor de base de datos requiere únicamente implementar los 6 métodos de `BaseAdapter` y agregar el decorador `@AdapterRegistry.register("nombre")`. Ninguna otra clase necesita ser modificada.
- Los 33 issues con criterios de aceptación medibles garantizan que cada feature es verificable objetivamente.
- El pipeline CI/CD detecta regresiones automáticamente en cada PR antes de mergear a `main`.

#### Lista de interesados (Stakeholders)

| Interesado | Rol en el proyecto | Interés principal |
|---|---|---|
| Estudiante desarrollador | Desarrollador | Completar el proyecto y adquirir conocimiento profundo en internals de bases de datos |
| Docente asesor | Supervisor académico | Evaluar calidad técnica, originalidad y contribución al aprendizaje |
| Desarrolladores de software | Usuarios finales primarios | Optimizar consultas sin herramientas especializadas ni consultores externos |
| DBAs (Administradores de BD) | Usuarios finales avanzados | Identificar y priorizar las consultas más costosas en entornos de producción |
| Comunidad open source | Usuarios y colaboradores potenciales | Disponer de una herramienta gratuita y extensible; contribuir nuevos drivers |
| Universidad Privada de Tacna | Institución académica | Validar que el proyecto cumple los requisitos académicos |

### 4.4. Factibilidad Legal

#### Licencias de software

Todas las dependencias del proyecto tienen licencias de código abierto compatibles entre sí y con la publicación bajo **licencia MIT**:

| Componente | Licencia | Compatible con MIT |
|---|---|:---:|
| Python 3.12 | PSF License | ✅ |
| uv | MIT / Apache 2.0 | ✅ |
| Textual | MIT | ✅ |
| Rich | MIT | ✅ |
| Typer | MIT | ✅ |
| Pydantic v2 | MIT | ✅ |
| PyYAML | MIT | ✅ |
| psycopg2-binary | LGPL v3 | ✅ |
| pymysql | MIT | ✅ |
| pymongo | Apache 2.0 | ✅ |
| redis-py | MIT | ✅ |
| neo4j (driver oficial) | Apache 2.0 | ✅ |
| influxdb-client | MIT | ✅ |
| elasticsearch-py | Apache 2.0 | ✅ |
| cassandra-driver | Apache 2.0 | ✅ |
| boto3 | Apache 2.0 | ✅ |
| pytest | MIT | ✅ |
| Ruff | MIT | ✅ |
| Docker (uso en desarrollo) | Apache 2.0 | ✅ |

#### Protección de datos personales

La herramienta opera exclusivamente en la máquina local del usuario. No recopila, transmite ni almacena datos de las bases de datos analizadas en ningún servidor externo. Los únicos datos que persisten localmente son:

- `~/.query-analyzer/config.yaml`: perfiles de conexión del usuario (en su propia máquina).
- `~/.query-analyzer/history.db`: historial de análisis con las queries ejecutadas (en su propia máquina).

Esta arquitectura garantiza compatibilidad con la **Ley N° 29733 — Ley de Protección de Datos Personales del Perú**, el **RGPD europeo** y las políticas corporativas de seguridad de la información, ya que los datos de producción del usuario nunca abandonan su entorno de trabajo.

#### Propiedad intelectual

El proyecto es un trabajo original desarrollado íntegramente por el estudiante. Todo el código producido es de autoría propia y será publicado bajo **licencia MIT**. No existe conflicto de propiedad intelectual con ninguna de las herramientas o librerías utilizadas como dependencias.

### 4.5. Factibilidad Social

**Democratización del análisis de rendimiento:** herramientas comerciales equivalentes (DataGrip, TablePlus, Redgate Monitor) tienen costos de $69 a $500 por usuario/año. El Query Performance Analyzer provee capacidades comparables completamente gratis, accesible a estudiantes, startups y proyectos open source.

**Impacto educativo:** las recomendaciones en lenguaje natural con SQL concreto funcionan simultáneamente como herramienta de diagnóstico y como herramienta de aprendizaje. Un desarrollador que recibe `CREATE INDEX CONCURRENTLY ON orders(status)` con la explicación del Seq Scan detectado aprende un concepto de bases de datos que recordará y aplicará en proyectos futuros.

**Extensibilidad comunitaria:** el diseño de adaptadores y la guía `docs/adding-a-driver.md` (issue #31) invitan activamente a la comunidad a agregar soporte para nuevos motores, enriqueciendo la herramienta más allá del alcance individual del proyecto.

**Ética del uso:** la herramienta opera en modo de solo lectura (ejecuta `EXPLAIN`, no modifica datos), requiere credenciales explícitamente proporcionadas por el usuario y funciona únicamente contra las bases de datos que el propio usuario autoriza. No presenta riesgos éticos significativos.

### 4.6. Factibilidad Ambiental

**Impacto ambiental directo — mínimo:** la herramienta es un proceso ligero (< 256 MB RAM) que no requiere servidor dedicado. Las consultas de análisis son operaciones de solo lectura con impacto energético despreciable.

**Impacto ambiental indirecto — positivo:** al optimizar consultas de base de datos, la herramienta contribuye a reducir el consumo de recursos computacionales:

- Una consulta que pasa de Seq Scan (500,000 filas) a Index Scan (1 fila) reduce su consumo de CPU e I/O en varios órdenes de magnitud.
- En entornos cloud (AWS DynamoDB, Google Cloud SQL), las consultas optimizadas reducen las unidades de cómputo facturadas, traduciendo directamente en menor consumo energético en data centers.
- Optimizaciones de consultas Redis (reemplazar `KEYS *` por `SCAN`) eliminan el bloqueo del event loop, mejorando la eficiencia de todo el servidor.

**Desarrollo digital:** el proyecto se desarrolla íntegramente en entornos digitales (GitHub, Docker, terminal). El backlog completo (33 issues), la documentación técnica y el código fuente residen en GitHub, minimizando el uso de papel.

---

## 5. Análisis Financiero

El plan financiero analiza los ingresos y gastos asociados al proyecto desde el punto de vista temporal, detectando situaciones financieramente inadecuadas y estimando el resultado económico de la inversión.

### 5.1. Justificación de la Inversión

#### 5.1.1. Beneficios del Proyecto

**Beneficios tangibles:**

| Beneficio | Descripción | Estimación |
|---|---|---|
| Reducción de tiempo de análisis de queries | De 30–60 min manual a < 1 min automatizado | ~25 min ahorrados por query analizada |
| Eliminación de herramientas comerciales | Alternativa a DataGrip ($69–$199/año) o pgAdmin Pro | S/. 250–720 ahorrados/año por usuario |
| Reducción de incidentes de rendimiento | Detección temprana antes del despliegue a producción | Variable; incidentes de producción cuestan horas-hombre de guardia |
| Reducción de costos cloud | Consultas optimizadas consumen menos RCUs / CPU en cloud | 20–50% menos gasto en cómputo para consultas optimizadas |

**Beneficios intangibles:**

- **Conocimiento profundo de internals de bases de datos:** implementar parsers para 13 motores distintos genera un conocimiento técnico especializado de alto valor en el mercado laboral, que no se adquiere con el uso superficial de las bases de datos.
- **Portafolio técnico profesional:** un proyecto publicado en PyPI, con 33 issues completados, CI/CD y documentación profesional, es un activo diferenciador en el perfil de un desarrollador junior.
- **Contribución a la comunidad open source:** la herramienta queda disponible para la comunidad internacional, con potencial de generar colaboraciones, visibilidad y oportunidades profesionales.
- **Disponibilidad de información de rendimiento:** permite tomar decisiones de optimización basadas en el plan de ejecución real, no en suposiciones o intuición.
- **Mejor servicio al usuario final:** las aplicaciones cuyas bases de datos son optimizadas con la herramienta ofrecen mejor rendimiento y experiencia al usuario final.
- **Toma acertada de decisiones de arquitectura:** el historial y el scoring permiten evaluar objetivamente el impacto de cambios como agregar un índice, reescribir una query o migrar de motor.

#### 5.1.2. Criterios de Inversión

**Supuestos para el análisis:**

- **Horizonte de evaluación:** 3 años desde la publicación de la v1.0.0.
- **Costo de oportunidad del capital (COK):** 12% anual.
- **Adopción estimada:** 3 desarrolladores en el año 1, escalando a 5 en el año 2 y 8 en el año 3.
- **Beneficio anual por desarrollador:** S/. 1,560/año. Desglose: 2 queries analizadas/semana × 25 min ahorrados × 52 semanas × S/. 15/hora = S/. 650/año (tiempo), más S/. 500/año (eliminación de herramientas comerciales), más 35% de beneficios indirectos = **S/. 1,553 ≈ S/. 1,560/año**.
- **Inversión inicial:** S/. 7,106.50 (costo total del proyecto).
- **Costo de mantenimiento anual:** S/. 480/año (actualizaciones de compatibilidad con nuevas versiones de motores: ~32 h/año × S/. 15/hora).

#### Flujo de caja proyectado

| Periodo | Usuarios | Beneficio bruto (S/.) | Costo mantenimiento (S/.) | Flujo neto (S/.) |
|:---:|:---:|:---:|:---:|:---:|
| Año 0 (inversión inicial) | — | — | 7,106.50 | **-7,106.50** |
| Año 1 | 3 | 4,680.00 | 480.00 | **4,200.00** |
| Año 2 | 5 | 7,800.00 | 480.00 | **7,320.00** |
| Año 3 | 8 | 12,480.00 | 480.00 | **12,000.00** |

##### 5.1.2.1. Relación Beneficio / Costo (B/C)

```
Beneficios en Valor Presente:
  VP Año 1 = 4,200.00 / (1.12)^1 =  3,750.00
  VP Año 2 = 7,320.00 / (1.12)^2 =  5,841.07
  VP Año 3 = 12,000.00 / (1.12)^3 = 8,541.52
  Σ VP Beneficios               = 18,132.59

Costos en Valor Presente:
  VP Año 0 = 7,106.50
  VP Año 1 = 480.00 / (1.12)^1 =   428.57
  VP Año 2 = 480.00 / (1.12)^2 =   382.65
  VP Año 3 = 480.00 / (1.12)^3 =   341.65
  Σ VP Costos                   = 8,259.37

B/C = 18,132.59 / 8,259.37 = 2.20
```

**B/C = 2.20 > 1 → Se acepta el proyecto.**

Por cada sol invertido en el proyecto, se obtienen S/. 2.20 en beneficios durante el horizonte de 3 años.

##### 5.1.2.2. Valor Actual Neto (VAN)

```
VAN = -7,106.50 + 4,200.00/(1.12)^1 + 7,320.00/(1.12)^2 + 12,000.00/(1.12)^3
    = -7,106.50 + 3,750.00 + 5,841.07 + 8,541.52
    = 11,026.09
```

**VAN = S/. 11,026.09 > 0 → Se acepta el proyecto.**

El proyecto genera un valor actual neto positivo de S/. 11,026.09 en el horizonte de evaluación de 3 años, confirmando que es una inversión rentable.

##### 5.1.2.3. Tasa Interna de Retorno (TIR)

Calculando iterativamente la tasa que hace VAN = 0:

```
0 = -7,106.50 + 4,200.00/(1+TIR)^1 + 7,320.00/(1+TIR)^2 + 12,000.00/(1+TIR)^3

TIR ≈ 88%
```

**TIR = 88% > COK (12%) → Se acepta el proyecto.**

La tasa interna de retorno del 88% supera ampliamente el costo de oportunidad del capital del 12%, confirmando que el proyecto es altamente rentable en relación a otras alternativas de inversión del mismo capital y esfuerzo.

#### Resumen de indicadores financieros

| Indicador | Valor calculado | Criterio de aceptación | Resultado |
|---|:---:|:---:|:---:|
| Relación B/C | **2.20** | B/C > 1 | ✅ **Aceptar** |
| Valor Actual Neto (VAN) | **S/. 11,026.09** | VAN > 0 | ✅ **Aceptar** |
| Tasa Interna de Retorno (TIR) | **88%** | TIR > COK (12%) | ✅ **Aceptar** |

---

## 6. Conclusiones

El análisis de factibilidad del proyecto **Query Performance Analyzer** arroja los siguientes resultados por dimensión:

**Factibilidad Técnica — VIABLE**
El 100% de las tecnologías requeridas son de código abierto, gratuitas y ampliamente adoptadas en la industria. La arquitectura en cuatro capas con el patrón de adaptadores es la solución técnica más adecuada para gestionar la heterogeneidad de 13 motores de bases de datos. El plan de 5 milestones (v0–v4) con 33 issues distribuye progresivamente la complejidad técnica, comenzando con el motor más documentado (PostgreSQL en v1) y avanzando hacia los más especializados (NoSQL y series de tiempo en v2).

**Factibilidad Económica — VIABLE**
El costo total del proyecto es de S/. 7,106.50, compuesto en un 93% por el tiempo del desarrollador. Al no requerir ninguna licencia comercial, infraestructura cloud ni hardware especializado, el proyecto es completamente accesible en el contexto de un proyecto académico autofinanciado. El uso de `uv`, GitHub Actions y PyPI elimina cualquier costo de ambiente o distribución.

**Factibilidad Operativa — VIABLE**
La herramienta aporta beneficios concretos y medibles: reducción del tiempo de análisis de 30–60 minutos a menos de 1 minuto por consulta. La arquitectura de adaptadores garantiza mantenibilidad a largo plazo. Los 33 issues con criterios de aceptación medibles aseguran la entrega de funcionalidad verificable en cada milestone.

**Factibilidad Legal — VIABLE**
El proyecto utiliza exclusivamente software con licencias de código abierto compatibles con MIT. No recopila ni transmite datos de los usuarios, siendo plenamente compatible con la Ley N° 29733 de Protección de Datos Personales del Perú. No existe conflicto con ninguna regulación legal aplicable.

**Factibilidad Social — VIABLE**
El proyecto democratiza el acceso a capacidades de análisis de rendimiento de bases de datos, anteriormente reservadas a herramientas comerciales costosas. Actúa simultáneamente como herramienta de diagnóstico y como herramienta educativa, reduciendo la brecha de conocimiento en internals de bases de datos entre desarrolladores generalistas.

**Factibilidad Ambiental — VIABLE**
El impacto ambiental directo es mínimo (proceso ligero sin servidor dedicado). El impacto ambiental indirecto es positivo: las optimizaciones que facilita la herramienta reducen el consumo energético de los servidores de bases de datos al eliminar operaciones costosas.

**Análisis Financiero — VIABLE EN LOS TRES INDICADORES**

| Indicador | Resultado | Decisión |
|---|:---:|:---:|
| Relación B/C | 2.20 | ✅ Aceptar |
| VAN | S/. 11,026.09 | ✅ Aceptar |
| TIR | 88% | ✅ Aceptar |

**Conclusión general:** el proyecto **Query Performance Analyzer** es **viable y factible** desde todas las perspectivas analizadas. Los tres indicadores financieros confirman la rentabilidad de la inversión sobre el costo de oportunidad del 12%. Se recomienda proceder con el desarrollo siguiendo el plan de 5 milestones (v0–v4) y 33 issues definido en el repositorio `@analizador-de-dependencias`, priorizando los milestones v0 (arquitectura base) y v1 (drivers SQL + detector de anti-patrones) para garantizar la entrega de valor funcional desde las primeras semanas de trabajo.
