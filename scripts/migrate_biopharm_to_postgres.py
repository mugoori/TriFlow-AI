"""
SQLite 한국바이오팜 데이터를 PostgreSQL로 마이그레이션

사용법:
    python scripts/migrate_biopharm_to_postgres.py --tenant-id <tenant_id>
"""
import sqlite3
import sys
from pathlib import Path
from uuid import UUID
import argparse

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings


def migrate_data(tenant_id: str, dry_run: bool = False):
    """SQLite 데이터를 PostgreSQL로 마이그레이션"""

    # SQLite DB 경로
    sqlite_db = project_root / "modules" / "korea_biopharm" / "backend" / "Data" / "formulation.db"

    if not sqlite_db.exists():
        print(f"[ERROR] SQLite DB not found: {sqlite_db}")
        return False

    print(f"[DB] SQLite DB: {sqlite_db}")
    print(f"[TENANT] Target tenant_id: {tenant_id}")
    print(f"[MODE] Dry run: {dry_run}")
    print()

    # SQLite 연결
    sqlite_conn = sqlite3.connect(str(sqlite_db))
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # PostgreSQL 연결
    pg_engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=pg_engine)
    pg_session = SessionLocal()

    try:
        # 1. recipe_metadata 마이그레이션
        print("[STEP] Step 1: Migrating recipe_metadata...")
        sqlite_cursor.execute("SELECT * FROM recipe_metadata")
        metadata_rows = sqlite_cursor.fetchall()
        print(f"   Found {len(metadata_rows)} recipes")

        if not dry_run:
            for row in metadata_rows:
                pg_session.execute(
                    text("""
                        INSERT INTO korea_biopharm.recipe_metadata
                        (tenant_id, filename, product_name, company_name, formulation_type, created_date, ingredient_count)
                        VALUES (:tenant_id, :filename, :product_name, :company_name, :formulation_type, :created_date, :ingredient_count)
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        'tenant_id': tenant_id,
                        'filename': row['filename'],
                        'product_name': row['product_name'],
                        'company_name': row['company_name'],
                        'formulation_type': row['formulation_type'],
                        'created_date': row['created_date'],
                        'ingredient_count': row['ingredient_count']
                    }
                )
            pg_session.commit()
            print(f"   [OK] Migrated {len(metadata_rows)} recipes")
        else:
            print(f"   (DRY RUN) Would migrate {len(metadata_rows)} recipes")

        # 2. historical_recipes 마이그레이션
        print()
        print("[STEP] Step 2: Migrating historical_recipes...")
        sqlite_cursor.execute("SELECT * FROM historical_recipes")
        recipe_rows = sqlite_cursor.fetchall()
        print(f"   Found {len(recipe_rows)} recipe details")

        if not dry_run:
            batch_size = 1000
            for i in range(0, len(recipe_rows), batch_size):
                batch = recipe_rows[i:i + batch_size]
                for row in batch:
                    pg_session.execute(
                        text("""
                            INSERT INTO korea_biopharm.historical_recipes
                            (tenant_id, filename, ingredient, ratio)
                            VALUES (:tenant_id, :filename, :ingredient, :ratio)
                        """),
                        {
                            'tenant_id': tenant_id,
                            'filename': row['filename'],
                            'ingredient': row['ingredient'],
                            'ratio': float(row['ratio']) if row['ratio'] else None
                        }
                    )
                pg_session.commit()
                print(f"   Progress: {min(i + batch_size, len(recipe_rows))}/{len(recipe_rows)}")

            print(f"   [OK] Migrated {len(recipe_rows)} recipe details")
        else:
            print(f"   (DRY RUN) Would migrate {len(recipe_rows)} recipe details")

        # 3. 통계 확인
        print()
        print("[SUMMARY] Migration Summary:")
        if not dry_run:
            result = pg_session.execute(
                text("""
                    SELECT
                        (SELECT COUNT(*) FROM korea_biopharm.recipe_metadata WHERE tenant_id = :tenant_id) as metadata_count,
                        (SELECT COUNT(*) FROM korea_biopharm.historical_recipes WHERE tenant_id = :tenant_id) as recipes_count,
                        (SELECT COUNT(DISTINCT ingredient) FROM korea_biopharm.historical_recipes WHERE tenant_id = :tenant_id) as unique_ingredients
                """),
                {'tenant_id': tenant_id}
            ).fetchone()

            print(f"   - Recipe Metadata: {result[0]}")
            print(f"   - Recipe Details: {result[1]}")
            print(f"   - Unique Ingredients: {result[2]}")

        print()
        print("[OK] Migration completed successfully!")
        return True

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        pg_session.rollback()
        return False
    finally:
        sqlite_conn.close()
        pg_session.close()


def main():
    parser = argparse.ArgumentParser(description='Migrate Korea Biopharm data to PostgreSQL')
    parser.add_argument('--tenant-id', required=True, help='Target tenant ID (UUID)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (do not commit)')

    args = parser.parse_args()

    # UUID 유효성 검사
    try:
        UUID(args.tenant_id)
    except ValueError:
        print(f"[ERROR] Invalid tenant_id: {args.tenant_id}")
        print("   Must be a valid UUID")
        sys.exit(1)

    success = migrate_data(args.tenant_id, args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
