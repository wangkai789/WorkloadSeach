# ============== MCP Server 入口（stdio） ==============
"""东华住院工作量查询系统 —— MCP Server。

把住院 / 门诊 / 患者明细查询和报表生成能力暴露为 MCP 工具，
供支持 MCP 的客户端（DSH、Claude Desktop 等）通过 stdio 调用。

运行：
    .venv\\Scripts\\python.exe mcp_server.py            # 启动 stdio 服务
    .venv\\Scripts\\python.exe mcp_server.py --status   # 只检查配置与数据库连通性
    .venv\\Scripts\\python.exe mcp_server.py --list-tools
"""
from __future__ import annotations

import argparse
import builtins
import json
import os
import sys
from typing import Literal

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(APP_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mcp.server.mcpserver import MCPServer  # noqa: E402  (需先设置 sys.path)

import mcp_tools  # noqa: E402

VERSION = '2.1'

INSTRUCTIONS = (
    '东华医院住院工作量查询系统。'
    '提供住院工作量（主任医师/副主任医师/护士/麻醉师）、门诊工作量（按员工编号）、'
    '患者明细（医生/护士/科室/诊断）查询，以及工作量报表（Excel/PDF）生成。'
    '日期格式统一为 YYYY-MM-DD，缺省为本月 1 日至今天；'
    '查询只读，不会修改数据库，也不会写文件，只有 generate_workload_report 会生成文件。'
)

server = MCPServer(
    name='dhcc-workload-query',
    title='东华住院工作量查询',
    version=VERSION,
    instructions=INSTRUCTIONS,
)


@server.tool(
    name='query_inpatient_workload',
    description=(
        '查询某人的住院工作量，按申报职称区分：sp=主任医师 / ap=副主任医师 / '
        'nurse=护士 / anes=麻醉师。返回列名、逐行数据和行数，行数据里通常含合计行。'
    ),
)
def query_inpatient_workload(
    name: str,
    query_type: Literal['sp', 'ap', 'nurse', 'anes'],
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """住院工作量查询。

    Args:
        name: 被查询人姓名，例如「席林」。
        query_type: 申报职称类型，sp/ap/nurse/anes。
        start_date: 统计开始日期 YYYY-MM-DD，缺省为本月 1 日。
        end_date: 统计结束日期 YYYY-MM-DD，缺省为今天。
    """
    return mcp_tools.query_inpatient_workload(name, query_type, start_date, end_date)


@server.tool(
    name='query_outpatient_workload',
    description=(
        '按员工编号查询门诊工作量（门诊人次），返回期间、医师姓名、门诊人次及合计行。'
        '门诊存储过程必须提供 employee_id，姓名只用于结果展示。'
    ),
)
def query_outpatient_workload(
    employee_id: str,
    name: str = '',
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """门诊工作量查询。

    Args:
        employee_id: 员工编号（如 01478），必填。
        name: 医师姓名，可选，仅用于结果展示。
        start_date: 统计开始日期 YYYY-MM-DD，缺省为本月 1 日。
        end_date: 统计结束日期 YYYY-MM-DD，缺省为今天。
    """
    return mcp_tools.query_outpatient_workload(employee_id, name, start_date, end_date)


@server.tool(
    name='query_patients',
    description=(
        '查询患者明细列表，kind 支持 doctor（按医生姓名）/ nurse（按护士姓名）/ '
        'dept（按科室）/ diag（按诊断关键字）。结果默认最多返回 200 行，'
        'total 是实际总行数，truncated=true 表示被截断。'
    ),
)
def query_patients(
    kind: Literal['doctor', 'nurse', 'dept', 'diag'],
    name: str,
    start_date: str | None = None,
    end_date: str | None = None,
    nurse_type: Literal['nurse', 'quality'] = 'nurse',
    limit: int = 200,
) -> dict:
    """患者明细查询。

    Args:
        kind: 查询维度，doctor/nurse/dept/diag。
        name: 医生姓名、护士姓名、科室名称或诊断关键字。
        start_date: 统计开始日期 YYYY-MM-DD，缺省为本月 1 日。
        end_date: 统计结束日期 YYYY-MM-DD，缺省为今天。
        nurse_type: kind=nurse 时区分责任护士（nurse）或质控护士（quality）。
        limit: 返回行数上限，1~2000，默认 200。
    """
    return mcp_tools.query_patients(kind, name, start_date, end_date, nurse_type, limit)


@server.tool(
    name='generate_workload_report',
    description=(
        '生成住院工作量报表文件：在 Excel 导出目录写入 .xlsx（可选再转 PDF），'
        '返回生成的文件路径。适合需要交付文件的场景；只查数据请用 query_inpatient_workload。'
    ),
)
def generate_workload_report(
    name: str,
    query_type: Literal['sp', 'ap', 'nurse', 'anes'],
    start_date: str | None = None,
    end_date: str | None = None,
    with_pdf: bool = True,
) -> dict:
    """生成工作量报表（Excel，可选 PDF）。

    Args:
        name: 被查询人姓名。
        query_type: 申报职称类型，sp/ap/nurse/anes。
        start_date: 统计开始日期 YYYY-MM-DD。
        end_date: 统计结束日期 YYYY-MM-DD。
        with_pdf: 是否同时转换为 PDF，默认 true。
    """
    return mcp_tools.generate_workload_report(name, query_type, start_date, end_date, with_pdf)


@server.tool(
    name='database_status',
    description='检查数据库配置与连通性（不返回密码），排障时先调用它。',
)
def database_status() -> dict:
    """数据库连通性检查。"""
    return mcp_tools.database_status()


def _route_prints_to_stderr():
    """把业务代码里的 print 全部导向 stderr。

    database.py 等模块会打印查询日志；stdio 传输下 stdout 是 JSON-RPC 专用通道，
    任何一行杂输出都会让客户端解析失败，因此在服务模式下统一改道。
    """
    real_print = builtins.print

    def _print(*args, **kwargs):
        kwargs.setdefault('file', sys.stderr)
        real_print(*args, **kwargs)

    builtins.print = _print


def _load_config_quietly():
    """加载配置；把业务代码的 print 引到 stderr，避免污染 stdio 协议流。"""
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        mcp_tools._ensure_config()
    finally:
        sys.stdout = real_stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description='东华住院工作量查询 MCP Server（stdio）')
    parser.add_argument('--status', action='store_true', help='只输出数据库连通性检查结果')
    parser.add_argument('--list-tools', action='store_true', help='只输出已注册工具清单')
    args = parser.parse_args(argv)

    _load_config_quietly()

    if args.status:
        print(json.dumps(mcp_tools.database_status(), ensure_ascii=False, indent=2))
        return 0

    if args.list_tools:
        import asyncio

        tools = asyncio.run(server.list_tools())
        payload = [
            {
                'name': tool.name,
                'description': tool.description,
                'input_schema': tool.input_schema,
            }
            for tool in tools
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f'[mcp] dhcc-workload-query v{VERSION} 通过 stdio 启动', file=sys.stderr, flush=True)
    _route_prints_to_stderr()
    server.run('stdio')
    return 0


if __name__ == '__main__':
    sys.exit(main())
