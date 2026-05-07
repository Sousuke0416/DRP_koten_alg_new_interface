"""
env/mapf_env.py
マルチエージェント経路探索 Gym 互換環境

Gym の Space / Env インターフェースを模倣した自前実装。
（gymnasium が利用できない環境向け）

主な仕様:
  - 重み付き無向グラフ上のマルチエージェント移動
  - 1 step = speed 5 の移動
  - エッジ上での方向転換不可
  - ゴールしたエージェントはノードを占有
  - 衝突距離 < 5 で COLLIDED 状態
  - 到達不能な場合は計画段階で STUCK 状態に設定
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from graph.map_graph import MapGraph
from agents.agent import Agent, AgentStatus
from env.collision import detect_collisions
from env.validation import validate_agent_configs, ConfigValidationError


# ------------------------------------------------------------------ #
#  入力データ型
# ------------------------------------------------------------------ #

@dataclass
class AgentConfig:
    """エージェント 1 体分の初期設定"""
    agent_id:   int
    start_node: int
    goal_node:  int


@dataclass
class EnvConfig:
    """環境全体の設定"""
    map_data:      dict          # MapGraph.from_dict() に渡す辞書
    agent_configs: List[AgentConfig]
    max_steps:     int = 1000    # タイムアウト上限


# ------------------------------------------------------------------ #
#  出力データ型
# ------------------------------------------------------------------ #

@dataclass
class StepResult:
    """step() の戻り値"""
    observations:   Dict[int, Any]
    rewards:        Dict[int, float]
    terminated:     bool          # 全エージェントが終了（GOAL/STUCK/COLLIDED）
    truncated:      bool          # max_steps 超過
    info:           Dict[str, Any]


@dataclass
class SimulationSummary:
    """シミュレーション終了時のサマリー"""
    total_agents:       int
    reached:            int           # ゴール到達数
    stuck:              int           # 到達不能数
    collided:           int           # 衝突停止数
    total_steps:        int           # 消費ステップ数
    elapsed_seconds:    float         # 実時間（秒）
    per_agent:          List[Dict]    # エージェントごとの詳細

    def __str__(self) -> str:
        lines = [
            "=" * 50,
            "  シミュレーション結果",
            "=" * 50,
            f"  エージェント総数  : {self.total_agents}",
            f"  ゴール到達        : {self.reached}",
            f"  到達不能 (STUCK)  : {self.stuck}",
            f"  衝突停止          : {self.collided}",
            f"  総ステップ数      : {self.total_steps}",
            f"  計算時間          : {self.elapsed_seconds:.4f} 秒",
            "-" * 50,
        ]
        for a in self.per_agent:
            status_str = a["status"]
            if a["status"] == "GOAL":
                lines.append(
                    f"  Agent {a['id']:>3}: {status_str:<10} "
                    f"(ゴールまで {a['steps']} steps)"
                )
            elif a["status"] == "STUCK":
                lines.append(
                    f"  Agent {a['id']:>3}: {status_str:<10} "
                    f"(到達不能: ノード {a['start']} → {a['goal']})"
                )
            else:
                lines.append(
                    f"  Agent {a['id']:>3}: {status_str:<10}"
                )
        lines.append("=" * 50)
        return "\n".join(lines)


# ------------------------------------------------------------------ #
#  環境本体
# ------------------------------------------------------------------ #

class MAPFEnv:
    """
    Multi-Agent Path Finding 環境 (Gym 互換インターフェース)

    使用例:
        config = EnvConfig(map_data=..., agent_configs=[...])
        env = MAPFEnv(config)
        obs, info = env.reset()
        done = False
        while not done:
            result = env.step()       # 外部アクション不要（自律移動）
            done = result.terminated or result.truncated
        summary = env.get_summary()
        print(summary)
    """

    metadata = {"render_modes": ["text", "matplotlib"]}

    def __init__(self, config: EnvConfig):
        self.config = config
        self.graph: Optional[MapGraph] = None
        self.agents: List[Agent] = []
        self._step_count: int = 0
        self._start_time: float = 0.0
        self._elapsed: float = 0.0
        self._terminated: bool = False
        self._truncated: bool = False

    # ------------------------------------------------------------------ #
    #  Gym インターフェース
    # ------------------------------------------------------------------ #

    def reset(self) -> Tuple[Dict[int, Any], Dict[str, Any]]:
        """
        環境を初期化する。
        戻り値: (observations, info)
        """
        self._step_count = 0
        self._terminated = False
        self._truncated  = False
        self._start_time = time.perf_counter()

        # グラフ構築
        self.graph = MapGraph.from_dict(self.config.map_data)

        # ── エージェント設定バリデーション ──────────────────────────────
        validate_agent_configs(self.config.agent_configs, self.graph)

        # エージェント構築 & 経路計画
        self.agents = []
        occupied: set = set()  # ゴール済み占有ノード

        for cfg in self.config.agent_configs:
            agent = Agent(cfg.agent_id, cfg.start_node, cfg.goal_node, self.graph)
            reachable = agent.plan_path(occupied)
            if not reachable:
                pass  # STUCK 状態で続行

            self.agents.append(agent)

        obs  = self._get_observations()
        info = {"step": 0, "agents": len(self.agents)}
        return obs, info

    def step(self, actions: Optional[Dict] = None) -> StepResult:
        """
        1 ステップ進める。
        actions: 外部からのアクション（本実装では自律移動のため省略可）
        """
        if self._terminated or self._truncated:
            raise RuntimeError("環境が終了しています。reset() を呼んでください。")

        # 占有ノード（ゴール済みエージェントのゴールノード）を mutable set で渡す
        # → agent.step() 内でゴールした瞬間に即座に追加される
        occupied: set = {
            a.goal_node for a in self.agents if a.status == AgentStatus.GOAL
        }

        # 全エージェントを移動（occupied は step() 内で随時更新される）
        for agent in self.agents:
            agent.step(occupied)

        # 衝突判定
        collided_ids = detect_collisions(self.agents)
        for agent in self.agents:
            if agent.agent_id in collided_ids:
                agent.status = AgentStatus.COLLIDED

        self._step_count += 1

        # ── 終了判定 ──────────────────────────────────────────────────
        # 1体でも衝突したら即終了
        any_collided = len(collided_ids) > 0
        # 全エージェントが終了状態（GOAL / STUCK / COLLIDED）になったら終了
        all_done = all(
            a.status in (AgentStatus.GOAL, AgentStatus.STUCK, AgentStatus.COLLIDED)
            for a in self.agents
        )
        self._terminated = any_collided or all_done
        self._truncated  = (not self._terminated) and (self._step_count >= self.config.max_steps)

        if self._terminated or self._truncated:
            self._elapsed = time.perf_counter() - self._start_time

        obs     = self._get_observations()
        rewards = self._get_rewards()
        info    = {
            "step":         self._step_count,
            "collided_ids": list(collided_ids),
            "occupied":     list(occupied),
        }

        return StepResult(obs, rewards, self._terminated, self._truncated, info)

    def render(self, mode: str = "text") -> None:
        """現在の状態をレンダリングする"""
        if mode == "text":
            self._render_text()
        elif mode == "matplotlib":
            self._render_matplotlib()
        else:
            raise ValueError(f"未対応の render mode: {mode}")

    def close(self) -> None:
        pass

    # ------------------------------------------------------------------ #
    #  サマリー
    # ------------------------------------------------------------------ #

    def get_summary(self) -> SimulationSummary:
        """シミュレーション終了後のサマリーを返す"""
        reached  = sum(1 for a in self.agents if a.status == AgentStatus.GOAL)
        stuck    = sum(1 for a in self.agents if a.status == AgentStatus.STUCK)
        collided = sum(1 for a in self.agents if a.status == AgentStatus.COLLIDED)

        per_agent = []
        for a in self.agents:
            cfg = next(c for c in self.config.agent_configs if c.agent_id == a.agent_id)
            per_agent.append({
                "id":     a.agent_id,
                "status": a.status.name,
                "steps":  a.steps_taken,
                "start":  cfg.start_node,
                "goal":   cfg.goal_node,
            })

        return SimulationSummary(
            total_agents    = len(self.agents),
            reached         = reached,
            stuck           = stuck,
            collided        = collided,
            total_steps     = self._step_count,
            elapsed_seconds = self._elapsed,
            per_agent       = per_agent,
        )

    # ------------------------------------------------------------------ #
    #  内部ヘルパー
    # ------------------------------------------------------------------ #

    def _get_observations(self) -> Dict[int, Any]:
        return {a.agent_id: a.get_state() for a in self.agents}

    def _get_rewards(self) -> Dict[int, float]:
        rewards = {}
        for a in self.agents:
            if a.status == AgentStatus.GOAL:
                rewards[a.agent_id] = 1.0
            elif a.status == AgentStatus.COLLIDED:
                rewards[a.agent_id] = -1.0
            elif a.status == AgentStatus.STUCK:
                rewards[a.agent_id] = -0.5
            else:
                rewards[a.agent_id] = -0.01  # 生存ペナルティ
        return rewards

    def _render_text(self) -> None:
        print(f"\n--- Step {self._step_count} ---")
        for a in self.agents:
            pos = a.get_continuous_position()
            print(
                f"  Agent {a.agent_id:>3}: "
                f"node={a.current_node}->{a.next_node} "
                f"progress={a.progress:.2f} "
                f"pos=({pos[0]:.1f},{pos[1]:.1f}) "
                f"status={a.status.name}"
            )

    def _render_matplotlib(self, save_path: Optional[str] = None) -> None:
        """Visualizer モジュールに委譲して描画する"""
        from utils.visualizer import Visualizer
        viz = Visualizer(self.graph, self.agents)
        path = save_path or f"/mnt/user-data/outputs/mapf_step_{self._step_count:04d}.png"
        import matplotlib.pyplot as plt
        fig = viz.render_frame(step=self._step_count, save_path=path)
        plt.close(fig)