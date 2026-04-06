r"""CockroachDB EXPLAIN parser.

Per YAGNI principle, reusamos PostgreSQLExplainParser directamente sin crear
una subclase dedicada. El formato JSON de CockroachDB (vía wire protocol) es
compatible con el output JSON de PostgreSQL.

Si emergen tipos de nodos específicos de CRDB o métricas especiales durante
testing, crear una subclase CockroachDBExplainParser en este archivo.
Para v1: reutilizamos directamente PostgreSQLExplainParser.

Nota:
    CockroachDB implementa el wire protocol de PostgreSQL, por lo que los
    planes EXPLAIN (ANALYZE, FORMAT JSON) son sintácticamente compatibles.
    Diferencias semánticas (replicación, distribución) se manejan en nivel
    de adapter, no en el parser.

Ejemplo de futura subclase (si es necesario):

    from .postgresql_parser import PostgreSQLExplainParser

    class CockroachDBExplainParser(PostgreSQLExplainParser):
        '''Parseador especializado para CockroachDB con manejo personalizado.

        Extiende PostgreSQLExplainParser para manejar nodos específicos de CRDB
        como operaciones distribuidas, scans inter-region, etc.
        '''

        def _categorize_joins(self, all_nodes: list[dict[str, Any]]) -> ...:
            # Override si tipos de joins en CRDB difieren significativamente
            pass
"""
