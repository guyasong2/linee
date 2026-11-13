from django.db import migrations

PG_FORWARD_SQL = """
CREATE OR REPLACE FUNCTION linee_audit_immutable()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit log is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS linee_audit_no_update_delete ON audit_auditlog;
CREATE TRIGGER linee_audit_no_update_delete
BEFORE UPDATE OR DELETE ON audit_auditlog
FOR EACH ROW EXECUTE FUNCTION linee_audit_immutable();
"""

PG_REVERSE_SQL = """
DROP TRIGGER IF EXISTS linee_audit_no_update_delete ON audit_auditlog;
DROP FUNCTION IF EXISTS linee_audit_immutable();
"""


def apply_trigger(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(PG_FORWARD_SQL)
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS linee_audit_no_update
            BEFORE UPDATE ON audit_auditlog
            BEGIN
                SELECT RAISE(FAIL, 'audit log is append-only');
            END;
            """
        )
        schema_editor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS linee_audit_no_delete
            BEFORE DELETE ON audit_auditlog
            BEGIN
                SELECT RAISE(FAIL, 'audit log is append-only');
            END;
            """
        )


def remove_trigger(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(PG_REVERSE_SQL)
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS linee_audit_no_update;")
        schema_editor.execute("DROP TRIGGER IF EXISTS linee_audit_no_delete;")


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_trigger, reverse_code=remove_trigger),
    ]
