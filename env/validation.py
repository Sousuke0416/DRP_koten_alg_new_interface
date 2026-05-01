"""
env/validation.py
エージェント設定のバリデーションモジュール

reset() の前に呼ばれ、不正な設定を早期にエラーとして検出する。

チェック項目:
  1. agent_id の重複
  2. start_node / goal_node がグラフに存在するか
  3. 同一ノードを複数エージェントが start_node に使っていないか
  4. 同一ノードを複数エージェントが goal_node に使っていないか
  5. 同一エージェントの start_node と goal_node が同じでないか
     ※ start==goal は「既にゴール済み」として扱うのではなく設定ミスとみなす
"""

from __future__ import annotations
from typing import List, TYPE_CHECKING

from graph.map_graph import MapGraph

if TYPE_CHECKING:
    from env.mapf_env import AgentConfig


class ConfigValidationError(ValueError):
    """エージェント設定に問題があるときに送出される例外"""
    pass


def validate_agent_configs(
    agent_configs: List[AgentConfig],
    graph: MapGraph,
) -> None:
    """
    エージェント設定を検証する。問題があれば ConfigValidationError を送出。

    Parameters
    ----------
    agent_configs : 検証対象のエージェント設定リスト
    graph         : 構築済みの MapGraph

    Raises
    ------
    ConfigValidationError
        いずれかのチェックに引っかかった場合
    """
    errors: List[str] = []

    # ── 1. agent_id の重複 ──────────────────────────────────────────────
    seen_ids: set = set()
    for cfg in agent_configs:
        if cfg.agent_id in seen_ids:
            errors.append(
                f"agent_id={cfg.agent_id} が重複しています。"
                f" agent_id はすべて異なる値にしてください。"
            )
        seen_ids.add(cfg.agent_id)

    # ── 2. ノードがグラフに存在するか ───────────────────────────────────
    for cfg in agent_configs:
        if not graph.has_node(cfg.start_node):
            errors.append(
                f"Agent {cfg.agent_id}: start_node={cfg.start_node} は"
                f" グラフに存在しません。"
            )
        if not graph.has_node(cfg.goal_node):
            errors.append(
                f"Agent {cfg.agent_id}: goal_node={cfg.goal_node} は"
                f" グラフに存在しません。"
            )

    # ── 3. start_node の重複 ────────────────────────────────────────────
    start_map: dict = {}   # node_id -> agent_id
    for cfg in agent_configs:
        if cfg.start_node in start_map:
            first_id = start_map[cfg.start_node]
            errors.append(
                f"Agent {cfg.agent_id} と Agent {first_id} が"
                f" 同じ start_node={cfg.start_node} を使っています。"
                f" 各エージェントの start_node は異なるノードにしてください。"
            )
        else:
            start_map[cfg.start_node] = cfg.agent_id

    # ── 4. goal_node の重複 ─────────────────────────────────────────────
    goal_map: dict = {}    # node_id -> agent_id
    for cfg in agent_configs:
        if cfg.goal_node in goal_map:
            first_id = goal_map[cfg.goal_node]
            errors.append(
                f"Agent {cfg.agent_id} と Agent {first_id} が"
                f" 同じ goal_node={cfg.goal_node} を使っています。"
                f" 各エージェントの goal_node は異なるノードにしてください。"
            )
        else:
            goal_map[cfg.goal_node] = cfg.agent_id

    # ── 5. start_node == goal_node ──────────────────────────────────────
    for cfg in agent_configs:
        if cfg.start_node == cfg.goal_node:
            errors.append(
                f"Agent {cfg.agent_id}: start_node と goal_node が"
                f" 同じノード（={cfg.start_node}）になっています。"
                f" 異なるノードを指定してください。"
            )

    # ── エラーをまとめて送出 ────────────────────────────────────────────
    if errors:
        msg = "エージェント設定にエラーがあります:\n"
        for i, e in enumerate(errors, 1):
            msg += f"  [{i}] {e}\n"
        raise ConfigValidationError(msg.rstrip())