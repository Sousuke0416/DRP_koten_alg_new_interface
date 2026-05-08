"""
examples/example_nmap.py

map_definitions.py で定義したマップを使ったシミュレーション例。

使い方:
    python3 examples/example_nmap.py

設定欄を書き換えるだけでマップ・プランナー・描画モードを切り替えられる。
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

利用可能な描画モード:
    "gif"         GIF アニメーション保存（GIF_FPS で速度調整）
    "interactive" ブラウザで開く HTML ビューア（手動 step 送り・速度調整付き）
    "png"         各ステップを PNG で保存
    "text"        テキストログをターミナルに出力
    None          描画なし
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
MAP_DATA = MAP_CUSTOM_EXAMPLE

# ── エージェント設定 ────────────────────────────────────────────────────────
#   start_node / goal_node はマップのノードIDに合わせること
#   （マップのノード配置は map_definitions.py のコメントを参照）
AGENT_CONFIGS = [
    AgentConfig(agent_id=0, start_node=0,  goal_node=1),  # 左上 → 右下
    AgentConfig(agent_id=1, start_node=4,  goal_node=2),  # 右上 → 左下    
]

# ── プランナー選択 ──────────────────────────────────────────────────────────
#   "dijkstra" : 衝突無視・最短経路（動作確認向け）
#   "cbs"      : 衝突回避保証・最適（エージェント数が少ない場合推奨）
#   "pibt"     : 衝突回避・高速（エージェント数が多い場合推奨）
PLANNER = "pibt"

# ── 描画モード ──────────────────────────────────────────────────────────────
#   "interactive" : ブラウザで開く HTML ビューア（手動で step を送れる・おすすめ）
#   "gif"         : GIF アニメーション保存（GIF_FPS で速度調整）
#   "png"         : 各ステップを PNG で保存
#   "text"        : テキストログをターミナルに出力
#   None          : 描画なし
RENDER_MODE = "interactive"

# ── GIF 速度（RENDER_MODE="gif" のときのみ有効） ────────────────────────────
#   4.0 = 速い  /  2.0 = 標準  /  1.0 = ゆっくり  /  0.5 = 非常にゆっくり
#   ※ "interactive" モードでは HTML 上のスライダーで再生速度をリアルタイム調整できる
GIF_FPS = 2.0

# ── その他オプション ────────────────────────────────────────────────────────
MAX_STEPS       = 100
RENDER_INTERVAL = 1   # "png" / "text" モード時の出力間隔（step 数）

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
        gif_fps         = GIF_FPS,
        caller_file     = __file__,
        verbose         = True,
    )
    return summary


if __name__ == "__main__":
    main()