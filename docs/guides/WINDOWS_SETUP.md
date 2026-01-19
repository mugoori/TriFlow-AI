# Windows 사용자 가이드

TriFlow AI를 Windows 환경에서 실행하는 방법을 안내합니다.

---

## 📋 목차

1. [Windows 전용 요구사항](#windows-전용-요구사항)
2. [Docker Desktop 설치](#docker-desktop-설치)
3. [Git 설치 및 설정](#git-설치-및-설정)
4. [Quick Start (Windows)](#quick-start-windows)
5. [Windows 특화 문제 해결](#windows-특화-문제-해결)
6. [개발 도구 추천](#개발-도구-추천)

---

## Windows 전용 요구사항

### 필수

- **Windows 10/11** (64-bit)
- **WSL2** (Windows Subsystem for Linux 2) - Docker Desktop 요구사항
- **Docker Desktop for Windows 4.20+**
- **Git for Windows 2.30+**

### 선택 (로컬 개발 시)

- **Python 3.11+** for Windows
- **Node.js 20+** for Windows
- **Visual Studio Code** (권장 IDE)

---

## Docker Desktop 설치

### 1. WSL2 활성화

관리자 권한 PowerShell에서 실행:

```powershell
# WSL 활성화
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# Virtual Machine Platform 활성화
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# 재부팅
Restart-Computer
```

재부팅 후:

```powershell
# WSL2를 기본값으로 설정
wsl --set-default-version 2
```

### 2. Docker Desktop 설치

1. https://www.docker.com/products/docker-desktop 에서 다운로드
2. 설치 프로그램 실행
3. "Use WSL 2 instead of Hyper-V" 옵션 선택
4. 재부팅
5. Docker Desktop 실행

### 3. Docker 설정 확인

PowerShell에서:

```powershell
docker --version
docker-compose --version
docker ps  # 실행 중인 컨테이너 확인 (비어있어야 정상)
```

---

## Git 설치 및 설정

### 1. Git for Windows 설치

https://git-scm.com/download/win 에서 다운로드

### 2. Line Ending 설정 (중요!)

```powershell
# Git Bash 또는 PowerShell에서
git config --global core.autocrlf true
```

**설명**:
- Windows: CRLF (\\r\\n)
- Linux: LF (\\n)
- `autocrlf=true`: checkout 시 CRLF로 변환, commit 시 LF로 변환

---

## Quick Start (Windows)

### PowerShell 사용 (권장)

```powershell
# 1. 저장소 클론
git clone https://github.com/mugoori/TriFlow-AI.git
cd triflow-ai

# 2. 환경 파일 복사
copy .env.example backend\.env

# 3. .env 파일 편집 (메모장 또는 VS Code)
notepad backend\.env
# ANTHROPIC_API_KEY 값 입력

# 4. Docker로 전체 시스템 실행
docker-compose up -d

# 5. 서비스 상태 확인 (2분 대기)
docker-compose ps
docker-compose logs -f --tail 20
```

### Git Bash 사용

```bash
# Linux 명령어 그대로 사용 가능
git clone https://github.com/mugoori/TriFlow-AI.git
cd triflow-ai
cp .env.example backend/.env

docker-compose up -d
docker-compose ps
```

---

## 로컬 개발 (Windows)

### Backend 로컬 실행

#### Python venv 사용

```powershell
cd backend

# 가상 환경 생성
python -m venv venv

# 활성화 (PowerShell)
venv\Scripts\Activate.ps1

# 활성화 (CMD)
venv\Scripts\activate.bat

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn app.main:app --reload
```

#### 실행 정책 오류 시

PowerShell 실행 정책 오류가 발생하면:

```powershell
# 관리자 권한 PowerShell에서
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 또는 일회성으로
powershell -ExecutionPolicy Bypass -File .\venv\Scripts\Activate.ps1
```

### Frontend 로컬 실행

```powershell
cd frontend

# 의존성 설치
npm install

# .env 파일 생성
echo VITE_API_URL=http://localhost:8000 > .env

# 개발 서버 실행
npm run dev

# 또는 Tauri Desktop
npm run tauri dev
```

---

## Hybrid 모드 (Windows)

DB만 Docker, Backend/Frontend는 로컬로 실행합니다.

### PowerShell 스크립트

```powershell
# 1. Docker로 DB 실행
docker-compose up -d postgres redis

# 2. Backend 실행 (새 PowerShell 창)
cd backend
venv\Scripts\Activate.ps1
uvicorn app.main:app --reload

# 3. Frontend 실행 (또 다른 PowerShell 창)
cd frontend
npm run dev
```

### 편의 스크립트 생성

`dev-start.ps1` 파일 생성:

```powershell
# TriFlow AI Development Start Script

Write-Host "Starting TriFlow AI Development Environment..." -ForegroundColor Green

# DB 시작
Write-Host "`n[1/3] Starting PostgreSQL and Redis..." -ForegroundColor Cyan
docker-compose up -d postgres redis

# Backend 시작 (백그라운드)
Write-Host "`n[2/3] Starting Backend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; venv\Scripts\Activate.ps1; uvicorn app.main:app --reload"

# 2초 대기
Start-Sleep -Seconds 2

# Frontend 시작 (백그라운드)
Write-Host "`n[3/3] Starting Frontend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "`n✓ All services started!" -ForegroundColor Green
Write-Host "Backend: http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Yellow
```

실행:
```powershell
.\dev-start.ps1
```

---

## Windows 특화 문제 해결

### 1. 포트 확인

```powershell
# 포트 사용 확인
netstat -ano | findstr :8000
netstat -ano | findstr :5432

# 프로세스 종료 (PID 확인 후)
taskkill /PID <PID> /F
```

### 2. 경로 문제

Windows는 백슬래시(\\)를 사용하지만, 대부분의 도구는 슬래시(/)도 지원합니다.

```powershell
# 슬래시 사용 (권장)
cd backend/app

# 백슬래시 (Windows 전통)
cd backend\app
```

### 3. 파일 권한 문제

Windows에서는 Linux 스타일 파일 권한이 없습니다.

```powershell
# 스크립트 실행 권한 (불필요)
# Linux의 chmod +x는 Windows에서 필요 없음
```

### 4. Line Ending (CRLF vs LF)

```powershell
# Git 설정 확인
git config core.autocrlf

# true여야 함 (Windows 권장)
git config --global core.autocrlf true
```

### 5. Python 가상 환경 충돌

```powershell
# 기존 venv 삭제
Remove-Item -Recurse -Force venv

# 재생성
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 6. Docker Desktop 메모리 부족

Docker Desktop 설정 → Resources → Memory 증가 (최소 4GB, 권장 8GB)

---

## 개발 도구 추천

### IDE

**Visual Studio Code** (무료, 강력 추천)
- 설치: https://code.visualstudio.com
- 확장:
  - Python
  - Pylance
  - ESLint
  - Prettier
  - Docker
  - GitLens

**PyCharm** (유료, 전문가용)
- Community Edition 무료

### 터미널

**Windows Terminal** (권장)
- Microsoft Store에서 설치
- PowerShell, CMD, Git Bash 통합
- 탭, 분할 화면 지원

**Git Bash**
- Git for Windows 설치 시 포함
- Linux 명령어 사용 가능

### 데이터베이스 클라이언트

**DBeaver** (무료, 추천)
- https://dbeaver.io

**pgAdmin** (PostgreSQL 전용)
- https://www.pgadmin.org

### API 테스트

**Postman** 또는 **Thunder Client** (VS Code 확장)

---

## 관련 문서

- [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) - 로컬 개발 가이드 (플랫폼 공통)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - 문제 해결 가이드
- [DEPLOYMENT.md](DEPLOYMENT.md) - 프로덕션 배포 가이드
