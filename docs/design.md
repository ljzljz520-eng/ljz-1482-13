# 设计说明：版本与依赖管理

## 1. 数据模型要点

- `characters`：角色主体，`status` ∈ active/soft_deleted/retired，`latest_version`，
  `lock_version`（乐观锁）。
- `character_versions`：不可变版本行 (character_id, version) 唯一，保存外观/语气/限制词。
- `reference_images`：参考图绑定到**版本**而非角色，使历史版本可完整重现。
- `image_assets`：物理图片对象，授权字段在资产维度；撤销授权影响所有使用它的版本。
- `script_character_links`：脚本→角色引用，CHECK 约束保证 pinned/floating 形态合法；
  `approved_text/approved_version/effective_version` 构成已批准台词的冻结基线。
- `cover_jobs`：异步任务（状态机 pending→processing→succeeded/failed/stale），
  保存来源图、裁切参数、目标尺寸与参数指纹。
- `generated_assets`：仅成功且未过期的封面才登记，角色卡封面从这里取。
- `export_snapshots / export_version_refs / export_image_refs`：导出时刻的版本与图片冻结，
  是图片 GC 的第五类引用。
- `review_items`：统一复核队列（冲突/授权撤销/生成失败/退役受阻/台词漂移）。

## 2. 固定 vs 跟随

- pinned：解析为 `pinned_version_id` 对应版本；角色改版无影响，永不漂移。
- floating：解析为当前 `latest_version`；一旦 latest > approved/effective 基线，
  `needs_review=true` 并生成复核项。解释文本本身不变，只有人工「确认复核」才推进基线。

## 3. 退役流程（并发安全）

1. `SELECT … FOR UPDATE` 锁角色，校验 `lock_version`。
2. 实时反向引用查询（脚本/素材/导出）。
3. soft_delete：仅置状态，引用全部保留，可 restore。
   retire：有引用必须指定替代角色；在同一事务迁移链接（pinned→pinned 替代角色最新版，
   floating→floating；已批准状态重置并建复核项）；历史导出引用不迁移。
4. 并发新增引用：链接写入也先锁角色行，非 active 直接 409。

## 4. 封面任务与旧任务晚到

- 入队即持久化原图 id 与裁切参数；渲染在 worker 进程，不阻塞 API。
- 完成时若该版本已存在 created_at 更晚的成功任务，本次输出落盘审计但状态置 stale，
  不写 generated_assets，因此角色卡永远只展示最新成功结果。
- worker 渲染前再查授权；撤销授权的在途任务失败并入复核队列。

## 5. 图片 GC 五类引用

参考图绑定、派生来源、派生产物、在途任务、历史导出快照。全部为空才物理删除文件与行；
历史导出只要存在，图就保留。

## 6. 权限

JWT 携带 uid+role；FastAPI 依赖 `require_roles` 在每个写接口服务端强制；
viewer 只读，退役/恢复/物理 GC 仅 admin。前端按钮隐藏不构成安全边界。

## 7. 动效可访问性

`useMotionAllowed(ref)` = IntersectionObserver(可见) ∧ document 未隐藏 ∧
未匹配 prefers-reduced-motion ∧ 用户偏好开启。CSS 动画 class 仅在为真时挂载，
并提供全局 reduced-motion 兜底。
