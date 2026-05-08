# MAPF シミュレーション環境

重み付き無向グラフ上のマルチエージェント経路計画（MAPF）シミュレーション環境。
Gym 互換インターフェースで構築されており、Dijkstra・CBS・PIBT の3種のプランナーを切り替えて実験できる。

---

## ファイル構成

```
mapf_env/
├── graph/
│   ├── __init__.py
│   └── map_graph.py             # 重み付き無向グラフ管理・Dijkstra経路探索
│
├── agents/
│   ├── __init__.py
│   └── agent.py                 # エージェント状態・移動ロジック・待機・方向転換禁止
│
├── env/
│   ├── __init__.py
│   ├── mapf_env.py              # Gym互換環境本体（reset / step / render）
│   ├── collision.py             # 衝突判定（エージェント間距離 < 5 で COLLIDED）
│   └── validation.py           # エージェント設定バリデーション
│
├── planners/
│   ├── __init__.py
│   ├── cbs.py                   # Conflict-Based Search（時空間A*・衝突回避保証）
│   └── pibt.py                  # Priority Inheritance with Backtracking
│
├── utils/
│   ├── __init__.py
│   ├── runner.py                # 実験実行・設定表示・進捗バー・描画管理
│   ├── visualizer.py            # matplotlib描画・GIF/PNG/HTML生成
│   └── map_presets.py           # グリッド・直線・スター等のマップ自動生成
│
├── map_definitions.py           # マップ定義ファイル（データ形式の解説付き）
├── requirements.txt
└── examples/
    ├── example_nmap.py          # メイン実験スクリプト（設定欄を書き換えるだけ）
    ├── example_grid.py          # グリッドマップの動作確認例
    ├── example_collision.py     # 衝突シナリオの例
    ├── example_unreachable.py   # 到達不能シナリオの例
    └── example_render.py        # 描画機能の確認例
```

---

## 環境仕様

| 項目 | 内容 |
|---|---|
| グラフ | 重み付き無向グラフ |
| エージェント速度 | 5 / step（固定） |
| エッジ上の方向転換 | 不可（進行方向へ進むか待機のみ） |
| ノード上の行動 | 接続エッジへ進むか待機 |
| 衝突判定 | エージェント間の連続座標距離 < 5 で COLLIDED |
| ゴール占有 | ゴール到達済みエージェントのノードは他エージェント進入不可 |
| 終了条件 | 全員ゴール / 1体でも衝突 / 1体でもSTUCK / max_steps超過 |

### エージェントのステータス

| ステータス | 説明 |
|---|---|
| MOVING | 移動中 |
| GOAL | ゴール到達（ノードを永久占有） |
| COLLIDED | 衝突停止（距離 < 5） |
| STUCK | 到達不能（経路なし or 占有ブロック） |
| WAITING | 待機中（初期状態） |

---

## プランナー

| プランナー | 衝突回避 | 最適性 | 速度 | 推奨用途 |
|---|---|---|---|---|
| `"dijkstra"` | なし | 各自最短 | 最速 | 動作確認・デバッグ |
| `"cbs"` | 保証あり | 最適 | 低速 | エージェント数 ≤ 8体 |
| `"pibt"` | ほぼ回避 | 非最適 | 高速 | エージェント数が多い場合 |

### 制約の扱い

- **ゴールノード占有制約**：ゴール到達済みエージェントのノードへは進入不可。
  CBS・PIBTとも計画段階でこの制約を考慮する。
  占有ノードを通過しないと解けないシナリオでは正しく **STUCK** と判定される。
- **エッジ上での方向転換禁止**：CBS（時空間A*の `on_edge_next`）・PIBT（`plan_step` の強制方向）ともに対応済み。
- **待機行動**：CBS は時空間A* 内で「同一ノードに留まる」選択肢を持つ。
  PIBT は候補リストの末尾に現在ノードを追加して待機を表現する。

---

## 描画モード

| モード | 説明 |
|---|---|
| `"interactive"` | ブラウザで開く HTML ビューア。手動 step 送り・速度調整スライダー付き（推奨） |
| `"gif"` | GIF アニメーション保存。`gif_fps` で速度調整（0.5〜4.0） |
| `"png"` | 各ステップを PNG として保存 |
| `"text"` | テキストログをターミナル出力 |
| `None` | 描画なし |

出力先は `outputs/<スクリプト名>/<YYYYMMDD_HHMMSS>/` に自動生成される。

---

## クイックスタート

### インストール

```bash
pip install -r requirements.txt
```

### 実験の実行

```bash
cd mapf_env
python3 examples/example_nmap.py
```

`example_nmap.py` の設定欄を書き換えるだけで実験を切り替えられる。

```python
# ── 使用するマップ ──
MAP_DATA = MAP_GRID_4x4          # MAP_LINE_5 / MAP_GRID_5x5 / MAP_WAREHOUSE など

# ── エージェント設定 ──
AGENT_CONFIGS = [
    AgentConfig(agent_id=0, start_node=0,  goal_node=15),
    AgentConfig(agent_id=1, start_node=3,  goal_node=12),
]

# ── プランナー ──
PLANNER = "cbs"                  # "dijkstra" / "cbs" / "pibt"

# ── 描画モード ──
RENDER_MODE = "interactive"      # "interactive" / "gif" / "png" / "text" / None

# ── GIF速度（gif モード時のみ有効） ──
GIF_FPS = 1.0                    # 4.0=速い  1.0=ゆっくり  0.5=非常にゆっくり
```

### コードから直接使う

```python
from env.mapf_env import EnvConfig, AgentConfig
from utils.runner import run_simulation
from map_definitions import MAP_GRID_4x4

config = EnvConfig(
    map_data      = MAP_GRID_4x4,
    agent_configs = [
        AgentConfig(agent_id=0, start_node=0,  goal_node=15),
        AgentConfig(agent_id=1, start_node=3,  goal_node=12),
    ],
    max_steps = 200,
    planner   = "cbs",           # "dijkstra" / "cbs" / "pibt"
)

summary = run_simulation(
    config,
    render_mode = "interactive", # 手動でstepを進めるHTMLビューア
    gif_fps     = 1.0,           # gif モード時の速度
    caller_file = __file__,      # 出力フォルダ名に使用
    verbose     = True,
)
print(f"到達: {summary.reached}/{summary.total_agents}")
```

---

## マップ定義

`map_definitions.py` に定義済みのマップと、カスタムマップの書き方を記載している。

### 定義済みマップ

| 変数名 | 構造 | ノード数 |
|---|---|---|
| `MAP_LINE_5` | 一直線 | 5 |
| `MAP_GRID_4x4` | 4×4 グリッド | 16 |
| `MAP_GRID_5x5` | 5×5 グリッド | 25 |
| `MAP_WAREHOUSE` | 倉庫風（棚あり） | 21 |
| `MAP_SPLIT` | 非連結（到達不能テスト用） | 6 |
| `MAP_CUSTOM_EXAMPLE` | T字路 | 5 |

### カスタムマップのデータ形式

```python
MY_MAP = {
    "nodes": [
        {"id": 0, "x":  0.0, "y": 0.0},
        {"id": 1, "x": 10.0, "y": 0.0},
        {"id": 2, "x": 20.0, "y": 0.0},
    ],
    "edges": [
        {"u": 0, "v": 1, "weight": 10.0},  # weight = 物理的な距離
        {"u": 1, "v": 2, "weight": 10.0},  # speed=5 なので 2 step で通過
    ],
}
```

- `weight` は正の値のみ。エージェント speed=5 なので `weight=5` で 1 step 通過。
- グラフは**無向**（u→v と v→u の両方向に通行可能）。

---

## バリデーション

`reset()` 呼び出し時に以下を自動チェックし、違反があれば `ConfigValidationError` を送出する。

1. `agent_id` の重複
2. `start_node` / `goal_node` がグラフに存在するか
3. 複数エージェントで同じ `start_node` を使っていないか
4. 複数エージェントで同じ `goal_node` を使っていないか
5. 同一エージェントで `start_node == goal_node` になっていないか

---

## 出力ファイル

```
outputs/
└── example_nmap/                # スクリプト名
    └── 20260508_120000/         # 実験時刻
        ├── viewer.html          # interactive モード
        ├── simulation.gif       # gif モード
        └── step_0001.png        # png モード（step ごと）
```