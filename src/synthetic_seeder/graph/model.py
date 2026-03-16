"""Graph model for schema relationships (tables and foreign keys)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from synthetic_seeder.schema import TableDef


@dataclass
class GraphNode:
    table_name: str
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    parent_table: str
    child_table: str
    fk_name: str | None = None


@dataclass
class SchemaGraph:
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)

    def add_edge(self, parent: str, child: str, fk_name: str | None = None) -> None:
        parent_key = parent.strip()
        child_key = child.strip()
        if parent_key not in self.nodes:
            self.nodes[parent_key] = GraphNode(table_name=parent_key)
        if child_key not in self.nodes:
            self.nodes[child_key] = GraphNode(table_name=child_key)
        self.nodes[parent_key].children.append(child_key)
        self.nodes[child_key].parents.append(parent_key)
        self.edges.append(GraphEdge(parent_table=parent_key, child_table=child_key, fk_name=fk_name))

    def roots(self) -> list[str]:
        """Tables with no parents (no incoming FKs)."""
        return [name for name, node in self.nodes.items() if not node.parents]

    def leaves(self) -> list[str]:
        """Tables with no children (no outgoing FKs)."""
        return [name for name, node in self.nodes.items() if not node.children]

