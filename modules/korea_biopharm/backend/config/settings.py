import os
import sys
import json
import socket
from pathlib import Path

def get_base_path():
    """PyInstaller exe 또는 개발 환경에서 기본 경로 반환."""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우: exe 파일 위치
        return Path(sys.executable).parent
    else:
        # 개발 환경: backend 폴더의 상위
        return Path(__file__).resolve().parent.parent.parent

def get_resource_path():
    """PyInstaller에서 패키징된 리소스(static 등) 경로 반환."""
    if getattr(sys, 'frozen', False):
        # PyInstaller 임시 폴더 (_MEIPASS)
        return Path(sys._MEIPASS)
    else:
        # 개발 환경
        return Path(__file__).resolve().parent.parent.parent

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent  # backend 폴더
BASE_PATH = get_base_path()
RESOURCE_PATH = get_resource_path()

# 개발 환경 vs 배포 환경 구분
IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:
    # 배포 환경: exe와 같은 폴더에 Data, config 폴더
    DB_PATH = BASE_PATH / "Data" / "formulation.db"
    API_KEYS_PATH = BASE_PATH / "config" / "api_keys.json"
    # static은 exe 내부에 패키징됨 (_MEIPASS 경로)
    STATIC_DIR = RESOURCE_PATH / "static"
else:
    # 개발 환경: TriFlow 모듈 내부 경로 사용
    PROJECT_ROOT = BASE_DIR.parent
    DB_PATH = BASE_DIR / "Data" / "formulation.db"
    API_KEYS_PATH = BASE_DIR / "config" / "api_keys.json"
    STATIC_DIR = PROJECT_ROOT / "frontend" / "dist"  # Vite 빌드 결과물

def load_api_keys():
    """Load API keys from config file."""
    try:
        if API_KEYS_PATH.exists():
            with open(API_KEYS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"API keys file not found: {API_KEYS_PATH}")
            return {}
    except Exception as e:
        print(f"Error loading API keys: {e}")
        return {}

API_KEYS = load_api_keys()

# CORS settings (배포 시에는 같은 origin이므로 필요 없지만 개발 편의를 위해 유지)
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# 서버 설정
SERVER_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

def find_available_port(start_port=8000, max_attempts=10):
    """사용 가능한 포트를 찾습니다."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((SERVER_HOST, port))
                return port
        except OSError:
            continue
    return start_port  # 찾지 못하면 기본 포트 반환

SERVER_PORT = find_available_port(DEFAULT_PORT) if IS_FROZEN else DEFAULT_PORT
