"""
examples/example_nmap.py

map_definitions.py で定義したマップを使ったシミュレーション例。

使い方:
    python3 examples/example_nmap.py

試したいマップとエージェント設定を下の MAP_NAME / AGENT_CONFIGS を
書き換えるだけで切り替えられる。

利用可能なマップ:
    MAP_LINE_5          一直線（ノード5個）
    MAP_GRID_4x4        4×4 グリッド（ノード16個）
    MAP_GRID_5x5        5×5 グリッド（ノード25個）
    MAP_WAREHOUSE       倉庫風マップ（ノード21個）
    MAP_SPLIT           非連結マップ・到達不能テスト用
    MAP_CUSTOM_EXAMPLE  T字路マップ（ノード5個）
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.mapf_env import EnvConfig, AgentConfig
from utils.runner import run_simulation

# map_definitions から使いたいマップをインポート
from map_definitions import (
    MAP_LINE_5,
    MAP_GRID_4x4,
    MAP_GRID_5x5,
    MAP_WAREHOUSE,
    MAP_SPLIT,
    MAP_CUSTOM_EXAMPLE,
)


# =============================================================================
# ここを書き換えてシナリオを切り替える
# =============================================================================

# ── 使用するマップ ──────────────────────────────────────────────────────────
MAP_DATA = MAP_WAREHOUSE

# ── エージェント設定 ────────────────────────────────────────────────────────
#   start_node / goal_node はマップのノードIDに合わせること
#   （マップのノード配置は map_definitions.py のコメントを参照）
AGENT_CONFIGS = [
    AgentConfig(agent_id=0, start_node=0,  goal_node=7),  # 左上 → 右下
    AgentConfig(agent_id=1, start_node=3,  goal_node=9),  # 右上 → 左下
    AgentConfig(agent_id=2, start_node=12, goal_node=14),   # 左下 → 右上
    AgentConfig(agent_id=3, start_node=7, goal_node=3),   # 右下 → 左上
]

# ── 実行オプション ──────────────────────────────────────────────────────────
MAX_STEPS      = 300
RENDER_MODE    = "gif"          # "text" / "png" / "gif" / None
RENDER_INTERVAL= 1              # png / text モード時の出力間隔（step 数）
OUTPUT_DIR     = "outputs/nmap" # png / gif の保存先ディレクトリ
GIF_PATH       = "outputs/nmap/simulation.gif"

# =============================================================================


def main():
    config = EnvConfig(
        map_data      = MAP_DATA,
        agent_configs = AGENT_CONFIGS,
        max_steps     = MAX_STEPS,
    )

    summary = run_simulation(
        config,
        render_mode     = RENDER_MODE,
        render_interval = RENDER_INTERVAL,
        output_dir      = OUTPUT_DIR,
        gif_path        = GIF_PATH,
        verbose         = True,
    )
    return summary


if __name__ == "__main__":
    main()