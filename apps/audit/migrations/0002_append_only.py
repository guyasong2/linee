from django.db import migrations

FORWARD_SQL = """
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

REVERSE_SQL = """
DROP TRIGGER IF EXISTS linee_audit_no_update_delete ON audit_auditlog;
DROP FUNCTION IF EXISTS linee_audit_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
