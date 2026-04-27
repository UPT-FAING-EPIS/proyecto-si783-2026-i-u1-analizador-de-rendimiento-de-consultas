"""Unit tests for MSSQL SHOWPLAN_XML parser."""

import pytest

SIMPLE_SEEK_XML = """<?xml version="1.0" encoding="utf-16"?>
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan">
  <BatchSequence>
    <Batch>
      <Statements>
        <StmtSimple StatementText="SELECT * FROM users WHERE id = 1">
          <QueryPlan CachedPlanSize="16">
            <RelOp NodeId="0" PhysicalOp="Clustered Index Seek"
                   LogicalOp="Clustered Index Seek"
                   EstimateRows="1" EstimatedTotalSubtreeCost="0.0032831">
              <Object Database="[test]" Schema="[dbo]" Table="[users]"
                      Index="[pk_users]" />
            </RelOp>
          </QueryPlan>
        </StmtSimple>
      </Statements>
    </Batch>
  </BatchSequence>
</ShowPlanXML>"""

TABLE_SCAN_XML = """<?xml version="1.0" encoding="utf-16"?>
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan">
  <BatchSequence>
    <Batch>
      <Statements>
        <StmtSimple>
          <QueryPlan>
            <RelOp NodeId="0" PhysicalOp="Table Scan"
                   LogicalOp="Table Scan"
                   EstimateRows="50000" EstimatedTotalSubtreeCost="2.5">
              <Object Database="[test]" Schema="[dbo]" Table="[large_table]" />
            </RelOp>
          </QueryPlan>
        </StmtSimple>
      </Statements>
    </Batch>
  </BatchSequence>
</ShowPlanXML>"""

NESTED_LOOP_XML = """<?xml version="1.0" encoding="utf-16"?>
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan">
  <BatchSequence>
    <Batch>
      <Statements>
        <StmtSimple>
          <QueryPlan>
            <RelOp NodeId="0" PhysicalOp="Nested Loops"
                   LogicalOp="Inner Join" EstimateRows="100"
                   EstimatedTotalSubtreeCost="0.5">
              <RelOp NodeId="1" PhysicalOp="Table Scan"
                     EstimateRows="10" EstimatedTotalSubtreeCost="0.2">
                <Object Database="[test]" Schema="[dbo]" Table="[orders]" />
              </RelOp>
              <RelOp NodeId="2" PhysicalOp="Clustered Index Seek"
                     EstimateRows="10" EstimatedTotalSubtreeCost="0.3">
                <Object Database="[test]" Schema="[dbo]" Table="[customers]"
                        Index="[pk_customers]" />
              </RelOp>
            </RelOp>
          </QueryPlan>
        </StmtSimple>
      </Statements>
    </Batch>
  </BatchSequence>
</ShowPlanXML>"""

HASH_JOIN_XML = """<?xml version="1.0" encoding="utf-16"?>
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan">
  <BatchSequence>
    <Batch>
      <Statements>
        <StmtSimple>
          <QueryPlan>
            <RelOp NodeId="0" PhysicalOp="Hash Match"
                   LogicalOp="Inner Join" EstimateRows="1000"
                   EstimatedTotalSubtreeCost="5.2">
              <RelOp NodeId="1" PhysicalOp="Table Scan"
                     EstimateRows="500" EstimatedTotalSubtreeCost="1.0">
                <Object Database="[test]" Schema="[dbo]" Table="[line_items]" />
              </RelOp>
              <RelOp NodeId="2" PhysicalOp="Table Scan"
                     EstimateRows="500" EstimatedTotalSubtreeCost="2.0">
                <Object Database="[test]" Schema="[dbo]" Table="[products]" />
              </RelOp>
            </RelOp>
          </QueryPlan>
        </StmtSimple>
      </Statements>
    </Batch>
  </BatchSequence>
</ShowPlanXML>"""


@pytest.fixture
def parser():
    """Create MSSQLExplainParser instance."""
    try:
        from query_analyzer.adapters.sql.sqlserver_parser import MSSQLExplainParser
    except ImportError:
        pytest.skip("MSSQLExplainParser not available")
    return MSSQLExplainParser()


class TestMSSQLExplainParserParse:
    """Tests for parse() method."""

    def test_parse_simple_seek(self, parser) -> None:
        result = parser.parse(SIMPLE_SEEK_XML)
        assert result["node_count"] == 1
        assert result["total_cost"] == pytest.approx(0.0032831)

    def test_parse_table_scan(self, parser) -> None:
        result = parser.parse(TABLE_SCAN_XML)
        assert result["node_count"] == 1
        assert result["total_cost"] == pytest.approx(2.5)
        assert len(result["scan_nodes"]) == 1
        assert result["scan_nodes"][0]["table_name"] == "[large_table]"

    def test_parse_nested_loop(self, parser) -> None:
        result = parser.parse(NESTED_LOOP_XML)
        assert result["node_count"] == 3
        assert len(result["join_nodes"]) >= 1

    def test_parse_hash_join(self, parser) -> None:
        result = parser.parse(HASH_JOIN_XML)
        assert result["node_count"] == 3
        assert len(result["join_nodes"]) >= 1

    def test_parse_most_expensive_node(self, parser) -> None:
        result = parser.parse(HASH_JOIN_XML)
        assert result["most_expensive_node"] != {}
        assert result["most_expensive_node"]["cost"] == pytest.approx(5.2)

    def test_parse_all_nodes_flat(self, parser) -> None:
        result = parser.parse(NESTED_LOOP_XML)
        all_nodes = result["all_nodes"]
        assert len(all_nodes) == 3
        node_types = [n["node_type"] for n in all_nodes]
        assert "Nested Loops" in node_types
        assert "Table Scan" in node_types
        assert "Clustered Index Seek" in node_types


class TestMSSQLExplainParserNormalize:
    """Tests for normalize_plan() method."""

    def test_normalize_xml_string(self, parser) -> None:
        normalized = parser.normalize_plan(SIMPLE_SEEK_XML)
        assert normalized["node_type"] == "Index Seek"
        assert normalized["table_name"] == "[users]"
        assert normalized["estimated_rows"] == 1
        assert normalized["children"] == []

    def test_normalize_table_scan_to_seq_scan(self, parser) -> None:
        normalized = parser.normalize_plan(TABLE_SCAN_XML)
        assert normalized["node_type"] == "Seq Scan"

    def test_normalize_nested_loops(self, parser) -> None:
        normalized = parser.normalize_plan(NESTED_LOOP_XML)
        assert normalized["node_type"] == "Nested Loop"
        assert len(normalized["children"]) == 2

    def test_normalize_hash_match_to_hash_join(self, parser) -> None:
        normalized = parser.normalize_plan(HASH_JOIN_XML)
        assert normalized["node_type"] == "Hash Join"

    def test_normalize_dict_input(self, parser) -> None:
        parsed = parser.parse(SIMPLE_SEEK_XML)
        node = parsed["all_nodes"][0]
        normalized = parser.normalize_plan(node)
        assert normalized["node_type"] in ("Index Seek", "Index Lookup")
        assert normalized["table_name"] == "[users]"

    def test_normalize_preserves_index(self, parser) -> None:
        normalized = parser.normalize_plan(SIMPLE_SEEK_XML)
        assert normalized["index_used"] == "[pk_users]"

    def test_normalize_actual_rows_is_none(self, parser) -> None:
        normalized = parser.normalize_plan(SIMPLE_SEEK_XML)
        assert normalized["actual_rows"] is None
        assert normalized["actual_time_ms"] is None


class TestMSSQLExplainParserMapping:
    """Tests for node type mapping."""

    def test_mapping_contains_expected_keys(self, parser) -> None:
        mapping = parser._get_node_type_mapping()
        assert "Table Scan" in mapping
        assert mapping["Table Scan"] == "Seq Scan"
        assert mapping["Clustered Index Seek"] == "Index Seek"
        assert mapping["Nested Loops"] == "Nested Loop"
        assert mapping["Hash Match"] == "Hash Join"


class TestMSSQLExplainParserEdgeCases:
    """Edge case handling."""

    def test_empty_normalize(self, parser) -> None:
        result = parser.normalize_plan({})
        assert result == {}

    def test_unknown_node_type_passthrough(self, parser) -> None:
        node = {
            "node_type": "SomeUnknownOp",
            "table_name": "t",
            "estimated_rows": 10,
            "estimated_cost": 1.0,
            "index_name": None,
            "children": [],
        }
        normalized = parser.normalize_plan(node)
        assert normalized["node_type"] == "SomeUnknownOp"
