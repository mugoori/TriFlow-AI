# 한국바이오팜 AI 배합비 추천 시스템

React + FastAPI 기반의 건강기능식품 배합비 추천 시스템입니다.

## 시스템 구조

```
한국바이오팜_React/
├── backend/                 # FastAPI Backend
│   ├── config/             # 설정 파일
│   ├── models/             # Pydantic 스키마
│   ├── routers/            # API 엔드포인트
│   ├── services/           # 비즈니스 로직
│   └── main.py             # 앱 진입점
├── frontend/               # React Frontend
│   ├── src/
│   │   ├── components/     # UI 컴포넌트
│   │   ├── services/       # API 클라이언트
│   │   ├── store/          # Zustand 상태관리
│   │   └── types/          # TypeScript 타입
│   └── index.html
└── start.bat               # 통합 실행 스크립트
```

## 기능

1. **제품 정보 입력**: 제품명, 제형, 목표 원가, 원료 요구사항 입력
2. **유사 제품 검색**: 내부 DB + 공공 API(식품안전나라) 검색
3. **프롬프트 생성**: Claude Desktop용 최적화 프롬프트 자동 생성
4. **결과 기록**: 선택한 배합비 옵션 및 피드백 저장

## 설치 및 실행

### 사전 요구사항
- Python 3.10+
- Node.js 18+
- npm 또는 yarn

### Backend 설정

```bash
cd backend
pip install -r requirements.txt
```

### Frontend 설정

```bash
cd frontend
npm install
```

### 실행

Windows에서 `start.bat`를 더블클릭하거나:

```bash
# Backend
cd backend
uvicorn main:app --reload --port 8000

# Frontend (새 터미널)
cd frontend
npm run dev
```

## API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/recipes` | GET | 레시피 목록 조회 |
| `/api/recipes/{id}` | GET | 레시피 상세 조회 |
| `/api/recipes/formulation-types` | GET | 제형 타입 목록 |
| `/api/ingredients/materials` | GET | 원료 목록 |
| `/api/ingredients/search` | POST | 원료로 레시피 검색 |
| `/api/search` | GET | 통합 검색 (내부+API) |
| `/api/prompt/generate` | POST | 프롬프트 생성 |
| `/api/feedback` | POST | 피드백 저장 |

## Claude Desktop 연동

1. Claude Desktop에서 SQL MCP 연결
2. 생성된 프롬프트를 Claude Desktop에 붙여넣기
3. Claude가 내부 DB를 검색하여 3가지 배합비 옵션 제안

### 출력 형식

각 배합비 옵션은 다음을 포함:
- 배합비 상세 (원료명, 배합비율)
- 예상 원가
- 제조 주의사항
- 예상 품질 평가

## 공공 API

- **식품안전나라**: 품목제조보고(C003) - 유사 제품 원료 조합, 소비기한 정보
- **공공데이터포털**: 건강기능식품정보 - 기능성 원료 정보 (승인 대기중)

## 라이선스

솔루션트리 © 2024
