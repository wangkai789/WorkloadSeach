# ============== 配置管理模块 ==============
import os
import json

# 默认配置
DEFAULT_CONFIG = {
    'database': {
        'server': '192.168.101.19',
        'port': 1433,
        'user': 'dhuser',
        'password': 'dhcctest',
        'database': 'dhcc'
    },
    'data_warehouse': {
        'driver': 'InterSystems IRIS ODBC35',
        'server': '172.20.16.28',
        'port': 51773,
        'namespace': 'MDR',
        'user': '_system',
        'password': ''
    },
    'paths': {
        'output_dir': r'D:\WorkSpace\东华住院工作量查询\dist',
        'xls_dir': r'D:\WorkSpace\东华住院工作量查询\dist\xls',
        'pdf_dir': r'D:\WorkSpace\东华住院工作量查询\dist\pdf',
        'clinic_data_dir': r'D:\WorkSpace\东华住院工作量查询\dist\data'
    },
    'clinic': {
        'clinic_reports': [
            "2019医生组出入院统计报表.xlsx",
            "2020医生组出入院统计报表.xlsx",
            "2021医生组出入院统计报表.xlsx",
            "2022医生组出入院统计报表.xlsx",
            "2023医生组出入院统计报表.xlsx",
            "2023医生组出入院统计报表(康复).xlsx",
            "2024医生组出入院统计报表.xlsx",
            "2024医生组出入院统计报表(康复).xlsx",
            "2025医生组出入院统计报表.xlsx",
            "2025医生组出入院统计报表(康复).xlsx",
            "202601-04.15医生组出入院统计报表.xlsx",
            "202601-04.15医生组出入院统计报表(康复).xlsx"
        ]
    },
    'feishu': {
        'app_id': '',
        'app_secret': '',
        'receive_id_type': 'open_id',
        'default_receive_id': ''
    }
}

# 全局变量
DB_CONFIG = {}
DATA_WAREHOUSE_CONFIG = {}
FEISHU_CONFIG = {}
OUTPUT_DIR = ''
XLS_DIR = ''
PDF_DIR = ''
CLINIC_DATA_DIR = ''
CLINIC_REPORTS = []


def get_config_file():
    """获取配置文件路径"""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'config.json')
    # 从 src/ 向上一级到 东华住院工作量查询/，再进入 dist/
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dist', 'config.json')


def load_config():
    """加载配置文件"""
    global DB_CONFIG, DATA_WAREHOUSE_CONFIG, FEISHU_CONFIG, OUTPUT_DIR, XLS_DIR, PDF_DIR, CLINIC_DATA_DIR, CLINIC_REPORTS
    config_file = get_config_file()
    
    # 兼容旧版INI配置
    ini_config_file = config_file.replace('.json', '.ini')
    if os.path.exists(ini_config_file) and not os.path.exists(config_file):
        try:
            import configparser
            parser = configparser.ConfigParser()
            parser.read(ini_config_file, encoding='utf-8')
            
            config = {
                'database': {
                    'server': parser.get('database', 'server', fallback=DEFAULT_CONFIG['database']['server']),
                    'port': parser.getint('database', 'port', fallback=DEFAULT_CONFIG['database']['port']),
                    'user': parser.get('database', 'user', fallback=DEFAULT_CONFIG['database']['user']),
                    'password': parser.get('database', 'password', fallback=DEFAULT_CONFIG['database']['password']),
                    'database': parser.get('database', 'database', fallback=DEFAULT_CONFIG['database']['database']),
                },
                'paths': {
                    'output_dir': parser.get('paths', 'output_dir', fallback=DEFAULT_CONFIG['paths']['output_dir']),
                    'xls_dir': parser.get('paths', 'xls_dir', fallback=DEFAULT_CONFIG['paths']['xls_dir']),
                    'pdf_dir': parser.get('paths', 'pdf_dir', fallback=DEFAULT_CONFIG['paths']['pdf_dir']),
                    'clinic_data_dir': parser.get('paths', 'clinic_data_dir', fallback=DEFAULT_CONFIG['paths']['clinic_data_dir']),
                },
                'clinic': {
                    'clinic_reports': DEFAULT_CONFIG['clinic']['clinic_reports']
                }
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            print(f"已从旧版INI配置迁移到JSON格式")
        except Exception as e:
            print(f"迁移配置失败: {e}")
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            DB_CONFIG = config.get('database', DEFAULT_CONFIG['database'])
            DATA_WAREHOUSE_CONFIG = config.get('data_warehouse', DEFAULT_CONFIG['data_warehouse'])
            FEISHU_CONFIG = config.get('feishu', DEFAULT_CONFIG['feishu'])
            paths = config.get('paths', DEFAULT_CONFIG['paths'])
            OUTPUT_DIR = paths.get('output_dir', DEFAULT_CONFIG['paths']['output_dir'])
            XLS_DIR = paths.get('xls_dir', DEFAULT_CONFIG['paths']['xls_dir'])
            PDF_DIR = paths.get('pdf_dir', DEFAULT_CONFIG['paths']['pdf_dir'])
            CLINIC_DATA_DIR = paths.get('clinic_data_dir', DEFAULT_CONFIG['paths']['clinic_data_dir'])
            CLINIC_REPORTS = config.get('clinic', {}).get('clinic_reports', DEFAULT_CONFIG['clinic']['clinic_reports'])
        except Exception as e:
            print(f"加载配置失败: {e}")
            init_db_config()
    else:
        init_db_config()


def init_db_config():
    """初始化数据库配置"""
    global DB_CONFIG, DATA_WAREHOUSE_CONFIG, FEISHU_CONFIG, OUTPUT_DIR, XLS_DIR, PDF_DIR, CLINIC_DATA_DIR, CLINIC_REPORTS
    DB_CONFIG = DEFAULT_CONFIG['database']
    DATA_WAREHOUSE_CONFIG = DEFAULT_CONFIG['data_warehouse']
    FEISHU_CONFIG = DEFAULT_CONFIG['feishu']
    OUTPUT_DIR = DEFAULT_CONFIG['paths']['output_dir']
    XLS_DIR = DEFAULT_CONFIG['paths']['xls_dir']
    PDF_DIR = DEFAULT_CONFIG['paths']['pdf_dir']
    CLINIC_DATA_DIR = DEFAULT_CONFIG['paths']['clinic_data_dir']
    CLINIC_REPORTS = DEFAULT_CONFIG['clinic']['clinic_reports']


def save_config_to_file(server, port, user, password, database, output_dir, xls_dir='', pdf_dir='', clinic_data_dir='', clinic_reports=None, data_warehouse=None):
    """保存配置文件到JSON格式"""
    global DB_CONFIG, DATA_WAREHOUSE_CONFIG, FEISHU_CONFIG, OUTPUT_DIR, XLS_DIR, PDF_DIR, CLINIC_DATA_DIR, CLINIC_REPORTS
    config_file = get_config_file()

    try:
        if not xls_dir:
            xls_dir = os.path.join(output_dir, 'xls')
        if not pdf_dir:
            pdf_dir = os.path.join(output_dir, 'pdf')
        if not clinic_data_dir:
            clinic_data_dir = DEFAULT_CONFIG['paths']['clinic_data_dir']
        if clinic_reports is None:
            clinic_reports = DEFAULT_CONFIG['clinic']['clinic_reports']

        current_data_warehouse = DATA_WAREHOUSE_CONFIG or DEFAULT_CONFIG['data_warehouse']
        if data_warehouse:
            current_data_warehouse = {
                'driver': data_warehouse.get('driver', current_data_warehouse.get('driver', '')),
                'server': data_warehouse.get('server', current_data_warehouse.get('server', '')),
                'port': int(data_warehouse.get('port', current_data_warehouse.get('port', 0))),
                'namespace': data_warehouse.get('namespace', current_data_warehouse.get('namespace', '')),
                'user': data_warehouse.get('user', current_data_warehouse.get('user', '')),
                'password': data_warehouse.get('password', current_data_warehouse.get('password', ''))
            }

        config = {
            'database': {
                'server': server,
                'port': int(port),
                'user': user,
                'password': password,
                'database': database
            },
            'data_warehouse': current_data_warehouse,
            # 飞书机器人凭证不由 Web 配置页维护，保存其他配置时原样保留，避免被清空
            'feishu': FEISHU_CONFIG or DEFAULT_CONFIG['feishu'],
            'paths': {
                'output_dir': output_dir,
                'xls_dir': xls_dir,
                'pdf_dir': pdf_dir,
                'clinic_data_dir': clinic_data_dir
            },
            'clinic': {
                'clinic_reports': clinic_reports
            }
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

        DB_CONFIG = config['database']
        DATA_WAREHOUSE_CONFIG = config['data_warehouse']
        OUTPUT_DIR = output_dir
        XLS_DIR = xls_dir
        PDF_DIR = pdf_dir
        CLINIC_DATA_DIR = clinic_data_dir
        CLINIC_REPORTS = clinic_reports
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False


def get_db_config():
    """获取数据库配置"""
    return DB_CONFIG


def get_data_warehouse_config():
    """获取东华数据仓库配置"""
    return DATA_WAREHOUSE_CONFIG


def get_feishu_config():
    """获取飞书机器人配置（app_id / app_secret / receive_id_type / default_receive_id）"""
    return FEISHU_CONFIG or DEFAULT_CONFIG['feishu']


def get_output_dir():
    """获取输出目录"""
    return OUTPUT_DIR


def get_xls_dir():
    """获取XLS导出目录"""
    return XLS_DIR


def get_pdf_dir():
    """获取PDF导出目录"""
    return PDF_DIR


def get_clinic_data_dir():
    """获取门诊数据目录"""
    return CLINIC_DATA_DIR


def get_clinic_reports():
    """获取门诊报表文件列表"""
    return CLINIC_REPORTS
