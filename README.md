# Normal-Shock Service

一个只做**正激波 Rankine–Hugoniot 间断**核算的常驻 HTTP 服务（Python 3.12 + FastAPI）。

给定来流马赫数 `M1` 和比热比 `γ`（可选来流静压 `p1`、静温 `T1`），返回：

- 波后马赫数 `M2`
- 静压比 `p2/p1`
- 静温比 `T2/T1`
- 密度比 `ρ2/ρ1`
- 总压恢复系数 `P02/P01`
- 给了有量纲来流时，顺带给出波前/波后的静态与滞止全套量，以及两侧质量通量 `ρu` 的核对值

不做面积-马赫关系、不做升力线、不涉及座舱仪表或航班时刻。工况登记只在内存，重启清空。

## 闭式关系（数学内核）

```
ρ2/ρ1 = (γ+1)·M1² / ((γ−1)·M1² + 2)
p2/p1 = 1 + 2γ·(M1²−1)/(γ+1)
T2/T1 = (p2/p1) / (ρ2/ρ1)
M2²   = (1 + (γ−1)/2·M1²) / (γ·M1² − (γ−1)/2)
```

滞止量：波前、波后各自用等熵关系升总压总温；**绝不用等熵关系跨过激波凑 p2**。
总温跨激波不变，总压恢复系数 = `P02 / P01`（`P02 = (p2/p1)·p1·π(M2)` 与 `(p2/p1)·π(M2)/π(M1)` 两种写法一致）。

## 预置手算工况

`seed-m2-g1.4`：`M1=2, γ=1.4`，闭式表值：

| M2 | p2/p1 | T2/T1 | ρ2/ρ1 | P02/P01 |
|---|---|---|---|---|
| 0.5774 | 4.5 | 1.6875 | 2.6667 | 0.7209 |

## 运行

```bash
docker compose up --build        # http://localhost:8000  ，文档 /docs
# 或不用容器：
python3.12 -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET  | `/healthz` | 运行状态（uptime、已登记工况数） |
| GET  | `/` | 服务简介 |
| POST | `/shock/evaluate` | 单次临时求值，条件写在请求体 |
| POST | `/cases` | 登记具名工况（内存） |
| GET  | `/cases` | 只读回显所有已登记工况 |
| GET  | `/cases/{name}` | 按工况名取回波后结果 |
| POST | `/shock/batch` | 一串马赫数批量求值，单条非法不影响其余 |

错误均为结构化、带类型的 JSON：`{"error": {"code": "...", "message": "..."}}`。

### 单次临时求值

```bash
curl -s localhost:8000/shock/evaluate \
  -H 'content-type: application/json' \
  -d '{"mach1": 2.0, "gamma": 1.4, "p1": 101325, "t1": 288.15}'
```

### 登记工况 → 按名取回

```bash
curl -s -X POST localhost:8000/cases -H 'content-type: application/json' \
  -d '{"name": "cruise", "mach1": 2.5, "gamma": 1.4}'
curl -s localhost:8000/cases/cruise
```

### 批量（激波极曲线）

```bash
curl -s -X POST localhost:8000/shock/batch -H 'content-type: application/json' \
  -d '{"gamma": 1.4, "machs": [1.2, 1.5, 2.0, 0.8]}'
```

批量与单条走同一个求值函数；非法条目只让自己失败：

```json
{"results": [
  {"mach1": 1.2, "status": "ok", "solution": {...}},
  {"mach1": 0.8, "status": "error",
   "error": {"code": "MACH_NOT_SUPERSONIC", "message": "..."}}
]}
```

## 非法输入（开算前挡下，HTTP 422/404/409）

- `mach1 <= 1` → `MACH_NOT_SUPERSONIC`
- `gamma <= 1` → `GAMMA_INVALID`
- 缺马赫数 → `MACH_MISSING`
- 有量纲输入中 `p1`/`T1`/`R` 非正 → `DIMENSIONAL_INPUT_INVALID`
- 点没登记过的工况名 → `CASE_NOT_FOUND`（404）
- 重名登记 → `CASE_ALREADY_EXISTS`（409）

## 测试

```bash
python3.12 -m pip install -r dev-requirements.txt
pytest -q
```

覆盖：M1=2 闭式表值、方向性（p2/p1 随 M1 升、M2 下降并趋于 √((γ−1)/(2γ))）、
密度比上限随 γ 变化、总温跨激波不变、质量通量两侧相等、压缩方向（ρ2>ρ1、M2<1）、
各类非法输入拦截、单条/批量一致、并发互不串扰。

## 目录

```
app/
  errors.py        # 带类型的结构化错误
  config.py        # 常量/预置工况
  physics/
    shock.py       # RH 间断关系数学内核
    stagnation.py  # 等熵滞止关系（只在波前/波后同侧使用）
    validation.py  # 输入校验（开算前）
  services/
    evaluator.py   # 求值编排：校验 + 内核 + 滞止 + 有量纲量
    registry.py    # 内存具名工况登记（线程安全）
  schemas.py       # HTTP 请求/响应模型
  api.py           # 路由
  main.py          # ASGI 入口、错误处理、启动预置工况
tests/             # pytest
```
