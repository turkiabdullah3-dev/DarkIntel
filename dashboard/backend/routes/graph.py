from fastapi import APIRouter, Depends, Query

from darkintel.graph import GraphStore

from ..dependencies import MAX_GRAPH_NODES, cases_root
from ..schemas import AnalystGraphEdgeCreate, AnalystGraphNodeCreate
from ..services.graph import graph_data, node_detail, path

router = APIRouter(prefix="/cases/{case_id}/graph", tags=["graph"])


@router.get("")
def graph(case_id: str, node_type: str | None = Query(None, max_length=64),
          relationship: str | None = Query(None, max_length=64), min_confidence: float = Query(0, ge=0, le=1),
          origin: str | None = Query(None, pattern="^(system|analyst)$"),
          value: str | None = Query(None, min_length=1, max_length=4_000),
          max_nodes: int = Query(MAX_GRAPH_NODES, ge=1, le=MAX_GRAPH_NODES), root=Depends(cases_root)):
    return graph_data(root, case_id, node_type, relationship, min_confidence, origin, value, max_nodes)


@router.get("/nodes/{node_id}")
def node(case_id: str, node_id: str, root=Depends(cases_root)):
    return node_detail(root, case_id, node_id)


@router.get("/path")
def graph_path(case_id: str, source: str = Query(alias="from", min_length=36, max_length=36),
               target: str = Query(alias="to", min_length=36, max_length=36),
               max_depth: int = Query(4, ge=1, le=6), root=Depends(cases_root)):
    return path(root, case_id, source, target, max_depth)


@router.post("/nodes", status_code=201)
def add_node(case_id: str, request: AnalystGraphNodeCreate, root=Depends(cases_root)):
    return GraphStore(root).add_node(case_id, request.type, request.value, request.label).to_dict()


@router.post("/edges", status_code=201)
def add_edge(case_id: str, request: AnalystGraphEdgeCreate, root=Depends(cases_root)):
    return GraphStore(root).add_edge(case_id, request.source, request.target,
                                     request.relationship, request.confidence).to_dict()
