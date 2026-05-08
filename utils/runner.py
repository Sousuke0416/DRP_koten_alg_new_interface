"""
utils/runner.py
シミュレーション実行ユーティリティ

MAPFEnv をラップし、ループ管理・実験設定表示・ログ出力・描画を担う。

描画オプション:
  render_mode="text"  : テキストログをコンソール出力
  render_mode="png"   : 各ステップの静止画を PNG 保存
  render_mode="gif"   : シミュレーション全体を GIF アニメーション保存
  render_mode="show"  : GUI ウィンドウにリアルタイム表示（要 GUI 環境）

出力先:
  outputs/<実験ファイル名>/<YYYYMMDD_HHMMSS>/simulation.gif  (gif モード)
  outputs/<実験ファイル名>/<YYYYMMDD_HHMMSS>/step_XXXX.png   (png モード)
"""

from __future__ import annotations
import os
import inspect
from datetime import datetime
from typing import List, Optional

from env.mapf_env import MAPFEnv, EnvConfig, SimulationSummary


# ------------------------------------------------------------------ #
#  実験設定の表示
# ------------------------------------------------------------------ #

def _map_name(map_data: dict) -> str:
    """マップ辞書からノード数・エッジ数を読み取って文字列化"""
    n_nodes = len(map_data.get("nodes", []))
    n_edges = len(map_data.get("edges", []))
    return f"{n_nodes} nodes, {n_edges} edges"


def print_experiment_info(
    config: EnvConfig,
    render_mode: Optional[str],
    output_path: Optional[str],
) -> None:
    """実験開始前に設定一覧をターミナルに表示する"""
    sep  = "=" * 56
    sep2 = "-" * 56

    planner_desc = {
        "dijkstra": "Dijkstra（衝突回避なし・最速）",
        "cbs":      "CBS（衝突回避保証・最適・低速）",
        "pibt":     "PIBT（衝突回避・高速・非最適）",
    }.get(config.planner.lower(), config.planner)

    render_desc = {
        "gif":  "GIF アニメーション保存",
        "png":  "PNG 静止画保存（各ステップ）",
        "text": "テキストログ出力",
        "show": "リアルタイム GUI 表示",
        None:   "なし",
    }.get(render_mode, str(render_mode))

    print(sep)
    print("  MAPF シミュレーション 実験設定")
    print(sep)
    print(f"  {'マップ':<14}: {_map_name(config.map_data)}")
    print(f"  {'プランナー':<13}: {planner_desc}")
    print(f"  {'エージェント数':<12}: {len(config.agent_configs)} 体")
    print(sep2)
    for cfg in config.agent_configs:
        print(f"    Agent {cfg.agent_id}  "
              f"start={cfg.start_node:>3}  →  goal={cfg.goal_node:>3}")
    print(sep2)
    print(f"  {'最大ステップ数':<12}: {config.max_steps}")
    print(f"  {'描画モード':<13}: {render_desc}")
    if output_path:
        print(f"  {'出力先':<14}: {output_path}")
    print(sep)
    print()


# ------------------------------------------------------------------ #
#  出力パスの自動生成
# ------------------------------------------------------------------ #

def _make_output_dir(render_mode: Optional[str], caller_file: Optional[str]) -> str:
    """
    outputs/<実験ファイル名>/<YYYYMMDD_HHMMSS>/ を生成して返す。
    caller_file: 呼び出し元スクリプトのパス（None なら "experiment"）
    """
    if caller_file:
        script_name = os.path.splitext(os.path.basename(caller_file))[0]
    else:
        script_name = "experiment"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir   = os.path.join("outputs", script_name, timestamp)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


# ------------------------------------------------------------------ #
#  メイン実行関数
# ------------------------------------------------------------------ #

def run_simulation(
    config: EnvConfig,
    render_mode: Optional[str] = None,
    render_interval: int = 1,
    output_dir: Optional[str] = None,   # None で自動生成
    gif_path: Optional[str] = None,     # None で自動生成
    verbose: bool = True,
    caller_file: Optional[str] = None,  # __file__ を渡す
) -> SimulationSummary:
    """
    シミュレーションを最後まで実行してサマリーを返す。

    Parameters
    ----------
    config          : 環境設定
    render_mode     : None / "text" / "png" / "gif" / "show"
    render_interval : "png" / "text" モード時に何 step 毎に出力するか
    output_dir      : 保存先ディレクトリ（None で自動生成）
    gif_path        : GIF 保存先パス（None で自動生成）
    verbose         : 実験設定・サマリーを標準出力に表示するか
    caller_file     : 呼び出し元の __file__（出力フォルダ名に使用）

    Returns
    -------
    SimulationSummary
    """
    # 呼び出し元ファイルを自動検出（caller_file 未指定時）
    if caller_file is None:
        frame = inspect.stack()
        for f in frame[1:]:
            if f.filename != __file__:
                caller_file = f.filename
                break

    # 出力先ディレクトリを決定
    if render_mode in ("png", "gif") and output_dir is None:
        output_dir = _make_output_dir(render_mode, caller_file)

    if render_mode == "gif" and gif_path is None and output_dir:
        gif_path = os.path.join(output_dir, "simulation.gif")

    # 実験設定の表示
    if verbose:
        display_path = gif_path if render_mode == "gif" else output_dir
        print_experiment_info(config, render_mode, display_path)

    env = MAPFEnv(config)
    obs, info = env.reset()

    # GIF / PNG モード用の Visualizer を初期化
    viz = None
    gif_frames: List[bytes] = []

    if render_mode in ("png", "gif", "show"):
        from utils.visualizer import Visualizer
        viz = Visualizer(env.graph, env.agents)
        if render_mode == "png" and output_dir:
            os.makedirs(output_dir, exist_ok=True)

    if viz and render_mode == "gif":
        gif_frames.append(viz.capture_frame(step=0))

    terminated = False
    truncated  = False

    while not (terminated or truncated):
        result     = env.step()
        terminated = result.terminated
        truncated  = result.truncated
        step       = env._step_count

        if viz:
            viz.agents = env.agents

        if render_mode == "text":
            if step % render_interval == 0 or terminated or truncated:
                env.render(mode="text")

        elif render_mode == "png":
            if step % render_interval == 0 or terminated or truncated:
                path = os.path.join(output_dir, f"step_{step:04d}.png")
                viz.render_frame(step=step, save_path=path)

        elif render_mode == "gif":
            gif_frames.append(viz.capture_frame(step=step))

        elif render_mode == "show":
            if step % render_interval == 0 or terminated or truncated:
                import matplotlib.pyplot as plt
                import matplotlib
                matplotlib.use("TkAgg")
                plt.ion()
                viz.show_live(step=step)

    if render_mode == "gif" and gif_frames:
        os.makedirs(os.path.dirname(gif_path) if os.path.dirname(gif_path) else ".", exist_ok=True)
        viz.save_gif(gif_frames, gif_path, fps=4)

    summary = env.get_summary()

    if verbose:
        print(summary)

    env.close()
    return summary