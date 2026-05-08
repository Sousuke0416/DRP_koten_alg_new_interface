# MAPF Gym 互換環境

## ファイル構成
変更
```
mapf_env/
├── graph/
│   ├── __init__.py
│   └── map_graph.py        # 重み付き無向グラフ管理
├── agents/
│   ├── __init__.py
│   └── agent.py            # エージェント状態・移動ロジック
├── env/
│   ├── __init__.py
│   ├── mapf_env.py         # Gym 互換環境本体
│   └── collision.py        # 衝突判定
├── utils/
│   ├── __init__.py
│   ├── runner.py           # シミュレーション実行ユーティリティ
│   └── map_presets.py      # マップ定義プリセット
└── examples/
    ├── example_grid.py     # グリッドマップの例
    ├── example_unreachable.py  # 到達不能の例
    └── example_collision.py    # 衝突の例
```

## 仕様

| 項目 | 値 |
|------|---|
| エージェント速度 | 5 / step |
| 衝突判定距離 | < 5（未満） |
| 方向転換 | エッジ上では不可 |
| ゴール後 | ノードを占有（他エージェント進入不可） |

## 使い方

```python
from env.mapf_env import EnvConfig, AgentConfig
from utils.runner import run_simulation
from utils.map_presets import grid_map

map_data = grid_map(rows=4, cols=4, weight=5.0)
config = EnvConfig(
    map_data=map_data,
    agent_configs=[
        AgentConfig(agent_id=0, start_node=0, goal_node=15),
        AgentConfig(agent_id=1, start_node=15, goal_node=0),
    ],
    max_steps=500,
)
summary = run_simulation(config, verbose=True)
```
