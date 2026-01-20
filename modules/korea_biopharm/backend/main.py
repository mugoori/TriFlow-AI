import sys
import webbrowser
import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ..config.settings import CORS_ORIGINS, STATIC_DIR, SERVER_HOST, SERVER_PORT, IS_FROZEN
from routers import recipes, ingredients, search, prompt, feedback

app = FastAPI(
    title="한국바이오팜 배합비 추천 API",
    description="건강기능식품 배합비 추천 시스템 Backend API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(recipes.router, prefix="/api/recipes", tags=["Recipes"])
app.include_router(ingredients.router, prefix="/api/ingredients", tags=["Ingredients"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(prompt.router, prefix="/api/prompt", tags=["Prompt"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])

# React 정적 파일 서빙 (배포 환경 또는 빌드된 파일이 있을 때)
if STATIC_DIR.exists():
    # 정적 파일 (JS, CSS, assets 등)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # SPA 라우팅: 모든 비-API 경로를 index.html로
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """React SPA를 위한 catch-all 라우트."""
        # API 경로는 제외 (이미 라우터에서 처리됨)
        if full_path.startswith("api/"):
            return {"error": "Not found"}

        # 정적 파일 확인
        static_file = STATIC_DIR / full_path
        if static_file.exists() and static_file.is_file():
            return FileResponse(static_file)

        # 그 외 모든 경로는 index.html 반환 (React Router 지원)
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)

        return {"error": "Frontend not built"}

@app.get("/")
async def root():
    """루트 경로 - React 앱 또는 API 정보 반환."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "한국바이오팜 배합비 추천 API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


def open_browser():
    """서버 시작 후 브라우저 열기."""
    time.sleep(1.5)  # 서버 시작 대기
    webbrowser.open(f"http://{SERVER_HOST}:{SERVER_PORT}")


def main():
    """메인 진입점 - exe 실행 시 사용."""
    import uvicorn

    # 배포 환경에서는 브라우저 자동 열기
    if IS_FROZEN:
        print("=" * 50)
        print("  한국바이오팜 AI 배합비 추천 시스템")
        print("=" * 50)
        print(f"\n서버 시작 중... http://{SERVER_HOST}:{SERVER_PORT}")
        print("브라우저가 자동으로 열립니다.")
        print("\n종료하려면 이 창을 닫으세요.")
        print("-" * 50)

        # 브라우저 열기 (별도 스레드)
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    # 서버 실행
    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="info" if IS_FROZEN else "debug"
    )


if __name__ == "__main__":
    main()
