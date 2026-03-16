"""Build a simple relationship graph from NormalizedSchema foreign keys."""

from __future__ import annotations

from synthetic_seeder.schema import NormalizedSchema, TableDef
from synthetic_seeder.graph.model import SchemaGraph


def build_schema_graph(schema: NormalizedSchema) -> SchemaGraph:
    """Build SchemaGraph from a normalized schema's foreign keys."""
    graph = SchemaGraph()
    for table in schema.tables:
        if table.name not in graph.nodes:
            graph.nodes[table.name] = graph.nodes.get(table.name) or graph.nodes.setdefault(
                table.name,  # type: ignore[call-arg]
                graph.nodes.get(table.name) or graph.nodes.setdefault(table.name, None),  # placeholder
            )
        # Ensure node exists cleanly
        if graph.nodes[table.name] is None:  # type: ignore[truthy-function]
            from synthetic_seeder.graph.model import GraphNode

            graph.nodes[table.name] = GraphNode(table_name=table.name)  # type: ignore[assignment]
        for fk in table.foreign_keys:
            parent = fk.target_table
            graph.add_edge(parent=parent, child=table.name, fk_name=fk.name)
    return graph

