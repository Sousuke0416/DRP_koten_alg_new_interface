"""
utils/runner.py
シミュレーション実行ユーティリティ

MAPFEnv をラップし、ループ管理・ログ出力・サマリー表示・描画を担う。

描画オプション:
  render_mode="text"        : テキストログをコンソール出力
  render_mode="png"         : 各ステップの静止画を PNG 保存
  render_mode="gif"         : シミュレーション全体を GIF アニメーション保存
  render_mode="show"        : GUI ウィンドウにリアルタイム表示（要 GUI 環境）
"""

from __future__ import annotations
import os
from typing import List, Optional

from env.mapf_env import MAPFEnv, EnvConfig, SimulationSummary


def run_simulation(
    config: EnvConfig,
    render_mode: Optional[str] = None,
    render_interval: int = 1,
    output_dir: str = "outputs",
    gif_path: Optional[str] = None,
    verbose: bool = True,
) -> SimulationSummary:
    """
    シミュレーションを最後まで実行してサマリーを返す。

    Parameters
    ----------
    config          : 環境設定
    render_mode     : None / "text" / "png" / "gif" / "show"
    render_interval : "png" / "text" モード時に何 step 毎に出力するか
    output_dir      : PNG 保存先ディレクトリ
    gif_path        : GIF 保存先パス（None の場合 output_dir/simulation.gif）
    verbose         : サマリーを標準出力に表示するか

    Returns
    -------
    SimulationSummary
    """
    env = MAPFEnv(config)
    obs, info = env.reset()

    if verbose:
        print(f"[開始] エージェント数={len(config.agent_configs)}, "
              f"max_steps={config.max_steps}, "
              f"render_mode={render_mode}")

    # GIF / PNG モード用の Visualizer を初期化
    viz = None
    gif_frames: List[bytes] = []

    if render_mode in ("png", "gif", "show"):
        from utils.visualizer import Visualizer
        viz = Visualizer(env.graph, env.agents)
        if render_mode == "png":
            os.makedirs(output_dir, exist_ok=True)

    # 初期フレーム（step=0）を記録
    if viz and render_mode == "gif":
        gif_frames.append(viz.capture_frame(step=0))

    terminated = False
    truncated  = False

    while not (terminated or truncated):
        result = env.step()
        terminated = result.terminated
        truncated  = result.truncated
        step       = env._step_count

        # エージェントリストを Visualizer に反映
        if viz:
            viz.agents = env.agents

        # --- テキスト出力 ---
        if render_mode == "text":
            if step % render_interval == 0 or terminated or truncated:
                env.render(mode="text")

        # --- PNG 出力 ---
        elif render_mode == "png":
            if step % render_interval == 0 or terminated or truncated:
                path = os.path.join(output_dir, f"step_{step:04d}.png")
                viz.render_frame(step=step, save_path=path)

        # --- GIF 用フレーム収集 ---
        elif render_mode == "gif":
            gif_frames.append(viz.capture_frame(step=step))

        # --- リアルタイム GUI 表示 ---
        elif render_mode == "show":
            if step % render_interval == 0 or terminated or truncated:
                import matplotlib.pyplot as plt
                import matplotlib
                matplotlib.use("TkAgg")
                plt.ion()
                viz.show_live(step=step)

    # --- GIF 保存 ---
    if render_mode == "gif" and gif_frames:
        out_path = gif_path or os.path.join(output_dir, "simulation.gif")
        os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
        viz.save_gif(gif_frames, out_path, fps=4)

    summary = env.get_summary()

    if verbose:
        print(summary)

    env.close()
    return summary