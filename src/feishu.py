# ============== 飞书模块 ==============
"""飞书自建应用（机器人）消息推送。

凭证不写死在代码里，统一从 config.json 的 feishu 段读取（可用环境变量覆盖）：

    "feishu": {
        "app_id": "cli_xxx",
        "app_secret": "xxx",
        "receive_id_type": "open_id",
        "default_receive_id": "ou_xxx"
    }

receive_id_type 可选 open_id / user_id / union_id / email / chat_id。
注意：按手机号定位用户需要 contact:user.id:readonly 权限，本实现不依赖它。
"""
import json
import os
import time

import requests

try:
    from .config import get_feishu_config
except ImportError:  # 以 src 为根目录运行（MCP / 命令行）
    from config import get_feishu_config

FEISHU_BASE = 'https://open.feishu.cn/open-apis'
TOKEN_URL = f'{FEISHU_BASE}/auth/v3/tenant_access_token/internal'
UPLOAD_URL = f'{FEISHU_BASE}/im/v1/files'
MESSAGE_URL = f'{FEISHU_BASE}/im/v1/messages'

# 上传文件大小上限（飞书 im/v1/files 限制 30MB）
MAX_UPLOAD_BYTES = 30 * 1024 * 1024

_token_cache = {'token': None, 'expire_at': 0.0}


def _credentials():
    """读取 app_id / app_secret，环境变量优先。"""
    config = get_feishu_config() or {}
    app_id = os.environ.get('FEISHU_APP_ID') or config.get('app_id', '')
    app_secret = os.environ.get('FEISHU_APP_SECRET') or config.get('app_secret', '')
    return app_id, app_secret


def _target(receive_id=None, receive_id_type=None):
    """确定接收方：显式传入 > 配置里的默认值。"""
    config = get_feishu_config() or {}
    return (
        receive_id or config.get('default_receive_id', ''),
        receive_id_type or config.get('receive_id_type', 'open_id'),
    )


def get_tenant_access_token(app_id=None, app_secret=None, force_refresh=False):
    """获取 tenant_access_token（进程内缓存到过期前 60 秒）。"""
    if not force_refresh and _token_cache['token'] and time.time() < _token_cache['expire_at'] - 60:
        return _token_cache['token']

    app_id, app_secret = app_id or _credentials()[0], app_secret or _credentials()[1]
    if not app_id or not app_secret:
        raise ValueError('未配置飞书 app_id / app_secret（config.json 的 feishu 段）')

    resp = requests.post(TOKEN_URL, json={'app_id': app_id, 'app_secret': app_secret}, timeout=15)
    result = resp.json()
    if result.get('code') != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {result.get('code')} {result.get('msg')}")

    _token_cache['token'] = result['tenant_access_token']
    _token_cache['expire_at'] = time.time() + int(result.get('expire', 7200))
    return _token_cache['token']


def upload_file(token, file_path):
    """上传文件到飞书，返回 file_key。"""
    file_name = os.path.basename(file_path)
    size = os.path.getsize(file_path)
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(f'文件超过 30MB（{size} 字节），无法通过飞书机器人发送')

    with open(file_path, 'rb') as handle:
        resp = requests.post(
            UPLOAD_URL,
            headers={'Authorization': f'Bearer {token}'},
            data={'file_type': 'stream', 'file_name': file_name},
            files={'file': (file_name, handle, 'application/octet-stream')},
            timeout=60,
        )
    result = resp.json()
    if result.get('code') != 0:
        raise RuntimeError(f"上传文件失败: {result.get('code')} {result.get('msg')}")
    return result['data']['file_key']


def send_file_message(token, file_key, receive_id, receive_id_type='open_id'):
    """发送文件消息，返回飞书响应。"""
    resp = requests.post(
        MESSAGE_URL,
        params={'receive_id_type': receive_id_type},
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        json={
            'receive_id': receive_id,
            'msg_type': 'file',
            'content': json.dumps({'file_key': file_key}),
        },
        timeout=30,
    )
    return resp.json()


def send_text_message(token, text, receive_id, receive_id_type='open_id'):
    """发送文本消息，返回飞书响应。"""
    resp = requests.post(
        MESSAGE_URL,
        params={'receive_id_type': receive_id_type},
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        json={
            'receive_id': receive_id,
            'msg_type': 'text',
            'content': json.dumps({'text': text}),
        },
        timeout=30,
    )
    return resp.json()


def get_app_info(app_id=None):
    """查询应用基本信息（名称、版本、能力），用于自检。"""
    app_id = app_id or _credentials()[0]
    token = get_tenant_access_token()
    resp = requests.get(
        f'{FEISHU_BASE}/application/v6/applications/{app_id}',
        headers={'Authorization': f'Bearer {token}'},
        params={'lang': 'zh_cn'},
        timeout=15,
    )
    result = resp.json()
    if result.get('code') != 0:
        raise RuntimeError(f"查询应用信息失败: {result.get('code')} {result.get('msg')}")
    return result['data']['app']


def send_file_to_feishu(file_path, xlsx_to_pdf_func=None, receive_id=None, receive_id_type=None):
    """把报表文件发送到飞书（主函数）。

    Args:
        file_path: 文件路径（xlsx 时会尝试先转 PDF）
        xlsx_to_pdf_func: xlsx 转 pdf 的函数，可选
        receive_id: 接收方 ID，缺省用配置里的 default_receive_id
        receive_id_type: open_id / user_id / union_id / email / chat_id

    Returns:
        (success, message)
    """
    if not file_path:
        return False, '文件路径为空'
    if not os.path.exists(file_path):
        return False, f'文件不存在: {file_path}'

    # 与钉钉推送保持一致：xlsx 先转 PDF 再发，失败则发原文件
    actual_path = file_path
    if file_path.lower().endswith('.xlsx') and xlsx_to_pdf_func:
        pdf_path = file_path.replace('\\xls\\', '\\pdf\\').replace('/xls/', '/pdf/').replace('.xlsx', '.pdf')
        if not os.path.exists(pdf_path):
            try:
                pdf_path = xlsx_to_pdf_func(file_path) or file_path
            except Exception as exc:
                print(f'生成PDF失败，改为发送 Excel: {exc}')
                pdf_path = file_path
        actual_path = pdf_path if os.path.exists(pdf_path) else file_path

    target, target_type = _target(receive_id, receive_id_type)
    if not target:
        return False, '未配置飞书接收方（config.json 的 feishu.default_receive_id）'

    try:
        token = get_tenant_access_token()
        file_key = upload_file(token, actual_path)
        result = send_file_message(token, file_key, target, target_type)
        if result.get('code') == 0:
            return True, f'已发送到飞书: {os.path.basename(actual_path)}'
        return False, f"飞书返回错误: {result.get('code')} {result.get('msg')}"
    except Exception as exc:
        return False, f'发送失败: {exc}'


def send_text_to_feishu(text, receive_id=None, receive_id_type=None):
    """发送纯文本消息（自检/通知用）。"""
    target, target_type = _target(receive_id, receive_id_type)
    if not target:
        return False, '未配置飞书接收方（config.json 的 feishu.default_receive_id）'
    try:
        result = send_text_message(get_tenant_access_token(), text, target, target_type)
        if result.get('code') == 0:
            return True, '已发送到飞书'
        return False, f"飞书返回错误: {result.get('code')} {result.get('msg')}"
    except Exception as exc:
        return False, f'发送失败: {exc}'
