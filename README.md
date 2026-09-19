# Normal Shock Service

常驻的正激波（Rankine–Hugoniot）核算服务。给定来流马赫数 M1 与比热比 γ，
返回波后马赫数、静压比、静温比、密度比与总压恢复系数；给足有量纲来流
静压/静温时，同时给出两侧静/滞止全状态（p、T、ρ、a、u、ρu、p0、T0）。

## 物理模型

闭式关系（`app/shock.py`）：

- 密度比 ρ2/ρ1 = (γ+1)M1² / ((γ−1)M1² + 2)
- 静压比 p2/p1 = 1 + 2γ(M1²−1)/(γ+1)
- 静温比 T2/T1 = (p2/p1)/(ρ2/ρ1)
- M2² = (1 + (γ−1)M1²/2) / (γM1² − (γ−1)/2)

滞止量（`app/stagnation.py`）只在激波**单侧**做等熵换算：来流静量升到
波前总量，波后静量升到波后总量；总温跨激波不变（T02 = T01），总压下降，
恢复系数 p02/p01 由两侧各自的等熵升压组合得到，绝不用等熵关系直接跨激波。

## 模块划分

| 模块 | 职责 |
|---|---|
| `app/shock.py` | Rankine–Hugoniot 间断关系内核 + 有量纲全状态合成 |
| `app/stagnation.py` | 等熵滞止关系、声速、气体常数 |
| `app/validation.py` | 输入校验与带类型的结构化错误 |
| `app/registry.py` | 具名工况的内存登记（重启即失，不落库） |
| `app/evaluation.py` | 单条/批量共用的唯一求值管线 |
| `app/routes.py` | HTTP 路由（薄层，无物理逻辑） |
| `app/main.py` | 应用装配、异常处理器、预置工况 |

## API

- `POST /evaluate` — 一次性求值：`{"mach": 2.0, "gamma": 1.4, "static_pressure": 101325, "static_temperature": 288.15}`（后两者可选）
- `POST /cases` — 登记具名工况（+ `name` 字段），201 返回
- `GET /cases` — 回显全部已登记工况（只读）
- `GET /cases/{name}/result` — 按工况名求值
- `POST /batch` — 批量：`{"gamma": 1.4, "machs": [1.5, 2.0, 3.0]}`，单条非法只让该条失败
- `GET /health` — 运行状态（uptime、已登记工况数）

错误统一为 `{"error": {"type": ..., "message": ...}}`：
`missing_mach` / `invalid_mach`（M1 ≤ 1）/ `invalid_gamma`（γ ≤ 1）/
`invalid_static_quantity`（非正静压静温）→ 422；
`unknown_case` → 404；`duplicate_case` → 409。

预置工况 `m2_gamma14`（M1=2, γ=1.4, p1=101325 Pa, T1=288.15 K），
手算对账：M2≈0.57735，p2/p1=4.5，ρ2/ρ1≈2.6667，T2/T1=1.6875，p02/p01≈0.72087。

## 运行

```bash
# Docker（推荐）
docker build -t normal-shock .
docker run -p 8000:8000 normal-shock

# 本地
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 测试

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```

覆盖：M1=2/γ=1.4 闭式对账、单调性（M1↑ → p 比↑、M2↓）、M1→1⁺ 弱激波极限、
强激波渐近（M2→√((γ−1)/2γ)、ρ 比→(γ+1)/(γ−1)）、总温跨激波不变、
质量通量 ρu 两侧相等、压缩而非膨胀、各类非法输入拦截、单条与批量一致性、
并发不串扰。
