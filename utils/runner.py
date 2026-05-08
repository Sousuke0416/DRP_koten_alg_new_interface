"""
utils/runner.py
シミュレーション実行ユーティリティ

描画モード一覧:
  render_mode="text"        : テキストログをコンソール出力
  render_mode="png"         : 各ステップの静止画を PNG 保存
  render_mode="gif"         : GIF アニメーション保存（gif_fps で速度調整）
  render_mode="interactive" : ブラウザで開く HTML ビューア（手動 step 送り）
  render_mode="show"        : GUI ウィンドウにリアルタイム表示（要 GUI 環境）

GIF 速度の目安（gif_fps）:
  4.0 = 速い   2.0 = ゆっくり（推奨）   1.0 = さらにゆっくり   0.5 = 非常にゆっくり

出力先（自動生成）:
  outputs/<スクリプト名>/<YYYYMMDD_HHMMSS>/simulation.gif
  outputs/<スクリプト名>/<YYYYMMDD_HHMMSS>/step_XXXX.png
  outputs/<スクリプト名>/<YYYYMMDD_HHMMSS>/viewer.html
"""

from __future__ import annotations
import os
import sys
import inspect
import time as _time_module
from datetime import datetime
from typing import List, Optional

from env.mapf_env import MAPFEnv, EnvConfig, SimulationSummary


# ================================================================== #
#  実験設定の表示
# ================================================================== #

def _map_name(map_data: dict) -> str:
    n_nodes = len(map_data.get("nodes", []))
    n_edges = len(map_data.get("edges", []))
    return f"{n_nodes} nodes, {n_edges} edges"


def print_experiment_info(
    config: EnvConfig,
    render_mode: Optional[str],
    output_path: Optional[str],
    gif_fps: float = 2.0,
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
        "gif":         f"GIF アニメーション保存（{gif_fps} fps）",
        "png":         "PNG 静止画保存（各ステップ）",
        "text":        "テキストログ出力",
        "show":        "リアルタイム GUI 表示",
        "interactive": "HTML インタラクティブビューア（手動 step 送り）",
        None:          "なし",
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


# ================================================================== #
#  進捗バー
# ================================================================== #

def _progress_bar(step: int, max_steps: int, elapsed: float, width: int = 34) -> str:
    """進捗バー文字列を生成する（\r で上書きする想定）"""
    ratio   = min(step / max_steps, 1.0) if max_steps > 0 else 1.0
    filled  = int(width * ratio)
    bar     = "█" * filled + "░" * (width - filled)
    pct     = int(ratio * 100)
    eta_str = f"~{(elapsed / ratio - elapsed):.1f}s" if ratio > 0 else "---"
    return (f"\r  [{bar}] {pct:3d}%  "
            f"step {step:>4}/{max_steps}  "
            f"経過 {elapsed:.1f}s  残り {eta_str}  ")


# ================================================================== #
#  出力パスの自動生成
# ================================================================== #

def _make_output_dir(caller_file: Optional[str]) -> str:
    script_name = (os.path.splitext(os.path.basename(caller_file))[0]
                   if caller_file else "experiment")
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir     = os.path.join("outputs", script_name, timestamp)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


# ================================================================== #
#  HTML インタラクティブビューア
# ================================================================== #

def _build_interactive_html(frames_b64: List[str], summary_text: str) -> str:
    """全フレームを Base64 埋め込みした自己完結 HTML を生成する"""
    frames_json     = "[" + ",".join(f'"{f}"' for f in frames_b64) + "]"
    summary_escaped = (summary_text
                       .replace("\\", "\\\\")
                       .replace('"', '\\"')
                       .replace("\n", "\\n"))

    return (
        '<!DOCTYPE html>\n'
        '<html lang="ja">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<title>MAPF Interactive Viewer</title>\n'
        '<style>\n'
        '*{box-sizing:border-box;margin:0;padding:0}\n'
        'body{font-family:"Segoe UI",sans-serif;background:#1a1a2e;color:#eee;'
        'display:flex;flex-direction:column;align-items:center;'
        'min-height:100vh;padding:24px;gap:12px}\n'
        'h1{font-size:1.4rem;color:#a8d8ea;letter-spacing:.05em}\n'
        '#frame-wrap{position:relative}\n'
        '#frame{max-width:860px;width:100%;border-radius:12px;'
        'box-shadow:0 8px 32px rgba(0,0,0,.5);display:block}\n'
        '.badge{position:absolute;top:12px;right:16px;background:rgba(0,0,0,.6);'
        'color:#fff;font-size:1.1rem;font-weight:bold;padding:4px 14px;border-radius:20px}\n'
        '.pw{width:min(860px,100%)}\n'
        '#progress{width:100%;accent-color:#22b573;cursor:pointer}\n'
        '.ctrl{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;align-items:center}\n'
        'button{padding:10px 22px;border:none;border-radius:8px;font-size:1rem;'
        'font-weight:bold;cursor:pointer;transition:opacity .15s,transform .1s}\n'
        'button:hover{opacity:.85;transform:scale(1.04)}\n'
        '#bp,#bn{background:#4a4e69;color:#fff}\n'
        '#bpl{background:#22b573;color:#fff;min-width:90px}\n'
        '#bf,#bl{background:#2d2d44;color:#aaa}\n'
        '.sw{display:flex;align-items:center;gap:8px;color:#aaa;font-size:.9rem}\n'
        '#speed{width:120px;accent-color:#22b573}\n'
        '#summary{width:min(860px,100%);background:#16213e;border-radius:10px;'
        'padding:16px 20px;font-family:monospace;font-size:.85rem;white-space:pre;'
        'color:#c8f0c8;box-shadow:0 4px 12px rgba(0,0,0,.4)}\n'
        '.hint{font-size:.8rem;color:#555}\n'
        'kbd{background:#3a3a5c;border-radius:4px;padding:1px 6px;'
        'font-size:.8rem;color:#ccc;margin:0 2px}\n'
        '</style>\n'
        '</head>\n'
        '<body>\n'
        '<h1>&#x1F916; MAPF Interactive Viewer</h1>\n'
        '<div id="frame-wrap">\n'
        '  <img id="frame" src="" alt="frame">\n'
        '  <div class="badge">Step <span id="sn">0</span> / <span id="sm">0</span></div>\n'
        '</div>\n'
        '<div class="pw"><input type="range" id="progress" min="0" value="0"></div>\n'
        '<div class="ctrl">\n'
        '  <button id="bf" title="最初へ">&#x23EE;</button>\n'
        '  <button id="bp" title="前へ">&#x25C4; 前へ</button>\n'
        '  <button id="bpl" title="再生/停止">&#x25BA; 再生</button>\n'
        '  <button id="bn" title="次へ">次へ &#x25BA;</button>\n'
        '  <button id="bl" title="最後へ">&#x23ED;</button>\n'
        '  <div class="sw">&#x1F422;<input type="range" id="speed" '
        'min="0.25" max="8" step="0.25" value="1">'
        '<span id="sv">1.00</span> fps&#x1F407;</div>\n'
        '</div>\n'
        '<p class="hint">'
        '<kbd>&#x2190;</kbd>前へ&nbsp;<kbd>&#x2192;</kbd>次へ&nbsp;'
        '<kbd>Space</kbd>再生/停止&nbsp;<kbd>Home</kbd>先頭&nbsp;<kbd>End</kbd>末尾'
        '</p>\n'
        '<pre id="summary"></pre>\n'
        '<script>\n'
        f'const F={frames_json};\n'
        'const N=F.length;\n'
        'let c=0,pl=false,tm=null;\n'
        'const img=document.getElementById("frame");\n'
        'const sn=document.getElementById("sn");\n'
        'const sm=document.getElementById("sm");\n'
        'const pg=document.getElementById("progress");\n'
        'const sp=document.getElementById("speed");\n'
        'const sv=document.getElementById("sv");\n'
        'const bpl=document.getElementById("bpl");\n'
        'sm.textContent=N-1;pg.max=N-1;\n'
        f'document.getElementById("summary").textContent="{summary_escaped}";\n'
        'function show(i){c=Math.max(0,Math.min(N-1,i));'
        'img.src="data:image/png;base64,"+F[c];'
        'sn.textContent=c;pg.value=c;'
        'if(c===N-1&&pl)stop();}\n'
        'function fps(){return parseFloat(sp.value);}\n'
        'function start(){pl=true;bpl.textContent="⏸ 停止";'
        'tm=setInterval(()=>show(c+1),1000/fps());}\n'
        'function stop(){pl=false;bpl.textContent="▶ 再生";clearInterval(tm);}\n'
        'document.getElementById("bp").onclick=()=>{stop();show(c-1);};\n'
        'document.getElementById("bn").onclick=()=>{stop();show(c+1);};\n'
        'document.getElementById("bf").onclick=()=>{stop();show(0);};\n'
        'document.getElementById("bl").onclick=()=>{stop();show(N-1);};\n'
        'bpl.onclick=()=>pl?stop():(c===N-1&&show(0),start());\n'
        'pg.oninput=()=>{stop();show(parseInt(pg.value));};\n'
        'sp.oninput=()=>{sv.textContent=parseFloat(sp.value).toFixed(2);'
        'if(pl){stop();start();}};\n'
        'document.addEventListener("keydown",e=>{\n'
        '  if(e.key==="ArrowRight"){e.preventDefault();stop();show(c+1);}\n'
        '  if(e.key==="ArrowLeft"){e.preventDefault();stop();show(c-1);}\n'
        '  if(e.key===" "){e.preventDefault();bpl.click();}\n'
        '  if(e.key==="Home"){e.preventDefault();stop();show(0);}\n'
        '  if(e.key==="End"){e.preventDefault();stop();show(N-1);}\n'
        '});\n'
        'show(0);\n'
        '</script>\n'
        '</body>\n'
        '</html>\n'
    )


# ================================================================== #
#  メイン実行関数
# ================================================================== #

def run_simulation(
    config: EnvConfig,
    render_mode: Optional[str] = None,
    render_interval: int = 1,
    output_dir: Optional[str] = None,
    gif_path: Optional[str] = None,
    gif_fps: float = 2.0,
    verbose: bool = True,
    caller_file: Optional[str] = None,
) -> SimulationSummary:
    """
    シミュレーションを最後まで実行してサマリーを返す。

    Parameters
    ----------
    config          : 環境設定
    render_mode     : None / "text" / "png" / "gif" / "interactive" / "show"
    render_interval : "png" / "text" モード時に何 step 毎に出力するか
    output_dir      : 保存先ディレクトリ（None で自動生成）
    gif_path        : GIF 保存先パス（None で自動生成）
    gif_fps         : GIF のフレームレート（デフォルト 2.0 fps）
    verbose         : 実験設定・進捗バー・サマリーを表示するか
    caller_file     : 呼び出し元の __file__（出力フォルダ名に使用）
    """
    # 呼び出し元ファイルを自動検出
    if caller_file is None:
        for f in inspect.stack()[1:]:
            if f.filename != __file__:
                caller_file = f.filename
                break

    # 出力先ディレクトリを決定
    needs_output = render_mode in ("png", "gif", "interactive")
    if needs_output and output_dir is None:
        output_dir = _make_output_dir(caller_file)

    if render_mode == "gif" and gif_path is None and output_dir:
        gif_path = os.path.join(output_dir, "simulation.gif")

    html_path = (os.path.join(output_dir, "viewer.html")
                 if render_mode == "interactive" and output_dir else None)

    # 実験設定の表示
    if verbose:
        display_path = (gif_path  if render_mode == "gif" else
                        html_path if render_mode == "interactive" else
                        output_dir)
        print_experiment_info(config, render_mode, display_path, gif_fps)

    env = MAPFEnv(config)
    env.reset()

    # Visualizer の初期化
    viz: Optional[object] = None
    gif_frames: List[bytes] = []

    if render_mode in ("png", "gif", "interactive", "show"):
        from utils.visualizer import Visualizer
        viz = Visualizer(env.graph, env.agents)

    if viz and render_mode in ("gif", "interactive"):
        gif_frames.append(viz.capture_frame(step=0))

    terminated = False
    truncated  = False
    sim_start  = _time_module.perf_counter()

    # ── メインループ ──────────────────────────────────────────────
    while not (terminated or truncated):
        result     = env.step()
        terminated = result.terminated
        truncated  = result.truncated
        step       = env._step_count
        elapsed    = _time_module.perf_counter() - sim_start

        if viz:
            viz.agents = env.agents

        # 進捗バー
        if verbose and render_mode != "text":
            sys.stdout.write(_progress_bar(step, config.max_steps, elapsed))
            sys.stdout.flush()

        if render_mode == "text":
            if step % render_interval == 0 or terminated or truncated:
                env.render(mode="text")

        elif render_mode == "png":
            if step % render_interval == 0 or terminated or truncated:
                path = os.path.join(output_dir, f"step_{step:04d}.png")
                viz.render_frame(step=step, save_path=path)

        elif render_mode in ("gif", "interactive"):
            gif_frames.append(viz.capture_frame(step=step))

        elif render_mode == "show":
            if step % render_interval == 0 or terminated or truncated:
                import matplotlib.pyplot as plt, matplotlib
                matplotlib.use("TkAgg"); plt.ion()
                viz.show_live(step=step)

    # 進捗バー終端
    if verbose and render_mode != "text":
        sys.stdout.write("\n")
        sys.stdout.flush()

    # GIF 保存
    if render_mode == "gif" and gif_frames:
        os.makedirs(
            os.path.dirname(gif_path) if os.path.dirname(gif_path) else ".",
            exist_ok=True,
        )
        viz.save_gif(gif_frames, gif_path, fps=gif_fps)

    summary = env.get_summary()
    if verbose:
        print(summary)

    # インタラクティブ HTML 保存
    if render_mode == "interactive" and gif_frames and html_path:
        import base64
        frames_b64 = [base64.b64encode(f).decode() for f in gif_frames]
        html       = _build_interactive_html(frames_b64, str(summary))
        with open(html_path, "w", encoding="utf-8") as fp:
            fp.write(html)
        print(f"  [interactive] HTML 保存: {html_path}")
        print(f"  → ブラウザで開いてください")

    env.close()
    return summary