# ============== 钉钉模块 ==============
import os
import requests

# ============== 钉钉配置 ==============
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=d68e1626c9e5689513089f2d67a9b698067442884f342c733b82e953abb71df7"
DINGTALK_CORP_ID = "ding5wrt0wqdqrwzpxpa"
DINGTALK_CORP_SECRET = "1QlNVwS75zFkIcscCeBmpC7mWg0d_4iAzK5hBWYGd22KOKaSGT7lf-oo2ikFH1Jx"
DINGTALK_AGENT_ID = "4362448726"


def get_dingtalk_token():
    """获取钉钉 access_token"""
    try:
        url = f"https://oapi.dingtalk.com/gettoken?appkey={DINGTALK_CORP_ID}&appsecret={DINGTALK_CORP_SECRET}"
        resp = requests.get(url, timeout=10)
        result = resp.json()
        if result.get('errcode') == 0:
            return result.get('access_token')
        return None
    except Exception as e:
        print(f"获取token失败: {e}")
        return None


def upload_dingtalk_file(token, file_path, file_type='file'):
    """上传文件到钉钉"""
    try:
        url = f"https://oapi.dingtalk.com/media/upload?access_token={token}&type={file_type}"
        files = {'media': (os.path.basename(file_path), open(file_path, 'rb'), 'application/octet-stream')}
        resp = requests.post(url, files=files, timeout=30)
        result = resp.json()
        if result.get('errcode') == 0:
            return result.get('media_id')
        return None
    except Exception as e:
        print(f"上传文件失败: {e}")
        return None


def query_dingtalk_send_result(token, task_id):
    """查询异步发送结果"""
    try:
        url = f"https://oapi.dingtalk.com/topapi/message/corpconversation/getsendresult?access_token={token}"
        payload = {
            "agent_id": DINGTALK_AGENT_ID,
            "task_id": task_id
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"查询发送结果失败: {e}")
        return None


def send_dingtalk_file_message(token, media_id, file_name, employee_id=None):
    """发送文件消息到钉钉"""
    try:
        user_id = None
        if employee_id:
            try:
                from .auth import get_dingtalk_userid_by_employee_id
                user_id = get_dingtalk_userid_by_employee_id(employee_id)
            except:
                pass
        
        if not user_id:
            user_id = get_user_id_by_name(token, "ourhospital")
        
        if not user_id:
            return {"errcode": 400, "errmsg": "用户不存在"}
        
        url = f"https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2?access_token={token}"
        payload = {
            "agent_id": DINGTALK_AGENT_ID,
            "userid_list": user_id,
            "msg": {
                "msgtype": "file",
                "file": {
                    "media_id": media_id
                }
            }
        }
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()
        
        if result.get('errcode') == 0 and result.get('task_id'):
            import time
            time.sleep(2)
            query_dingtalk_send_result(token, result.get('task_id'))
        
        return result
    except Exception as e:
        print(f"发送消息失败: {e}")
        return None


def get_user_id_by_name(token, name):
    """根据用户名获取用户ID"""
    try:
        from .auth import get_dingtalk_userid_by_employee_id
        userid = get_dingtalk_userid_by_employee_id(name)
        if userid:
            return userid
    except:
        pass
    return name


def send_file_to_dingtalk(file_path, xlsx_to_pdf_func=None, employee_id=None):
    """
    发送文件到钉钉（主函数）
    
    Args:
        file_path: 文件路径
        xlsx_to_pdf_func: xlsx转pdf的函数（可选）
        employee_id: 员工编号，用于获取钉钉用户ID
    
    Returns:
        tuple: (success, message)
    """
    from datetime import datetime
    
    if not file_path:
        return False, '文件路径为空'
    
    # xlsx转pdf
    pdf_path = file_path
    if file_path.endswith('.xlsx') and xlsx_to_pdf_func:
        pdf_path = file_path.replace('\\xls\\', '\\pdf\\').replace('/xls/', '/pdf/').replace('.xlsx', '.pdf')
        if not os.path.exists(pdf_path):
            try:
                pdf_path = xlsx_to_pdf_func(file_path)
            except:
                pdf_path = file_path
    
    # 检查文件是否存在
    actual_path = pdf_path if os.path.exists(pdf_path) else (file_path if os.path.exists(file_path) else None)
    if not actual_path:
        return False, '文件不存在'
    
    file_name = os.path.basename(actual_path)
    
    # 尝试使用企业应用API发送
    if DINGTALK_CORP_SECRET:
        token = get_dingtalk_token()
        if token:
            media_id = upload_dingtalk_file(token, actual_path, 'file')
            if media_id:
                result = send_dingtalk_file_message(token, media_id, file_name, employee_id)
                if result and result.get('errcode') == 0:
                    return True, '已发送到钉钉'
    
    # 回退到webhook
    try:
        msg_content = f"📊 查询报表\n\n**文件名**: {file_name}\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n> 文件路径: `{actual_path}`"
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": "查询报表",
                "text": msg_content
            }
        }
        
        response = requests.post(DINGTALK_WEBHOOK, json=payload, timeout=10)
        result = response.json()
        
        if result.get('errcode') == 0:
            return True, '已发送到钉钉'
        else:
            return False, f'钉钉返回错误: {result.get("errmsg", "未知错误")}'
    except Exception as e:
        return False, f'发送失败: {str(e)}'
