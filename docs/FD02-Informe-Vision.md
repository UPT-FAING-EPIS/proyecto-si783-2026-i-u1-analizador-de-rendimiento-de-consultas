<center>

![Logo UPT](./media/logo-upt.png)

**UNIVERSIDAD PRIVADA DE TACNA**

**FACULTAD DE INGENIERÍA**

**Escuela Profesional de Ingeniería de Sistemas**

**Proyecto *Analizador de Rendimiento de Consultas***

Curso: *Base de Datos II*

Docente: *Mag. Patrick Cuadros Quiroga*

Integrantes:

***Carbajal Vargas, Andre Alejandro (2023077287)***

***Yupa Gómez, Fátima Sofía (2023076618)***

**Tacna - Perú**

***2026***

</center>

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

Sistema *Query Performance Analyzer*

**Documento de Visión**

**Versión *1.0***

| CONTROL DE VERSIONES |           |              |               |            |                                           |
|:--------------------:|:----------|:-------------|:--------------|:-----------|:------------------------------------------|
|       Version        | Hecha por | Revisada por | Aprobada por  | Fecha      | Motivo                                    |
|         1.0          | ACV, FSY  | ACV, FSY     | P. Cuadros Q. | 2026-04-04 | Primera versión del documento             |

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

**ÍNDICE GENERAL**

[1. Introducción](#_Toc52661346)
   - [1.1 Propósito](#_Toc52661346)
   - [1.2 Alcance](#_Toc52661346)
   - [1.3 Definiciones, Siglas y Abreviaturas](#_Toc52661346)
   - [1.4 Referencias](#_Toc52661346)
   - [1.5 Visión General](#_Toc52661346)

[2. Posicionamiento](#_Toc52661347)
   - [2.1 Oportunidad de negocio](#_Toc52661347)
   - [2.2 Definición del problema](#_Toc52661347)

[3. Descripción de los interesados y usuarios](#_Toc52661348)
   - [3.1 Resumen de los interesados](#_Toc52661348)
   - [3.2 Resumen de los usuarios](#_Toc52661348)
   - [3.3 Entorno de usuario](#_Toc52661348)
   - [3.4 Perfiles de los interesados](#_Toc52661348)
   - [3.5 Perfiles de los usuarios](#_Toc52661348)
   - [3.6 Necesidades de los interesados y usuarios](#_Toc52661348)

[4. Vista General del Producto](#_Toc52661349)
   - [4.1 Perspectiva del producto](#_Toc52661349)
   - [4.2 Resumen de capacidades](#_Toc52661349)
   - [4.3 Suposiciones y dependencias](#_Toc52661349)
   - [4.4 Costos y precios](#_Toc52661349)
   - [4.5 Licenciamiento e instalación](#_Toc52661349)

[5. Características del producto](#_Toc52661350)

[6. Restricciones](#_Toc52661351)

[7. Rangos de calidad](#_Toc52661352)

[8. Precedencia y Prioridad](#_Toc52661353)

[9. Otros requerimientos del producto](#_Toc52661354)
   - [9.1 Estándares legales](#_Toc52661354)
   - [9.2 Estándares de comunicación](#_Toc52661354)
   - [9.3 Estándares de cumplimiento de la plataforma](#_Toc52661354)
   - [9.4 Estándares de calidad y seguridad](#_Toc52661354)

[CONCLUSIONES](#_Toc52661355)

[RECOMENDACIONES](#_Toc52661356)

[BIBLIOGRAFÍA](#_Toc52661357)

[WEBGRAFÍA](#_Toc52661358)

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

**<u>Informe de Visión</u>**

1. <span id="_Toc52661346" class="anchor"></span>**Introducción**

   **1.1 Propósito**

   El presente informe define la visión funcional y académica del sistema *Query Performance Analyzer* (Analizador de Rendimiento de Consultas). Su propósito es establecer una referencia común para estudiantes, docente evaluador y futuros mantenedores del proyecto, describiendo con claridad:

    - El problema real que se busca resolver.
    - El alcance de la solución en su versión actual.
    - Las capacidades esperadas y sus límites.
    - Los criterios de calidad y prioridad para su evolución.

   Este documento también cumple una función de trazabilidad, porque conecta el objetivo del proyecto con artefactos técnicos verificables (CLI, módulos de análisis, reportes y pruebas).

   **1.2 Alcance**

   **Alcance funcional (incluido):**

    - Conexión y análisis de planes de ejecución en 13+ motores de bases de datos: PostgreSQL, MySQL, SQLite, CockroachDB, YugabyteDB, SQL Server (MSSQL), MongoDB, DynamoDB, Redis, Cassandra, Elasticsearch, InfluxDB y Neo4j.
    - Detección automática del tipo de base de datos mediante el módulo `ProjectDetector`.
    - Extracción y parseo de planes de ejecución según el formato nativo de cada motor (JSON, texto estructurado, planes binarios).
    - Análisis de anti-patrones conocidos (full table scans, estimación de filas incorrecta, nested loops ineficientes, comandos bloqueantes O(n), filtros post-escaneo, entre otros).
    - Generación de puntuación de rendimiento (0-100) basada en severidad de anti-patrones.
    - Clasificación de recomendaciones por prioridad con código SQL/Cypher/MongoDB listo para aplicar.
    - Emisión de salida legible en consola con formato enriquecido (colores, tablas) y salida estructurada en JSON.
    - Interfaz de línea de comandos (CLI) typing-safe basada en typer.
    - Interfaz interactiva de terminal (TUI) basada en Textual para flujos de trabajo interactivos.
    - Gestión segura de perfiles de conexión con encriptación de credenciales.

   **Alcance no funcional (incluido):**

    - Ejecución local por línea de comandos en JVM Python 3.14+.
    - Compatibilidad operativa con Windows, Linux y macOS.
    - Uso de bibliotecas de código abierto mantenidas por la comunidad.
    - Modularidad mediante patrón Adapter para agregar nuevos motores sin modificar código existente.

   **Fuera de alcance (versión actual):**

    - Interfaz gráfica web o de escritorio nativa.
    - Remediación automática de planes de ejecución en el servidor de base de datos.
    - Integración nativa con plataformas empresariales propietarias (Datadog, New Relic, etc.).
    - Sustitución completa de herramientas de profiling comerciales de nivel empresarial.
    - Machine learning para predicción de rendimiento.

   **1.3 Definiciones, Siglas y Abreviaturas**

    - **CLI (Command Line Interface):** interfaz de línea de comandos para ejecutar funciones del sistema mediante comandos tipados.
    - **EXPLAIN PLAN:** sentencia SQL/NoSQL que devuelve el plan de ejecución de una consulta.
    - **Anti-patrón:** patrón de consulta o índice que genera rendimiento subóptimo (ej: full table scan, nested loops).
    - **Adapter Pattern:** patrón de diseño que permite integrar nuevos motores de BD sin modificar código existente.
    - **TUI (Text User Interface):** interfaz de usuario interactiva en terminal usando bibliotecas como Textual.
    - **Scoring:** puntuación numérica (0-100) que representa la calidad del rendimiento de una consulta.
    - **Registry (Adapter):** registro centralizado que almacena y crea instancias de adaptadores por tipo de motor.
    - **Recomendación:** sugerencia accionable con código concreto (SQL, Cypher, agregación MongoDB) para mejorar rendimiento.
    - **Dependencia transitiva:** librería incluida indirectamente por otra dependencia directa.

   **1.4 Referencias**

    - Documento base de uso: `README.md`.
    - Configuración de build: `pyproject.toml`.
    - Punto de entrada CLI: `query_analyzer/cli/main.py`.
    - Punto de entrada TUI: `query_analyzer/tui/app.py`.
    - Motor de análisis: `query_analyzer/core/anti_pattern_detector.py`.
    - Detector de anti-patrones especializado: `query_analyzer/core/dynamodb_anti_pattern_detector.py`.
    - Modelo de reporte: `query_analyzer/adapters/models.py` (`QueryAnalysisReport`).
    - Interfaz base de adaptadores: `query_analyzer/adapters/base.py` (`BaseAdapter`).
    - Registro de adaptadores: `query_analyzer/adapters/registry.py` (`AdapterRegistry`).
    - Gestión de configuración: `query_analyzer/config/manager.py`.
    - Encriptación de credenciales: `query_analyzer/config/crypto.py`.
    - Sitios oficiales: PostgreSQL, MySQL, MongoDB, DynamoDB, Elasticsearch, Neo4j, Textual, Typer.

   **1.5 Visión General**

   Query Performance Analyzer se visiona como una herramienta académica y profesional que permite evaluar rápidamente el rendimiento de consultas en múltiples motores de bases de datos. La propuesta de valor central es reducir incertidumbre técnica al consolidar, en una sola ejecución CLI/TUI, la información de:

    - Plan de ejecución nativo (normalizado y presentado de forma entendible).
    - Anti-patrones detectados automáticamente.
    - Puntuación de rendimiento con criterio objetivo.
    - Recomendaciones concretas y priorización de acciones.

   Desde la perspectiva de calidad de software, el sistema aporta detección temprana de cuellos de botella, soporte para decisiones de optimización y evidencia objetiva para auditorías de base de datos y procesos de enseñanza-aprendizaje.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

2. <span id="_Toc52661347" class="anchor"></span>**Posicionamiento**

   **2.1 Oportunidad de negocio**

   En entornos de desarrollo moderno, la adopción de múltiples motores de bases de datos (SQL, NoSQL, grafos, series de tiempo) incrementa la complejidad de diagnosticar y optimizar consultas lentas. Cada motor expone su plan de ejecución en formato diferente (JSON en PostgreSQL, texto estructurado en MySQL, agregaciones en MongoDB), lo que obliga a los desarrolladores a cambiar herramientas constantemente o carecer de un análisis unificado.

   La oportunidad del proyecto se ubica en proveer una solución local, de bajo costo de adopción y código abierto para:

    - Cursos universitarios orientados a bases de datos, rendimiento y optimización.
    - Equipos de desarrollo que requieren diagnosticar rápidamente consultas problemáticas.
    - Administradores de bases de datos que necesitan evidencia objetiva para decisiones de indexación.
    - Flujos de integración continua que demandan análisis automatizado de planes de ejecución.

   **Propuesta de valor resumida:**

    - Implementación ligera basada en CLI + TUI interactivo.
    - Soporte unificado para 13+ motores de bases de datos en una sola herramienta.
    - Reporte directo, JSON y markdown para consumo humano y automatizado.
    - Anti-patrones detectados automáticamente con puntuación objetiva.
    - Recomendaciones accionables con código listo para aplicar.

   **2.2 Definición del problema**

   El problema principal es la baja visibilidad del rendimiento real de consultas en entornos multi-motor, lo que genera tres consecuencias directas:

    1. **Ineficiencia operacional:** consultas lentas no detectadas en tiempo de desarrollo, causando degradación en producción.
    2. **Deuda técnica:** permanencia de índices subóptimos y planes de ejecución ineficientes sin sistematización de revisión.
    3. **Falta de experiencia educativa:** estudiantes carecen de herramienta accesible para aprender cómo optimizar consultas en diferentes motores.

   **Causas identificadas:**

    - Múltiples formatos de planes de ejecución según motor de BD.
    - Complejidad de interpretar planes jerárquicos y encontrar anti-patrones.
    - Falta de una herramienta académica unificada que enseñe optimización sin costo.
    - Necesidad de herramientas propietarias costosas para análisis profundo.

   **Efecto esperado con Query Performance Analyzer:**

    - Reducir tiempo de diagnóstico de consultas lentas.
    - Mejorar la priorización de acciones correctivas basadas en puntuación objetiva.
    - Fortalecer prácticas de rendimiento en el ciclo de desarrollo.
    - Proporcionar experiencia educativa accesible en optimización de bases de datos.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

3. <span id="_Toc52661348" class="anchor"></span>**Descripción de los interesados y usuarios**

   **3.1 Resumen de los interesados**

   | Interesado | Rol principal | Interés | Criterio de éxito |
   |---|---|---|---|
   | Estudiantes desarrolladores | Implementar y mantener la herramienta | Cumplir objetivos académicos y técnicos | Entregables funcionales, documentados y evaluados positivamente |
   | Docente del curso | Supervisar y evaluar el proyecto | Evidencia de calidad del proceso y producto | Coherencia entre documento, código y pruebas; demostración de conocimiento en BD |
   | Universidad (UPT) | Institución formadora | Promover proyectos aplicados útiles | Producto reutilizable en contextos educativos posteriores |
   | Comunidad técnica | Usuario potencial | Acceder a herramienta útil y abierta | Facilidad de uso, resultados confiables y comunidad de soporte |

   **3.2 Resumen de los usuarios**

   El usuario objetivo tiene perfil técnico, conoce SQL básico y ha trabajado con terminal. Se identifican cuatro grupos:

    - **Usuario académico:** ejecuta análisis para validar tareas de optimización y aprender anti-patrones.
    - **Usuario desarrollador:** evalúa consultas críticas antes de liberar cambios a producción.
    - **Usuario DBA:** usa reportes para planificar estrategias de indexación y mantenimiento.
    - **Usuario de CI/CD:** integra análisis en pipelines para validación automática de cambios en SQL/NoSQL.

   **3.3 Entorno de usuario**

    - Sistema operativo: Windows, Linux o macOS.
    - Requisito de ejecución: Python 3.14 o superior.
    - Conectividad: acceso de red a servidores de base de datos (local o remoto).
    - Entorno de trabajo: terminal local, pipeline de CI/CD, o script automatizado.
    - Formato de resultados: texto enriquecido en consola, JSON para automatización, markdown para reportes.

   **Escenarios representativos de uso:**

    - **Escenario A (diagnóstico manual):** usuario ejecuta `qa analyze "SELECT ..."` sobre una consulta problemática y revisa recomendaciones en consola.
    - **Escenario B (automatización CI):** usuario ejecuta `qa analyze --file slow_query.sql --output json` y procesa el resultado en otro paso del pipeline.
    - **Escenario C (interactivo con TUI):** usuario ejecuta `qa tui`, carga un perfil guardado de base de datos y analiza interactivamente múltiples consultas.
    - **Escenario D (gestión de perfiles):** usuario ejecuta `qa profile add` para guardar credenciales de múltiples bases de datos (desarrollo, staging, producción).

   **3.4 Perfiles de los interesados**

    - **Docente evaluador:** enfoque en trazabilidad, calidad documental, consistencia metodológica y alineación con currículo de BD.
    - **Equipo desarrollador:** enfoque en correctitud funcional, mantenibilidad, cobertura de pruebas y facilidad de agregar nuevos motores.
    - **Institución académica:** enfoque en impacto formativo, reusabilidad en futuros cursos y potencial para proyectos de mayor escala.

   **3.5 Perfiles de los usuarios**

    - **Usuario técnico básico:** requiere comandos simples (`qa analyze`), salida interpretable sin configuración previa.
    - **Usuario técnico intermedio:** requiere salida JSON, parámetros de control (`--output`, `--profile`), gestión de perfiles guardados.
    - **Usuario técnico avanzado:** integra resultados en scripts, consume JSON en otros sistemas, optimiza consultas de forma iterativa.

   **3.6 Necesidades de los interesados y usuarios**

   | Necesidad | Tipo | Respuesta del sistema |
   |---|---|---|
   | Detectar problemas de rendimiento en consultas | Funcional | Análisis de plan de ejecución y puntuación de rendimiento (0-100) |
   | Identificar anti-patrones automáticamente | Funcional | Detección de 7+ anti-patrones comunes + especializados por motor |
   | Obtener recomendaciones accionables | Funcional | Sugerencias con código concreto (SQL, Cypher, agregaciones) |
   | Comparar rendimiento entre consultas | Funcional | Exportación de múltiples análisis en JSON para comparación |
   | Guardar credenciales de forma segura | Funcional | Perfiles encriptados con soporte para múltiples bases de datos |
   | Integrar en automatizaciones | Interoperabilidad | Exportación JSON estructurada y código de salida shell |
   | Facilidad de adopción | Operativa | Ejecución local sin infraestructura compleja, instalación vía PyPI |
   | Aprender sobre optimización de BD | Educativa | Recomendaciones con explicación, ejemplos en múltiples motores |

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

4. <span id="_Toc52661349" class="anchor"></span>**Vista General del Producto**

   **4.1 Perspectiva del producto**

   Query Performance Analyzer es una herramienta complementaria a entornos de desarrollo local, IDEs y pipelines de CI/CD. Su rol no es reemplazar sistemas de monitoreo de producción (APM), sino inspeccionar planes de ejecución de forma consistente en múltiples motores y producir información de apoyo para la toma de decisiones de optimización.

   **Flujo funcional general:**

    1. Usuario crea o carga un perfil de conexión a una base de datos.
    2. Usuario proporciona una consulta (línea de comandos, archivo, stdin o editor interactivo).
    3. Sistema se conecta a la base de datos y ejecuta el comando EXPLAIN nativo.
    4. Sistema parsea y normaliza el plan de ejecución según el motor.
    5. Sistema detecta anti-patrones y genera una puntuación de rendimiento (0-100).
    6. Sistema emite recomendaciones prioridades con código concreto.
    7. Sistema presenta reporte en consola, JSON, markdown o interfaz interactiva.

   **4.2 Resumen de capacidades**

   | ID | Capacidad | Estado | Evidencia técnica |
   |---|---|---|---|
   | CAP-01 | Detección automática del tipo de motor de BD | Implementado | `ProjectDetector.detect()`, registro de adaptadores en `AdapterRegistry` |
   | CAP-02 | Parseo de planes EXPLAIN para 13+ motores | Implementado | Módulos `query_analyzer/adapters/sql/*`, `nosql/*`, `timeseries/*` |
   | CAP-03 | Análisis de anti-patrones comunes | Implementado | `query_analyzer/core/anti_pattern_detector.py` (7+ patrones) |
   | CAP-04 | Análisis especializado por motor | Implementado | `dynamodb_anti_pattern_detector.py`, `cassandra_anti_pattern_detector.py` |
   | CAP-05 | Generación de puntuación de rendimiento (0-100) | Implementado | Scoring en `QueryAnalysisReport.score`, lógica en core detectors |
   | CAP-06 | Generación de recomendaciones priorizadas | Implementado | `Recommendation` en models, código concreto por motor en adapters |
   | CAP-07 | Presentación enriquecida en consola | Implementado | Rich formatting en `cli/commands/`, colores y tablas |
   | CAP-08 | Exportación a JSON estructurado | Implementado | Serialización en `QueryAnalysisReport`, `--output json` en CLI |
   | CAP-09 | Interfaz interactiva TUI | Implementado | `query_analyzer/tui/app.py`, screens y widgets con Textual |
   | CAP-10 | Gestión de perfiles de conexión con encriptación | Implementado | `query_analyzer/config/manager.py`, crypto en `config/crypto.py` |

   **4.3 Suposiciones y dependencias**

   **Suposiciones de operación:**

    - El servidor de base de datos está accesible y operativo.
    - Las credenciales de conexión son válidas.
    - El motor de base de datos está entre los 13+ soportados.
    - La consulta es sintácticamente válida en el motor de destino.
    - Existe conectividad de red si la base de datos es remota.

   **Dependencias técnicas principales:**

    - Python 3.14 o superior.
    - Gestor de paquetes `uv` para reproducibilidad.
    - Drivers de base de datos: psycopg2 (PostgreSQL), pymysql (MySQL), pymongo (MongoDB), boto3 (DynamoDB), redis, elasticsearch, neo4j, influxdb-client, cassandra-driver.
    - Marcos de trabajo: typer (CLI), Textual (TUI), Pydantic (validación v2.12+).
    - Presentación: Rich (formato enriquecido), Markdown (exportación).
    - Seguridad: cryptography (encriptación de credenciales).
    - Testing: pytest (unitarias + integración), Docker (servicios de BD para tests).

   **Dependencias externas de información:**

    - Servidores de base de datos con acceso al comando EXPLAIN/equivalent.
    - Documentación de formato de planes de ejecución por motor (para mantener parsers).

   **4.4 Costos y precios**

   El proyecto tiene orientación académica y de código abierto. No se establece un precio de comercialización para esta fase. Según el contexto académico, el costo directo de desarrollo es bajo y concentrado en operación local, mientras que el stack tecnológico utiliza herramientas de acceso gratuito para fines educativos.

   **Modelo de adopción esperado:**

    - **Costo de licencia:** sin definir para uso académico interno. Licencia abierta (MIT o similar) para distribución comunitaria.
    - **Costo de instalación:** bajo, asociado a tener Python 3.14+ y acceso de red a bases de datos.
    - **Costo de operación:** bajo, dependiendo de consumo de bandwidth para consultas remotas.

   **4.5 Licenciamiento e instalación**

   La instalación se basa en distribución vía PyPI (Python Package Index):

    - Instalación: `pip install query-analyzer` o `uv pip install query-analyzer`.
    - Uso CLI: `qa analyze "SELECT ..."` o `qa profile add`.
    - Uso TUI: `qa tui` para interfaz interactiva.

   **Comandos de referencia (ejemplo):**

```bash
# Instalar desde PyPI
pip install query-analyzer

# Configurar perfil de base de datos
qa profile add

# Analizar una consulta directa
qa analyze "SELECT COUNT(*) FROM users"

# Analizar desde archivo
qa analyze --file slow_query.sql --profile production

# Exportar a JSON para automatización
qa analyze --file query.sql --output json > report.json

# Interfaz interactiva
qa tui
```

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

5. <span id="_Toc52661350" class="anchor"></span>**Características del producto**

**5.1 Requisitos funcionales principales**

| ID    | Requisito funcional                        | Descripción resumida                                                              |
|-------|--------------------------------------------|-----------------------------------------------------------------------------------|
| RF-01 | Detectar motor de BD automáticamente        | El sistema identifica automáticamente el tipo de BD en el que se ejecuta la consulta |
| RF-02 | Conectar a múltiples motores de BD          | El sistema soporta PostgreSQL, MySQL, SQLite, MongoDB, DynamoDB y 8 motores más   |
| RF-03 | Ejecutar EXPLAIN en el motor de BD          | El sistema ejecuta el comando de análisis de plan nativo del motor               |
| RF-04 | Parsear plan de ejecución                   | El sistema extrae e interpreta el plan según formato nativo (JSON, texto, etc.)   |
| RF-05 | Detectar anti-patrones automáticamente      | El sistema identifica 7+ anti-patrones (full scan, nested loops, etc.)            |
| RF-06 | Generar puntuación de rendimiento (0-100)   | El sistema calcula un score objetivo basado en severidad de anti-patrones         |
| RF-07 | Generar recomendaciones prioridades         | El sistema sugiere acciones concretas ordenadas por impacto (1-10)               |
| RF-08 | Mostrar salida enriquecida en consola        | El sistema presenta tablas, colores y formato legible en terminal                |
| RF-09 | Exportar salida a JSON                      | El sistema serializa análisis completo en JSON válido y parseable                 |
| RF-10 | Exportar salida a Markdown                  | El sistema genera reportes en formato Markdown para documentación                |
| RF-11 | Gestionar perfiles de conexión              | El sistema guarda y carga configuraciones de BD de forma segura y cifrada        |
| RF-12 | Soportar múltiples métodos de entrada       | El sistema acepta consultas por CLI, archivo, stdin o editor interactivo         |
| RF-13 | Interfaz interactiva (TUI)                  | El sistema proporciona una interfaz gráfica en terminal para flujo interactivo    |

**5.2 Requisitos no funcionales asociados**

- **RNF-01 (Portabilidad):** ejecución en Windows, Linux y macOS con Python 3.14+.
- **RNF-02 (Usabilidad técnica):** sintaxis de comandos simple, ayuda clara (--help), mensajes de error contextuales.
- **RNF-03 (Mantenibilidad):** separación modular entre parsers, adaptadores, core, CLI y TUI; sin modificación de código existente al agregar motores.
- **RNF-04 (Confiabilidad):** manejo de errores durante conexión, timeouts y excepciones de parseo con mensajes controlados.
- **RNF-05 (Interoperabilidad):** formato JSON estable y documentado para consumo por scripts y herramientas externas.
- **RNF-06 (Seguridad):** credenciales encriptadas en perfiles guardados, sin exposición de contraseñas en output.
- **RNF-07 (Performance):** análisis de consultas simples en < 10 segundos, consultas complejas en < 30 segundos.

**5.3 Escenarios de uso prioritarios**

1. **Diagnóstico de consulta lenta:** analizar una consulta que se ejecuta lentamente en producción para identificar anti-patrones y obtener recomendaciones.
2. **Validación pre-merge:** ejecutar análisis en rama para verificar que cambios de SQL/NoSQL no empeoran rendimiento.
3. **Auditoría de índices:** revisar múltiples consultas para identificar oportunidades de indexación.
4. **Educación en BD:** estudiantes usan la herramienta para aprender cómo diferentes motores optimizan consultas y qué anti-patrones evitar.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

6. <span id="_Toc52661351" class="anchor"></span>**Restricciones**

**6.1 Restricciones técnicas**

- Requiere Python 3.14 compatible y ejecución en entorno local (no servidor web nativo).
- Requiere acceso de red para conectar a servidores de BD remotos.
- El análisis depende de la versión del motor de BD; cambios en formato de EXPLAIN pueden requerir actualización de parsers.
- No funciona sin conectividad a la base de datos; no es un analizador estático de código SQL.

**6.2 Restricciones funcionales**

- No realiza cambios en la base de datos (read-only en todos los casos).
- No incluye interfaz gráfica web o GUI de escritorio nativa.
- No reemplaza herramientas de profiling a nivel de producción (APM, query logs, métricas históricas).
- Análisis limitado a un plan de ejecución a la vez; no mantiene histórico de cambios de rendimiento.

**6.3 Restricciones de proyecto académico**

- Alcance acotado al período del curso (semestre 2026-I).
- Priorizacion de entregables verificables sobre funcionalidades experimentales.
- Evolución incremental sujeta a tiempo disponible y validación del docente.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

7. <span id="_Toc52661352" class="anchor"></span>**Rangos de Calidad**

| Atributo              | Indicador                                      | Meta objetivo                               | Método de verificación             |
|-----------------------|------------------------------------------------|---------------------------------------------|------------------------------------|
| Correctitud funcional | Anti-patrones detectados correctamente         | >= 90% en casos de prueba definidos         | Pruebas unitarias de detectores    |
| Confiabilidad         | Ejecuciones sin error en entradas válidas      | >= 95% de ejecuciones exitosas              | Pruebas de integración             |
| Rendimiento           | Tiempo de análisis en consulta simple/compleja | <= 10 s / <= 30 s en entorno local          | Medición por corrida controlada    |
| Usabilidad técnica    | Comprensión del reporte por usuario técnico    | >= 80% de comprensión en evaluación         | Revisión de usuarios del curso     |
| Interoperabilidad     | JSON válido y parseable                        | 100% de reportes JSON válidos               | Validación de estructura de salida |
| Mantenibilidad        | Modulos con pruebas asociadas                  | Cobertura en componentes críticos (>=70%)   | Revision de suite de test          |
| Seguridad             | Credenciales expuestas en output               | 0 casos de exposición accidental            | Revisión de logs y output          |

**Criterios de aceptación global:**

- El sistema se considera aceptable si cumple al menos los umbrales de correctitud, confiabilidad e interoperabilidad.
- Rendimiento y usabilidad se consideran metas de mejora continua si el entorno de prueba presenta variaciones.
- Seguridad es no-negociable; cualquier exposición de credenciales es crítica.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

8. <span id="_Toc52661353" class="anchor"></span>**Precedencia y Prioridad**

| Nivel | Elemento                                       | Tipo             | Justificación académica                        |
|-------|------------------------------------------------|------------------|------------------------------------------------|
| Alta  | Parseo de plan EXPLAIN y detección anti-patrones | Núcleo funcional | Sin este bloque no existe análisis útil        |
| Alta  | Generación de puntuación de rendimiento (0-100) | Validación       | Proporciona criterio objetivo de calidad       |
| Alta  | Reporte claro en consola con recomendaciones    | Usabilidad       | Permite interpretación inmediata de resultados |
| Media | Exportación JSON                               | Integración      | Favorece automatización y trazabilidad         |
| Media | Interfaz TUI interactiva                       | Experiencia UX   | Mejora ergonomía para análisis iterativos     |
| Media | Parámetros de ejecución (--profile, --output)  | Operativa        | Mejora adaptabilidad a entornos diversos      |
| Baja  | Características avanzadas (ML, historial)      | Evolutivo        | Puede incorporarse en iteraciones futuras      |

**Criterio de precedencia aplicado:**

Se priorizan funcionalidades que impactan directamente la detección de problemas de rendimiento y la evidencia de calidad. Las mejoras de experiencia o extensiones quedan subordinadas al cumplimiento del núcleo funcional.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

9. <span id="_Toc52661354" class="anchor"></span>**Otros requerimientos del producto**

**9.1 Estándares legales**

- Respetar términos de uso de APIs y servicios consultados.
- Mantener atribución de bibliotecas de terceros utilizadas (licencias en pyproject.toml).
- Preservar buenas prácticas de propiedad intelectual en contexto académico.
- Evitar inclusion de datos sensibles (credenciales, consultas médicas/financieras) en reportes compartidos públicamente.
- Cumplir con regulaciones de protección de datos (GDPR, CCPA si aplica) en contexto educativo.

**9.2 Estándares de comunicación**

- Reportar resultados con lenguaje técnico claro y verificable.
- Documentar cambios relevantes mediante control de versiones del repositorio.
- Facilitar trazabilidad entre requisitos (FD02), implementación (código) y pruebas (suite de test).
- Mantener README.md actualizado con cambios de API y nuevos motores soportados.
- Proporcionar guías de inicio rápido y ejemplos para cada motor de BD soportado.

**9.3 Estándares de cumplimiento de la plataforma**

- Cumplir convenciones Python (PEP 8, PEP 257 para docstrings estilo Google).
- Utilizar type hints en todas las funciones (Mypy type checking).
- Mantener estructura modular del código (`adapters/`, `core/`, `config/`, `cli/`, `tui/`).
- Preservar compatibilidad con Python 3.14+ (usar features estables, evitar beta).
- Mantener salida JSON estable y documentada para integración externa (no cambios breaking sin versión mayor).

**9.4 Estándares de calidad y seguridad**

- Ejecutar pruebas unitarias para componentes críticos (parsers, detectores).
- Ejecutar pruebas de integración con servicios reales de BD (PostgreSQL, MongoDB, etc.) en Docker.
- Manejar errores de conexión y timeouts con mensajes controlados y retry logic.
- No realizar cambios destructivos en el servidor de base de datos (análisis read-only).
- Priorizar transparencia del reporte (detalle de patrón, severidad, impacto).
- Encriptar credenciales en perfiles guardados; no exponer en logs o output.
- Validar input de usuario para evitar inyección SQL o comandos maliciosos.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

<span id="_Toc52661355" class="anchor"></span>**CONCLUSIONES**

1. La visión del proyecto queda definida con mayor precisión técnica y académica, delimitando claramente su alcance (13+ motores de BD), sus fronteras (no es APM, no es CI/CD profundo) y su contexto educativo.

2. Query Performance Analyzer responde a una necesidad concreta de análisis unificado de rendimiento de consultas en entornos multi-motor, particularmente en contextos educativos y equipos de desarrollo ágil.

3. La estructura funcional implementada en CLI/TUI, junto con salida en consola enriquecida y JSON, habilita tanto uso manual como semiautomatizado en pipelines.

4. El documento establece criterios medibles de calidad (correctitud >= 90%, confiabilidad >= 95%, performance <= 30s) que permiten evaluar el avance del producto de forma objetiva.

5. La priorizacion propuesta (núcleo: parsing + anti-patrones + score; media: TUI + JSON; baja: features avanzadas) favorece la entrega de valor real en versión 1.0 y ordena su evolución futura.

6. La modularidad mediante patrón Adapter reduce fricción para agregar nuevos motores de BD sin modificación de código existente, favoreciendo mantenibilidad a largo plazo.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

<span id="_Toc52661356" class="anchor"></span>**RECOMENDACIONES**

1. Mantener sincronizados `docs/FD01-Informe-Factibilidad.md`, `docs/FD02-Informe-Vision.md` y `README.md` en cada iteración del proyecto para evitar divergencia de información.

2. Incorporar una matriz de trazabilidad formal (Requisito RF-XX → Módulo → Prueba → Issue GitHub) como anexo del proyecto para facilitar verificación de cobertura.

3. Definir una línea base de medición para los indicadores de calidad (tiempo de análisis, tasa de éxito, cobertura de test) para validar cumplimiento de metas.

4. Fortalecer pruebas para escenarios de error (timeouts, BD inaccesible, versiones no soportadas) y proyectos con configuraciones no estándar.

5. Evaluar, en fases posteriores a v1.0, funciones de apoyo como histórico de cambios de rendimiento, integración con herramientas de monitoreo y machine learning para predicción de problemas.

6. Considerar publicación en PyPI y documentación en readthedocs.org para mejorar descubribilidad comunitaria y adopción fuera del contexto académico.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

<span id="_Toc52661357" class="anchor"></span>**BIBLIOGRAFÍA**

1. Pressman, R. S., & Maxim, B. R. (2020). *Software Engineering: A Practitioner's Approach* (10th ed.). McGraw-Hill Education.

2. Sommerville, I. (2016). *Software Engineering* (10th ed.). Pearson.

3. ISO/IEC 25010:2011. *Systems and software quality models*. International Organization for Standardization.

4. Kleppmann, M. (2017). *Designing Data-Intensive Applications: The Big Ideas Behind Reliable, Scalable, and Maintainable Systems*. O'Reilly Media.

5. Garcia-Molina, H., Ullman, J. D., & Widom, J. (2009). *Database Systems: The Complete Book* (2nd ed.). Prentice Hall.

6. PostgreSQL Global Development Group. (2026). *PostgreSQL Documentation: EXPLAIN*.

7. Oracle Corporation. (2026). *MySQL 8.0 Reference Manual: EXPLAIN Output Format*.

8. MongoDB, Inc. (2026). *MongoDB Manual: Aggregation Pipeline Explain Output*.

9. Amazon Web Services. (2026). *AWS DynamoDB Developer Guide: PartiQL Select Statements*.

10. The Elasticsearch Company. (2026). *Elasticsearch Documentation: Profiling Queries*.

11. Neo4j, Inc. (2026). *Neo4j Cypher Manual: EXPLAIN*.

12. JetBrains. (2026). *Kotlin Documentation*.

13. Tiobe. (2026). *Tiobe Index: Python Popularity in 2026*.

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>

<span id="_Toc52661358" class="anchor"></span>**WEBGRAFÍA**

- Repositorio del proyecto: [GitHub - Query Performance Analyzer](https://github.com/estudiantes/query-performance-analyzer)
- Documentación principal: [README.md](../../README.md)
- Documento de factibilidad: [docs/FD01-Informe-Factibilidad.md](./FD01-Informe-Factibilidad.md)
- Configuración de build: [pyproject.toml](../../pyproject.toml)
- Punto de entrada CLI: [query_analyzer/cli/main.py](../../query_analyzer/cli/main.py)
- Punto de entrada TUI: [query_analyzer/tui/app.py](../../query_analyzer/tui/app.py)
- Motor de análisis: [query_analyzer/core/anti_pattern_detector.py](../../query_analyzer/core/anti_pattern_detector.py)
- Interfaz de adaptadores: [query_analyzer/adapters/base.py](../../query_analyzer/adapters/base.py)
- Registro de adaptadores: [query_analyzer/adapters/registry.py](../../query_analyzer/adapters/registry.py)

**Documentación oficial de tecnologías utilizadas:**

- https://www.python.org/doc/
- https://typer.tiangolo.com/
- https://textual.textualize.io/
- https://docs.pydantic.dev/latest/
- https://rich.readthedocs.io/
- https://www.postgresql.org/docs/
- https://dev.mysql.com/doc/
- https://docs.mongodb.com/
- https://docs.aws.amazon.com/dynamodb/
- https://www.elastic.co/guide/en/elasticsearch/reference/current/
- https://neo4j.com/docs/
- https://docs.redis.com/
- https://cassandra.apache.org/doc/

<div style="page-break-after: always; visibility: hidden">\pagebreak</div>
