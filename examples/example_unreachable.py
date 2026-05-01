"""
examples/example_unreachable.py
到達不能エージェントを含むシミュレーション例

マップ: 2 つの孤立した連結成分
  成分 A: ノード 0, 1, 2
  成分 B: ノード 3, 4, 5

Agent 0: 0 → 2 （到達可能）
Agent 1: 0 → 4 （到達不能: 別成分）
Agent 2: 3 → 5 （到達可能）
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.mapf_env import EnvConfig, AgentConfig
from utils.runner import run_simulation
from utils.map_presets import custom_map


def main():
    map_data = custom_map(
        nodes=[
            {"id": 0, "x":  0.0, "y": 0.0},
            {"id": 1, "x": 10.0, "y": 0.0},
            {"id": 2, "x": 20.0, "y": 0.0},
            {"id": 3, "x": 40.0, "y": 0.0},
            {"id": 4, "x": 50.0, "y": 0.0},
            {"id": 5, "x": 60.0, "y": 0.0},
        ],
        edges=[
            {"u": 0, "v": 1, "weight": 10.0},
            {"u": 1, "v": 2, "weight": 10.0},
            {"u": 3, "v": 4, "weight": 10.0},
            {"u": 4, "v": 5, "weight": 10.0},
            # 成分 A と B の間にエッジなし → 到達不能
        ],
    )

    agent_configs = [
        AgentConfig(agent_id=0, start_node=0, goal_node=2),
        AgentConfig(agent_id=1, start_node=0, goal_node=4),  # 到達不能
        AgentConfig(agent_id=2, start_node=3, goal_node=5),
    ]

    config = EnvConfig(
        map_data      = map_data,
        agent_configs = agent_configs,
        max_steps     = 200,
    )

    summary = run_simulation(config, render_mode="gif", render_interval=3, verbose=True)
    return summary


if __name__ == "__main__":
    main()
