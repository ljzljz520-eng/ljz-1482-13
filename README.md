# 角色工作室 · 版本与依赖管理 (Character Studio)

为角色设计页提供**不可变版本管理**与**显式依赖（引用）管理**的全栈系统：网页维护人物的
**外观 / 语气 / 参考图 / 限制词**，后台 API 写入 PostgreSQL 关系库，并为封面图生成异步派生任务。

> 核心承诺：改角色只能追加新版本，永不原地改写；脚本引用必须显式声明「固定某版」或「跟随最新版」；
> 已批准台词不会因角色改版而被悄悄重新解释——所有漂移都进入人工复核队列。

## ✨ 能力对照（需求 → 实现）

| 需求 | 实现 |
|---|---|
| 维护外观、语气、参考图、限制词 | `character_versions` 不可变版本，`reference_images` 绑定到**具体版本** |
| 脚本可固定某版 / 跟随最新，界面可见 | `script_character_links.ref_mode = pinned / floating`，场次页徽章明确显示 📌vN / 🔄跟随 |
| 修改角色后已批准台词不悄悄改变 | floating 引用改版后仅产生 `approved_drift` 待复核项，`approved_text` 冻结不变，需人工「确认复核」 |
| 删除前查真实反向引用 | 退役前 dry-run 查：脚本（场次）、生成素材、历史导出、固定/跟随数量 |
| 软删除保留引用 vs 替换后退役 | `soft_delete` 保留全部引用可恢复；`retire + 替代角色` 同事务迁移引用再退役，无替代且有引用则 409 |
| 并发安全退役 | `SELECT … FOR UPDATE` 行级锁 + `lock_version` 乐观锁；退役进行中新增引用被 409 拒绝 |
| 封面任务绑定原图与裁切参数 | `cover_jobs` 记录 source_asset_id、crop(x/y/w/h)、目标尺寸与 params 指纹 |
| 旧任务晚到不覆盖新角色卡 | 完成时检查同版本是否已有更晚的成功任务；晚到结果落盘审计但标记 `stale`，不生成 `generated_assets` |
| 动画仅在可见且允许动态效果时播放 | `useMotionAllowed`：IntersectionObserver + visibilitychange + `prefers-reduced-motion` 三者同时满足 |
| 验收：两人改同一字段 | 后提交者收到 409 并生成 `edit_conflict` 复核项 |
| 验收：退役时另一人新增引用 | 角色行锁互斥；非 active 角色新增引用返回 409 |
| 验收：素材生成失败 | 失败任务 + `generation_failed` 复核项，可一键重新入队（支持 force_fail 注入） |
| 验收：来源图授权撤销 | 返回受影响版本/场次/在途任务/历史导出影响面；worker 渲染时二次校验授权并中止 |
| 页面呈现受影响场次与待复核项 | 复核工作台：受影响场次、待复核项、失败/过期任务、软删除角色四区 |
| 权限在服务端检查 | JWT + RBAC（admin/editor/viewer），每个写接口强制角色校验，前端隐藏只是体验 |
| 清理未引用图片考虑历史导出 | GC 前检查 5 类引用：参考图 / 派生来源 / 派生产物 / 在途任务 / **历史导出快照**，任一存在即保留 |

## 🛠 技术栈

- **Frontend**: React 18 + TypeScript 5.2 + Vite 5 + Tailwind CSS 3 + Zustand + React Router 6 + react-hot-toast
- **Backend**: FastAPI + SQLAlchemy 2.0 (ORM) + Pydantic v2 + PyJWT + Pillow
- **Database**: PostgreSQL 16
- **Async Worker**: 独立 Python 进程，`FOR UPDATE SKIP LOCKED` 认领任务，与 API 共享 DB 与媒体卷
- **Infra**: Docker Compose 四服务（db / api / worker / frontend-nginx），命名卷持久化数据库与图片

## 🚀 启动指南 (How to Run)

1. 确保 Docker Desktop / Docker Engine 已启动。
2. 在仓库根目录执行：
   ```bash
   docker compose up --build
   ```
3. 等待数据库健康检查、种子执行完成（api 日志出现 `seed complete`）。
4. 浏览器访问：**http://localhost:3000**

## 🔗 服务地址

- Frontend: http://localhost:3000
- Backend Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health
- PostgreSQL: localhost:5432 （user/pass/db: `charapp / charapp / charstudio`）
- 容器内前端通过服务名访问后端：`http://api:8000`（nginx 反代 `/api`、`/media`）

## 🧪 测试账号（种子自动创建）

| 用户名 | 密码 | 角色 | 能做什么 |
|---|---|---|---|
| `admin` | 123456 | 管理员 | 全部权限；**退役角色、恢复软删除、物理清理图片**仅管理员可用 |
| `editor_a` | 123456 | 编剧（编辑） | 角色/版本/脚本/引用/批准台词/上传图片/封面任务/导出 |
| `editor_b` | 123456 | 美术（编辑） | 同上，用于演示两人并发修改同一角色 |
| `viewer` | 123456 | 访客（只读） | 只读；所有写接口服务端返回 403 |

种子数据：2 个角色共 3 个不可变版本、3 个场次（含固定 v1 与跟随最新两种引用、一条改版后待复核台词）、
参考图与 1 份历史导出快照。

## 🧭 推荐验收路径（四人场景）

1. **两人改同一字段**：用 `editor_a` 与 `editor_b` 分别打开「瑶光」详情；一人先发布新版本后，
   另一人用旧页面提交 → 409 冲突提示，「复核工作台」出现冲突项。
2. **已批准台词不被悄悄重释**：场次 S02 为跟随最新引用，批准基线停在 v1；瑶光升到 v2 后
   场次标黄「待复核（解释未改变）」，工作台「受影响场次」可见，点「确认复核」才重新冻结。
3. **退役时另一人新增引用**：管理员在退役弹窗执行「软删除/替换退役」期间，其他人对该角色
   新增引用会被 409 拒绝；退役弹窗先展示脚本/素材/导出真实引用数量；选择替代角色后引用在同一事务迁移，
   原已批准台词重置并进入复核。
4. **封面异步任务**：角色详情 →「封面派生任务」，选择来源图、调整裁切框（越界会被 422 拒绝），
   勾选「模拟素材生成失败」可验收失败入队与复核；连续创建两个任务（worker 有约 4s 处理延迟），
   先完成新任务、旧任务晚到 → 旧任务显示「旧任务·已归档」，不覆盖当前角色卡。
5. **来源图授权撤销**：图片库对任一参考图点「撤销授权」，弹窗给出受影响版本/场次/在途任务/
   历史导出数量；撤销后不能再派生封面，已在途任务 worker 会中止。
6. **清理未引用图片**：图片库每张图显示 5 类引用标记；管理员点「清理未引用图片」，
   只要还被历史导出（📦）引用，对象与物理文件都会保留。
7. **动效**：系统偏好开启「减少动态效果」或将标签页切到后台，封面处理脉冲、卡片 Ken Burns
   与入场动画都会暂停。

## 🗂 目录结构

```
.
├── docker-compose.yml          # db + api + worker + frontend 全容器编排
├── backend/
│   ├── Dockerfile / Dockerfile.worker
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI 入口、统一错误处理、静态媒体
│       ├── config.py database.py models.py schemas.py security.py deps.py
│       ├── seed.py             # 幂等种子（pg_advisory_xact_lock）
│       ├── worker.py           # 封面异步 worker（SKIP LOCKED 认领）
│       ├── routers/            # auth characters scripts images covers exports review
│       └── services/           # characters(版本/退役) scripts(引用/批准)
│                               # covers(派生/旧任务守卫) images(授权/GC)
│                               # references(反向引用) exports dashboard serializers
└── frontend/
    ├── Dockerfile nginx.conf   # 反代 /api 与 /media 到 api:8000
    └── src/
        ├── pages/              # Characters CharacterDetail Scripts Review Assets Exports Login
        ├── components/         # RetireFlow CoverJobPanel NewVersionModal ui 等
        ├── hooks/              # useMotionAllowed（动效守门） usePolling（可见时轮询）
        └── api/ store/ types.ts
```

## 🔒 关键并发与一致性设计

- **版本不可变**：所有修改走 `POST /characters/{id}/versions`，只 INSERT 新版本并推进
  `latest_version`；历史行永不 UPDATE/DELETE。
- **乐观锁**：角色带 `lock_version`，前端编辑时回传 `expected_lock_version`，不符则 409。
- **行级锁**：发布版本 / 退役 / 新增引用均 `SELECT … FOR UPDATE`，串行化互斥操作。
- **引用一致性约束**：`ck_ref_mode_consistency` 保证 floating 不能带 pinned_version_id、
  pinned 必须带；外键 `ON DELETE RESTRICT` 防止误删仍被引用的版本/图片。
- **异步任务幂等认领**：worker 用 `FOR UPDATE SKIP LOCKED`，多副本也不会重复渲染。
- **历史导出不可变**：`export_snapshots` 冻结版本与图片引用，不随退役迁移，且阻止图片 GC。

## 📝 备注

- 封面渲染使用 Pillow 本地裁切/缩放（无需外部服务）；`COVER_JOB_DELAY_SECONDS=4`
  用于让验收者观察任务排队与「晚到」效果，可在 compose 中调整。
- 媒体文件存于命名卷 `media:/data/media`，API 以 `/media/...` 提供只读访问。
