# ============== 飞书机器人：消息查询入口 ==============
"""飞书机器人：接收消息 → 解析查询指令 → 回复查询结果或报表文件。

运行（长连接模式，无需公网地址）：

    .venv\\Scripts\\python.exe feishu_bot.py

支持的指令（单聊直接发，群里 @机器人 后发）：

    门诊 01478 席林 2026-01-01 2026-10-18
    住院 席林 副主任 2026-01-01 2026-10-18
    患者 席林 2026-01-01 2026-10-18
    帮助

命令里带「文件」「导出」或「报表」时，回复 Excel/PDF 文件而不是文字结果。

前置条件（飞书开发者后台）：
1. 开通「长连接」订阅方式；
2. 订阅事件 im.message.receive_v1；
3. 申请权限 im:message.p2p_msg:readonly（单聊）和 im:message.group_at_msg:readonly
   或 im:message.group_msg（群聊），以及 im:message:send_as_bot（发消息）。
"""
from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import traceback
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(APP_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import lark_oapi as lark  # noqa: E402
from lark_oapi.api.im.v1 import (  # noqa: E402
    CreateFileRequest,
    CreateFileRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from config import get_feishu_config, load_config  # noqa: E402

DATE_RE = re.compile(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})')
EMPLOYEE_ID_RE = re.compile(r'^0\d{3,5}$')

TYPE_WORDS = {
    'sp': ('主任医师', '主任', '正高'),
    'ap': ('副主任医师', '副主任', '副高'),
    'nurse': ('护士', '护理'),
    'anes': ('麻醉师', '麻醉'),
}

TYPE_NAMES = {'sp': '主任医师', 'ap': '副主任医师', 'nurse': '护士', 'anes': '麻醉师'}

# 长的词优先匹配，避免「副主任」被「主任」抢先命中
TYPE_MATCHERS = sorted(
    ((word, key) for key, words in TYPE_WORDS.items() for word in words),
    key=lambda item: len(item[0]),
    reverse=True,
)

# 文字回复里患者明细最多展示的行数
PATIENT_PREVIEW_ROWS = 10

HELP_TEXT = """工作量查询机器人使用说明

1) 门诊工作量（按员工编号）
   门诊 01478 席林 2026-01-01 2026-10-18

2) 住院工作量（按姓名 + 申报职称）
   住院 席林 副主任 2026-01-01 2026-10-18
   职称支持：主任 / 副主任 / 护士 / 麻醉

3) 患者明细
   患者 席林 2026-01-01 2026-10-18
   可选维度：科室 / 诊断 / 护士，例如「患者 科室 针灸科 2026-01-01 2026-10-18」

4) 需要 Excel/PDF 时，在命令末尾加「文件」
   门诊 01478 席林 2026-01-01 2026-10-18 文件

日期缺省为「本月 1 日 ~ 今天」。"""


# ---------------------------------------------------------------- 指令解析
def parse_command(text):
    """把一句自然输入解析成查询指令。"""
    raw = (text or '').strip()
    raw = re.sub(r'@_user_\d+', ' ', raw)  # 群里 @机器人 的占位符
    raw = re.sub(r'\s+', ' ', raw).strip()
    if not raw:
        return {'action': 'help'}

    lowered = raw.lower()
    if lowered in ('帮助', 'help', '?', '？', '菜单', '说明'):
        return {'action': 'help'}

    dates = ['%s-%02d-%02d' % (year, int(month), int(day)) for year, month, day in DATE_RE.findall(raw)]
    body = DATE_RE.sub(' ', raw)

    # 指令类型：优先看句首，避免把科室名里的「住院」误当成住院查询
    action = None
    for word, name in (('门诊', 'outpatient'), ('住院', 'inpatient'), ('患者', 'patients')):
        if raw.startswith(word):
            action = name
            body = body.replace(word, ' ', 1)
            break
    if action is None:
        found = [(body.find(word), name, word) for word, name in
                 (('门诊', 'outpatient'), ('住院', 'inpatient'), ('患者', 'patients')) if word in body]
        if found:
            position, name, word = min(found)
            action = name
            body = body[:position] + ' ' + body[position + len(word):]

    want_file = any(word in body for word in ('文件', '导出', '报表', 'PDF', 'pdf', 'xlsx', 'Excel', 'excel'))
    for word in ('工作量', '查询', '一下', '请', '帮忙', '文件', '导出', '报表',
                 'PDF', 'pdf', 'xlsx', 'Excel', 'excel', '工号', '员工编号', '姓名'):
        body = body.replace(word, ' ')

    query_type = None
    if action in (None, 'inpatient'):
        for word, key in TYPE_MATCHERS:
            if word in body:
                query_type = key
                body = body.replace(word, ' ')
                break

    patient_kind = 'doctor'
    if action == 'patients':
        for word, kind in (('科室', 'dept'), ('诊断', 'diag'), ('护士', 'nurse')):
            if word in body:
                patient_kind = kind
                body = body.replace(word, ' ')
                break

    employee_id = ''
    name = ''
    for token in re.split(r'[ \t,，、;；:：]+', body):
        token = token.strip('（）()[]【】。. ')
        if not token:
            continue
        if EMPLOYEE_ID_RE.match(token):
            employee_id = token
        elif not name and not re.fullmatch(r'[A-Za-z0-9_\-]+', token):
            name = token

    if action is None:
        if employee_id:
            action = 'outpatient'
        elif query_type:
            action = 'inpatient'
        else:
            return {'action': 'help'}

    if action == 'patients':
        return {'action': 'patients', 'name': name, 'patient_kind': patient_kind,
                'start_date': dates[0] if dates else None,
                'end_date': dates[1] if len(dates) > 1 else None,
                'want_file': want_file}

    if action == 'outpatient':
        return {'action': 'outpatient', 'employee_id': employee_id, 'name': name,
                'start_date': dates[0] if dates else None,
                'end_date': dates[1] if len(dates) > 1 else None,
                'want_file': want_file}

    return {'action': 'inpatient', 'name': name, 'query_type': query_type or 'sp',
            'start_date': dates[0] if dates else None,
            'end_date': dates[1] if len(dates) > 1 else None,
            'want_file': want_file}


def _resolve_period(start_date, end_date):
    today = datetime.now()
    return (
        start_date or today.replace(day=1).strftime('%Y-%m-%d'),
        end_date or today.strftime('%Y-%m-%d'),
    )


# ---------------------------------------------------------------- 结果格式化
def _cell(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def format_outpatient(employee_id, name, start_date, end_date, columns, rows):
    lines = [f'【门诊工作量】{name or "-"}（工号 {employee_id}）',
             f'统计期间：{start_date} ~ {end_date}']
    for row in rows:
        period, _, count = (list(row) + ['', '', ''])[:3]
        if _cell(period) == '合计':
            lines.append(f'合计：{_cell(count)} 人次')
        else:
            lines.append(f'{_cell(period)} 年：{_cell(count)} 人次')
    if len(lines) == 2:
        lines.append('未查询到数据')
    return '\n'.join(lines)


def format_inpatient(name, query_type, start_date, end_date, columns, rows):
    lines = [f'【住院工作量】{name}（{TYPE_NAMES.get(query_type, query_type)}）',
             f'统计期间：{start_date} ~ {end_date}']
    for row in rows:
        parts = [f'{_cell(col)}={_cell(val)}' for col, val in zip(columns, row) if _cell(val) != '']
        lines.append('· ' + '，'.join(parts))
    if len(lines) == 2:
        lines.append('未查询到数据')
    return '\n'.join(lines)


def format_patients(kind_name, name, start_date, end_date, columns, rows):
    total = len(rows)
    lines = [f'【患者明细】{kind_name}：{name}',
             f'统计期间：{start_date} ~ {end_date}']
    if not total:
        lines.append('未查询到数据')
        return '\n'.join(lines)
    lines.append(f'共 {total} 条，先展示前 {min(total, PATIENT_PREVIEW_ROWS)} 条：')
    for index, row in enumerate(rows[:PATIENT_PREVIEW_ROWS], 1):
        parts = [f'{_cell(col)}={_cell(val)}' for col, val in zip(columns, row) if _cell(val) != '']
        lines.append(f'{index}. ' + '，'.join(parts))
    if total > PATIENT_PREVIEW_ROWS:
        lines.append(f'……其余 {total - PATIENT_PREVIEW_ROWS} 条请加「文件」获取完整报表')
    return '\n'.join(lines)


# ---------------------------------------------------------------- 执行查询
def execute(command):
    """执行解析后的指令，返回 (ok, 文本, 文件路径或 None)。"""
    action = command['action']
    if action == 'help':
        return True, HELP_TEXT, None

    start_date, end_date = _resolve_period(command.get('start_date'), command.get('end_date'))
    want_file = command.get('want_file', False)

    if action == 'outpatient':
        from clinic_query import export_clinic_to_xlsx, query_clinic_data

        employee_id = command.get('employee_id', '')
        name = command.get('name', '')
        if not employee_id:
            return False, '门诊查询需要员工编号，例如：门诊 01478 席林 2026-01-01 2026-10-18', None

        result_df, total = query_clinic_data(employee_id, name, start_date, end_date)
        if result_df is None:
            return False, f'门诊查询失败：{total}', None

        columns = [str(column) for column in result_df.columns]
        rows = [list(row) for row in result_df.itertuples(index=False, name=None)]
        text = format_outpatient(employee_id, name, start_date, end_date, columns, rows)

        file_path = None
        if want_file:
            file_path = export_clinic_to_xlsx(name or employee_id, result_df)
        return True, text, file_path

    if action == 'inpatient':
        from database import QUERY_TYPES, query_data

        name = command.get('name', '')
        query_type = command.get('query_type', 'sp')
        if not name:
            return False, '住院查询需要姓名，例如：住院 席林 副主任 2026-01-01 2026-10-18', None
        if query_type not in QUERY_TYPES:
            query_type = 'sp'

        columns, rows, result = query_data(name, query_type, start_date, end_date, save_excel=bool(want_file))
        if columns is None:
            return False, f'住院查询失败：{result}', None

        text = format_inpatient(name, query_type, start_date, end_date, list(columns), rows)
        return True, text, (result if want_file else None)

    # 患者明细
    from database import (
        query_patients_by_dept,
        query_patients_by_diag,
        query_patients_by_doctor,
        query_patients_by_nurse,
    )

    kind = command.get('patient_kind', 'doctor')
    name = command.get('name', '')
    if not name:
        return False, '患者查询需要姓名 / 科室 / 诊断，例如：患者 席林 2026-01-01 2026-10-18', None

    if kind == 'dept':
        columns, rows, path, error = query_patients_by_dept(name, start_date, end_date, save_excel=bool(want_file))
        kind_name = '按科室'
    elif kind == 'diag':
        columns, rows, path, error = query_patients_by_diag(name, start_date, end_date, save_excel=bool(want_file))
        kind_name = '按诊断'
    elif kind == 'nurse':
        columns, rows, path, error = query_patients_by_nurse(name, start_date, end_date, 'nurse',
                                                             save_excel=bool(want_file))
        kind_name = '按护士'
    else:
        columns, rows, path, error = query_patients_by_doctor(name, start_date, end_date, save_excel=bool(want_file))
        kind_name = '按医生'

    if columns is None:
        return False, f'患者查询失败：{error}', None

    text = format_patients(kind_name, name, start_date, end_date, list(columns), rows)
    if not rows and error:
        text += f'\n（{error}）'
    return True, text, (path if want_file else None)


# ---------------------------------------------------------------- 飞书交互
class FeishuBot:
    def __init__(self):
        config = get_feishu_config()
        self.app_id = config.get('app_id', '')
        self.app_secret = config.get('app_secret', '')
        self.allowed = set(config.get('allowed_open_ids') or [])
        if not self.app_id or not self.app_secret:
            raise RuntimeError('未配置飞书 app_id / app_secret（config.json 的 feishu 段）')
        self.client = lark.Client.builder().app_id(self.app_id).app_secret(self.app_secret).build()
        self.jobs = queue.Queue()
        self.seen = set()
        self.seen_lock = threading.Lock()

    # ---- 事件入口（SDK 回调，必须尽快返回）
    def on_message(self, data):
        try:
            message = data.event.message
            message_id = message.message_id
            if message.message_type != 'text':
                self._reply_text(message_id, '目前只支持文本指令，发送「帮助」查看用法。')
                return

            with self.seen_lock:
                if message_id in self.seen:
                    return
                self.seen.add(message_id)
                if len(self.seen) > 500:
                    self.seen.clear()

            text = json.loads(message.content or '{}').get('text', '')
            sender = data.event.sender
            open_id = getattr(sender.sender_id, 'open_id', '') if sender and sender.sender_id else ''
            if self.allowed and open_id not in self.allowed:
                self._reply_text(message_id, '你没有使用权限，请联系管理员把 open_id 加入 allowed_open_ids。')
                return

            self.jobs.put((message_id, text))
        except Exception:
            traceback.print_exc()

    def _worker(self):
        while True:
            message_id, text = self.jobs.get()
            try:
                command = parse_command(text)
                ok, body, file_path = execute(command)
                prefix = '' if ok else '❌ '
                if file_path and os.path.exists(file_path):
                    self._reply_text(message_id, prefix + body)
                    self._reply_file(message_id, file_path)
                else:
                    self._reply_text(message_id, prefix + body)
            except Exception as exc:
                traceback.print_exc()
                self._reply_text(message_id, f'❌ 处理失败：{exc}')
            finally:
                self.jobs.task_done()

    # ---- 回复
    def _reply_text(self, message_id, text):
        self._reply(message_id, 'text', json.dumps({'text': text}))

    def _reply_file(self, message_id, file_path):
        try:
            name = os.path.basename(file_path)
            with open(file_path, 'rb') as handle:
                body = (CreateFileRequestBody.builder()
                        .file_type('stream')
                        .file_name(name)
                        .file(handle)
                        .build())
                response = self.client.im.v1.file.create(CreateFileRequest.builder().request_body(body).build())
            if not response.success():
                self._reply_text(message_id, f'❌ 文件上传失败：{response.code} {response.msg}')
                return
            self._reply(message_id, 'file', json.dumps({'file_key': response.data.file_key}))
        except Exception as exc:
            self._reply_text(message_id, f'❌ 文件发送失败：{exc}')

    def _reply(self, message_id, msg_type, content):
        try:
            body = ReplyMessageRequestBody.builder().msg_type(msg_type).content(content).build()
            request = ReplyMessageRequest.builder().message_id(message_id).request_body(body).build()
            response = self.client.im.v1.message.reply(request)
            if not response.success():
                print(f'[feishu-bot] 回复失败: {response.code} {response.msg}', file=sys.stderr)
        except Exception:
            traceback.print_exc()

    def run(self):
        handler = (lark.EventDispatcherHandler.builder('', '')
                   .register_p2_im_message_receive_v1(self.on_message)
                   .build())
        threading.Thread(target=self._worker, daemon=True).start()
        print('[feishu-bot] 长连接启动，等待消息…', file=sys.stderr)
        lark.ws.Client(self.app_id, self.app_secret,
                       event_handler=handler,
                       log_level=lark.LogLevel.INFO).start()


def main():
    load_config()
    FeishuBot().run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
