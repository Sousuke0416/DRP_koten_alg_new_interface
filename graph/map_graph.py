"""
graph/map_graph.py
重み付き無向グラフのマップ管理モジュール
"""

from __future__ import annotations
import networkx as nx
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class NodePosition:
    """ノードの2D座標（可視化用）"""
    x: float
    y: float


class MapGraph:
    """
    重み付き無向グラフとして表現されたマップ。
    エッジの重み = 物理的な距離（エージェントの移動距離計算に使用）
    """

    def __init__(self):
        self._graph: nx.Graph = nx.Graph()
        self._positions: Dict[int, NodePosition] = {}

    # ------------------------------------------------------------------ #
    #  構築メソッド
    # ------------------------------------------------------------------ #

    def add_node(self, node_id: int, x: float = 0.0, y: float = 0.0) -> None:
        """ノードを追加する"""
        self._graph.add_node(node_id)
        self._positions[node_id] = NodePosition(x, y)

    def add_edge(self, u: int, v: int, weight: float = 1.0) -> None:
        """
        無向エッジを追加する。
        weight はエッジの物理的な長さ（移動距離）を表す。
        """
        if u not in self._graph or v not in self._graph:
            raise ValueError(f"ノード {u} または {v} が存在しません。")
        if weight <= 0:
            raise ValueError(f"エッジの重みは正の値でなければなりません。weight={weight}")
        self._graph.add_edge(u, v, weight=weight)

    # ------------------------------------------------------------------ #
    #  クエリメソッド
    # ------------------------------------------------------------------ #

    @property
    def nodes(self) -> List[int]:
        return list(self._graph.nodes)

    @property
    def edges(self) -> List[Tuple[int, int, float]]:
        return [(u, v, d["weight"]) for u, v, d in self._graph.edges(data=True)]

    def neighbors(self, node_id: int) -> List[int]:
        return list(self._graph.neighbors(node_id))

    def edge_weight(self, u: int, v: int) -> float:
        if not self._graph.has_edge(u, v):
            raise ValueError(f"エッジ ({u}, {v}) は存在しません。")
        return self._graph[u][v]["weight"]

    def has_node(self, node_id: int) -> bool:
        return self._graph.has_node(node_id)

    def has_edge(self, u: int, v: int) -> bool:
        return self._graph.has_edge(u, v)

    def get_position(self, node_id: int) -> Optional[NodePosition]:
        return self._positions.get(node_id)

    def position_dict(self) -> Dict[int, Tuple[float, float]]:
        """networkx の draw 関数用に {node: (x, y)} 形式で返す"""
        return {n: (p.x, p.y) for n, p in self._positions.items()}

    def shortest_path(self, src: int, dst: int) -> Optional[List[int]]:
        """Dijkstra 法による最短経路（ノードリスト）を返す。到達不能なら None。"""
        try:
            return nx.dijkstra_path(self._graph, src, dst, weight="weight")
        except nx.NetworkXNoPath:
            return None
        except nx.NodeNotFound:
            return None

    def shortest_path_length(self, src: int, dst: int) -> Optional[float]:
        """最短経路の総重み（距離）を返す。到達不能なら None。"""
        try:
            return nx.dijkstra_path_length(self._graph, src, dst, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def is_reachable(self, src: int, dst: int) -> bool:
        return nx.has_path(self._graph, src, dst)

    # ------------------------------------------------------------------ #
    #  ファクトリメソッド
    # ------------------------------------------------------------------ #

    @classmethod
    def from_dict(cls, map_data: dict) -> "MapGraph":
        """
        辞書形式のマップ定義からグラフを構築する。

        map_data 形式:
        {
            "nodes": [
                {"id": 0, "x": 0.0, "y": 0.0},
                ...
            ],
            "edges": [
                {"u": 0, "v": 1, "weight": 3.0},
                ...
            ]
        }
        """
        g = cls()
        for node in map_data.get("nodes", []):
            g.add_node(node["id"], node.get("x", 0.0), node.get("y", 0.0))
        for edge in map_data.get("edges", []):
            g.add_edge(edge["u"], edge["v"], edge.get("weight", 1.0))
        return g

    def __repr__(self) -> str:
        return (f"MapGraph(nodes={len(self._graph.nodes)}, "
                f"edges={len(self._graph.edges)})")
