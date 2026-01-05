#!/usr/bin/env python
"""
Module Definitions and Industry Profiles Seeding Script
테넌트 모듈 및 산업 프로필 초기 데이터 삽입

사용법:
    cd backend
    python scripts/seed_modules.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.database import get_db_context
from app.seeds.modules import MODULE_DEFINITIONS, INDUSTRY_PROFILES


def seed_module_definitions():
    """모듈 정의 마스터 데이터 삽입"""
    print("\n[1/2] 모듈 정의 시딩 시작...")

    with get_db_context() as db:
        # 기존 데이터 확인
        existing = db.execute(
            text("SELECT COUNT(*) FROM core.module_definitions")
        ).scalar()

        if existing > 0:
            print(f"  - 기존 데이터 {existing}개 존재, 스킵합니다.")
            return

        inserted = 0
        for module in MODULE_DEFINITIONS:
            try:
                db.execute(
                    text("""
                        INSERT INTO core.module_definitions
                        (module_code, name, description, category, icon,
                         default_enabled, requires_subscription, depends_on, display_order)
                        VALUES
                        (:module_code, :name, :description, :category, :icon,
                         :default_enabled, :requires_subscription, :depends_on, :display_order)
                        ON CONFLICT (module_code) DO NOTHING
                    """),
                    {
                        "module_code": module["module_code"],
                        "name": module["name"],
                        "description": module.get("description"),
                        "category": module["category"],
                        "icon": module["icon"],
                        "default_enabled": module.get("default_enabled", False),
                        "requires_subscription": module.get("requires_subscription"),
                        "depends_on": module.get("depends_on"),
                        "display_order": module.get("display_order", 0),
                    }
                )
                inserted += 1
                print(f"  + {module['module_code']}: {module['name']}")
            except Exception as e:
                print(f"  ! {module['module_code']} 삽입 실패: {e}")

        db.commit()
        print(f"  => 모듈 정의 {inserted}개 삽입 완료")


def seed_industry_profiles():
    """산업별 프로필 데이터 삽입"""
    print("\n[2/2] 산업 프로필 시딩 시작...")

    with get_db_context() as db:
        # 기존 데이터 확인
        existing = db.execute(
            text("SELECT COUNT(*) FROM core.industry_profiles")
        ).scalar()

        if existing > 0:
            print(f"  - 기존 데이터 {existing}개 존재, 스킵합니다.")
            return

        inserted = 0
        for profile in INDUSTRY_PROFILES:
            try:
                db.execute(
                    text("""
                        INSERT INTO core.industry_profiles
                        (industry_code, name, description, default_modules,
                         default_kpis, sample_rulesets, icon)
                        VALUES
                        (:industry_code, :name, :description, :default_modules,
                         :default_kpis, :sample_rulesets, :icon)
                        ON CONFLICT (industry_code) DO NOTHING
                    """),
                    {
                        "industry_code": profile["industry_code"],
                        "name": profile["name"],
                        "description": profile.get("description"),
                        "default_modules": profile.get("default_modules", []),
                        "default_kpis": profile.get("default_kpis", []),
                        "sample_rulesets": profile.get("sample_rulesets", []),
                        "icon": profile.get("icon"),
                    }
                )
                inserted += 1
                print(f"  + {profile['industry_code']}: {profile['name']}")
            except Exception as e:
                print(f"  ! {profile['industry_code']} 삽입 실패: {e}")

        db.commit()
        print(f"  => 산업 프로필 {inserted}개 삽입 완료")


def verify_seeding():
    """시딩 결과 검증"""
    print("\n[검증] 시딩 결과 확인...")

    with get_db_context() as db:
        # 모듈 정의 확인
        modules = db.execute(
            text("""
                SELECT module_code, name, category, default_enabled
                FROM core.module_definitions
                ORDER BY display_order
            """)
        ).fetchall()

        print(f"\n  모듈 정의 ({len(modules)}개):")
        for m in modules:
            status = "✓" if m[3] else "○"
            print(f"    [{status}] {m[0]}: {m[1]} ({m[2]})")

        # 산업 프로필 확인
        profiles = db.execute(
            text("""
                SELECT industry_code, name, array_length(default_modules, 1) as module_count
                FROM core.industry_profiles
                ORDER BY industry_code
            """)
        ).fetchall()

        print(f"\n  산업 프로필 ({len(profiles)}개):")
        for p in profiles:
            print(f"    - {p[0]}: {p[1]} (기본 모듈 {p[2] or 0}개)")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("TriFlow AI - Module & Industry Profile Seeding")
    print("=" * 60)

    try:
        seed_module_definitions()
        seed_industry_profiles()
        verify_seeding()

        print("\n" + "=" * 60)
        print("시딩 완료!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] 시딩 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
