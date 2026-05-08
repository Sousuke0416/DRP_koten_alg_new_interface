"""
planners/pibt.py
Priority Inheritance with Backtracking (PIBT) プランナー

論文: Okumura et al., "Priority Inheritance with Backtracking for
      Iterative Multi-agent Path Finding" (IJCAI 2019)

拡張制約:
  1. ゴールノード占有制約
     ゴール到達済みエージェントのゴールノードには他エージェントが進入できない。
  2. エッジ上での方向転換禁止制約
     エッジ走行中のエージェントは必ず next_node 方向へ進む。
     ノード上にいる場合のみ PIBT が次ノードを決定できる。

PIBT の概要:
  - 各 step で優先度に従い 1 エージェントずつ次ノードを割り当てる
  - 割り当て失敗時は優先度を伝播（バックトラック付き）
  - 計算量は O(k) / step（k = エージェント数）で非常に高速
  - 完全性は保証されないが実用上は優秀

優先度ルール:
  - ゴールに近い（ヒューリスティック値が小さい）エージェントを低優先にする
  - ゴール済みエージェントは最低優先（動かない）
  - 優先度は毎 step 動的に更新
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Set, Tuple

from graph.map_graph import MapGraph

# ------------------------------------------------------------------ #
#  型エイリアス
# ------------------------------------------------------------------ #

AgentId = int
NodeId  = int
SPEED: float = 5.0


# ------------------------------------------------------------------ #
#  ヒューリスティック（ゴールまでの最短経路長 / speed）
# ------------------------------------------------------------------ #

def _h(graph: MapGraph, node: NodeId, goal: NodeId) -> float:
    d = graph.shortest_path_length(node, goal)
    return (d / SPEED) if d is not None else float("inf")

def _steps_for_edge(weight: float) -> int:
    import math
    return max(1, math.ceil(weight / SPEED))


def _steps_for_edge(weight: float) -> int:
    return max(1, math.ceil(weight / SPEED))


# ------------------------------------------------------------------ #
#  PIBT コア
# ------------------------------------------------------------------ #

class PIBTPlanner:
    """
    Priority Inheritance with Backtracking プランナー。

    使い方（reset 後に 1 step 分の次ノードを決定する）:
        planner = PIBTPlanner(graph)
        next_nodes = planner.plan_step(
            current_nodes  = {0: 3, 1: 7},
            goals          = {0: 15, 1: 0},
            occupied_goals = {5},          # ゴール済みエージェントの占有ノード
            on_edge_nexts  = {1: 8},       # エージェント1はエッジ上で8方向強制
        )
        # next_nodes[agent_id] = 次に向かうノード（None = 待機）

    注意:
        PIBT は「次にどのノードへ移動するか」を 1 step ごとに決める。
        エッジ重みが speed の倍数でない場合、エッジ走行中のエージェントは
        on_edge_nexts で方向を固定し、ノード到達まで PIBT の対象外とする。
    """

    def __init__(self, graph: MapGraph, seed: int = 42):
        self.graph = graph
        self._rng  = random.Random(seed)

    def plan_step(
        self,
        current_nodes:  Dict[AgentId, NodeId],
        goals:          Dict[AgentId, NodeId],
        occupied_goals: Set[NodeId]                      = None,
        on_edge_nexts:  Dict[AgentId, Optional[NodeId]] = None,
        prev_nodes:     Dict[AgentId, NodeId]            = None,
        forbidden_edges: Set[Tuple[NodeId, NodeId]]      = None,
    ) -> Dict[AgentId, Optional[NodeId]]:
        """
        1 step 分の次ノードを全エージェント分決定する。

        Parameters
        ----------
        current_nodes  : {agent_id: 現在ノード}
        goals          : {agent_id: ゴールノード}
        occupied_goals : 進入禁止の占有ノード集合
        on_edge_nexts  : エッジ上エージェントの強制方向 {agent_id: next_node}
        prev_nodes     : 直前ノード（スワップ衝突回避用）{agent_id: prev_node}

        Returns
        -------
        {agent_id: next_node | None}
          next_node == current_node の場合は「待機」
        """
        occupied_goals   = occupied_goals   or set()
        on_edge_nexts    = on_edge_nexts    or {}
        prev_nodes       = prev_nodes       or {}
        forbidden_edges  = forbidden_edges  or set()
        agent_ids        = list(current_nodes.keys())

        # ── エッジ上のエージェントは強制方向 ──
        fixed: Dict[AgentId, NodeId] = {}
        free_agents: List[AgentId]   = []

        for aid in agent_ids:
            if aid in on_edge_nexts and on_edge_nexts[aid] is not None:
                fixed[aid] = on_edge_nexts[aid]
            else:
                free_agents.append(aid)

        # ── 優先度計算 ──
        def priority(aid: AgentId) -> float:
            if goals[aid] == current_nodes[aid]:
                return -float("inf")
            h = _h(self.graph, current_nodes[aid], goals[aid])
            return h + self._rng.uniform(0, 1e-6)

        free_agents.sort(key=priority, reverse=True)

        # ── PIBT 本体 ──
        reservations: Dict[NodeId, AgentId] = {}
        for aid, nxt in fixed.items():
            reservations[nxt] = aid

        result: Dict[AgentId, Optional[NodeId]] = dict(fixed)

        def pibt_agent(aid: AgentId, caller: Optional[AgentId]) -> bool:
            cur  = current_nodes[aid]
            goal = goals[aid]

            candidates = list(self.graph.neighbors(cur))
            candidates = [
                nb for nb in candidates
                if (nb not in occupied_goals or nb == goal)
                and (cur, nb) not in forbidden_edges   # 逆走スワップ禁止
            ]
            # スワップ衝突回避: 他エージェントが cur にいて nb に向かう = 自分が nb に行くと衝突
            safe_candidates = []
            for nb in candidates:
                swap = False
                for other_aid, other_cur in current_nodes.items():
                    if other_aid == aid:
                        continue
                    # 相手が nb にいて自分が cur に向かうケース（逆走）
                    if other_cur == nb and cur in list(self.graph.neighbors(nb)):
                        # prev_nodes に cur が入っていれば確実にスワップ
                        if prev_nodes.get(other_aid) == cur:
                            swap = True
                            break
                        # 相手も nb に来たばかり（current==nb）で自分の cur が prev なら危険
                        # → 相手が今 nb にいて自分が cur にいる → 相手が cur に戻る可能性
                        # ここでは「相手が今 nb にいて自分が nb→cur を使う」でスワップ
                        if other_cur == nb and (nb, cur) not in forbidden_edges:
                            # 相手も nb に来たばかりで自分が nb→cur を要求するのは問題ない
                            # 実際のスワップは「自分が nb→cur, 相手が cur→nb 同時」
                            # → result で相手が cur→nb に決まった場合のみ禁止
                            # ここでは reserved で判断
                            pass
                if not swap:
                    safe_candidates.append(nb)
            candidates = safe_candidates if safe_candidates else candidates

            candidates.sort(key=lambda nb: _h(self.graph, nb, goal))
            candidates.append(cur)  # 待機

            for nxt in candidates:
                if nxt in reservations and reservations[nxt] != aid:
                    blocker = reservations[nxt]
                    if blocker == caller:
                        continue
                    if blocker in free_agents and blocker not in result:
                        old_res = reservations.get(nxt)
                        reservations[nxt] = aid
                        success = pibt_agent(blocker, caller=aid)
                        if success:
                            reservations[nxt] = aid
                            result[aid] = nxt
                            return True
                        else:
                            if old_res is not None:
                                reservations[nxt] = old_res
                            else:
                                del reservations[nxt]
                    continue

                reservations[nxt] = aid
                result[aid] = nxt
                return True

            reservations[cur] = aid
            result[aid] = cur
            return False

        for aid in free_agents:
            if aid not in result:
                pibt_agent(aid, caller=None)

        return result

    def plan_full_path(
        self,
        starts:         Dict[AgentId, NodeId],
        goals:          Dict[AgentId, NodeId],
        occupied_goals: Set[NodeId] = None,
        max_steps:      int = 500,
    ) -> Dict[AgentId, Optional[List[NodeId]]]:
        """
        PIBT を繰り返してフルパスを生成する。

        エッジ重み > speed のケースに対応するため、
        step展開ベースで位置追跡し、エッジ走行中スワップを防ぐ。
        """
        occupied_goals = occupied_goals or set()

        # エージェントの状態
        # current_node: 今いるノード（エッジ上の場合は出発ノード）
        # next_node    : 向かっているノード（ノード上なら current と同じ）
        # edge_steps   : エッジ上の残り step 数（0 = ノード上）
        cur_node   = dict(starts)
        nxt_node   = dict(starts)
        edge_steps = {aid: 0 for aid in starts}

        # 返却用のノード列（重複なし、ゴール到達ノードまで）
        node_paths: Dict[AgentId, List[NodeId]] = {aid: [n] for aid, n in starts.items()}
        done: Set[AgentId] = set()

        for _step in range(max_steps * 4):   # step展開なので多めに
            if len(done) == len(starts):
                break

            # ── ノード上のエージェントのみ PIBT で次を決める ──
            on_node = {
                aid for aid in starts
                if aid not in done and edge_steps[aid] == 0
            }
            on_edge = {
                aid for aid in starts
                if aid not in done and edge_steps[aid] > 0
            }

            if not on_node and not on_edge:
                break

            # PIBT で次ノードを決定（ノード上のエージェントのみ）
            if on_node:
                active_cur  = {aid: cur_node[aid] for aid in on_node}
                active_goal = {aid: goals[aid]    for aid in on_node}

                edge_occupied = {nxt_node[aid] for aid in on_edge}
                all_occupied  = occupied_goals | edge_occupied

                forbidden: Set[Tuple[NodeId, NodeId]] = set()
                for aid in on_edge:
                    forbidden.add((nxt_node[aid], cur_node[aid]))

                nexts = self.plan_step(
                    active_cur, active_goal,
                    occupied_goals=all_occupied,
                    forbidden_edges=forbidden,
                    prev_nodes={aid: cur_node[aid] for aid in on_node},
                )

                # ── スワップ後処理: 決定後に逆走ペアを検出して低優先側を待機に ──
                decided_moves = {aid: nxt for aid, nxt in nexts.items()
                                 if nxt != active_cur.get(aid)}
                for a1 in list(decided_moves):
                    for a2 in list(decided_moves):
                        if a1 >= a2:
                            continue
                        c1, n1 = active_cur[a1], decided_moves[a1]
                        c2, n2 = active_cur[a2], decided_moves[a2]
                        # スワップ: a1が c1→n1, a2が c2→n2 で c1==n2 and c2==n1
                        if c1 == n2 and c2 == n1:
                            # 低優先（h が大きい）側を待機させる
                            h1 = _h(self.graph, c1, active_goal[a1])
                            h2 = _h(self.graph, c2, active_goal[a2])
                            loser = a1 if h1 >= h2 else a2
                            nexts[loser] = active_cur[loser]  # 待機
            else:
                nexts = {}

            # ── 全エージェントを 1 step 進める ──
            for aid in starts:
                if aid in done:
                    continue

                if edge_steps[aid] > 0:
                    # エッジ走行中: 残り step を消費
                    edge_steps[aid] -= 1
                    if edge_steps[aid] == 0:
                        # ノードに到達
                        cur_node[aid] = nxt_node[aid]
                        node_paths[aid].append(cur_node[aid])
                        if cur_node[aid] == goals[aid]:
                            done.add(aid)
                            occupied_goals.add(cur_node[aid])
                else:
                    # ノード上: PIBT の決定を適用
                    nxt = nexts.get(aid, cur_node[aid])
                    if nxt is None:
                        nxt = cur_node[aid]
                    if nxt != cur_node[aid]:
                        # エッジへ踏み出す
                        steps = _steps_for_edge(
                            self.graph.edge_weight(cur_node[aid], nxt))
                        nxt_node[aid]   = nxt
                        edge_steps[aid] = steps - 1   # 今 step で 1 消費
                        if edge_steps[aid] == 0:
                            # 1 step で通過
                            cur_node[aid] = nxt
                            node_paths[aid].append(cur_node[aid])
                            if cur_node[aid] == goals[aid]:
                                done.add(aid)
                                occupied_goals.add(cur_node[aid])
                        # else: まだエッジ上
                    # 待機の場合は何もしない

        result: Dict[AgentId, Optional[List[NodeId]]] = {}
        for aid in starts:
            if aid in done or cur_node.get(aid) == goals.get(aid):
                result[aid] = node_paths[aid]
            else:
                result[aid] = None
        return result