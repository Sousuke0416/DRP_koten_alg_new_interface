"""
utils/map_presets.py
よく使うマップのプリセット定義
"""

from __future__ import annotations


def grid_map(rows: int, cols: int, weight: float = 5.0) -> dict:
    """
    rows × cols のグリッドグラフを生成する。
    ノード ID = row * cols + col
    エッジの重みはすべて weight（デフォルト 5.0）。
    """
    nodes = []
    edges = []

    for r in range(rows):
        for c in range(cols):
            nid = r * cols + c
            nodes.append({"id": nid, "x": float(c * 10), "y": float(r * 10)})

    for r in range(rows):
        for c in range(cols):
            nid = r * cols + c
            if c + 1 < cols:
                edges.append({"u": nid, "v": nid + 1, "weight": weight})
            if r + 1 < rows:
                edges.append({"u": nid, "v": nid + cols, "weight": weight})

    return {"nodes": nodes, "edges": edges}


def line_map(n_nodes: int, weight: float = 5.0) -> dict:
    """一直線のグラフ（ノード 0—1—2—…—n_nodes-1）"""
    nodes = [{"id": i, "x": float(i * 10), "y": 0.0} for i in range(n_nodes)]
    edges = [{"u": i, "v": i + 1, "weight": weight} for i in range(n_nodes - 1)]
    return {"nodes": nodes, "edges": edges}


def star_map(n_leaves: int, center_weight: float = 5.0, leaf_weight: float = 5.0) -> dict:
    """
    中央ノード（ID=0）からリーフが放射状に伸びるスターグラフ。
    リーフ ID = 1 ～ n_leaves
    """
    import math
    nodes = [{"id": 0, "x": 0.0, "y": 0.0}]
    edges = []
    for i in range(1, n_leaves + 1):
        angle = 2 * math.pi * (i - 1) / n_leaves
        nodes.append({
            "id": i,
            "x": round(10 * math.cos(angle), 2),
            "y": round(10 * math.sin(angle), 2),
        })
        edges.append({"u": 0, "v": i, "weight": center_weight})
    return {"nodes": nodes, "edges": edges}


def custom_map(
    nodes: list,   # [{"id": int, "x": float, "y": float}, ...]
    edges: list,   # [{"u": int, "v": int, "weight": float}, ...]
) -> dict:
    """任意のノード・エッジリストをそのままマップ辞書として返す"""
    return {"nodes": nodes, "edges": edges}
