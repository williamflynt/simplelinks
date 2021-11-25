"""Load a CSV file into a Graph."""

import csv
import logging
from typing import Optional, Tuple

from models import Graph, VertexType, Edge, EdgeCollection

logger = logging.getLogger(__name__)


def load(filename: str) -> Tuple[Graph, Optional[VertexType]]:
    """Load a Graph from a CSV file with the given filename."""
    if not filename.endswith(".csv"):
        raise ValueError(f"must input a CSV (text) filename; got '{filename}'")

    with open(filename, "r") as f:
        load_data = _load(f)
    return load_data


def _load(ff) -> Tuple[Graph, Optional[VertexType]]:
    """Load a Graph from a CSV file with the given filename."""
    reader = csv.DictReader(ff)
    central_vertex_id: Optional[str] = None
    vertexs = {}
    edges = []
    required_entities = ["entity", "vertex_id"]
    for i, r in enumerate(reader):
        # VALIDATE REQUIRED entities.
        if i == 0:
            # Only validate headers for the first object, because the rest
            # should have all the headers we need.
            for f in required_entities:
                if f not in r:
                    raise AttributeError(
                        f"input CSV must have at least 'entity' and 'vertex_id' headers"
                    )

        # MAKE VERTEX TYPE.
        vertex_id = r["vertex_id"]
        vertex_name = r.get("vertex_name")
        if not central_vertex_id and (
            vertex_name == "CENTRAL" or bool(r.get("central_vtx_type")) == vertex_id
        ):
            central_vertex_id = vertex_id
        if vertex_id not in vertexs:
            n = _make_vertex(vertex_id, vertex_name, central_vertex_id == vertex_id)
            if n is None:
                continue
            vertexs[vertex_id] = n

        # ADD THIS entity.
        vertex_entity = r["entity"]
        if not vertex_entity:
            logger.error("invalid vtx_type entity", vertex_entity, vertex_id, vertex_name)
        gnf = vertexs[vertex_id].add_entity(vertex_entity)

        # ADD RELATED ENTITY.
        n2_id = r.get("vertex_id2")
        n2_name = r.get("vertex_name2")
        if r.get("entity2") and n2_id:
            n2 = vertexs.get(n2_id)
            if n2 is None:
                n2 = _make_vertex(n2_id, n2_name, central_vertex_id == n2_id)
                vertexs[n2_id] = n2
            n2_entity = r["entity2"]
            if not n2_entity:
                logger.error(
                    "invalid vertex2 entity", vertex_entity, vertex_id, vertex_name
                )
            gnf2 = n2.add_entity(n2_entity)

            # MAKE EDGE TUPLE.
            directed = bool(r.get("directed", False))
            edges.append(
                Edge(
                    gnf,
                    gnf2,
                    edge_id=None,
                    edge_type=r.get("edge_type"),
                    directed=directed,
                )
            )

    # FINAL CENTRALITY UPDATE.
    # This is because we could create a vtx_type before we have a chance to see centrality.
    central_vertex: Optional[VertexType] = vertexs.get(central_vertex_id)
    if central_vertex_id:
        for n_id in vertexs:
            vertexs[n_id].central = central_vertex_id == n_id

    # MAKE MAPPING.
    logger.info(f"mapping with {len(vertexs)} vertexs and {len(edges)} edges")
    r_coll = EdgeCollection(*edges)
    m = Graph(*list(vertexs.values()))
    m.edges = r_coll
    return m, central_vertex


def _make_vertex(
    vertex_id: str, vertex_name: str = None, central: bool = None, *entities: str
) -> Optional[VertexType]:
    """Make a VertexType with a given ID, optional name, and optional entities."""
    if not vertex_id:
        logger.error("empty vertex_id - skipping")
        return
    n = VertexType(list(entities), vertex_id, vertex_name or vertex_id, central)
    return n
