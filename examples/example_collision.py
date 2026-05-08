"""
examples/example_collision.py
衝突が発生するシミュレーション例

マップ: 一直線（ノード 0—1—2—3—4）、エッジ重み = 5
Agent 0: 0 → 4（左から右）
Agent 1: 4 → 0（右から左）
→ 中央付近で距離 < 5 になり衝突判定
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.mapf_env import EnvConfig, AgentConfig
from utils.runner import run_simulation
from utils.map_presets import line_map


def main():
    map_data = line_map(n_nodes=5, weight=5.0)

    agent_configs = [
        AgentConfig(agent_id=0, start_node=0, goal_node=4),
        AgentConfig(agent_id=1, start_node=4, goal_node=0),
    ]

    config = EnvConfig(
        map_data      = map_data,
        agent_configs = agent_configs,
        max_steps     = 100,
    )

    summary = run_simulation(config, render_mode="gif", render_interval=1, verbose=True)
    return summary


if __name__ == "__main__":
    main()
