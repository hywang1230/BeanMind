import sqlite3

from backend.infrastructure.persistence.init_db import init_database


def test_init_database_migrates_legacy_monthly_reports_schema(tmp_path):
    db_path = tmp_path / "beanmind.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE monthly_reports (
                month VARCHAR(7) NOT NULL,
                status VARCHAR(20) NOT NULL,
                trigger_source VARCHAR(32) NOT NULL,
                skill_name VARCHAR(64) NOT NULL,
                source_facts_hash VARCHAR(64) NOT NULL,
                report_payload TEXT NOT NULL,
                facts_payload TEXT NOT NULL,
                error_message TEXT NOT NULL,
                generated_at DATETIME,
                id VARCHAR(36) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO monthly_reports (
                month, status, trigger_source, skill_name, source_facts_hash,
                report_payload, facts_payload, error_message, generated_at,
                id, created_at, updated_at
            ) VALUES (
                '2026-04', 'READY', 'manual', 'monthly_report', 'hash-1',
                '{"monthly_summary":"ok"}', '{"income":"1"}', '',
                '2026-04-29 09:00:00', 'report-1',
                '2026-04-29 09:00:00', '2026-04-29 09:00:00'
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    init_database(str(db_path))

    migrated = sqlite3.connect(db_path)
    try:
        columns = {
            row[1]
            for row in migrated.execute("PRAGMA table_info(monthly_reports)").fetchall()
        }
        assert "user_id" in columns
        assert "report_month" in columns
        assert "report_json" in columns
        assert "facts_json" in columns

        row = migrated.execute(
            """
            SELECT user_id, report_month, status, report_json, facts_json
            FROM monthly_reports
            WHERE id = 'report-1'
            """
        ).fetchone()
        assert row == (
            "default",
            "2026-04",
            "READY",
            '{"monthly_summary":"ok"}',
            '{"income":"1"}',
        )
    finally:
        migrated.close()
