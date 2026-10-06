# 角色设计工作台 · Character Design Workbench

面向影视/动画前期的**角色设计版本与依赖管理**全栈系统：维护人物外观、语气、参考图与限制词；
脚本可**固定（pinned）某一版**或明确选择**跟随最新版（latest）**；角色修改不会悄悄改变已批准
台词的解释；退役前审计脚本、生成素材与导出快照的真实反向引用；封面图异步派生并绑定原图与裁切
参数；来源图授权撤销会级联标记受影响场次。

## 🛠 技术栈

- **Frontend**: React 18 + TypeScript 5 + Vite 5 + Tailwind CSS 3 + Zustand + Axios + react-hot-toast
- **Backend**: FastAPI + SQLAlchemy 2.0 ORM + Pydantic v2 + Pillow（封面裁切）+ 后台任务线程
- **Database**: PostgreSQL 16（测试使用 SQLite，无需额外服务）
- **Infra**: Docker Compose 三容器（db / backend / frontend-nginx）+ 命名卷持久化

## 🚀 启动指南 (How to Run)

1. 确保 Docker Desktop / Docker Engine 已启动。
2. 在仓库根目录执行：

   ```bash
   docker compose up --build
   ```

3. 等待数据库健康检查通过、后端完成自动建表与种子数据填充后访问：
   - 前端：http://localhost:3000
   - 后端 Swagger：http://localhost:8000/docs
   - 健康检查：http://localhost:8000/health

前端 Nginx 会把 `/api/*`（含媒体文件）反代到 `backend:8000`，容器间全部使用服务名通信。

## 🧪 测试账号

| 用户名 | 密码 | 角色 | 能力 |
|--------|--------|------|------|
| `admin` | `123456` | 管理员 | 全部操作：退役、撤销授权、存储清理、手动执行任务队列 |
| `editor` | `123456` | 编剧 | 角色/版本/脚本/台词/封面任务的读写，不能退役与撤销授权 |
| `viewer` | `123456` | 观众 | 全局只读 |

种子内容：3 个角色（林晚 v1/v2、顾珩、小满）、1 个剧本（3 个场次、5 句台词，其中林晚固定 v1、
顾珩跟随最新）、已生成封面、1 份历史导出快照。

## 🔑 核心业务规则

### 1. 版本与引用
- 每次修改外观/语气/限制词都生成**不可变版本（append-only）**，角色头指针指向最新版。
- 脚本引用有两种模式，界面显著区分：
  - 📌 **固定版本**：永远解析到指定版本（`pinned_version_id`）；
  - 🌀 **跟随最新**：动态解析到角色当前版本。
- 台词批准时把该版本的外观/语气/限制词**冻结为解释快照**。之后发布新版本：
  - 固定引用下的已批准台词完全不动；
  - 跟随最新引用的已批准台词**保留旧快照**并打上“待复核”，进入复核队列，绝不被静默改写。
  - 复核通过后可显式“按最新版重新批准”。

### 2. 并发安全
- 角色元信息使用 `revision` **乐观锁**：两人改同一字段，后提交者收到 `409` 并提示重新合并。
- 退役流程使用行锁：`SELECT ... FOR UPDATE` 锁定角色与脚本引用，提交时重新核对界面传入的
  **反向引用总数**，数量变化即 `409` 拒绝；退役事务进行中另一人新增引用也会被挡住。
- 退役策略二选一：
  - **软删除保留引用**：角色标记 `retired`（只读），全部历史引用、导出、审批继续可读，
    相关场次生成复核项，禁止再新增任何引用；
  - **替换后退役**：脚本引用（含固定版本）迁移到替换角色当前版本，素材任务随迁，
    台词保留并强制复核；同一脚本已引用替换角色时拒绝自动迁移。

### 3. 封面派生异步任务
- 任务绑定 `(角色, 版本, 来源原图, 裁切参数, 输出尺寸)`，参数经哈希**幂等去重**。
- 后台 worker 轮询队列（约 3 秒），使用 Pillow 按相对坐标裁切渲染。
- **旧任务晚到不覆盖新角色卡**：按任务请求时间比较，晚到结果标记为 `stale`，素材留档但不上封面。
- 来源图授权撤销：排队/处理中任务立即失败，相关封面下架，台词与场次进入复核队列。
- 可用 `force_fail` 参数模拟素材生成失败（失败自动产生“待复核”项）。

### 4. 动画与可访问性
- 封面光扫/缩放动画同时满足三个条件才播放：元素进入视口（IntersectionObserver）、
  页面标签可见（visibilitychange）、用户在应用内开启动效且系统未开启“减少动态效果”
  （prefers-reduced-motion）。顶栏可一键关闭动效。

### 5. 权限（服务端强制）
- 所有接口（含媒体文件）需要 Bearer Token；viewer 只读，退役/撤销授权/清理仅 admin，
  前端隐藏按钮只是体验，**后端逐接口鉴权**。

### 6. 存储清理
- 管理员清理分四类输出：删除的来源图、删除的派生素材、**被历史导出快照保护（保留）**、
  仍被版本/任务使用（保留）。默认 dry-run 预览。

## 📁 目录结构

```
backend/
  app/
    main.py              # FastAPI 入口、生命周期、建表、种子、worker 启动
    config.py database.py models.py security.py deps.py schemas.py serializers.py
    routers/             # auth / characters / lifecycle / scripts / lines /
                         # images / covers / exports / reviews / admin / media
    services/            # characters(版本+台词保护) retire references covers(worker)
                         # licenses exports cleanup media reviews
    seed.py              # 演示数据与占位美术（Pillow 生成）
  tests/test_api.py      # 17 个验收测试
frontend/
  src/
    api/  types/  store/  hooks/  components/
    pages/
      auth/ characters/ scripts/ reviews/
      ImageLibraryPage.tsx AdminPage.tsx
```

## 🧪 后端测试

覆盖验收场景（在 `backend/` 目录执行，容器内同样可运行）：

```bash
pip install -r requirements.txt
pytest -q
```

- `TestPermissions`：未认证 401、viewer 写入 403、editor 不能退役/撤销
- `TestConcurrentEdit`：两人改同一字段，第二人 409
- `TestLineReviewProtection`：跟随最新已批准台词被标记、固定引用不受影响、重新批准清除标记
- `TestRetire`：反向引用预检、引用数变化拒绝、退役后新增引用拒绝、替换迁移
- `TestCoverJobs`：幂等创建、worker 成功 + 旧任务晚到保护、失败生成复核项
- `TestExports`：导出快照包含解析版本与冻结台词
- `TestLicenseRevoke`：撤销授权级联（任务失败、台词标记、禁止再派生）
- `TestCleanup`：清理权限、历史导出保护对象不被删除

## 🔌 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录获取 Token |
| GET/POST | `/api/characters` | 角色列表/创建（同时发 v1） |
| PATCH | `/api/characters/{id}` | 元信息编辑（`expected_revision` 乐观锁） |
| POST | `/api/characters/{id}/versions` | 发布不可变新版本 |
| GET | `/api/characters/{id}/references` | 退役前实际反向引用清单 |
| POST | `/api/characters/{id}/retire` | 软删除 / 替换退役（管理员） |
| POST | `/api/scripts/{id}/characters` | 建立 pinned / latest 引用 |
| POST | `/api/lines/{id}/approve` `/reapprove` | 批准冻结 / 按最新重新批准 |
| POST | `/api/characters/{c}/versions/{v}/cover-jobs` | 封面任务入队（幂等） |
| POST | `/api/cover-jobs/process` | 同步执行队列（管理员/测试） |
| POST | `/api/images/{id}/revoke` | 撤销来源图授权（管理员，级联） |
| POST | `/api/scripts/{id}/exports` | 生成不可变导出快照 |
| GET | `/api/reviews` | 待复核队列（按场次呈现） |
| POST | `/api/admin/cleanup?dry_run=` | 未引用对象清理（默认预览） |
