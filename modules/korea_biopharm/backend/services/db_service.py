"""
Korea Biopharm Database Service - PostgreSQL Version
SQLite에서 PostgreSQL로 마이그레이션됨
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, func
from uuid import UUID


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
