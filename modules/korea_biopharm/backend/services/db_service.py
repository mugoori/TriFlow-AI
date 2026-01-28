"""
Korea Biopharm Database Service - PostgreSQL Version
SQLite에서 PostgreSQL로 마이그레이션됨
"""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, func
from uuid import UUID

logger = logging.getLogger(__name__)


def get_all_recipes(
    db: Session,
    tenant_id: UUID,
    page: int = 1,
    page_size: int = 20,
    formulation_type: Optional[str] = None
) -> Dict[str, Any]:
    """Get all recipe metadata with pagination."""

    # Build query
    query = text("""
        SELECT id, filename, product_name, company_name, formulation_type,
               created_date, ingredient_count
        FROM korea_biopharm.recipe_metadata
        WHERE tenant_id = :tenant_id
        """ + (" AND formulation_type = :formulation_type" if formulation_type else "") + """
        ORDER BY created_date DESC
        LIMIT :page_size OFFSET :offset
    """)

    count_query = text("""
        SELECT COUNT(*)
        FROM korea_biopharm.recipe_metadata
        WHERE tenant_id = :tenant_id
        """ + (" AND formulation_type = :formulation_type" if formulation_type else ""))

    params = {
        'tenant_id': str(tenant_id),
        'page_size': page_size,
        'offset': (page - 1) * page_size
    }
    if formulation_type:
        params['formulation_type'] = formulation_type

    # Execute
    rows = db.execute(query, params).fetchall()
    total_count = db.execute(count_query, params).scalar()

    return {
        "products": [dict(row._mapping) for row in rows],
        "total_count": total_count,
        "page": page,
        "page_size": page_size
    }


def get_recipe_detail(db: Session, tenant_id: UUID, filename: str) -> Optional[Dict[str, Any]]:
    """Get detailed recipe information including ingredients."""

    # Get metadata
    metadata_query = text("""
        SELECT id, filename, product_name, company_name, formulation_type,
               created_date, ingredient_count
        FROM korea_biopharm.recipe_metadata
        WHERE tenant_id = :tenant_id AND filename = :filename
    """)

    metadata = db.execute(
        metadata_query,
        {'tenant_id': str(tenant_id), 'filename': filename}
    ).fetchone()

    if not metadata:
        return None

    # Get ingredients
    ingredients_query = text("""
        SELECT ingredient, ratio
        FROM korea_biopharm.historical_recipes
        WHERE tenant_id = :tenant_id AND filename = :filename
        ORDER BY ratio DESC
    """)

    ingredients = db.execute(
        ingredients_query,
        {'tenant_id': str(tenant_id), 'filename': filename}
    ).fetchall()

    return {
        "metadata": dict(metadata._mapping),
        "ingredients": [dict(row._mapping) for row in ingredients]
    }


def get_recipe_detail_by_id(db: Session, tenant_id: UUID, recipe_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed recipe information by ID."""

    # Get metadata by ID
    metadata_query = text("""
        SELECT id, filename, product_name, company_name, formulation_type,
               created_date, ingredient_count
        FROM korea_biopharm.recipe_metadata
        WHERE tenant_id = :tenant_id AND id = :recipe_id
    """)

    metadata = db.execute(
        metadata_query,
        {'tenant_id': str(tenant_id), 'recipe_id': recipe_id}
    ).fetchone()

    if not metadata:
        return None

    metadata_dict = dict(metadata._mapping)
    filename = metadata_dict.get('filename')

    # Get ingredients
    ingredients_query = text("""
        SELECT ingredient as ingredient_name,
               ratio,
               CASE WHEN ratio > 0 THEN ratio * 10 ELSE NULL END as amount
        FROM korea_biopharm.historical_recipes
        WHERE tenant_id = :tenant_id AND filename = :filename
        ORDER BY ratio DESC
    """)

    ingredients = db.execute(
        ingredients_query,
        {'tenant_id': str(tenant_id), 'filename': filename}
    ).fetchall()

    return {
        "metadata": metadata_dict,
        "details": [dict(row._mapping) for row in ingredients]
    }


def search_recipes(
    db: Session,
    tenant_id: UUID,
    query: str,
    formulation_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Dict[str, Any]:
    """Search recipes by product name, company name, or ingredient."""

    # Build query
    search_query = text("""
        SELECT id, filename, product_name, company_name, formulation_type,
               created_date, ingredient_count
        FROM korea_biopharm.recipe_metadata
        WHERE tenant_id = :tenant_id
          AND (product_name ILIKE :search OR company_name ILIKE :search)
        """ + (" AND formulation_type = :formulation_type" if formulation_type else "") + """
        ORDER BY created_date DESC
        LIMIT :page_size OFFSET :offset
    """)

    count_query = text("""
        SELECT COUNT(*)
        FROM korea_biopharm.recipe_metadata
        WHERE tenant_id = :tenant_id
          AND (product_name ILIKE :search OR company_name ILIKE :search)
        """ + (" AND formulation_type = :formulation_type" if formulation_type else ""))

    params = {
        'tenant_id': str(tenant_id),
        'search': f'%{query}%',
        'page_size': page_size,
        'offset': (page - 1) * page_size
    }
    if formulation_type:
        params['formulation_type'] = formulation_type

    rows = db.execute(search_query, params).fetchall()
    total_count = db.execute(count_query, params).scalar()

    return {
        "products": [dict(row._mapping) for row in rows],
        "total_count": total_count,
        "page": page,
        "page_size": page_size
    }


def search_by_ingredients(
    db: Session,
    tenant_id: UUID,
    ingredients: List[str],
    formulation_type: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Search recipes that contain specific ingredients."""

    # Build ingredient search conditions
    ingredient_conditions = " OR ".join(["hr.ingredient ILIKE :ing" + str(i) for i in range(len(ingredients))])

    query_text = f"""
        SELECT DISTINCT rm.*, COUNT(DISTINCT hr.ingredient) as match_count
        FROM korea_biopharm.recipe_metadata rm
        JOIN korea_biopharm.historical_recipes hr ON rm.filename = hr.filename AND rm.tenant_id = hr.tenant_id
        WHERE rm.tenant_id = :tenant_id AND ({ingredient_conditions})
    """

    params = {'tenant_id': str(tenant_id)}
    for i, ing in enumerate(ingredients):
        params[f'ing{i}'] = f'%{ing}%'

    if formulation_type:
        query_text += " AND rm.formulation_type = :formulation_type"
        params['formulation_type'] = formulation_type

    query_text += """
        GROUP BY rm.id, rm.filename, rm.product_name, rm.company_name, rm.formulation_type,
                 rm.created_date, rm.ingredient_count, rm.tenant_id, rm.created_at, rm.updated_at
        ORDER BY match_count DESC, rm.created_date DESC
        LIMIT :limit
    """
    params['limit'] = limit

    rows = db.execute(text(query_text), params).fetchall()
    return [dict(row._mapping) for row in rows]


def get_formulation_types(db: Session, tenant_id: UUID) -> List[Dict[str, Any]]:
    """Get all formulation types with counts."""

    query = text("""
        SELECT formulation_type, COUNT(*) as count
        FROM korea_biopharm.recipe_metadata
        WHERE tenant_id = :tenant_id
          AND formulation_type IS NOT NULL
          AND formulation_type != ''
        GROUP BY formulation_type
        ORDER BY count DESC
    """)

    rows = db.execute(query, {'tenant_id': str(tenant_id)}).fetchall()
    return [dict(row._mapping) for row in rows]


def get_materials(db: Session, tenant_id: UUID) -> List[str]:
    """Get all unique ingredients/materials."""

    query = text("""
        SELECT DISTINCT ingredient
        FROM korea_biopharm.historical_recipes
        WHERE tenant_id = :tenant_id
          AND ingredient IS NOT NULL
        ORDER BY ingredient
    """)

    rows = db.execute(query, {'tenant_id': str(tenant_id)}).fetchall()
    return [row[0] for row in rows]


def search_materials(db: Session, tenant_id: UUID, query_str: str) -> List[str]:
    """Search materials by query string."""

    query = text("""
        SELECT DISTINCT ingredient
        FROM korea_biopharm.historical_recipes
        WHERE tenant_id = :tenant_id
          AND ingredient IS NOT NULL
          AND ingredient ILIKE :search
        ORDER BY ingredient
        LIMIT 50
    """)

    rows = db.execute(
        query,
        {'tenant_id': str(tenant_id), 'search': f'%{query_str}%'}
    ).fetchall()

    return [row[0] for row in rows]


# ===================================
# AI 생성 레시피 관련 함수
# ===================================

def create_ai_recipe(
    db: Session,
    tenant_id: UUID,
    user_id: Optional[UUID],
    recipe_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a new AI-generated recipe."""
    import json

    query = text("""
        INSERT INTO korea_biopharm.ai_generated_recipes (
            tenant_id, product_name, formulation_type, option_type, title,
            ingredients, total_ratio, estimated_cost, notes, quality, summary,
            source_type, source_reference, external_id, created_by
        ) VALUES (
            :tenant_id, :product_name, :formulation_type, :option_type, :title,
            CAST(:ingredients AS jsonb), :total_ratio, :estimated_cost, :notes, :quality, :summary,
            :source_type, :source_reference, :external_id, :created_by
        )
        RETURNING recipe_id, tenant_id, product_name, formulation_type, option_type,
                  title, ingredients, total_ratio, estimated_cost, notes, quality, summary,
                  source_type, source_reference, external_id, status, version,
                  created_at, updated_at
    """)

    params = {
        'tenant_id': str(tenant_id),
        'product_name': recipe_data.get('product_name'),
        'formulation_type': recipe_data.get('formulation_type'),
        'option_type': recipe_data.get('option_type'),
        'title': recipe_data.get('title'),
        'ingredients': json.dumps(recipe_data.get('ingredients', []), ensure_ascii=False),
        'total_ratio': recipe_data.get('total_ratio'),
        'estimated_cost': recipe_data.get('estimated_cost'),
        'notes': recipe_data.get('notes'),
        'quality': recipe_data.get('quality'),
        'summary': recipe_data.get('summary'),
        'source_type': recipe_data.get('source_type', 'ai_generated'),
        'source_reference': recipe_data.get('source_reference'),
        'external_id': recipe_data.get('external_id'),
        'created_by': str(user_id) if user_id else None
    }

    try:
        logger.info(f"[AI Recipe Create] Attempting insert for tenant {tenant_id}")
        result = db.execute(query, params).fetchone()
        db.commit()
        logger.info(f"[AI Recipe Create] Success: {result._mapping.get('recipe_id') if result else 'No result'}")
        return dict(result._mapping)
    except Exception as e:
        logger.exception(f"[AI Recipe Create] Error: {e}, params: {params}")
        db.rollback()
        raise


def get_ai_recipe_by_id(db: Session, tenant_id: UUID, recipe_id: str) -> Optional[Dict[str, Any]]:
    """Get AI-generated recipe by ID."""

    query = text("""
        SELECT recipe_id, tenant_id, product_name, formulation_type, option_type,
               title, ingredients, total_ratio, estimated_cost, notes, quality, summary,
               source_type, source_reference, external_id, status, version,
               parent_recipe_id, created_by, approved_by, approved_at,
               created_at, updated_at
        FROM korea_biopharm.ai_generated_recipes
        WHERE tenant_id = :tenant_id AND recipe_id = :recipe_id
    """)

    result = db.execute(query, {'tenant_id': str(tenant_id), 'recipe_id': recipe_id}).fetchone()
    if not result:
        return None

    return dict(result._mapping)


def get_ai_recipes(
    db: Session,
    tenant_id: UUID,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    source_type: Optional[str] = None
) -> Dict[str, Any]:
    """Get AI-generated recipes with pagination."""

    filters = ["tenant_id = :tenant_id"]
    params = {'tenant_id': str(tenant_id), 'page_size': page_size, 'offset': (page - 1) * page_size}

    if status:
        filters.append("status = :status")
        params['status'] = status
    if source_type:
        filters.append("source_type = :source_type")
        params['source_type'] = source_type

    where_clause = " AND ".join(filters)

    query = text(f"""
        SELECT recipe_id, tenant_id, product_name, formulation_type, option_type,
               title, ingredients, total_ratio, estimated_cost, notes, quality, summary,
               source_type, source_reference, external_id, status, version,
               created_at, updated_at
        FROM korea_biopharm.ai_generated_recipes
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT :page_size OFFSET :offset
    """)

    count_query = text(f"""
        SELECT COUNT(*)
        FROM korea_biopharm.ai_generated_recipes
        WHERE {where_clause}
    """)

    rows = db.execute(query, params).fetchall()
    total_count = db.execute(count_query, params).scalar()

    return {
        "recipes": [dict(row._mapping) for row in rows],
        "total_count": total_count,
        "page": page,
        "page_size": page_size
    }


def delete_ai_recipe(db: Session, tenant_id: UUID, recipe_id: str) -> bool:
    """Delete an AI-generated recipe."""

    query = text("""
        DELETE FROM korea_biopharm.ai_generated_recipes
        WHERE tenant_id = :tenant_id AND recipe_id = :recipe_id
        RETURNING recipe_id
    """)

    result = db.execute(query, {'tenant_id': str(tenant_id), 'recipe_id': recipe_id}).fetchone()
    db.commit()

    return result is not None


def update_ai_recipe_status(
    db: Session,
    tenant_id: UUID,
    recipe_id: str,
    status: str,
    approved_by: Optional[UUID] = None
) -> Optional[Dict[str, Any]]:
    """Update AI recipe status."""

    if status == 'approved' and approved_by:
        query = text("""
            UPDATE korea_biopharm.ai_generated_recipes
            SET status = :status, approved_by = :approved_by, approved_at = NOW()
            WHERE tenant_id = :tenant_id AND recipe_id = :recipe_id
            RETURNING recipe_id, status, approved_by, approved_at, updated_at
        """)
        params = {
            'tenant_id': str(tenant_id),
            'recipe_id': recipe_id,
            'status': status,
            'approved_by': str(approved_by)
        }
    else:
        query = text("""
            UPDATE korea_biopharm.ai_generated_recipes
            SET status = :status
            WHERE tenant_id = :tenant_id AND recipe_id = :recipe_id
            RETURNING recipe_id, status, updated_at
        """)
        params = {'tenant_id': str(tenant_id), 'recipe_id': recipe_id, 'status': status}

    result = db.execute(query, params).fetchone()
    db.commit()

    if not result:
        return None
    return dict(result._mapping)


# ===================================
# 통합 레시피 뷰 관련 함수
# ===================================

def get_unified_recipes(
    db: Session,
    tenant_id: UUID,
    page: int = 1,
    page_size: int = 20,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    formulation_type: Optional[str] = None,
    search_query: Optional[str] = None
) -> Dict[str, Any]:
    """Get unified recipes (historical + AI-generated)."""

    filters = ["tenant_id = :tenant_id"]
    params = {'tenant_id': str(tenant_id), 'page_size': page_size, 'offset': (page - 1) * page_size}

    if source_type:
        filters.append("source_type = :source_type")
        params['source_type'] = source_type
    if status:
        filters.append("status = :status")
        params['status'] = status
    if formulation_type:
        filters.append("formulation_type = :formulation_type")
        params['formulation_type'] = formulation_type
    if search_query:
        filters.append("product_name ILIKE :search_query")
        params['search_query'] = f'%{search_query}%'

    where_clause = " AND ".join(filters)

    query = text(f"""
        SELECT recipe_id, tenant_id, product_name, formulation_type, option_type,
               ingredient_count, source_type, source_reference, status, created_at, created_by
        FROM korea_biopharm.unified_recipes
        WHERE {where_clause}
        ORDER BY created_at DESC NULLS LAST
        LIMIT :page_size OFFSET :offset
    """)

    count_query = text(f"""
        SELECT COUNT(*)
        FROM korea_biopharm.unified_recipes
        WHERE {where_clause}
    """)

    rows = db.execute(query, params).fetchall()
    total_count = db.execute(count_query, params).scalar()

    return {
        "recipes": [dict(row._mapping) for row in rows],
        "total_count": total_count,
        "page": page,
        "page_size": page_size
    }


# ===================================
# 피드백 관련 함수
# ===================================

def create_recipe_feedback(
    db: Session,
    tenant_id: UUID,
    recipe_id: str,
    user_id: Optional[UUID],
    feedback_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create feedback for an AI recipe."""

    query = text("""
        INSERT INTO korea_biopharm.recipe_feedback (
            tenant_id, recipe_id, rating, comment, feedback_type, created_by
        ) VALUES (
            :tenant_id, :recipe_id, :rating, :comment, :feedback_type, :created_by
        )
        RETURNING feedback_id, tenant_id, recipe_id, rating, comment, feedback_type, created_at
    """)

    params = {
        'tenant_id': str(tenant_id),
        'recipe_id': recipe_id,
        'rating': feedback_data.get('rating'),
        'comment': feedback_data.get('comment'),
        'feedback_type': feedback_data.get('feedback_type'),
        'created_by': str(user_id) if user_id else None
    }

    result = db.execute(query, params).fetchone()
    db.commit()

    return dict(result._mapping)


def get_recipe_feedback(db: Session, tenant_id: UUID, recipe_id: str) -> List[Dict[str, Any]]:
    """Get all feedback for a recipe."""

    query = text("""
        SELECT feedback_id, recipe_id, rating, comment, feedback_type, created_by, created_at
        FROM korea_biopharm.recipe_feedback
        WHERE tenant_id = :tenant_id AND recipe_id = :recipe_id
        ORDER BY created_at DESC
    """)

    rows = db.execute(query, {'tenant_id': str(tenant_id), 'recipe_id': recipe_id}).fetchall()
    return [dict(row._mapping) for row in rows]
