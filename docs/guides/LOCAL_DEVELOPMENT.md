# 로컬 개발 가이드

TriFlow AI를 Docker 없이 로컬 환경에서 개발하는 방법을 안내합니다.

---

## 📋 목차

1. [개요](#개요)
2. [환경 설정](#환경-설정)
3. [Backend 로컬 실행](#backend-로컬-실행)
4. [Frontend 로컬 실행](#frontend-로컬-실행)
5. [Hybrid 모드](#hybrid-모드)
6. [문제 해결](#문제-해결)

---

## 개요

로컬 개발 환경은 3가지 방식으로 구성할 수 있습니다:

| 방식 | Backend | Frontend | Database | 장점 | 단점 |
|------|---------|----------|----------|------|------|
| **Full Docker** | Docker | Docker | Docker | 간단, 일관성 | 빌드 시간, 리소스 |
| **Hybrid** | 로컬 | 로컬 | Docker | 빠른 개발 | DB 의존성 |
| **Full Local** | 로컬 | 로컬 | 로컬 | 완전 제어 | 복잡한 설정 |

**권장**: Hybrid 모드 (DB만 Docker, Backend/Frontend 로컬)

---

## 환경 설정

### 1. 필수 도구 설치

#### Python 3.11+
```bash
# 버전 확인
python --version  # 3.11 이상이어야 함

# venv 모듈 확인
python -m venv --help
```

#### Node.js 20+
```bash
# 버전 확인
node --version  # v20 이상
npm --version
```

#### Docker (DB용)
```bash
# Docker 설치 확인
docker --version
docker-compose --version
```

---

## Backend 로컬 실행

### 1. Python 가상 환경 생성

```bash
cd backend

# 가상 환경 생성
python -m venv venv

# 활성화
source venv/bin/activate  # Mac/Linux
# 또는
venv\Scripts\activate  # Windows
```

### 2. 의존성 설치

```bash
# pip 업그레이드
pip install --upgrade pip

# 의존성 설치
pip install -r requirements.txt

# 설치 확인
pip list | grep fastapi
```

### 3. 환경 변수 설정

```bash
# .env 파일 생성
cp ../.env.example .env

# .env 파일 편집 (필수 항목)
# - ANTHROPIC_API_KEY=sk-ant-api03-...
# - DATABASE_URL=postgresql://triflow:triflow_dev_password@localhost:5432/triflow_ai
# - REDIS_URL=redis://:triflow_redis_password@localhost:6379/0
```

### 4. 데이터베이스 마이그레이션

```bash
# DB가 실행 중이어야 함 (Docker 또는 로컬)
docker-compose up -d postgres redis

# 마이그레이션 실행
alembic upgrade head

# 확인
alembic current
```

### 5. 서버 실행

```bash
# 개발 모드 (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 또는 포트 변경
uvicorn app.main:app --reload --port 8001
```

### 6. 서버 확인

```bash
# Health check
curl http://localhost:8000/health

# Swagger UI
open http://localhost:8000/docs  # Mac
start http://localhost:8000/docs  # Windows
```

---

## Frontend 로컬 실행

### 1. 의존성 설치

```bash
cd frontend

# 의존성 설치
npm install

# 설치 확인
npm list react
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
echo "VITE_API_URL=http://localhost:8000" > .env

# 또는 수동 편집
# VITE_API_URL=http://localhost:8000
```

### 3. 개발 서버 실행

#### Vite Dev Server (웹 브라우저)

```bash
npm run dev
```

접속: http://localhost:5173

#### Tauri Desktop App

```bash
npm run tauri dev
```

Desktop 앱이 자동으로 열림

### 4. 빌드 (배포용)

```bash
# 웹 빌드
npm run build

# Tauri 빌드
npm run tauri build
```

---

## Hybrid 모드 (권장)

DB와 Redis만 Docker로 실행하고 Backend/Frontend는 로컬로 실행합니다.

### 1. Docker로 DB 실행

```bash
# 루트 디렉토리에서
docker-compose up -d postgres redis

# 상태 확인
docker-compose ps
```

### 2. Backend 로컬 실행

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate

# .env 확인 (DATABASE_URL이 localhost:5432를 가리켜야 함)
cat .env | grep DATABASE_URL

# 서버 실행
uvicorn app.main:app --reload
```

### 3. Frontend 로컬 실행

```bash
# 별도 터미널
cd frontend
npm run dev
```

### 4. 모든 서비스 확인

- Backend: http://localhost:8000/docs
- Frontend: http://localhost:5173
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

## 개발 워크플로우

### 코드 변경 시

#### Backend 변경
```bash
# Python 코드 자동 reload됨 (uvicorn --reload)
# 새 의존성 추가 시:
pip install <package>
pip freeze > requirements.txt
```

#### Frontend 변경
```bash
# Vite/Tauri 자동 reload됨
# 새 의존성 추가 시:
npm install <package>
```

#### DB 스키마 변경
```bash
cd backend

# 마이그레이션 파일 생성
alembic revision --autogenerate -m "Add new table"

# 마이그레이션 적용
alembic upgrade head
```

### 디버깅

#### Backend 디버깅
```python
# 코드에 추가
import pdb; pdb.set_trace()

# 또는 print 디버깅
print(f"DEBUG: variable = {variable}")
```

#### Frontend 디버깅
```typescript
// 브라우저 DevTools 사용
console.log('DEBUG:', variable);

// React DevTools 설치 권장
```

---

## 문제 해결

### "ModuleNotFoundError" 오류

```bash
# 가상 환경 확인
which python  # venv 경로여야 함

# 의존성 재설치
pip install -r requirements.txt
```

### "Connection refused" 오류

```bash
# DB 실행 확인
docker-compose ps postgres

# DB 로그 확인
docker-compose logs postgres

# 연결 테스트
psql postgresql://triflow:triflow_dev_password@localhost:5432/triflow_ai
```

### "CORS" 오류

```bash
# backend/.env에서 CORS_ORIGINS 확인
# Frontend URL이 포함되어야 함
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Port 충돌

```bash
# 다른 포트 사용
uvicorn app.main:app --reload --port 8001  # Backend
npm run dev -- --port 5174  # Frontend
```

---

## 성능 최적화

### Backend

```bash
# 프로덕션 모드 (Gunicorn)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker

# 프로파일링
pip install py-spy
py-spy record -o profile.svg -- python -m uvicorn app.main:app
```

### Frontend

```bash
# 빌드 분석
npm run build -- --mode analyze

# 프로덕션 미리보기
npm run preview
```

---

## 관련 문서

- [DEPLOYMENT.md](DEPLOYMENT.md) - 프로덕션 배포 가이드
- [TESTING.md](TESTING.md) - 테스트 가이드
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - 문제 해결 가이드
- [WINDOWS_SETUP.md](WINDOWS_SETUP.md) - Windows 사용자 가이드
