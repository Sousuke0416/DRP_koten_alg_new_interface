"""
examples/example_grid.py
グリッドマップ上のシミュレーション例

マップ: 4×4 グリッド（エッジ重み = 5）
エージェント: 4 体
  Agent 0: ノード  0 →  15 (左上 → 右下)
  Agent 1: ノード 15 →   0 (右下 → 左上)
  Agent 2: ノード  3 →  12 (右上 → 左下)
  Agent 3: ノード 12 →   3 (左下 → 右上)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.mapf_env import EnvConfig, AgentConfig
from utils.runner import run_simulation
from utils.map_presets import grid_map


def main():
    map_data = grid_map(rows=4, cols=4, weight=5.0)

    agent_configs = [
        AgentConfig(agent_id=0, start_node=0,  goal_node=15),
        AgentConfig(agent_id=1, start_node=15, goal_node=0),
        AgentConfig(agent_id=2, start_node=3,  goal_node=12),
        AgentConfig(agent_id=3, start_node=12, goal_node=3),
    ]

    config = EnvConfig(
        map_data      = map_data,
        agent_configs = agent_configs,
        max_steps     = 500,
    )

    summary = run_simulation(config, render_mode="gif", render_interval=5, verbose=True)
    return summary


if __name__ == "__main__":
    main()
