import sqlite3
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from ..config.settings import DB_PATH

@contextmanager
def get_db_connection():
    """Database connection context manager."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def get_all_recipes(
    page: int = 1,
    page_size: int = 20,
    formulation_type: Optional[str] = None
) -> Dict[str, Any]:
    """Get all recipe metadata with pagination."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Build query
        where_clause = ""
        params = []
        if formulation_type:
            where_clause = "WHERE formulation_type = ?"
            params.append(formulation_type)

        # Get total count
        count_query = f"SELECT COUNT(*) FROM recipe_metadata {where_clause}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Get paginated results
        offset = (page - 1) * page_size
        query = f"""
            SELECT * FROM recipe_metadata
            {where_clause}
            ORDER BY created_date DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [page_size, offset])
        rows = cursor.fetchall()

        return {
            "products": [dict(row) for row in rows],
            "total_count": total_count,
            "page": page,
            "page_size": page_size
        }

def get_recipe_detail(filename: str) -> Optional[Dict[str, Any]]:
    """Get detailed recipe information including ingredients."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get metadata
        cursor.execute("SELECT * FROM recipe_metadata WHERE filename = ?", (filename,))
        metadata = cursor.fetchone()
        if not metadata:
            return None

        # Get ingredients
        cursor.execute("""
            SELECT ingredient, ratio
            FROM historical_recipes
            WHERE filename = ?
            ORDER BY ratio DESC
        """, (filename,))
        ingredients = cursor.fetchall()

        return {
            "metadata": dict(metadata),
            "ingredients": [dict(row) for row in ingredients]
        }

def get_recipe_detail_by_id(recipe_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed recipe information by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get metadata by ID
        cursor.execute("SELECT * FROM recipe_metadata WHERE id = ?", (recipe_id,))
        metadata = cursor.fetchone()
        if not metadata:
            return None

        metadata_dict = dict(metadata)
        filename = metadata_dict.get('filename')

        # Get ingredients (배합비 상세)
        cursor.execute("""
            SELECT ingredient as ingredient_name, ratio,
                   CASE WHEN ratio > 0 THEN ratio * 10 ELSE NULL END as amount
            FROM historical_recipes
            WHERE filename = ?
            ORDER BY ratio DESC
        """, (filename,))
        ingredients = cursor.fetchall()

        return {
            "metadata": metadata_dict,
            "details": [dict(row) for row in ingredients]
        }

def search_recipes(
    query: str,
    formulation_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Dict[str, Any]:
    """Search recipes by product name, company name, or ingredient."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Build query
        where_clauses = ["(product_name LIKE ? OR company_name LIKE ?)"]
        params = [f"%{query}%", f"%{query}%"]

        if formulation_type:
            where_clauses.append("formulation_type = ?")
            params.append(formulation_type)

        where_str = " AND ".join(where_clauses)

        # Get total count
        count_query = f"SELECT COUNT(*) FROM recipe_metadata WHERE {where_str}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Get paginated results
        offset = (page - 1) * page_size
        query_sql = f"""
            SELECT * FROM recipe_metadata
            WHERE {where_str}
            ORDER BY created_date DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query_sql, params + [page_size, offset])
        rows = cursor.fetchall()

        return {
            "products": [dict(row) for row in rows],
            "total_count": total_count,
            "page": page,
            "page_size": page_size
        }

def search_by_ingredients(
    ingredients: List[str],
    formulation_type: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Search recipes that contain specific ingredients."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Build ingredient search conditions
        ingredient_conditions = " OR ".join(["hr.ingredient LIKE ?" for _ in ingredients])
        params = [f"%{ing}%" for ing in ingredients]

        query = f"""
            SELECT DISTINCT rm.*, COUNT(DISTINCT hr.ingredient) as match_count
            FROM recipe_metadata rm
            JOIN historical_recipes hr ON rm.filename = hr.filename
            WHERE ({ingredient_conditions})
        """

        if formulation_type:
            query += " AND rm.formulation_type = ?"
            params.append(formulation_type)

        query += """
            GROUP BY rm.filename
            ORDER BY match_count DESC, rm.created_date DESC
            LIMIT ?
        """
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

def get_formulation_types() -> List[Dict[str, Any]]:
    """Get all formulation types with counts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT formulation_type, COUNT(*) as count
            FROM recipe_metadata
            WHERE formulation_type IS NOT NULL AND formulation_type != ''
            GROUP BY formulation_type
            ORDER BY count DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_materials() -> List[str]:
    """Get all unique ingredients/materials."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT ingredient
            FROM historical_recipes
            WHERE ingredient IS NOT NULL
            ORDER BY ingredient
        """)
        rows = cursor.fetchall()
        return [row['ingredient'] for row in rows]


def execute_query(query: str, params: tuple = ()) -> None:
    """Execute a write query (INSERT, UPDATE, DELETE)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()


def fetch_all(query: str, params: tuple = ()) -> List[tuple]:
    """Fetch all rows from a query."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
