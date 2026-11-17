# DataWeave Issue Workflow

本目录使用 [issues.md](issues.md) 作为功能、缺陷和技术债的本地管理清单，并通过 `scripts/issue_manager.py` 与 GitHub Issues 同步。

## 前置条件

```bash
gh auth status
gh issue list --repo spewmeps/DataWeave
```

脚本默认仓库为 `spewmeps/DataWeave`，可以用全局参数 `--repo owner/repo` 或环境变量 `DATAWEAVE_ISSUE_REPO` 覆盖。

## 常用命令

```bash
# 检查 Markdown 格式和重复 Key / Issue 编号
python3 scripts/issue_manager.py check

# 重新生成 issues.md 顶部汇总表
python3 scripts/issue_manager.py index

# 查看远端 Issue
python3 scripts/issue_manager.py list --state all

# 预览将要创建或更新的 Issue，不修改 GitHub
python3 scripts/issue_manager.py sync

# 同步全部 Issue 到 GitHub
python3 scripts/issue_manager.py sync --apply

# 只同步指定 Issue
python3 scripts/issue_manager.py sync DW-001 DW-004 --apply
```

同步前，脚本会用 Issue 正文中的稳定 Key（如 `DW-001`）与远端对账。如果上一次创建请求已在 GitHub 成功、但本地因 TLS 超时没有收到响应，重新执行同一条 `sync --apply` 会显示 `RECOVER`、回填已有 Issue 编号并继续，不会重复创建。创建结果未知时脚本会安全停止，不会自动重试 POST。

## 新增 Issue

在 `issues.md` 中复制一个完整 Issue 区块：

```markdown
## [DW-999] 简洁、可执行的标题
<!-- issue: number=; state=open; labels=enhancement,priority:P1,area:frontend; assignees= -->
<!-- issue-body -->
### 背景

说明为什么要做。

### 功能范围

- 范围内事项

### 验收标准

- [ ] 可以验证的完成条件

### 非目标

- 本次不做的事项
<!-- /issue-body -->
```

规则：

- `DW-999` 是稳定 Key，创建 GitHub Issue 后也不修改。
- `number=` 首次保持为空；`sync --apply` 创建成功后自动回写编号。
- `state` 只允许 `open` 或 `closed`。
- `labels` 和 `assignees` 使用英文逗号分隔；空负责人写 `assignees=`。
- 标题、正文、状态、标签和负责人以 Markdown 清单为准。

## 代码提交关联 Issue

先同步 Issue，确保清单中已经有 GitHub 编号。然后使用：

```bash
# 使用已经 git add 的文件，提交信息附加 Refs #N
python3 scripts/issue_manager.py commit DW-001 -m "feat: add context review API"

# 先添加指定文件再提交
python3 scripts/issue_manager.py commit DW-001 -m "feat: add context review API" \
  --paths src/backend/dataweave/context.py src/backend/tests/test_context.py

# 添加所有改动，并在 PR 合入默认分支时关闭 Issue
python3 scripts/issue_manager.py commit DW-001 -m "feat: complete context review" --all --close

# 一个提交关联多个 Issue
python3 scripts/issue_manager.py commit DW-001 DW-004 -m "feat: publish context artifacts"
```

默认使用 `Refs #N`，只建立关联；传入 `--close` 后使用 `Closes #N`。GitHub 会在提交进入默认分支或 PR 合并后按关闭关键字处理 Issue。

## 推荐工作流

1. 在 `issues/issues.md` 新增或更新功能/缺陷。
2. 执行 `check` 和 `sync` 预览。
3. 确认后执行 `sync --apply`。
4. 从 Issue 创建 `codex/DW-001-short-name` 分支。
5. 开发、测试并用 `commit` 命令关联 Issue。
6. PR 描述继续使用 `Refs #N`；全部验收完成时使用 `Closes #N`。

脚本不会自动执行 `git push`、创建 PR 或删除 Issue，这些高影响操作保持显式执行。
