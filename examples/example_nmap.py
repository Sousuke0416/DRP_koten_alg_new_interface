"""
examples/example_nmap.py

map_definitions.py で定義したマップを使ったシミュレーション例。

使い方:
    python3 examples/example_nmap.py

試したいマップ・エージェント・プランナーを下の設定欄を書き換えるだけで切り替えられる。
結果ファイルは outputs/example_nmap/<YYYYMMDD_HHMMSS>/ に自動保存される。

利用可能なマップ:
    MAP_LINE_5          一直線（ノード5個）
    MAP_GRID_4x4        4×4 グリッド（ノード16個）
    MAP_GRID_5x5        5×5 グリッド（ノード25個）
    MAP_WAREHOUSE       倉庫風マップ（ノード21個）
    MAP_SPLIT           非連結マップ・到達不能テスト用
    MAP_CUSTOM_EXAMPLE  T字路マップ（ノード5個）

利用可能なプランナー:
    "dijkstra"  各エージェントが独立に最短経路を走る（衝突回避なし・高速）
    "cbs"       Conflict-Based Search（衝突回避保証・最適・低速）
    "pibt"      Priority Inheritance with Backtracking（衝突回避・高速・非最適）
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.mapf_env import EnvConfig, AgentConfig
from utils.runner import run_simulation

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
MAP_DATA = MAP_GRID_4x4

# ── エージェント設定 ────────────────────────────────────────────────────────
#   start_node / goal_node はマップのノードIDに合わせること
#   （マップのノード配置は map_definitions.py のコメントを参照）
AGENT_CONFIGS = [
    AgentConfig(agent_id=0, start_node=0,  goal_node=15),  # 左上 → 右下
    AgentConfig(agent_id=1, start_node=3,  goal_node=12),  # 右上 → 左下
    AgentConfig(agent_id=2, start_node=12, goal_node=3),   # 左下 → 右上
    AgentConfig(agent_id=3, start_node=15, goal_node=0),   # 右下 → 左上
]

# ── プランナー選択 ──────────────────────────────────────────────────────────
#   "dijkstra" : 衝突無視・最短経路（動作確認向け）
#   "cbs"      : 衝突回避保証・最適（エージェント数が少ない場合推奨）
#   "pibt"     : 衝突回避・高速（エージェント数が多い場合推奨）
PLANNER = "cbs"

# ── 実行オプション ──────────────────────────────────────────────────────────
MAX_STEPS       = 300
RENDER_MODE     = "gif"   # "text" / "png" / "gif" / None
RENDER_INTERVAL = 1       # png / text モード時の出力間隔（step 数）

# 出力先は outputs/example_nmap/<YYYYMMDD_HHMMSS>/ に自動生成されます

# =============================================================================


def main():
    config = EnvConfig(
        map_data      = MAP_DATA,
        agent_configs = AGENT_CONFIGS,
        max_steps     = MAX_STEPS,
        planner       = PLANNER,
    )

    summary = run_simulation(
        config,
        render_mode     = RENDER_MODE,
        render_interval = RENDER_INTERVAL,
        caller_file     = __file__,   # 出力フォルダ名に使用
        verbose         = True,
    )
    return summary


if __name__ == "__main__":
    main()