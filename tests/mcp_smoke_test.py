"""MCP stdio 冒烟测试。

启动 mcp_server.py 子进程，走完整 MCP 握手，依次调用各工具并检查返回结构。
依赖：pip install -r requirements-mcp.txt；数据库可用时才会校验真实数据。

用法：
    python tests/mcp_smoke_test.py
退出码 0 表示通过。
"""
import asyncio
import json
import os
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')
PYTHON = VENV_PY if os.path.exists(VENV_PY) else sys.executable

EXPECTED_TOOLS = {
    'query_inpatient_workload',
    'query_outpatient_workload',
    'query_patients',
    'generate_workload_report',
    'database_status',
}

failures = []


def check(condition, message):
    print(('PASS  ' if condition else 'FAIL  ') + message)
    if not condition:
        failures.append(message)


def payload(result):
    text = result.content[0].text if result.content else '{}'
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {'_raw': text}


async def main():
    params = StdioServerParameters(
        command=PYTHON,
        args=[os.path.join(ROOT, 'mcp_server.py')],
        cwd=ROOT,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
    )

    async with Client(params, raise_exceptions=False) as client:
        print('服务端:', client.server_info.name, client.server_info.version)

        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        check(EXPECTED_TOOLS <= names, f'已注册工具: {sorted(names)}')

        status = payload(await client.call_tool('database_status', {}))
        print('database_status:', json.dumps(status, ensure_ascii=False))
        check('server' in status and status['server'], 'database_status 返回服务器地址')

        if not status.get('connected'):
            print('SKIP  数据库不可用，跳过真实查询校验')
            return

        workload = payload(await client.call_tool(
            'query_inpatient_workload',
            {'name': '席林', 'query_type': 'ap', 'start_date': '2026-01-01', 'end_date': '2026-06-30'}))
        check(workload.get('ok') is True and workload.get('total', 0) >= 1,
              f"住院工作量: {workload.get('total')} 行")
        check(bool(workload.get('columns')), '住院工作量返回列名')

        outpatient = payload(await client.call_tool(
            'query_outpatient_workload',
            {'employee_id': '01478', 'name': '席林', 'start_date': '2026-01-01', 'end_date': '2026-06-30'}))
        check(outpatient.get('ok') is True and outpatient.get('total', 0) >= 1,
              f"门诊工作量: {outpatient.get('total')} 行")

        patients = payload(await client.call_tool(
            'query_patients',
            {'kind': 'doctor', 'name': '席林', 'start_date': '2026-01-01', 'end_date': '2026-06-30', 'limit': 5}))
        check(patients.get('ok') is True, '患者明细查询成功')
        check(len(patients.get('rows', [])) <= 5, '患者明细遵守 limit')

        invalid = await client.call_tool('query_inpatient_workload', {'name': '席林', 'query_type': 'zzz'})
        check(invalid.is_error, '非法 query_type 被 schema 拒绝')


asyncio.run(main())

if failures:
    print(f'\n{len(failures)} 项失败')
    sys.exit(1)
print('\n全部通过')
