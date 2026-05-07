"""
agents/agent.py
エージェントの状態・移動ロジック管理モジュール

移動モデル:
  - エージェントは 1 step で speed=5 の距離を進む
  - エッジ上で方向転換不可（エッジを通り終えるまで逆走不可）
  - ゴール到達後はそのノードを「占有」し他エージェントはそのノードに入れない
"""


from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple

from graph.map_graph import MapGraph


class AgentStatus(Enum):
    WAITING   = auto()   # 経路計算待ち / 開始前
    MOVING    = auto()   # 移動中
    GOAL      = auto()   # ゴール到達済み
    STUCK     = auto()   # 到達不能（経路なし）
    COLLIDED  = auto()   # 衝突停止


@dataclass
class AgentState:
    """エージェントの完全な状態スナップショット"""
    agent_id:       int
    current_node:   int               # 現在いるノード（エッジ上は出発ノード）
    next_node:      int               # 向かっているノード（ノード上にいる時は current と同じ）
    progress:       float             # エッジ上の進捗 [0.0, edge_weight]
    path:           List[int]         # 残りの経路（次のノード以降）
    status:         AgentStatus
    steps_taken:    int               # 移動に要した step 数
    goal_node:      int


class Agent:
    """
    1 体のエージェントを管理するクラス。
    MapGraph への参照を持ち、自分の移動を計算する。
    """

    SPEED: float = 5.0          # 1 step あたりの移動距離
    COLLISION_DIST: float = 5.0 # 衝突判定距離（未満で衝突）

    def __init__(
        self,
        agent_id: int,
        start_node: int,
        goal_node: int,
        graph: MapGraph,
    ):
        self.agent_id   = agent_id
        self.start_node = start_node
        self.goal_node  = goal_node
        self._graph     = graph

        # 移動状態
        self.current_node: int   = start_node
        self.next_node:    int   = start_node
        self.progress:     float = 0.0        # エッジ上の累積移動距離
        self.path:         List[int] = []     # current_node の次から goal まで
        self.status:       AgentStatus = AgentStatus.WAITING
        self.steps_taken:  int = 0
        self._wait_count:  int = 0        # 連続待機カウント（デッドロック検出用）
        self._WAIT_LIMIT:  int = 50       # これを超えたら STUCK とみなす

    # ------------------------------------------------------------------ #
    #  初期化
    # ------------------------------------------------------------------ #

    def plan_path(self, occupied_nodes: Optional[set] = None) -> bool:
        """
        Dijkstra で経路を計算する。
        occupied_nodes : ゴール済みエージェントが占有しているノード集合
        戻り値: 経路が存在すれば True
        """
        occupied_nodes = occupied_nodes or set()

        # スタートとゴールが同じ
        if self.start_node == self.goal_node:
            self.path   = []
            self.status = AgentStatus.GOAL
            return True

        full_path = self._graph.shortest_path(self.start_node, self.goal_node)
        if full_path is None:
            self.status = AgentStatus.STUCK
            return False

        self.path   = full_path[1:]   # current_node を除く
        self.status = AgentStatus.MOVING
        self._advance_target()
        return True

    @property
    def on_edge(self) -> bool:
        """エッジ上（ノード間移動中）かどうか"""
        return self.current_node != self.next_node or self.progress > 0.0

    def set_path(self, path: List[int]) -> None:
        """
        外部プランナー（CBS/PIBT）から経路をセットする。
        エッジ上にいる場合は方向転換禁止：
          - next_node が path[0] と一致する方向のみ受け付ける
          - 不一致（逆走指示）の場合は現在の next_node 方向を維持する
        """
        if self.on_edge:
            # エッジ上 → next_node 方向への経路のみ受け付ける
            if path and path[0] == self.next_node:
                self.path = path[1:]   # next_node は既に next_node なので除く
            # 逆走指示は無視（現在の next_node 方向を維持）
        else:
            # ノード上 → 自由に経路変更可
            self.path = path
            if self.path:
                self._advance_target()

    # ------------------------------------------------------------------ #
    #  毎 step の更新
    # ------------------------------------------------------------------ #

    def step(self, occupied_nodes: set) -> None:
        """
        1 step 分の移動を実行する。
        occupied_nodes : ゴール済みエージェントが占有しているノード集合
                         ※ step() 内で新たにゴールしたノードも即座に追加される
        """
        if self.status in (AgentStatus.GOAL, AgentStatus.STUCK, AgentStatus.COLLIDED):
            return

        # ── step 開始時点でノード上にいてゴール済みか確認（即時判定）──
        if (self.current_node == self.next_node
                and self.progress == 0.0
                and self.current_node == self.goal_node):
            self.status = AgentStatus.GOAL
            occupied_nodes.add(self.goal_node)   # 即座に占有登録
            self.steps_taken += 1
            return

        remaining_move = self.SPEED

        # エッジを移動し続ける（1 step で複数エッジをまたぐ可能性あり）
        while remaining_move > 0 and self.status == AgentStatus.MOVING:
            if self.current_node == self.next_node and self.progress == 0.0:
                # ── ノード上 ──
                if not self.path:
                    # 経路終端に到達
                    if self.current_node == self.goal_node:
                        self.status = AgentStatus.GOAL
                        occupied_nodes.add(self.goal_node)  # 即座に占有登録
                    break

                candidate_next = self.path[0]

                # 占有ノードへは進入不可 → このstepは待機
                if candidate_next in occupied_nodes:
                    self._wait_count += 1
                    if self._wait_count >= self._WAIT_LIMIT:
                        self.status = AgentStatus.STUCK
                    break

                self._wait_count = 0  # 進める場合はリセット
                self._advance_target()

            elif self.current_node == self.next_node and self.progress > 0.0:
                # 内部不整合ガード
                self.progress = 0.0

            # ── エッジ走行 ──
            edge_weight  = self._graph.edge_weight(self.current_node, self.next_node)
            dist_to_next = edge_weight - self.progress

            if remaining_move >= dist_to_next:
                # 次のノードへ到達
                remaining_move    -= dist_to_next
                self.progress      = 0.0
                self.current_node  = self.next_node
                # path から消費済みノードを除去
                if self.path and self.path[0] == self.current_node:
                    self.path.pop(0)

                # ── ノード到達と同時にゴール判定（即時）──
                if self.current_node == self.goal_node and not self.path:
                    self.status = AgentStatus.GOAL
                    occupied_nodes.add(self.goal_node)  # 即座に占有登録
                    break

                # 到達ノードが占有済みなら即時停止（通り抜け禁止）
                if self.current_node in occupied_nodes:
                    # ゴールできなかった場合は経路を失効させて待機
                    self.path = []
                    self.next_node = self.current_node
                    break

            else:
                # エッジ途中で止まる
                self.progress  += remaining_move
                remaining_move  = 0.0

        self.steps_taken += 1

    def _advance_target(self) -> None:
        """path の先頭を next_node に設定する"""
        if self.path:
            self.next_node = self.path[0]
            self._on_edge  = True
        else:
            self._on_edge = False

    # ------------------------------------------------------------------ #
    #  座標・距離
    # ------------------------------------------------------------------ #

    def get_continuous_position(self) -> Tuple[float, float]:
        """
        エッジ上の連続座標 (x, y) を返す（可視化・衝突判定用）。
        ノード上にいる場合はノード座標を返す。
        """
        pos_cur = self._graph.get_position(self.current_node)
        if pos_cur is None:
            return (0.0, 0.0)

        if self.current_node == self.next_node or self.progress == 0.0:
            return (pos_cur.x, pos_cur.y)

        pos_nxt = self._graph.get_position(self.next_node)
        if pos_nxt is None:
            return (pos_cur.x, pos_cur.y)

        edge_weight = self._graph.edge_weight(self.current_node, self.next_node)
        t = self.progress / edge_weight  # [0, 1]
        x = pos_cur.x + t * (pos_nxt.x - pos_cur.x)
        y = pos_cur.y + t * (pos_nxt.y - pos_cur.y)
        return (x, y)

    def distance_to(self, other: "Agent") -> float:
        """他エージェントとのユークリッド距離"""
        x1, y1 = self.get_continuous_position()
        x2, y2 = other.get_continuous_position()
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

    # ------------------------------------------------------------------ #
    #  状態スナップショット
    # ------------------------------------------------------------------ #

    def get_state(self) -> AgentState:
        return AgentState(
            agent_id     = self.agent_id,
            current_node = self.current_node,
            next_node    = self.next_node,
            progress     = self.progress,
            path         = list(self.path),
            status       = self.status,
            steps_taken  = self.steps_taken,
            goal_node    = self.goal_node,
        )

    def __repr__(self) -> str:
        return (f"Agent(id={self.agent_id}, "
                f"node={self.current_node}->{self.next_node}, "
                f"progress={self.progress:.2f}, "
                f"status={self.status.name})")