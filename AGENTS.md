# 协作约定

## 提交与推送（强制）

**每次修改程序后，必须提交并推送到 GitHub，不允许只在本地留改动。**

- 仓库：https://github.com/wangkai789/WorkloadSeach
- 远端：`origin` → `https://github.com/wangkai789/WorkloadSeach.git`，主分支 `main`

流程：

1. `git status` / `git diff` 确认改动范围，只把本次改动相关的文件加入暂存区。
2. 提交前做基本校验：改到 Python 文件时至少跑一次
   `python -m py_compile src/xxx.py`（或对应文件），确认语法通过。
3. 提交信息沿用仓库既有风格：英文、`类型: 摘要`，类型用 `feat` / `fix` / `docs` / `refactor` / `chore`；
   一个完整的改动一个提交，正文用 `-` 列要点。
4. `git push origin main`，并用 `git ls-remote origin refs/heads/main` 核对远端已到最新提交。

## 注意事项

- `config.json`、`*.db`、`*.env` 已在 `.gitignore` 中，**不要**强行加入仓库（含数据库连接信息）。
- 仓库里的 `docs/screenshots/` 含真实员工姓名和手机号，推送到 GitHub 前需使用者明确同意。
- 本机 `~/.gitconfig` 里的 `http.proxy` / `https.proxy` 指向的 `127.0.0.1:7890` 未必在监听，
  实际可用端口常见为 `127.0.0.1:7897`；本仓库已在 `.git/config` 中单独指定，其他仓库推送失败时先查代理。
- 在受限沙箱中 `git push` 会因凭据管理器无法创建进程而报 `could not read Username`，
  需要以完整权限放行一次（凭据由 Windows 凭据管理器提供，不需要在仓库里写入密码或 token）。

## 项目结构速览

- `web_app_inpatient.py`：Flask 入口
- `src/api/`：按业务域拆分的路由（`auth.py`、`clinic.py` 等）
- `src/database.py`：SQL Server 查询与存储过程调用
- `src/clinic_query.py`：门诊工作量（`Search_Doctor_OPWorkload`）
- `templates/`：页面模板，`templates/partials/` 为公共片段
