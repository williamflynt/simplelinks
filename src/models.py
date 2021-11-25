import logging
import random
import string
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

import graphviz as g

logger = logging.getLogger(__name__)


class VertexEntity:
    def __init__(self, vtx_type, entity: str):
        if entity not in vtx_type.raw_entities:
            raise AttributeError(
                f"vtx_type '{vtx_type.vertex_id}' does not have entity '{entity}'"
            )
        self.vtx_type = vtx_type
        self.entity = entity

    @property
    def key(self) -> str:
        return f"{self.entity}.{self.vtx_type.vertex_id}"

    def __eq__(self, other):
        if not hasattr(other, "key"):
            return False
        return self.key == other.key

    def __repr__(self) -> str:
        return f"{self.entity}"

    def __hash__(self):
        return hash(self.key)


class VertexType:
    """A vtx_type in our Graph, containing a collection of VertexEntity."""

    def __init__(
        self,
        entities: List[str],
        vertex_id: str = None,
        name: str = None,
        central: bool = False,
    ) -> None:
        """Create a new VertexType with the specified entities and vertex_id."""
        self.vertex_id = vertex_id or self._make_id()
        self.name = name or self.vertex_id
        self.raw_entities = [f for f in entities if f]
        self.entities_table = {f: self._entity(f) for f in entities if f}
        self.central = central

    def add_entity(self, f: str) -> VertexEntity:
        """Add a entity and return the VertexEntity."""
        if not f:
            raise ValueError(f"cannot empty string as entity - got '{f}'")
        self.raw_entities.append(f)
        self.entities_table[f] = self._entity(f)
        return self.entities_table[f]

    def entity_by_name(self, f: str) -> Optional[VertexEntity]:
        """Get a entity by name, or None if it doesn't exist."""
        return self.entities_table.get(f)

    @property
    def entities(self) -> List[VertexEntity]:
        return list(self.entities_table.values())

    def _entity(self, entity: str) -> VertexEntity:
        """
        Returns a VertexEntity instance.

        :returns: VertexEntity
        """
        return VertexEntity(self, entity)

    @classmethod
    def _make_id(cls) -> str:
        """Make a random vtx_type ID."""
        r_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"vtx_type-{r_str}"

    def __bool__(self):
        return True

    def __eq__(self, other) -> bool:
        if not other:
            return False
        return self.vertex_id == other.vertex_id

    def __hash__(self) -> int:
        return hash(self.vertex_id)

    def __iter__(self):
        for gnf in self.entities:
            yield gnf

    def __len__(self):
        return len(self.entities_table)

    def __repr__(self):
        return f"{self.name} ({self.vertex_id})"


class Edge:
    """
    A mapping of VertexEntity, with optional ID and arbitrary edge type.

    The edge_type, if added, makes this into a "triple", useful in RDF-type graphs.
    """

    def __init__(
        self,
        from_: VertexEntity,
        to_: VertexEntity,
        edge_id: int = None,
        edge_type: str = None,
        directed: bool = False,
    ) -> None:
        """Create a Edge between two VertexEntity."""
        if not from_ or not to_:
            raise ValueError("must have from_ and to_ for Edge")
        self.from_ = from_
        self.to_ = to_
        self.edge_id = edge_id
        self.edge_type = edge_type
        self.directed = directed

    @property
    def type_string(self) -> str:
        t = "---"
        if self.edge_type is not None:
            t = f"--.{self.edge_type}.--"
        if self.directed:
            t = t + ">>"  # Make an arrow.
        return t

    @property
    def entity(self) -> str:
        return f"{self.from_.entity} -> {self.to_.entity}"

    @property
    def sumhash(self) -> int:
        """Sumhash is a symmetric way of showing the vertices in this edge."""
        return hash(self.from_.key) + hash(self.to_.key)

    def __repr__(self):
        s = f"[{self.from_.key}] {self.type_string} [{self.to_.key}]"
        if self.edge_id is not None:
            s = f"({self.edge_id}) " + s
        return s

    def __eq__(self, other):
        if not self.directed:
            if self.edge_type != other.edge_type:
                return False
            return self.sumhash == other.sumhash
        return (
            self.from_ == other.from_
            and self.to_ == other.to_
            and self.edge_type == other.edge_type
        )

    def __hash__(self):
        if not self.directed:
            # The sumhash is the same if the relation is defined either way.
            # We are just differing on edge_type
            sumhash = hash(self.from_.key) + hash(self.to_.key)
            return hash(":".join([str(sumhash), self.edge_type or ""]))
        s = ":".join([self.from_.key, self.to_.key, self.edge_type or ""])
        return hash(s)


class EdgeCollection:
    """A collection of Edge that can be used for N VertexTypes."""

    def __init__(self, *edges: Edge) -> None:
        # If we set sumhash_sensitive, do not add an edge if the linked entities
        # already have any other edge and the new edge is undirected.
        self.sumhash_sensitive = False
        # The attr_idx_map answers the question "do we have a Edge for this?"
        # Maps to a value corresponding to the list of indexes containing the key.
        self.attr_idx_map: Dict[str, List[int]] = defaultdict(list)
        # The IDs for all edges we've ever seen. Pure GUI/referential sugar.
        self.id_ledger: List[int] = []
        # Initialize with the provided entity_pairs.
        self.edges = []
        self.edges = self.add(*edges)

    def add(self, *edges: Edge) -> List[Edge]:
        """Add a ready-to-go Edge (with optional edge_id) to collection."""
        for r in edges:
            if r.edge_id is None:
                r.edge_id = self._next_id()
            self._add(r)
        return self.edges

    def delete_by_attrs(
        self,
        *,
        from_: VertexEntity = None,
        to_: VertexEntity = None,
        edge_type: str = None,
    ) -> int:
        """Remove zero to N GraphEdges by attributes."""
        intersection = self._get_for_attrs_idx(
            from_=from_, to_=to_, edge_type=edge_type
        )
        return self._delete(intersection)

    def delete_by_id(self, *edge_ids: int) -> int:
        indexes = []
        for edge_id in edge_ids:
            indexes.extend(self.attr_idx_map[self._key_id(edge_id)])
        return self._delete(indexes)

    def delete_self_ref(self) -> None:
        """Remove Edges that reference the same VertexEntity for from_ and to_."""
        idx = [i for i, r in enumerate(self.edges) if r.from_ == r.to_]
        self._delete(idx)

    def fetch(self, edge_id: int) -> Optional[Edge]:
        vals = self.attr_idx_map[self._key_id(edge_id)]
        if vals:
            return self.edges[vals[0]]
        return None

    def get_for_attrs(
        self,
        *,
        from_: VertexEntity = None,
        to_: VertexEntity = None,
        edge_type: str = None,
    ) -> List[Edge]:
        intersection = self._get_for_attrs_idx(
            from_=from_, to_=to_, edge_type=edge_type
        )
        if intersection:  # Useful for debugging.
            return [self.edges[i] for i in intersection]
        return []

    @property
    def edges_by_vertex(self) -> Dict[VertexType, List[VertexEntity]]:
        """Return a dictionary of VertexType -> the entities that have entity_pairs here."""
        d = defaultdict(list)
        for r in self.edges:
            d[r.from_.vtx_type].append(r.from_)
            d[r.to_.vtx_type].append(r.to_)
        return d

    def _add(self, r: Edge) -> None:
        """Add the edge to our tracking sets."""
        if r in self.edges:
            # This exact edge exists - determined by Edge.__eq__
            return
        if self.sumhash_sensitive and not r.directed:
            if self._key_sumhash(r.sumhash) in self.attr_idx_map:
                # Another edge already exists for the vertices in this Edge.
                return
        self.edges.append(r)
        idx = len(self.edges) - 1
        self._add_to_tables(r, idx)

    def _add_to_tables(self, r: Edge, idx: int) -> List[str]:
        """Add the edge to our tracking sets."""
        keys = [
            self._key_from(r.from_.key),
            self._key_to(r.to_.key),
            self._key_sumhash(r.sumhash),
        ]
        if r.edge_type:
            keys.append(self._key_type(r.edge_type))

        if r.edge_id is not None:
            keys.append(self._key_id(r.edge_id))
            self.id_ledger.append(r.edge_id)

        for k in keys:
            self.attr_idx_map[k].append(idx)
        return keys

    def _delete(self, indexes: Iterable[int]) -> int:
        """Remove the GraphEdges at the given indexes from the collection."""
        # Remove from the main list first...
        new_edges = [r for i, r in enumerate(self.edges) if i not in indexes]
        # Get diff empirically, before setting self.entity_pairs to new list.
        diff_rels = len(self.edges) - len(new_edges)
        # Rebuild our entire underlying structures to reflect the removal of items.
        self.attr_idx_map = defaultdict(list)
        self.edges = []
        self.add(*new_edges)
        return diff_rels

    def _get_for_attrs_idx(
        self,
        *,
        from_: VertexEntity = None,
        to_: VertexEntity = None,
        edge_type: str = None,
    ) -> Iterable[int]:
        buckets = []
        if from_:
            k = self._key_from(from_.key)
            buckets.append(self.attr_idx_map[k])
        if to_:
            k = self._key_to(to_.key)
            buckets.append(self.attr_idx_map[k])
        if edge_type:
            k = self._key_type(edge_type)
            buckets.append(self.attr_idx_map[k])
        intersection = set.intersection(*[set(b) for b in buckets])
        return intersection

    @staticmethod
    def _key(prefix: str, stringable: str) -> str:
        """Make a double-colon-separated key from a stringable object."""
        return f"{prefix}::{stringable}"

    def _key_from(self, stringable) -> str:
        """Make a key for from_."""
        return self._key("id", stringable)

    def _key_id(self, stringable) -> str:
        """Make a key for edge_id."""
        return self._key("id", stringable)

    def _key_sumhash(self, stringable) -> str:
        """Make a key for sumhash."""
        return self._key("sumhash", stringable)

    def _key_to(self, stringable) -> str:
        """Make a key for to_."""
        return self._key("to", stringable)

    def _key_type(self, stringable) -> str:
        """Make a key for edge_type."""
        return self._key("type", stringable)

    def _next_id(self) -> int:
        """Generate the next available ID in our collection."""
        new_id = 0
        if self.id_ledger:
            new_id = max(self.id_ledger) + 1
        return new_id

    def __iter__(self):
        for item in self.edges:
            yield item

    def __len__(self):
        return len(self.edges)


class Graph:
    """A directed graph."""

    def __init__(
        self,
        *vtx_types: VertexType,
        entity_pairs: List[Tuple[VertexEntity, VertexEntity]] = None,
    ) -> None:
        """
        Create a new instance of Graph with the specified vtx_types and entity_pairs.
        """
        self.vtx_types = list(vtx_types)
        self.edges = EdgeCollection()
        if entity_pairs:
            for r in entity_pairs:
                self.edges.add(Edge(r[0], r[1]))
        self._uid = "m-" + "".join(random.choices(string.ascii_lowercase, k=5))

    def add_edges(self, *groups: List[VertexEntity], edge_type: str = None):
        """Create N-M new GraphEdges."""
        paired_groups = []
        for i, group in enumerate(groups):
            for j, other in enumerate(groups):
                if i == j:
                    continue
                paired_groups.append((group, other))

        for pair in paired_groups:
            x, y = pair
            self._add_edges(x, y, edge_type=edge_type)

    def add_edges_central(
        self,
        *groups: List[VertexEntity],
        central_vtx_type: VertexType,
        edge_type: str = None,
    ):
        """
        Create N-M new GraphEdges.

        Only create entity_pairs TO the central_vtx_type vtx_type FROM other groups.

        This requires groups to be pre-grouped by VertexType.

        Create all Edge class instances first, then add, to ensure we
        do exhaustive error checking before committing changes to the
        underlying EdgeCollection.
        """
        paired_groups = []
        for i, group in enumerate(groups):
            if not group:
                continue
            for j, other in enumerate(groups):
                if not other:
                    continue
                if i == j:
                    continue
                paired_groups.append((group, other))

        edges = []
        for pair in paired_groups:
            x, y = pair
            if not x or not y:
                continue
            if x[0].vtx_type != central_vtx_type and y[0].vtx_type != central_vtx_type:
                continue
            if x[0].vtx_type == y[0].vtx_type:
                continue
            central, non = y, x
            if x[0].vtx_type == central_vtx_type:
                central, non = x, y
            c_vertex = None  # For pre-grouping testing.
            n_vertex = None  # For pre-grouping testing.
            n_checked_flag = False
            for c in central:
                if c_vertex is None:
                    c_vertex = c.vtx_type
                if c_vertex != c.vtx_type:
                    raise ValueError("groups must contain only one VertexType")
                for n in non:
                    if n_checked_flag is False:
                        if n_vertex is None:
                            n_vertex = n.vtx_type
                        if n_vertex != n.vtx_type:
                            raise ValueError("groups must contain only one VertexType")
                    if c == n:
                        continue
                    edges.append(Edge(n, c, edge_type=edge_type))
                n_checked_flag = True  # Show that we checked `non` for good pre-group.

        self.edges.add(*edges)

    def add_edges_dir(
        self,
        from_: List[VertexEntity],
        to_: List[VertexEntity],
        edge_type: str = None,
    ):
        """Create N-M new directed GraphEdges."""
        self._add_edges(from_, to_, edge_type=edge_type, directed=True)

    def remove_edge(self, *edge_ids: int) -> None:
        self.edges.delete_by_id(*edge_ids)

    def write(self, central_vtx_type: Optional[VertexType] = None) -> None:
        """
        Write the graph as DOT and CSV. Honor an optional central_vtx_type VertexType.
        """
        dot = g.Graph(comment="Graph")
        for n in self.vtx_types:
            dot.node(
                n.vertex_id, n.name.upper(), color="dodgerblue", fontcolor="dodgerblue3"
            )
        for r in self.edges.edges:
            dot.node(r.to_.key, f"{r.to_.entity}", color="gray28", fontcolor="gray14")
            dot.edge(r.to_.vtx_type.vertex_id, r.to_.key, color="dodgerblue")

            dot.node(
                r.from_.key, f"{r.from_.entity}", color="gray28", fontcolor="gray14"
            )
            dot.edge(r.from_.vtx_type.vertex_id, r.from_.key, color="dodgerblue")

            dot.edge(
                r.from_.key,
                r.to_.key,
                label=r.edge_type,
                r_id=str(r.edge_id),
                dir=None if r.directed else "none",  # Graphviz-specific attr.
                color="gray",
                fontcolor="gray",
            )
        # Renders as PDF and logs filename.
        fn = dot.render(f"out/{self._uid}-graph-mapping.gv")
        logger.info(fn)
        # Render a CSV for easy entity understanding.
        with open(f"out/{self._uid}-all_entities.gv.csv", "w") as f:
            f.write(
                "entity,vertex_name,vertex_id,vertex_central,edge_type,directed,entity2,vertex_name2,vertex_id2"
            )
            edgeset = set()
            for vertex in self.vtx_types:
                central = vertex == central_vtx_type
                for entity in vertex.entities:
                    edges = self.edges.get_for_attrs(from_=entity)
                    edges = edges + self.edges.get_for_attrs(to_=entity)
                    if edges:
                        edgeset = edgeset.union(set(edges))
                    f.write("\n")
                    f.write(
                        f"{entity.entity},{vertex.name},{vertex.vertex_id},{central},,,,,"
                    )
            for r in edgeset:
                central = r.from_.vtx_type == central_vtx_type
                f.write("\n")
                f.write(
                    f"{r.from_.entity},{r.from_.vtx_type.name},{r.from_.vtx_type.vertex_id},{central},{r.edge_type or ''},{r.directed},{r.to_.entity},{r.to_.vtx_type.name},{r.to_.vtx_type.vertex_id}"
                )

    def _add_edges(
        self,
        from_: List[VertexEntity],
        to_: List[VertexEntity],
        edge_type: str = None,
        directed: bool = False,
    ):
        """Create N-M new directed GraphEdges."""
        for f in from_:
            for t in to_:
                if f == t:
                    continue
                self.edges.add(Edge(f, t, edge_type=edge_type, directed=directed))
