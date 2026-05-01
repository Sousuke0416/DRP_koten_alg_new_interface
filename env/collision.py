"""
env/collision.py
衝突判定モジュール

ルール:
  - エージェント間の連続座標距離が COLLISION_THRESHOLD 未満の場合に衝突とみなす
  - 衝突したエージェントはその step の移動をキャンセルし COLLIDED 状態になる
  - ゴール済みエージェントは衝突判定から除外する
"""

from __future__ import annotations
from typing import List, Set, Tuple

from agents.agent import Agent, AgentStatus

COLLISION_THRESHOLD: float = 5.0  # 距離がこの値「未満」で衝突


def detect_collisions(agents: List[Agent]) -> Set[int]:
    """
    全エージェントペアを検査し、衝突しているエージェント ID の集合を返す。
    ゴール済み・到達不能エージェントは対象外。
    """
    active = [a for a in agents if a.status == AgentStatus.MOVING]
    collided_ids: Set[int] = set()

    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            a, b = active[i], active[j]
            dist = a.distance_to(b)
            if dist < COLLISION_THRESHOLD:
                collided_ids.add(a.agent_id)
                collided_ids.add(b.agent_id)

    return collided_ids


def check_node_conflicts(agents: List[Agent]) -> List[Tuple[int, int]]:
    """
    同一ノード上に複数エージェントがいるケースを検出する（デバッグ用）。
    返り値: [(node_id, agent_id), ...]
    """
    from collections import defaultdict
    node_map = defaultdict(list)
    for a in agents:
        if a.status == AgentStatus.MOVING:
            node_map[a.current_node].append(a.agent_id)
    conflicts = []
    for node, ids in node_map.items():
        if len(ids) > 1:
            for aid in ids:
                conflicts.append((node, aid))
    return conflicts
