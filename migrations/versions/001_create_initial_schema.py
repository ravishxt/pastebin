"""create initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-02-17 17:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create paste_status_enum type
    # op.execute("CREATE TYPE paste_status_enum AS ENUM ('ACTIVE', 'VIEWED', 'EXPIRED', 'DELETED')")

    # Create pastes table
    op.create_table(
        'pastes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('max_views', sa.Integer(), nullable=False),
        sa.Column('current_views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', postgresql.ENUM('ACTIVE', 'VIEWED', 'EXPIRED', 'DELETED', name='paste_status_enum'), nullable=False, server_default='ACTIVE'),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('max_views >= 1', name='ck_pastes_max_views_min_1'),
        sa.CheckConstraint('current_views >= 0', name='ck_pastes_current_views_non_negative'),
    )

    # Create trigger for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    op.execute("""
        CREATE TRIGGER update_pastes_updated_at BEFORE UPDATE ON pastes
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create access_logs table
    op.create_table(
        'access_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('paste_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('accessed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['paste_id'], ['pastes.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_access_logs_paste_id'), 'access_logs', ['paste_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_access_logs_paste_id'), table_name='access_logs')
    op.drop_table('access_logs')
    op.execute('DROP TRIGGER IF EXISTS update_pastes_updated_at ON pastes')
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')
    op.drop_table('pastes')
    op.execute('DROP TYPE paste_status_enum')
