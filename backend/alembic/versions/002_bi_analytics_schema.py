# -*- coding: utf-8 -*-
"""002 BI Analytics Schema

Revision ID: 002_bi_analytics
Revises: 001_core_baseline
Create Date: 2025-12-26

BI Analytics Schema (based on B-3-2 spec)
- Create analytics schema
- RAW tables (raw_mes_production, raw_erp_order, raw_inventory, raw_equipment_event)
- Dimension tables (dim_date, dim_line, dim_product, dim_equipment, dim_kpi, dim_shift)
- Fact tables (fact_daily_production, fact_daily_defect, fact_inventory_snapshot, fact_equipment_event, fact_hourly_production)
- BI Catalog (bi_datasets, bi_metrics, bi_dashboards, bi_components)
- ETL Metadata (etl_jobs, etl_job_executions)
- Data Quality (data_quality_rules, data_quality_checks)
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002_bi_analytics'
down_revision: Union[str, None] = '001_core_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # Create Analytics Schema
    # ============================================
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")

    # ============================================
    # 1. RAW Tables (with partition support)
    # ============================================

    # raw_mes_production table (MES production data)
    op.execute("""
        CREATE TABLE analytics.raw_mes_production (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            src_system text NOT NULL DEFAULT 'MES',
            src_table text NOT NULL,
            src_pk text NOT NULL,
            payload jsonb NOT NULL,
            event_time timestamptz NOT NULL,
            ingested_at timestamptz NOT NULL DEFAULT now(),
            processing_status text NOT NULL DEFAULT 'pending'
                CHECK (processing_status IN ('pending','processed','error','duplicate')),
            error_message text,
            metadata jsonb NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX idx_raw_mes_prod_tenant_event ON analytics.raw_mes_production (tenant_id, event_time DESC)")
    op.execute("CREATE INDEX idx_raw_mes_prod_status ON analytics.raw_mes_production (processing_status) WHERE processing_status = 'pending'")
    op.execute("CREATE INDEX idx_raw_mes_prod_src_pk ON analytics.raw_mes_production (src_system, src_table, src_pk)")
    op.execute("CREATE INDEX idx_raw_mes_prod_payload ON analytics.raw_mes_production USING GIN (payload)")
    op.execute("COMMENT ON TABLE analytics.raw_mes_production IS 'MES Production RAW Data'")

    # raw_erp_order table (ERP order data)
    op.execute("""
        CREATE TABLE analytics.raw_erp_order (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            src_system text NOT NULL DEFAULT 'ERP',
            src_table text NOT NULL,
            src_pk text NOT NULL,
            payload jsonb NOT NULL,
            event_time timestamptz NOT NULL,
            ingested_at timestamptz NOT NULL DEFAULT now(),
            processing_status text NOT NULL DEFAULT 'pending'
                CHECK (processing_status IN ('pending','processed','error','duplicate')),
            error_message text,
            metadata jsonb NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX idx_raw_erp_order_tenant_event ON analytics.raw_erp_order (tenant_id, event_time DESC)")
    op.execute("CREATE INDEX idx_raw_erp_order_status ON analytics.raw_erp_order (processing_status) WHERE processing_status = 'pending'")
    op.execute("COMMENT ON TABLE analytics.raw_erp_order IS 'ERP Order/Inventory RAW Data'")

    # raw_inventory table (inventory data)
    op.execute("""
        CREATE TABLE analytics.raw_inventory (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            src_system text NOT NULL,
            src_table text NOT NULL,
            src_pk text NOT NULL,
            payload jsonb NOT NULL,
            event_time timestamptz NOT NULL,
            ingested_at timestamptz NOT NULL DEFAULT now(),
            processing_status text NOT NULL DEFAULT 'pending'
                CHECK (processing_status IN ('pending','processed','error','duplicate')),
            error_message text,
            metadata jsonb NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX idx_raw_inventory_tenant_event ON analytics.raw_inventory (tenant_id, event_time DESC)")
    op.execute("CREATE INDEX idx_raw_inventory_status ON analytics.raw_inventory (processing_status) WHERE processing_status = 'pending'")
    op.execute("COMMENT ON TABLE analytics.raw_inventory IS 'Inventory Status RAW Data'")

    # raw_equipment_event table (equipment events)
    op.execute("""
        CREATE TABLE analytics.raw_equipment_event (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            src_system text NOT NULL,
            src_table text NOT NULL,
            src_pk text NOT NULL,
            payload jsonb NOT NULL,
            event_time timestamptz NOT NULL,
            ingested_at timestamptz NOT NULL DEFAULT now(),
            processing_status text NOT NULL DEFAULT 'pending'
                CHECK (processing_status IN ('pending','processed','error','duplicate')),
            error_message text,
            metadata jsonb NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX idx_raw_equip_event_tenant_event ON analytics.raw_equipment_event (tenant_id, event_time DESC)")
    op.execute("CREATE INDEX idx_raw_equip_event_status ON analytics.raw_equipment_event (processing_status) WHERE processing_status = 'pending'")
    op.execute("COMMENT ON TABLE analytics.raw_equipment_event IS 'Equipment Event RAW Data'")

    # ============================================
    # 2. Dimension Tables
    # ============================================

    # dim_date table (date dimension)
    op.execute("""
        CREATE TABLE analytics.dim_date (
            date date PRIMARY KEY,
            year int NOT NULL,
            quarter int NOT NULL CHECK (quarter BETWEEN 1 AND 4),
            month int NOT NULL CHECK (month BETWEEN 1 AND 12),
            week int NOT NULL CHECK (week BETWEEN 1 AND 53),
            day_of_year int NOT NULL CHECK (day_of_year BETWEEN 1 AND 366),
            day_of_month int NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
            day_of_week int NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
            day_name text NOT NULL,
            is_weekend boolean NOT NULL,
            is_holiday boolean NOT NULL DEFAULT false,
            holiday_name text,
            fiscal_year int,
            fiscal_quarter int,
            fiscal_month int,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_dim_date_year_month ON analytics.dim_date (year, month)")
    op.execute("CREATE INDEX idx_dim_date_is_holiday ON analytics.dim_date (is_holiday) WHERE is_holiday = true")
    op.execute("COMMENT ON TABLE analytics.dim_date IS 'Date Dimension Table (2020-2030)'")

    # dim_date seed data (2020-2030)
    op.execute("""
        INSERT INTO analytics.dim_date (date, year, quarter, month, week, day_of_year, day_of_month, day_of_week, day_name, is_weekend)
        SELECT
            d::date,
            EXTRACT(year FROM d)::int,
            EXTRACT(quarter FROM d)::int,
            EXTRACT(month FROM d)::int,
            EXTRACT(week FROM d)::int,
            EXTRACT(doy FROM d)::int,
            EXTRACT(day FROM d)::int,
            EXTRACT(dow FROM d)::int,
            to_char(d, 'Day'),
            EXTRACT(dow FROM d) IN (0, 6)
        FROM generate_series('2020-01-01'::date, '2030-12-31'::date, '1 day'::interval) d
    """)

    # dim_line table (line dimension)
    op.execute("""
        CREATE TABLE analytics.dim_line (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            line_code text NOT NULL,
            name text NOT NULL,
            category text CHECK (category IN ('assembly','processing','packaging','inspection','warehouse')),
            capacity_per_hour numeric,
            capacity_unit text,
            timezone text NOT NULL DEFAULT 'Asia/Seoul',
            plant_code text,
            department text,
            manager text,
            cost_center text,
            attributes jsonb NOT NULL DEFAULT '{}',
            is_active boolean NOT NULL DEFAULT true,
            activated_at date,
            deactivated_at date,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, line_code)
        )
    """)
    op.execute("CREATE INDEX idx_dim_line_active ON analytics.dim_line (tenant_id, is_active) WHERE is_active = true")
    op.execute("CREATE INDEX idx_dim_line_category ON analytics.dim_line (category)")
    op.execute("COMMENT ON TABLE analytics.dim_line IS 'Production Line Dimension Table'")

    # dim_product table (product dimension)
    op.execute("""
        CREATE TABLE analytics.dim_product (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            product_code text NOT NULL,
            name text NOT NULL,
            name_en text,
            spec text,
            category text,
            subcategory text,
            unit text NOT NULL DEFAULT 'EA',
            standard_cost numeric,
            target_cycle_time_sec numeric,
            quality_standard text,
            attributes jsonb NOT NULL DEFAULT '{}',
            is_active boolean NOT NULL DEFAULT true,
            activated_at date,
            discontinued_at date,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, product_code)
        )
    """)
    op.execute("CREATE INDEX idx_dim_product_active ON analytics.dim_product (tenant_id, is_active) WHERE is_active = true")
    op.execute("CREATE INDEX idx_dim_product_category ON analytics.dim_product (category, subcategory)")
    op.execute("COMMENT ON TABLE analytics.dim_product IS 'Product Dimension Table'")

    # dim_equipment table (equipment dimension)
    op.execute("""
        CREATE TABLE analytics.dim_equipment (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            equipment_code text NOT NULL,
            line_code text NOT NULL,
            name text NOT NULL,
            equipment_type text CHECK (equipment_type IN ('machine','robot','conveyor','inspection','utility')),
            vendor text,
            model text,
            serial_number text,
            install_date date,
            warranty_expiry_date date,
            maintenance_cycle_days int,
            last_maintenance_date date,
            next_maintenance_date date,
            mtbf_hours numeric,
            mttr_hours numeric,
            attributes jsonb NOT NULL DEFAULT '{}',
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, equipment_code),
            FOREIGN KEY (tenant_id, line_code) REFERENCES analytics.dim_line(tenant_id, line_code)
        )
    """)
    op.execute("CREATE INDEX idx_dim_equipment_line ON analytics.dim_equipment (tenant_id, line_code)")
    op.execute("CREATE INDEX idx_dim_equipment_type ON analytics.dim_equipment (equipment_type)")
    op.execute("CREATE INDEX idx_dim_equipment_maintenance ON analytics.dim_equipment (next_maintenance_date) WHERE is_active = true")
    op.execute("COMMENT ON TABLE analytics.dim_equipment IS 'Equipment Dimension Table'")

    # dim_kpi table (KPI dimension)
    op.execute("""
        CREATE TABLE analytics.dim_kpi (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            kpi_code text NOT NULL,
            name text NOT NULL,
            name_en text,
            category text NOT NULL CHECK (category IN ('quality','production','efficiency','cost','safety','inventory')),
            unit text,
            description text,
            calculation_method text,
            default_target numeric,
            green_threshold numeric,
            yellow_threshold numeric,
            red_threshold numeric,
            higher_is_better boolean NOT NULL DEFAULT true,
            aggregation_method text CHECK (aggregation_method IN ('sum','avg','min','max','last')),
            attributes jsonb NOT NULL DEFAULT '{}',
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, kpi_code)
        )
    """)
    op.execute("CREATE INDEX idx_dim_kpi_category ON analytics.dim_kpi (category)")
    op.execute("COMMENT ON TABLE analytics.dim_kpi IS 'KPI Definition Dimension Table'")

    # dim_shift table (shift dimension)
    op.execute("""
        CREATE TABLE analytics.dim_shift (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            shift_code text NOT NULL,
            name text NOT NULL,
            start_time time NOT NULL,
            end_time time NOT NULL,
            duration_hours numeric NOT NULL,
            is_night_shift boolean NOT NULL DEFAULT false,
            shift_order int NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, shift_code)
        )
    """)
    op.execute("COMMENT ON TABLE analytics.dim_shift IS 'Shift Dimension Table'")

    # ============================================
    # 3. Fact Tables
    # ============================================

    # fact_daily_production table (daily production)
    op.execute("""
        CREATE TABLE analytics.fact_daily_production (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            date date NOT NULL REFERENCES analytics.dim_date(date),
            line_code text NOT NULL,
            product_code text NOT NULL,
            shift text NOT NULL,
            total_qty numeric NOT NULL DEFAULT 0,
            good_qty numeric NOT NULL DEFAULT 0,
            defect_qty numeric NOT NULL DEFAULT 0,
            rework_qty numeric NOT NULL DEFAULT 0,
            scrap_qty numeric NOT NULL DEFAULT 0,
            cycle_time_avg numeric,
            cycle_time_std numeric,
            runtime_minutes numeric NOT NULL DEFAULT 0,
            downtime_minutes numeric NOT NULL DEFAULT 0,
            setup_time_minutes numeric NOT NULL DEFAULT 0,
            planned_qty numeric,
            target_cycle_time numeric,
            work_order_count int NOT NULL DEFAULT 0,
            operator_count int,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, date, line_code, product_code, shift),
            FOREIGN KEY (tenant_id, line_code) REFERENCES analytics.dim_line(tenant_id, line_code),
            FOREIGN KEY (tenant_id, product_code) REFERENCES analytics.dim_product(tenant_id, product_code)
        )
    """)
    op.execute("CREATE INDEX idx_fact_daily_prod_date ON analytics.fact_daily_production (tenant_id, date DESC)")
    op.execute("CREATE INDEX idx_fact_daily_prod_line ON analytics.fact_daily_production (tenant_id, line_code, date DESC)")
    op.execute("CREATE INDEX idx_fact_daily_prod_product ON analytics.fact_daily_production (tenant_id, product_code, date DESC)")
    op.execute("COMMENT ON TABLE analytics.fact_daily_production IS 'Daily Production FACT'")

    # fact_daily_defect table (daily defects)
    op.execute("""
        CREATE TABLE analytics.fact_daily_defect (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            date date NOT NULL REFERENCES analytics.dim_date(date),
            line_code text NOT NULL,
            product_code text NOT NULL,
            shift text NOT NULL,
            defect_type text NOT NULL,
            defect_qty numeric NOT NULL DEFAULT 0,
            defect_cost numeric,
            root_cause text,
            countermeasure text,
            responsible_dept text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, date, line_code, product_code, shift, defect_type),
            FOREIGN KEY (tenant_id, line_code) REFERENCES analytics.dim_line(tenant_id, line_code),
            FOREIGN KEY (tenant_id, product_code) REFERENCES analytics.dim_product(tenant_id, product_code)
        )
    """)
    op.execute("CREATE INDEX idx_fact_daily_defect_date ON analytics.fact_daily_defect (tenant_id, date DESC)")
    op.execute("CREATE INDEX idx_fact_daily_defect_type ON analytics.fact_daily_defect (defect_type, date DESC)")
    op.execute("COMMENT ON TABLE analytics.fact_daily_defect IS 'Daily Defect Detail FACT'")

    # fact_inventory_snapshot table (inventory snapshot)
    op.execute("""
        CREATE TABLE analytics.fact_inventory_snapshot (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            date date NOT NULL REFERENCES analytics.dim_date(date),
            product_code text NOT NULL,
            location text NOT NULL,
            stock_qty numeric NOT NULL DEFAULT 0,
            safety_stock_qty numeric NOT NULL DEFAULT 0,
            reserved_qty numeric NOT NULL DEFAULT 0,
            available_qty numeric NOT NULL DEFAULT 0,
            in_transit_qty numeric NOT NULL DEFAULT 0,
            stock_value numeric,
            avg_daily_usage numeric,
            coverage_days numeric,
            last_receipt_date date,
            last_issue_date date,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, date, product_code, location),
            FOREIGN KEY (tenant_id, product_code) REFERENCES analytics.dim_product(tenant_id, product_code)
        )
    """)
    op.execute("CREATE INDEX idx_fact_inv_snapshot_date ON analytics.fact_inventory_snapshot (tenant_id, date DESC)")
    op.execute("CREATE INDEX idx_fact_inv_snapshot_product ON analytics.fact_inventory_snapshot (tenant_id, product_code, date DESC)")
    op.execute("COMMENT ON TABLE analytics.fact_inventory_snapshot IS 'Daily Inventory Snapshot FACT'")

    # fact_equipment_event table (equipment event aggregation)
    op.execute("""
        CREATE TABLE analytics.fact_equipment_event (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            date date NOT NULL REFERENCES analytics.dim_date(date),
            equipment_code text NOT NULL,
            event_type text NOT NULL CHECK (event_type IN ('alarm','breakdown','maintenance','setup','idle')),
            event_count int NOT NULL DEFAULT 0,
            total_duration_minutes numeric NOT NULL DEFAULT 0,
            avg_duration_minutes numeric,
            max_duration_minutes numeric,
            severity_distribution jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, date, equipment_code, event_type),
            FOREIGN KEY (tenant_id, equipment_code) REFERENCES analytics.dim_equipment(tenant_id, equipment_code)
        )
    """)
    op.execute("CREATE INDEX idx_fact_equip_event_date ON analytics.fact_equipment_event (tenant_id, date DESC)")
    op.execute("CREATE INDEX idx_fact_equip_event_equip ON analytics.fact_equipment_event (tenant_id, equipment_code, date DESC)")
    op.execute("COMMENT ON TABLE analytics.fact_equipment_event IS 'Equipment Event Aggregation FACT'")

    # fact_hourly_production table (hourly production)
    op.execute("""
        CREATE TABLE analytics.fact_hourly_production (
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            hour_timestamp timestamptz NOT NULL,
            line_code text NOT NULL,
            product_code text NOT NULL,
            total_qty numeric NOT NULL DEFAULT 0,
            good_qty numeric NOT NULL DEFAULT 0,
            defect_qty numeric NOT NULL DEFAULT 0,
            cycle_time_avg numeric,
            runtime_minutes numeric NOT NULL DEFAULT 0,
            downtime_minutes numeric NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, hour_timestamp, line_code, product_code),
            FOREIGN KEY (tenant_id, line_code) REFERENCES analytics.dim_line(tenant_id, line_code),
            FOREIGN KEY (tenant_id, product_code) REFERENCES analytics.dim_product(tenant_id, product_code)
        )
    """)
    op.execute("CREATE INDEX idx_fact_hourly_prod_time ON analytics.fact_hourly_production (tenant_id, hour_timestamp DESC)")
    op.execute("CREATE INDEX idx_fact_hourly_prod_line ON analytics.fact_hourly_production (tenant_id, line_code, hour_timestamp DESC)")
    op.execute("COMMENT ON TABLE analytics.fact_hourly_production IS 'Hourly Production FACT (Real-time Monitoring)'")

    # ============================================
    # 4. BI Catalog Tables
    # ============================================

    # bi_datasets table (dataset definitions)
    op.execute("""
        CREATE TABLE analytics.bi_datasets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            name text NOT NULL,
            description text,
            source_type text NOT NULL CHECK (source_type IN ('postgres_table','postgres_view','materialized_view','api_endpoint')),
            source_ref text NOT NULL,
            default_filters jsonb,
            refresh_schedule text,
            last_refresh_at timestamptz,
            row_count bigint,
            created_by uuid REFERENCES core.users(user_id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, name)
        )
    """)
    op.execute("CREATE INDEX idx_bi_datasets_tenant ON analytics.bi_datasets (tenant_id)")
    op.execute("COMMENT ON TABLE analytics.bi_datasets IS 'BI Dataset Definitions'")

    # bi_metrics table (metric definitions)
    op.execute("""
        CREATE TABLE analytics.bi_metrics (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            name text NOT NULL,
            description text,
            dataset_id uuid NOT NULL REFERENCES analytics.bi_datasets(id) ON DELETE CASCADE,
            expression_sql text NOT NULL,
            agg_type text CHECK (agg_type IN ('sum','avg','min','max','count','distinct_count','median','percentile')),
            format_type text CHECK (format_type IN ('number','percent','currency','duration')),
            format_options jsonb,
            default_chart_type text,
            created_by uuid REFERENCES core.users(user_id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, name)
        )
    """)
    op.execute("CREATE INDEX idx_bi_metrics_dataset ON analytics.bi_metrics (dataset_id)")
    op.execute("COMMENT ON TABLE analytics.bi_metrics IS 'BI Metric Definitions'")

    # bi_dashboards table (dashboard definitions)
    op.execute("""
        CREATE TABLE analytics.bi_dashboards (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            name text NOT NULL,
            description text,
            layout jsonb NOT NULL,
            is_public boolean NOT NULL DEFAULT false,
            owner_id uuid NOT NULL REFERENCES core.users(user_id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, name)
        )
    """)
    op.execute("CREATE INDEX idx_bi_dashboards_tenant ON analytics.bi_dashboards (tenant_id)")
    op.execute("CREATE INDEX idx_bi_dashboards_owner ON analytics.bi_dashboards (owner_id)")
    op.execute("COMMENT ON TABLE analytics.bi_dashboards IS 'BI Dashboard Definitions'")

    # bi_components table (component templates)
    op.execute("""
        CREATE TABLE analytics.bi_components (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            type text NOT NULL CHECK (type IN ('chart','table','kpi_card','gauge','heatmap','pivot')),
            name text NOT NULL,
            required_fields jsonb NOT NULL,
            options_schema jsonb NOT NULL,
            default_options jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, type, name)
        )
    """)
    op.execute("COMMENT ON TABLE analytics.bi_components IS 'BI Component Templates'")

    # ============================================
    # 5. ETL Metadata Tables
    # ============================================

    # etl_jobs table (ETL job definitions)
    op.execute("""
        CREATE TABLE analytics.etl_jobs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            name text NOT NULL,
            description text,
            job_type text NOT NULL CHECK (job_type IN ('raw_to_fact','fact_to_agg','refresh_mv','data_quality')),
            source_tables text[] NOT NULL,
            target_tables text[] NOT NULL,
            transform_logic text,
            schedule_cron text,
            is_enabled boolean NOT NULL DEFAULT true,
            max_runtime_minutes int NOT NULL DEFAULT 60,
            retry_count int NOT NULL DEFAULT 3,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, name)
        )
    """)
    op.execute("CREATE INDEX idx_etl_jobs_tenant ON analytics.etl_jobs (tenant_id)")
    op.execute("COMMENT ON TABLE analytics.etl_jobs IS 'ETL Job Definitions'")

    # etl_job_executions table (ETL execution history)
    op.execute("""
        CREATE TABLE analytics.etl_job_executions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id uuid NOT NULL REFERENCES analytics.etl_jobs(id),
            status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','failed','cancelled')),
            rows_processed bigint,
            rows_inserted bigint,
            rows_updated bigint,
            rows_deleted bigint,
            error_message text,
            started_at timestamptz NOT NULL DEFAULT now(),
            ended_at timestamptz,
            duration_seconds int,
            metadata jsonb NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX idx_etl_executions_job ON analytics.etl_job_executions (job_id, started_at DESC)")
    op.execute("CREATE INDEX idx_etl_executions_status ON analytics.etl_job_executions (status) WHERE status = 'running'")
    op.execute("COMMENT ON TABLE analytics.etl_job_executions IS 'ETL Execution History'")

    # ============================================
    # 6. Data Quality Tables
    # ============================================

    # data_quality_rules table (quality rules)
    op.execute("""
        CREATE TABLE analytics.data_quality_rules (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES core.tenants(tenant_id),
            name text NOT NULL,
            description text,
            table_name text NOT NULL,
            rule_type text NOT NULL CHECK (rule_type IN ('not_null','range','uniqueness','referential_integrity','pattern','custom_sql')),
            rule_config jsonb NOT NULL,
            severity text NOT NULL CHECK (severity IN ('info','warning','error','critical')),
            is_enabled boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, name)
        )
    """)
    op.execute("COMMENT ON TABLE analytics.data_quality_rules IS 'Data Quality Validation Rules'")

    # data_quality_checks table (quality check results)
    op.execute("""
        CREATE TABLE analytics.data_quality_checks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            rule_id uuid NOT NULL REFERENCES analytics.data_quality_rules(id),
            status text NOT NULL CHECK (status IN ('pass','fail','warning')),
            failed_row_count int,
            total_row_count int,
            sample_failed_rows jsonb,
            executed_at timestamptz NOT NULL DEFAULT now(),
            metadata jsonb NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX idx_dq_checks_rule ON analytics.data_quality_checks (rule_id, executed_at DESC)")
    op.execute("CREATE INDEX idx_dq_checks_status ON analytics.data_quality_checks (status) WHERE status = 'fail'")
    op.execute("COMMENT ON TABLE analytics.data_quality_checks IS 'Data Quality Check Results'")


def downgrade() -> None:
    # Drop tables in reverse order
    op.execute("DROP TABLE IF EXISTS analytics.data_quality_checks CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.data_quality_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.etl_job_executions CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.etl_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.bi_components CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.bi_dashboards CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.bi_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.bi_datasets CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.fact_hourly_production CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.fact_equipment_event CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.fact_inventory_snapshot CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.fact_daily_defect CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.fact_daily_production CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.dim_shift CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.dim_kpi CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.dim_equipment CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.dim_product CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.dim_line CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.dim_date CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.raw_equipment_event CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.raw_inventory CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.raw_erp_order CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics.raw_mes_production CASCADE")

    # Drop schema
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
