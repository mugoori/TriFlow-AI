"""
TriFlow AI - RAG (문서/지식베이스) API 라우터
==============================================
문서 업로드, 검색, 관리 엔드포인트

스키마 버전: Migration 012 (B-3-3 스펙)
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.models.core import User
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG - Knowledge Base"])


# ===========================================
# Schemas (Migration 012 스키마 기준)
# ===========================================

class DocumentCreate(BaseModel):
    """문서 생성 요청 (새 스키마)"""
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    source_type: str = Field(
        default="manual",
        description="manual, sop, wiki, faq, judgment_log, feedback, external_doc"
    )
    source_id: Optional[str] = Field(None, description="소스 식별자 (예: SOP-001)")
    section: Optional[str] = Field(None, description="문서 섹션")
    metadata: Optional[dict] = None
    tags: Optional[List[str]] = Field(default=[], description="문서 태그")


class DocumentResponse(BaseModel):
    """문서 응답"""
    document_id: str
    title: str
    source_type: str
    source_id: Optional[str] = None
    created_at: Optional[str] = None
    chunk_count: int = 0
    tags: List[str] = []


class SearchRequest(BaseModel):
    """검색 요청"""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    source_type: Optional[str] = Field(None, description="소스 타입 필터")


class SearchResult(BaseModel):
    """검색 결과 항목 (새 스키마)"""
    document_id: str
    title: str
    source_type: str
    source_id: Optional[str] = None
    section: Optional[str] = None
    text: str  # chunk_text → text
    chunk_index: int
    similarity: float
    tags: List[str] = []


class SearchResponse(BaseModel):
    """검색 응답"""
    success: bool
    query: str
    results: List[SearchResult]
    count: int


# ===========================================
# Endpoints
# ===========================================

@router.post("/documents", response_model=dict, summary="문서 추가")
async def add_document(
    document: DocumentCreate,
    current_user: User = Depends(get_current_user),
):
    """
    새 문서를 RAG 시스템에 추가합니다. (Migration 012 스키마)
    - 문서는 자동으로 청크로 분할됩니다.
    - 각 청크는 벡터 임베딩으로 변환되어 저장됩니다.
    - source_type: manual, sop, wiki, faq, judgment_log, feedback, external_doc
    """
    logger.info(f"RAG add_document request: title={document.title}, tenant_id={current_user.tenant_id}")
    try:
        rag_service = get_rag_service()
        result = await rag_service.add_document(
            tenant_id=current_user.tenant_id,
            title=document.title,
            content=document.content,
            source_type=document.source_type,
            source_id=document.source_id,
            section=document.section,
            metadata=document.metadata,
            tags=document.tags,
        )
        logger.info(f"RAG add_document result: {result}")

        if not result["success"]:
            logger.error(f"RAG add_document failed: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to add document"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"RAG add_document exception: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/upload", response_model=dict, summary="파일 업로드")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source_type: str = Form("manual"),
    source_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """
    파일을 업로드하여 RAG 시스템에 추가합니다.
    지원 형식: .txt, .md, .pdf (PDF는 텍스트 추출)
    """
    # 파일 읽기
    content = await file.read()

    # 파일 타입에 따른 처리
    filename = file.filename or "unknown.txt"

    if filename.endswith(".pdf"):
        # PDF 텍스트 추출 (간단한 구현)
        try:
            # PyMuPDF 또는 pdfplumber 사용
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(stream=content, filetype="pdf")
                text_content = ""
                for page in doc:
                    text_content += page.get_text()
                doc.close()
            except ImportError:
                raise HTTPException(
                    status_code=400,
                    detail="PDF processing requires PyMuPDF (fitz). Install with: pip install pymupdf"
                )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    else:
        # 텍스트 파일
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            text_content = content.decode("cp949", errors="ignore")

    # 문서 추가
    rag_service = get_rag_service()
    result = await rag_service.add_document(
        tenant_id=current_user.tenant_id,
        title=title or filename,
        content=text_content,
        source_type=source_type,
        source_id=source_id or f"upload://{filename}",
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to add document"))

    return result


@router.post("/search", response_model=SearchResponse, summary="문서 검색")
async def search_documents(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    RAG 시스템에서 유사한 문서 청크를 검색합니다.
    - 쿼리와 유사한 문서 청크를 벡터 유사도로 검색
    - top_k: 반환할 최대 결과 수
    - similarity_threshold: 최소 유사도 (0~1)
    """
    rag_service = get_rag_service()
    result = await rag_service.search(
        tenant_id=current_user.tenant_id,
        query=request.query,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
    )

    return SearchResponse(
        success=result["success"],
        query=result["query"],
        results=[SearchResult(**r) for r in result.get("results", [])],
        count=result.get("count", 0),
    )


@router.get("/documents", response_model=dict, summary="문서 목록")
async def list_documents(
    source_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    """
    RAG 시스템의 문서 목록을 조회합니다.
    source_type 필터: manual, sop, wiki, faq, judgment_log, feedback, external_doc
    """
    rag_service = get_rag_service()
    result = await rag_service.list_documents(
        tenant_id=current_user.tenant_id,
        source_type=source_type,
        limit=limit,
        offset=offset,
    )

    return result


@router.get("/documents/{document_id}", response_model=dict, summary="문서 상세 조회")
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    RAG 시스템에서 문서의 상세 내용을 조회합니다.
    - document_id는 parent_document_id (source_id)입니다.
    - 모든 청크의 내용을 병합하여 반환합니다.
    """
    rag_service = get_rag_service()
    result = await rag_service.get_document(
        tenant_id=current_user.tenant_id,
        document_id=document_id,
    )

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Document not found"))

    return result


@router.delete("/documents/{document_id}", response_model=dict, summary="문서 삭제")
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """
    RAG 시스템에서 문서를 삭제합니다.
    - 관련 임베딩도 함께 삭제됩니다.
    """
    rag_service = get_rag_service()
    result = await rag_service.delete_document(
        tenant_id=current_user.tenant_id,
        document_id=document_id,
    )

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Document not found"))

    return result


@router.get("/context", response_model=dict, summary="컨텍스트 생성")
async def get_context(
    query: str,
    max_tokens: int = 2000,
    top_k: int = 5,
    current_user: User = Depends(get_current_user),
):
    """
    쿼리에 대한 RAG 컨텍스트를 생성합니다.
    - 에이전트가 사용할 수 있는 형태로 검색 결과를 조합
    """
    rag_service = get_rag_service()
    context = await rag_service.get_context(
        tenant_id=current_user.tenant_id,
        query=query,
        max_tokens=max_tokens,
        top_k=top_k,
    )

    return {
        "success": True,
        "query": query,
        "context": context,
        "context_length": len(context),
    }
