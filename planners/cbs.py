"""
planners/cbs.py
Conflict-Based Search (CBS) プランナー

拡張制約:
  1. ゴールノード占有制約
     ゴール到達済みエージェントのゴールノードには他エージェントが進入できない。
  2. エッジ上での方向転換禁止制約
     エッジ走行中のエージェントへの経路再計画時、逆方向の経路は禁止。
     Agent.set_path() がこの制約を実施する。

CBS の概要:
  - 高レベル探索: 衝突を制約として追加しながらノード木を展開
  - 低レベル探索: 制約を満たす単一エージェントの時空間最短経路（A*）
  - 衝突種別:
      ノード衝突  : 同一時刻に同一ノードに 2 体以上
      エッジ衝突  : 同一エッジを逆方向にすれ違う（スワップ衝突）
      ゴール占有  : 到達済みエージェントのゴールノードへの進入

時刻は「ノード到達時刻（step 単位）」として扱う。
エッジ重みが speed=5 の倍数でない場合は ceil で切り上げた step 数を使用。
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from graph.map_graph import MapGraph


# ------------------------------------------------------------------ #
#  型エイリアス
# ------------------------------------------------------------------ #

Path       = List[int]          # ノード列（時刻 0, 1, 2, ... に対応）
AgentId    = int
NodeId     = int
Time       = int                # step 単位の整数時刻

SPEED: float = 5.0              # エージェント速度（Agent クラスと同値）


# ------------------------------------------------------------------ #
#  制約
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class NodeConstraint:
    """agent_id は時刻 time に node_id にいてはいけない"""
    agent_id: AgentId
    node_id:  NodeId
    time:     Time

@dataclass(frozen=True)
class EdgeConstraint:
    """agent_id は時刻 time に u→v のエッジを通ってはいけない"""
    agent_id: AgentId
    u:        NodeId
    v:        NodeId
    time:     Time   # u を出発する時刻


# ------------------------------------------------------------------ #
#  衝突
# ------------------------------------------------------------------ #

@dataclass
class Conflict:
    kind:     str            # "node" | "edge" | "goal"
    agents:   Tuple[AgentId, AgentId]
    node:     Optional[NodeId] = None
    edge:     Optional[Tuple[NodeId, NodeId]] = None
    time:     Time = 0


# ------------------------------------------------------------------ #
#  CBS ノード（高レベル探索の状態）
# ------------------------------------------------------------------ #

@dataclass(order=True)
class CBSNode:
    cost:        int                              # 全エージェントの経路長合計
    constraints: FrozenSet = field(compare=False)
    paths:       Dict[AgentId, Path] = field(compare=False, default_factory=dict)


# ------------------------------------------------------------------ #
#  低レベル探索：制約付き時空間 A*
# ------------------------------------------------------------------ #

def _steps_for_edge(weight: float) -> int:
    """エッジ重みを通過するのに必要な step 数（speed=5 基準, 切り上げ）"""
    return max(1, math.ceil(weight / SPEED))


def _heuristic(graph: MapGraph, node: NodeId, goal: NodeId,
               _cache: dict = {}) -> float:
    key = (id(graph), goal)
    if key not in _cache:
        # goal からの全ノードへの最短距離を一括計算
        import networkx as nx
        try:
            lengths = nx.single_source_dijkstra_path_length(
                graph._graph, goal, weight="weight")
            _cache[key] = dict(lengths)
        except Exception:
            _cache[key] = {}
    d = _cache[key].get(node)
    return (d / SPEED) if d is not None else float("inf")


def spacetime_astar(
    graph:           MapGraph,
    agent_id:        AgentId,
    start:           NodeId,
    goal:            NodeId,
    constraints:     FrozenSet,
    occupied_goals:  Set[NodeId],
    on_edge_next:    Optional[NodeId] = None,
    max_time:        int = 500,
) -> Optional[Path]:
    """
    制約付き時空間 A* で単一エージェントの最短経路を求める。
    状態 = (node, time) で管理し、同一状態を再訪しない。
    """
    node_constraints: Set[Tuple[NodeId, Time]] = set()
    edge_constraints: Set[Tuple[NodeId, NodeId, Time]] = set()

    for c in constraints:
        if isinstance(c, NodeConstraint) and c.agent_id == agent_id:
            node_constraints.add((c.node_id, c.time))
        elif isinstance(c, EdgeConstraint) and c.agent_id == agent_id:
            edge_constraints.add((c.u, c.v, c.time))

    # heap: (f, g, tie_break, node, time, path)
    counter = 0
    open_heap: List[Tuple] = []
    h0 = _heuristic(graph, start, goal)
    heapq.heappush(open_heap, (h0, 0, counter, start, 0, [start]))
    # visited: (node, time) → best g
    visited: Dict[Tuple[NodeId, Time], int] = {}

    while open_heap:
        f, g, _, node, t, path = heapq.heappop(open_heap)

        state = (node, t)
        if state in visited:
            continue
        visited[state] = g

        if node == goal:
            return path

        if t >= max_time:
            continue

        # 待機（その場に留まる）
        nt = t + 1
        if (node, nt) not in node_constraints and (node, nt) not in visited:
            new_g = g + 1
            counter += 1
            heapq.heappush(open_heap,
                (new_g + _heuristic(graph, node, goal), new_g, counter,
                 node, nt, path + [node]))

        # 隣接ノードへの移動
        neighbors = list(graph.neighbors(node))

        # 方向転換禁止：t==0 かつ on_edge_next が指定されている場合
        if on_edge_next is not None and t == 0:
            neighbors = [on_edge_next] if on_edge_next in neighbors else []

        for nb in neighbors:
            # ゴール占有ノードへは進入不可（自分のゴールは除く）
            if nb in occupied_goals and nb != goal:
                continue

            steps    = _steps_for_edge(graph.edge_weight(node, nb))
            arrive_t = t + steps

            if arrive_t > max_time:
                continue

            if (nb, arrive_t) in visited:
                continue

            # ノード制約
            if (nb, arrive_t) in node_constraints:
                continue

            # エッジ制約（u を time に出発することを禁止）
            # A* の t は現在ノードへの到着時刻
            if (node, nb, t) in edge_constraints:
                continue
            # スワップ衝突（逆方向）: nb→node を time+1 に出発 ≒ node→nb と同タイミングすれ違い
            if (nb, node, t) in edge_constraints:
                continue

            new_g = g + steps
            counter += 1
            heapq.heappush(open_heap,
                (new_g + _heuristic(graph, nb, goal), new_g, counter,
                 nb, arrive_t, path + [nb]))

    return None


# ------------------------------------------------------------------ #
#  衝突検出
# ------------------------------------------------------------------ #

def _expand_path(graph: MapGraph, path: Path) -> List[NodeId]:
    """
    ノード列を step 単位に展開する。
    例: [0, 1, 3] でエッジ重みが全て 10（2step）なら
        [0, 0, 1, 1, 3] を返す（各エッジを steps 数分繰り返す）
    """
    if not path:
        return path
    expanded = [path[0]]
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        steps = _steps_for_edge(graph.edge_weight(u, v))
        # steps-1 個の中間状態（u を追加）＋ v
        for _ in range(steps - 1):
            expanded.append(u)
        expanded.append(v)
    return expanded


def _detect_conflicts(
    paths: Dict[AgentId, Path],
    graph: Optional[MapGraph] = None,
) -> Optional[Conflict]:
    """
    パス辞書から最初の衝突を1つ返す（なければ None）。
    graph が与えられた場合はエッジ重みを考慮した step 展開を行う。
    """
    ids = list(paths.keys())

    # step 単位に展開
    if graph is not None:
        expanded = {aid: _expand_path(graph, p) for aid, p in paths.items()}
    else:
        expanded = paths

    max_t = max((len(p) for p in expanded.values()), default=0)

    def node_at(aid: AgentId, t: Time) -> NodeId:
        p = expanded[aid]
        return p[min(t, len(p) - 1)]

    for t in range(max_t):
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a1, a2 = ids[i], ids[j]
                n1, n2 = node_at(a1, t), node_at(a2, t)

                # ノード衝突
                if n1 == n2:
                    return Conflict(kind="node", agents=(a1, a2), node=n1, time=t)

                # エッジ衝突（スワップ）
                n1_next = node_at(a1, t + 1)
                n2_next = node_at(a2, t + 1)
                if n1 == n2_next and n2 == n1_next:
                    return Conflict(kind="edge", agents=(a1, a2),
                                    edge=(n1, n2), time=t)

    return None


# ------------------------------------------------------------------ #
#  CBS 高レベル探索
# ------------------------------------------------------------------ #

class CBSPlanner:
    """
    Conflict-Based Search プランナー。

    使い方:
        planner = CBSPlanner(graph)
        paths = planner.plan(
            starts  = {0: 0, 1: 15},
            goals   = {0: 15, 1: 0},
            occupied_goals = set(),
        )
        # paths[agent_id] = [node_id, node_id, ...]  (step 毎のノード列)
        # 到達不能なら paths[agent_id] = None
    """

    def __init__(self, graph: MapGraph, max_time: int = 500):
        self.graph    = graph
        self.max_time = max_time

    def plan(
        self,
        starts:          Dict[AgentId, NodeId],
        goals:           Dict[AgentId, NodeId],
        occupied_goals:  Set[NodeId] = None,
        on_edge_nexts:   Dict[AgentId, Optional[NodeId]] = None,
    ) -> Dict[AgentId, Optional[Path]]:
        """
        全エージェントの経路を計画する。

        Parameters
        ----------
        starts         : {agent_id: start_node}
        goals          : {agent_id: goal_node}
        occupied_goals : 進入禁止のゴール占有ノード集合
        on_edge_nexts  : エッジ上のエージェントの強制方向 {agent_id: next_node}

        Returns
        -------
        {agent_id: path | None}  None は到達不能
        """
        occupied_goals = occupied_goals or set()
        on_edge_nexts  = on_edge_nexts  or {}
        agent_ids      = list(starts.keys())

        # 初期低レベル計画
        root_paths: Dict[AgentId, Optional[Path]] = {}
        for aid in agent_ids:
            p = spacetime_astar(
                self.graph, aid, starts[aid], goals[aid],
                frozenset(), occupied_goals,
                on_edge_nexts.get(aid),
                self.max_time,
            )
            root_paths[aid] = p

        # 到達不能エージェントは除いて CBS を実行
        reachable = {aid: p for aid, p in root_paths.items() if p is not None}
        unreachable = {aid: None for aid, p in root_paths.items() if p is None}

        if not reachable:
            return unreachable

        root_cost = sum(len(p) for p in reachable.values())
        root = CBSNode(cost=root_cost, constraints=frozenset(), paths=reachable)

        open_list: List[CBSNode] = [root]
        heapq.heapify(open_list)

        while open_list:
            node = heapq.heappop(open_list)

            conflict = _detect_conflicts(node.paths, self.graph)
            if conflict is None:
                # 解を発見
                result = dict(node.paths)
                result.update(unreachable)
                return result

            # 衝突を解消する制約を 2 つ生成
            a1, a2 = conflict.agents
            new_constraints = []

            if conflict.kind == "node":
                new_constraints = [
                    NodeConstraint(a1, conflict.node, conflict.time),
                    NodeConstraint(a2, conflict.node, conflict.time),
                ]
            elif conflict.kind == "edge":
                u, v = conflict.edge
                # conflict.time はexpanded配列でのすれ違い検出時刻（u→vの途中step）
                # A*でのエッジu→v出発時刻 = u への到着時刻
                # expanded上でconflict.time直前のu区間の開始インデックスを出発時刻とする
                # 簡略: A*時刻 = expanded上でuが始まる時刻 = conflict.time - (steps_uv - 1)
                steps_uv = _steps_for_edge(
                    self.graph.edge_weight(u, v) if self.graph.has_edge(u, v) else SPEED)
                steps_vu = _steps_for_edge(
                    self.graph.edge_weight(v, u) if self.graph.has_edge(v, u) else SPEED)
                # expanded[conflict.time] = u (agent0), expanded[conflict.time] = v (agent1)
                # agent0 が u に到着した時刻 = conflict.time - (steps_uv - 1)
                # ただし最低0
                depart_a1 = max(0, conflict.time - (steps_uv - 1))
                depart_a2 = max(0, conflict.time - (steps_vu - 1))
                new_constraints = [
                    EdgeConstraint(a1, u, v, depart_a1),
                    EdgeConstraint(a2, v, u, depart_a2),
                ]

            for new_c in new_constraints:
                new_constraints_set = node.constraints | frozenset([new_c])
                new_paths = dict(node.paths)

                # 制約を受けたエージェントの経路を再計算
                affected = new_c.agent_id
                if affected not in starts:
                    continue

                new_p = spacetime_astar(
                    self.graph, affected,
                    starts[affected], goals[affected],
                    new_constraints_set, occupied_goals,
                    on_edge_nexts.get(affected),
                    self.max_time,
                )
                if new_p is None:
                    continue   # この制約では解なし

                new_paths[affected] = new_p
                new_cost = sum(len(p) for p in new_paths.values())
                child = CBSNode(cost=new_cost,
                                constraints=new_constraints_set,
                                paths=new_paths)
                heapq.heappush(open_list, child)

        # CBS が解を見つけられなかった（タイムアウト等）
        result = {aid: None for aid in agent_ids}
        result.update(unreachable)
        return result