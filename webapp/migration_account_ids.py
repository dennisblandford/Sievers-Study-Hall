"""One-off migration: give every existing user a UUID account id.

The UUID-login feature replaced the old email/password columns with an
``account_id``. Fresh databases already get the column from
``db.create_all()``; for existing databases this helper rebuilds the ``user``
table in place (SQLite cannot drop a column reliably on older versions) and
copies the existing ids, emails and creation timestamps across.

The function is idempotent: once ``account_id`` exists it does nothing.
"""

from users.users.models import db, generate_account_id


def migrate_account_ids():
    """Rebuild the ``user`` table with an ``account_id`` column if needed."""
    # AUTOCOMMIT is required so the foreign_keys PRAGMA actually takes effect
    # and so the table rebuild is not wrapped in an implicit transaction.
    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(user)").fetchall()

        if not columns:
            return

        column_names = {column[1] for column in columns}
        if "account_id" in column_names:
            return

        rows = conn.exec_driver_sql(
            "SELECT id, email, created_at FROM user"
        ).fetchall()

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")

        conn.exec_driver_sql(
            """
            CREATE TABLE user_new (
                id INTEGER PRIMARY KEY,
                account_id VARCHAR(36) NOT NULL,
                email VARCHAR(255),
                created_at DATETIME
            )
            """
        )

        for user_id, email, created_at in rows:
            conn.exec_driver_sql(
                "INSERT INTO user_new (id, account_id, email, created_at) VALUES (?, ?, ?, ?)",
                (user_id, generate_account_id(), email, created_at),
            )

        conn.exec_driver_sql("DROP TABLE user")
        conn.exec_driver_sql("ALTER TABLE user_new RENAME TO user")

        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX ix_user_account_id ON user (account_id)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX ix_user_email ON user (email)"
        )

        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
