"""
utils/visualizer.py
描画モジュール

対応する出力形式:
  - インタラクティブ表示 (matplotlib GUI ウィンドウ)
  - PNG 静止画 (1 step 分)
  - GIF アニメーション (シミュレーション全体)

使い方:
    viz = Visualizer(graph, agents, figsize=(10, 8))

    # --- 静止画 (1フレーム) ---
    viz.render_frame(step=3, save_path="frame.png")

    # --- インタラクティブ表示 ---
    viz.show()

    # --- GIF アニメーション生成 ---
    viz = Visualizer(graph, agents)
    frames = []
    while not done:
        result = env.step()
        frames.append(viz.capture_frame(step=env._step_count))
    viz.save_gif(frames, "simulation.gif", fps=4)
"""

from __future__ import annotations

import io
from typing import List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")          # ヘッドレス環境でも動作するバックエンド
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import networkx as nx
import numpy as np

from graph.map_graph import MapGraph
from agents.agent import Agent, AgentStatus


# ------------------------------------------------------------------ #
#  カラーパレット
# ------------------------------------------------------------------ #

AGENT_COLORS = [
    "#E74C3C", "#3498DB", "#2ECC71", "#F39C12",
    "#9B59B6", "#1ABC9C", "#E67E22", "#34495E",
    "#E91E63", "#00BCD4", "#8BC34A", "#FF5722",
]

AGENT_COLOR_NAMES = [
    "Red", "Blue", "Green", "Orange",
    "Purple", "Teal", "Amber", "Slate",
    "Pink", "Cyan", "Lime", "Deep Orange",
]

NODE_COLOR      = "white"
NODE_EDGE_COLOR = "black"
EDGE_COLOR      = "#85929E"
BG_COLOR        = "#FDFEFE"


# ------------------------------------------------------------------ #
#  Visualizer 本体
# ------------------------------------------------------------------ #

class Visualizer:
    """
    MapGraph と Agent リストを受け取り、各種描画を担当するクラス。
    """

    def __init__(
        self,
        graph: MapGraph,
        agents: List[Agent],
        figsize: Tuple[float, float] = (10, 8),
    ):
        self.graph   = graph
        self.agents  = agents
        self.figsize = figsize

        # networkx グラフ構築（描画専用）
        self._nx_graph = nx.Graph()
        for node in graph.nodes:
            self._nx_graph.add_node(node)
        for u, v, w in graph.edges:
            self._nx_graph.add_edge(u, v, weight=w)

        self._pos = graph.position_dict()

        # エージェントIDごとに色を固定
        self._agent_color: dict = {}
        self._agent_color_name: dict = {}
        for i, a in enumerate(agents):
            self._agent_color[a.agent_id]      = AGENT_COLORS[i % len(AGENT_COLORS)]
            self._agent_color_name[a.agent_id] = AGENT_COLOR_NAMES[i % len(AGENT_COLOR_NAMES)]

    # ------------------------------------------------------------------ #
    #  公開 API
    # ------------------------------------------------------------------ #

    def render_frame(
        self,
        step: int,
        save_path: Optional[str] = None,
        show: bool = False,
    ) -> plt.Figure:
        """
        現在の状態を 1 フレーム描画する。
        save_path が指定されれば PNG 保存。
        show=True でGUI表示（ヘッドレス環境では無効）。
        """
        fig = self._build_figure(step)

        if save_path:
            fig.savefig(save_path, dpi=120, bbox_inches="tight",
                        facecolor=BG_COLOR)
            print(f"  [render] PNG 保存: {save_path}")

        if show:
            try:
                matplotlib.use("TkAgg")
                plt.show()
            except Exception:
                print("  [render] GUI 表示不可（ヘッドレス環境）")

        return fig

    def capture_frame(self, step: int) -> bytes:
        """
        現在フレームを PNG バイト列として返す（GIF 生成用）。
        """
        fig = self._build_figure(step)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                    facecolor=BG_COLOR)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def save_gif(
        self,
        frames: List[bytes],
        save_path: str,
        fps: float = 4.0,
        loop: int = 0,
    ) -> None:
        """
        capture_frame() で収集したフレームリストを GIF として保存する。

        Parameters
        ----------
        frames    : capture_frame() の戻り値リスト
        save_path : 保存先パス（.gif）
        fps       : フレームレート
        loop      : GIF ループ回数（0 = 無限）
        """
        try:
            from PIL import Image
        except ImportError:
            # Pillow なしでも matplotlib で連番 PNG → GIF 変換
            self._save_gif_fallback(frames, save_path, fps)
            return

        duration_ms = int(1000 / fps)
        images = [Image.open(io.BytesIO(f)).convert("RGBA") for f in frames]
        images[0].save(
            save_path,
            save_all=True,
            append_images=images[1:],
            duration=duration_ms,
            loop=loop,
            optimize=False,
        )
        print(f"  [render] GIF 保存: {save_path}  ({len(frames)} frames, {fps} fps)")

    def save_png_sequence(self, frames: List[bytes], out_dir: str) -> List[str]:
        """フレームを連番 PNG として保存する（デバッグ用）"""
        import os
        os.makedirs(out_dir, exist_ok=True)
        paths = []
        for i, frame in enumerate(frames):
            path = os.path.join(out_dir, f"frame_{i:04d}.png")
            with open(path, "wb") as f:
                f.write(frame)
            paths.append(path)
        print(f"  [render] {len(paths)} 枚の PNG を {out_dir} に保存")
        return paths

    # ------------------------------------------------------------------ #
    #  描画ロジック
    # ------------------------------------------------------------------ #

    def _build_figure(self, step: int) -> plt.Figure:
        fig, ax = plt.subplots(figsize=self.figsize)
        fig.patch.set_facecolor(BG_COLOR)
        ax.set_facecolor(BG_COLOR)

        # ── 正円を保証するために equal アスペクト比を設定 ──
        ax.set_aspect("equal", adjustable="datalim")

        self._draw_edges(ax)
        self._draw_nodes(ax)
        self._draw_agents(ax)
        self._draw_legend(ax)
        self._draw_status_panel(ax, step)

        ax.set_title(
            f"MAPF Simulation  —  Step {step}",
            fontsize=14, fontweight="bold", pad=12,
        )
        ax.axis("off")
        plt.tight_layout()
        return fig

    def _draw_edges(self, ax: plt.Axes) -> None:
        """エッジを描画（重みラベル付き）"""
        for u, v, w in self.graph.edges:
            x0, y0 = self._pos[u]
            x1, y1 = self._pos[v]
            ax.plot([x0, x1], [y0, y1], "-",
                    color=EDGE_COLOR, linewidth=2, zorder=1)
            # 重みラベル（エッジ中央）
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            ax.text(mx, my, f"{w:.1f}",
                    fontsize=7, color="#5D6D7E",
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15",
                              fc=BG_COLOR, ec="none", alpha=0.8),
                    zorder=2)

    def _draw_nodes(self, ax: plt.Axes) -> None:
        """ノードを描画。
        通常ノード : 背景=白, 枠=黒
        ゴールノード: 背景=白, 枠=そのエージェントの色（複数エージェントが同ゴールの場合は最初の色）
        """
        # goal_node → エージェント色 のマッピングを構築
        goal_node_color: dict = {}
        for a in self.agents:
            if a.goal_node not in goal_node_color:
                goal_node_color[a.goal_node] = self._agent_color[a.agent_id]

        for node in self.graph.nodes:
            x, y = self._pos[node]
            ec = goal_node_color.get(node, NODE_EDGE_COLOR)
            lw = 2.5 if node in goal_node_color else 1.5
            circle = plt.Circle(
                (x, y), radius=1.5,
                fc=NODE_COLOR, ec=ec,
                linewidth=lw, zorder=3,
            )
            ax.add_patch(circle)
            ax.text(
                x, y, str(node),
                fontsize=9, fontweight="bold",
                ha="center", va="center",
                color="#1A252F", zorder=4,
            )

    def _draw_agents(self, ax: plt.Axes) -> None:
        """エージェントをエッジ上の連続座標に描画"""
        for agent in self.agents:
            x, y = agent.get_continuous_position()
            color = self._agent_color[agent.agent_id]
            status = agent.status

            # ゴール済み・衝突・行き詰まりはリングで強調
            if status == AgentStatus.GOAL:
                ring = plt.Circle((x, y), radius=2.2,
                                   fc="none", ec="#F1C40F",
                                   linewidth=2.5, zorder=5)
                ax.add_patch(ring)
            elif status == AgentStatus.COLLIDED:
                ring = plt.Circle((x, y), radius=2.2,
                                   fc="none", ec="#E74C3C",
                                   linewidth=2.5, linestyle="--", zorder=5)
                ax.add_patch(ring)
            elif status == AgentStatus.STUCK:
                color = "#95A5A6"

            # エージェント本体
            circle = plt.Circle((x, y), radius=1.6,
                                  fc=color, ec="white",
                                  linewidth=1.5, zorder=6)
            ax.add_patch(circle)

            # ID テキスト
            ax.text(x, y, str(agent.agent_id),
                    fontsize=8, fontweight="bold",
                    ha="center", va="center",
                    color="white", zorder=7,
                    path_effects=[
                        pe.withStroke(linewidth=1.5, foreground="black")
                    ])

            # ゴールへの矢印（MOVING のみ）
            if status == AgentStatus.MOVING and self._pos.get(agent.goal_node):
                gx, gy = self._pos[agent.goal_node]
                ax.annotate(
                    "", xy=(gx, gy), xytext=(x, y),
                    arrowprops=dict(
                        arrowstyle="->",
                        color=color,
                        alpha=0.25,
                        lw=1.2,
                        connectionstyle="arc3,rad=0.1",
                    ),
                    zorder=2,
                )

    def _draw_legend(self, ax: plt.Axes) -> None:
        """凡例を描画。エージェントの色対応 + ステータス記号を表示"""
        legend_items = []

        # ── エージェント色の対応 ──
        for a in self.agents:
            color = self._agent_color[a.agent_id]
            cname = self._agent_color_name[a.agent_id]
            legend_items.append(
                mpatches.Patch(color=color, label=f"Agent {a.agent_id}  ({cname})")
            )

        # ── ステータス記号の説明 ──
        legend_items.append(mpatches.Patch(color="none", label="──────────"))
        legend_items.append(mpatches.Patch(facecolor="white", edgecolor="black",
                                            linewidth=1.5, label="Normal node"))
        legend_items.append(mpatches.Patch(facecolor="white", edgecolor="#E74C3C",
                                            linewidth=2.5, label="Goal node (agent color)"))
        legend_items.append(mpatches.Patch(color="#F1C40F",   label="GOAL ring"))
        legend_items.append(mpatches.Patch(color="#E74C3C",   label="COLLIDED ring"))
        legend_items.append(mpatches.Patch(color="#95A5A6",   label="STUCK"))

        ax.legend(
            handles=legend_items,
            loc="upper left",
            fontsize=8,
            framealpha=0.9,
            edgecolor="#BDC3C7",
            title="Legend",
            title_fontsize=8,
        )

    def _draw_status_panel(self, ax: plt.Axes, step: int) -> None:
        """右下にエージェントステータス一覧を表示"""
        lines = [f"Step: {step}"]
        for a in self.agents:
            sym = {"GOAL": "✔", "COLLIDED": "✖",
                   "STUCK": "–", "MOVING": "→", "WAITING": "…"
                   }.get(a.status.name, "?")
            lines.append(f"  {sym} Agent {a.agent_id}: {a.status.name}")

        text = "\n".join(lines)
        ax.text(
            0.99, 0.01, text,
            transform=ax.transAxes,
            fontsize=8, va="bottom", ha="right",
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.4",
                      fc=BG_COLOR, ec="#BDC3C7", alpha=0.9),
        )

    # ------------------------------------------------------------------ #
    #  Pillow なし GIF フォールバック
    # ------------------------------------------------------------------ #

    def _save_gif_fallback(
        self, frames: List[bytes], save_path: str, fps: float
    ) -> None:
        """
        Pillow が使えない場合は連番 PNG を保存し、
        matplotlib の animation を使って GIF を生成する。
        """
        try:
            import matplotlib.animation as animation

            pil_images = []
            for frame_bytes in frames:
                buf = io.BytesIO(frame_bytes)
                img = plt.imread(buf)
                pil_images.append(img)

            fig2, ax2 = plt.subplots(figsize=self.figsize)
            ax2.axis("off")
            im = ax2.imshow(pil_images[0])

            def update(i):
                im.set_data(pil_images[i])
                return [im]

            ani = animation.FuncAnimation(
                fig2, update, frames=len(pil_images),
                interval=int(1000 / fps), blit=True,
            )
            ani.save(save_path, writer="pillow", fps=fps)
            plt.close(fig2)
            print(f"  [render] GIF 保存 (fallback): {save_path}")
        except Exception as e:
            print(f"  [render] GIF 生成失敗: {e}")
            print("  → pip install Pillow を試してください")