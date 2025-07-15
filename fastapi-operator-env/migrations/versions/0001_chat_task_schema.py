"""add chat and task schema"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "threads",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(length=255)),
        sa.Column("participants", sa.ARRAY(sa.String)),
        sa.Column("project_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("thread_id", sa.Integer, sa.ForeignKey("threads.id")),
        sa.Column("sender", sa.String(length=50)),
        sa.Column("recipient", sa.String(length=50), nullable=True),
        sa.Column("content", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("metadata", sa.JSON),
        sa.Column("attachments", sa.JSON, nullable=True),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(length=255)),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(length=50)),
        sa.Column("assigned_to", sa.String(length=50)),
        sa.Column("created_by", sa.String(length=50)),
        sa.Column("due_date", sa.DateTime, nullable=True),
        sa.Column("parent_task", sa.Integer, sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("thread_id", sa.Integer, sa.ForeignKey("threads.id"), nullable=True),
        sa.Column("priority", sa.Integer),
        sa.Column("tags", sa.ARRAY(sa.String)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("filename", sa.String(length=255)),
        sa.Column("uploader", sa.String(length=50)),
        sa.Column("path", sa.String(length=255)),
        sa.Column("thread_id", sa.Integer, sa.ForeignKey("threads.id"), nullable=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("metadata", sa.JSON),
    )
    op.create_index("ix_messages_thread_sender", "messages", ["thread_id", "sender"])
    op.create_index("ix_tasks_assigned_status", "tasks", ["assigned_to", "status"])


def downgrade() -> None:
    op.drop_index("ix_tasks_assigned_status", table_name="tasks")
    op.drop_index("ix_messages_thread_sender", table_name="messages")
    op.drop_table("files")
    op.drop_table("tasks")
    op.drop_table("messages")
    op.drop_table("threads")
