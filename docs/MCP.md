# MCP 服务（mcp_server.py）

把系统的查询能力通过 [MCP（Model Context Protocol）](https://modelcontextprotocol.io) 暴露给支持 MCP 的客户端
（DSH、Claude Desktop 等）。传输方式为 **stdio**，与现有 Flask Web 端并存、共用同一套业务代码和配置文件。

- 入口：`mcp_server.py`（仓库根目录）
- 业务包装：`src/mcp_tools.py`
- 配置：与 Web 端相同，源码运行时读取 `dist/config.json`
- 只读：除 `generate_workload_report` 会写 Excel/PDF 外，其余工具都不落盘、不写数据库

## 1. 环境准备

服务端依赖 `mcp` Python SDK（2.x）：

```powershell
python -m pip install -r requirements-mcp.txt
```

自检（不需要客户端）：

```powershell
python mcp_server.py --status       # 数据库配置与连通性
python mcp_server.py --list-tools   # 已注册工具与参数结构
```

## 2. 工具清单

| 工具 | 作用 | 关键参数 |
|------|------|----------|
| `query_inpatient_workload` | 住院工作量（主任医师/副主任医师/护士/麻醉师） | `name`、`query_type`=sp/ap/nurse/anes、`start_date`、`end_date` |
| `query_outpatient_workload` | 门诊工作量（门诊人次） | `employee_id`（必填）、`name`、`start_date`、`end_date` |
| `query_patients` | 患者明细 | `kind`=doctor/nurse/dept/diag、`name`、`nurse_type`、`limit` |
| `generate_workload_report` | 生成住院工作量报表文件 | `name`、`query_type`、`with_pdf` |
| `database_status` | 配置与数据库连通性检查 | 无 |

约定：

- 日期一律 `YYYY-MM-DD`，不传则取「本月 1 日 ~ 今天」；
- 返回 JSON：成功 `{"ok": true, "columns": [...], "rows": [...], "total": n, ...}`，
  失败 `{"ok": false, "error": "原因"}`（业务失败不抛异常，便于模型自行重试或改写参数）；
- `query_patients` 默认最多返回 200 行（上限 2000），`total` 是实际总行数，`truncated=true` 表示被截断。

## 3. 客户端接入

### 3.1 DSH

在 DSH 中用一个「只做配置」的 bundle 接入，`cordis.patch.yml`：

```yaml
- insert:
    - id: dhcc-workload-mcp
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: dhcc
        transport: stdio
        command: D:\WorkSpace\东华住院工作量查询\.venv\Scripts\python.exe
        args:
          - D:\WorkSpace\东华住院工作量查询\mcp_server.py
        cwd: D:\WorkSpace\东华住院工作量查询
        failOnStartupError: true
```

接入后工具名前缀为 `mcp__dhcc__`，例如 `mcp__dhcc__query_inpatient_workload`。

> `command` 里的解释器路径只是示例（本机 `.venv`），换机器时改成实际安装了 `mcp` 的 Python 解释器；
> `args` 必须指向真实存在的 `mcp_server.py`，`cwd` 设为仓库根目录。

### 3.2 Claude Desktop

`claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "dhcc": {
      "command": "C:\\Python314\\python.exe",
      "args": ["D:\\WorkSpace\\东华住院工作量查询\\mcp_server.py"],
      "cwd": "D:\\WorkSpace\\东华住院工作量查询"
    }
  }
}
```

### 3.3 其他客户端

任何支持 stdio 传输的 MCP 客户端都可以直接拉起
`python mcp_server.py`；工作目录设为仓库根目录，或保证 `dist/config.json` 可读。

## 4. 手工调试

用官方 SDK 自带客户端跑一次完整握手（需要 `mcp` 已安装）：

```powershell
python tests\mcp_smoke_test.py
```

该脚本会启动 `mcp_server.py` 子进程，依次调用 `database_status`、住院/门诊/患者查询并打印结果。

## 5. 排障

| 现象 | 处理 |
|------|------|
| 工具返回 `ok:false`，错误含「客户端不支持加密」 | 本机 PyODBC 驱动与 SQL Server 的 TLS 协商失败，换 `ODBC Driver 18` 或检查服务器加密设置 |
| 工具返回 `ok:false`，错误含「登录失败 / 无法连接」 | 先跑 `python mcp_server.py --status`，再核对 `dist/config.json` |
| 客户端报「Failed to parse JSONRPC message」 | 有非协议内容写到了 stdout。业务代码的 `print` 已在服务模式下统一改道 stderr，新增代码也必须遵守 |
| 中文乱码 | 客户端/终端用 UTF-8；服务端内部统一 UTF-8 |

服务端日志全部输出到 **stderr**，stdout 只承载 JSON-RPC 消息。

## 6. 安全说明

- 不暴露 `users` 表、密码、会话等数据，只提供工作量与患者查询；
- 患者查询返回的是病历明细（含姓名、诊断），接入范围应限于内网可信客户端；
- 报表文件写入 `dist/xls`、`dist/pdf`（见 `dist/config.json` 的 `paths`）。
