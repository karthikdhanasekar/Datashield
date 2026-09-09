"""Initial schema — all tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organizations ─────────────────────────────────────────────────────────
    op.create_table('organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('domain', sa.String(255), nullable=True),
        sa.Column('subscription_tier', sa.String(50), nullable=True),
        sa.Column('max_members', sa.Integer(), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id', name='pk_organizations'),
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('phone_number', sa.String(20), nullable=True),
        sa.Column('role', sa.String(20), nullable=False, server_default='individual'),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending_verification'),
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('mfa_secret', sa.String(32), nullable=True),
        sa.Column('mfa_backup_codes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_verification_token', sa.String(100), nullable=True),
        sa.Column('phone_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('password_reset_token', sa.String(100), nullable=True),
        sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notification_email', sa.Boolean(), server_default='true'),
        sa.Column('notification_sms', sa.Boolean(), server_default='false'),
        sa.Column('notification_push', sa.Boolean(), server_default='true'),
        sa.Column('timezone', sa.String(50), server_default='UTC'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_ip', sa.String(45), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'],
                                name='fk_users_organization_id_organizations'),
        sa.PrimaryKeyConstraint('id', name='pk_users'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )
    op.create_index('ix_users_email_status', 'users', ['email', 'status'])

    # ── user_sessions ─────────────────────────────────────────────────────────
    op.create_table('user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('jti', sa.String(64), nullable=False),
        sa.Column('refresh_token_hash', sa.String(64), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_user_sessions_user_id_users'),
        sa.PrimaryKeyConstraint('id', name='pk_user_sessions'),
        sa.UniqueConstraint('jti', name='uq_user_sessions_jti'),
    )
    op.create_index('ix_user_sessions_jti', 'user_sessions', ['jti'])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='success'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL',
                                name='fk_audit_logs_user_id_users'),
        sa.PrimaryKeyConstraint('id', name='pk_audit_logs'),
    )
    op.create_index('ix_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])

    # ── scan_requests ─────────────────────────────────────────────────────────
    op.create_table('scan_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scan_type', sa.String(30), nullable=False),
        sa.Column('query_value', sa.String(500), nullable=False),
        sa.Column('query_masked', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('celery_task_id', sa.String(100), nullable=True),
        sa.Column('progress', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_findings', sa.Integer(), server_default='0'),
        sa.Column('critical_count', sa.Integer(), server_default='0'),
        sa.Column('high_count', sa.Integer(), server_default='0'),
        sa.Column('medium_count', sa.Integer(), server_default='0'),
        sa.Column('low_count', sa.Integer(), server_default='0'),
        sa.Column('exposure_score', sa.Float(), server_default='0'),
        sa.Column('modules_run', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('modules_completed', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_scan_requests_user_id_users'),
        sa.PrimaryKeyConstraint('id', name='pk_scan_requests'),
    )
    op.create_index('ix_scan_requests_user_status', 'scan_requests', ['user_id', 'status'])
    op.create_index('ix_scan_requests_created', 'scan_requests', ['created_at'])

    # ── findings ──────────────────────────────────────────────────────────────
    op.create_table('findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('finding_type', sa.String(30), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('source_domain', sa.String(255), nullable=True),
        sa.Column('source_title', sa.Text(), nullable=True),
        sa.Column('source_name', sa.String(255), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False, server_default='low'),
        sa.Column('risk_score', sa.Float(), server_default='0'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('exposed_data_types', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('identity_theft_risk', sa.Boolean(), server_default='false'),
        sa.Column('financial_risk', sa.Boolean(), server_default='false'),
        sa.Column('reputation_risk', sa.Boolean(), server_default='false'),
        sa.Column('credential_exposure', sa.Boolean(), server_default='false'),
        sa.Column('government_id_exposure', sa.Boolean(), server_default='false'),
        sa.Column('raw_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('snippet', sa.Text(), nullable=True),
        sa.Column('screenshot_url', sa.String(500), nullable=True),
        sa.Column('evidence_hash', sa.String(64), nullable=True),
        sa.Column('is_verified', sa.Boolean(), server_default='false'),
        sa.Column('is_false_positive', sa.Boolean(), server_default='false'),
        sa.Column('is_removed', sa.Boolean(), server_default='false'),
        sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('discovered_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['scan_id'], ['scan_requests.id'], ondelete='CASCADE',
                                name='fk_findings_scan_id_scan_requests'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_findings_user_id_users'),
        sa.PrimaryKeyConstraint('id', name='pk_findings'),
    )
    op.create_index('ix_findings_user_severity', 'findings', ['user_id', 'severity'])
    op.create_index('ix_findings_scan', 'findings', ['scan_id'])
    op.create_index('ix_findings_source_domain', 'findings', ['source_domain'])

    # ── evidence_reports ──────────────────────────────────────────────────────
    op.create_table('evidence_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_title', sa.String(255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('finding_count', sa.Integer(), server_default='0'),
        sa.Column('pdf_url', sa.String(500), nullable=True),
        sa.Column('json_url', sa.String(500), nullable=True),
        sa.Column('csv_url', sa.String(500), nullable=True),
        sa.Column('package_url', sa.String(500), nullable=True),
        sa.Column('report_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['scan_id'], ['scan_requests.id'], ondelete='CASCADE',
                                name='fk_evidence_reports_scan_id_scan_requests'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_evidence_reports_user_id_users'),
        sa.PrimaryKeyConstraint('id', name='pk_evidence_reports'),
    )

    # ── takedown_requests ─────────────────────────────────────────────────────
    op.create_table('takedown_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('finding_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_type', sa.String(40), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('legal_references', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('target_url', sa.Text(), nullable=False),
        sa.Column('target_domain', sa.String(255), nullable=False),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('abuse_email', sa.String(255), nullable=True),
        sa.Column('privacy_officer_email', sa.String(255), nullable=True),
        sa.Column('contact_form_url', sa.Text(), nullable=True),
        sa.Column('whois_registrar', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('follow_up_count', sa.Integer(), server_default='0'),
        sa.Column('next_follow_up_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_received', sa.Text(), nullable=True),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.Column('complaint_filed', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ondelete='CASCADE',
                                name='fk_takedown_requests_finding_id_findings'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_takedown_requests_user_id_users'),
        sa.PrimaryKeyConstraint('id', name='pk_takedown_requests'),
    )
    op.create_index('ix_takedown_user_status', 'takedown_requests', ['user_id', 'status'])

    # ── takedown_status_history ───────────────────────────────────────────────
    op.create_table('takedown_status_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('takedown_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_status', sa.String(20), nullable=True),
        sa.Column('new_status', sa.String(20), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.String(100), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['takedown_id'], ['takedown_requests.id'], ondelete='CASCADE',
                                name='fk_takedown_status_history_takedown_id_takedown_requests'),
        sa.PrimaryKeyConstraint('id', name='pk_takedown_status_history'),
    )

    # ── monitor_configs ───────────────────────────────────────────────────────
    op.create_table('monitor_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('finding_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_url', sa.Text(), nullable=False),
        sa.Column('target_domain', sa.String(255), nullable=False),
        sa.Column('monitor_interval', sa.String(20), server_default='weekly'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_check_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), server_default='0'),
        sa.Column('last_status', sa.String(50), nullable=True),
        sa.Column('last_snapshot_url', sa.String(500), nullable=True),
        sa.Column('alert_on_reappear', sa.Boolean(), server_default='true'),
        sa.Column('alert_on_new_leak', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_monitor_configs_user_id_users'),
        sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ondelete='SET NULL',
                                name='fk_monitor_configs_finding_id_findings'),
        sa.PrimaryKeyConstraint('id', name='pk_monitor_configs'),
    )

    # ── monitor_check_history ─────────────────────────────────────────────────
    op.create_table('monitor_check_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('monitor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('http_status_code', sa.Integer(), nullable=True),
        sa.Column('page_accessible', sa.Boolean(), nullable=True),
        sa.Column('data_still_present', sa.Boolean(), nullable=True),
        sa.Column('snapshot_url', sa.String(500), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['monitor_id'], ['monitor_configs.id'], ondelete='CASCADE',
                                name='fk_monitor_check_history_monitor_id_monitor_configs'),
        sa.PrimaryKeyConstraint('id', name='pk_monitor_check_history'),
    )

    # ── cybercrime_complaints ─────────────────────────────────────────────────
    op.create_table('cybercrime_complaints',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('incident_summary', sa.Text(), nullable=False),
        sa.Column('affected_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('exposure_timeline', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('jurisdiction', sa.String(100), nullable=True),
        sa.Column('authority_name', sa.String(255), nullable=True),
        sa.Column('authority_url', sa.String(500), nullable=True),
        sa.Column('package_url', sa.String(500), nullable=True),
        sa.Column('finding_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_submitted', sa.Boolean(), server_default='false'),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reference_number', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_cybercrime_complaints_user_id_users'),
        sa.PrimaryKeyConstraint('id', name='pk_cybercrime_complaints'),
    )

    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table('notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), server_default='info'),
        sa.Column('is_read', sa.Boolean(), server_default='false'),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('email_sent', sa.Boolean(), server_default='false'),
        sa.Column('sms_sent', sa.Boolean(), server_default='false'),
        sa.Column('push_sent', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_notifications_user_id_users'),
        sa.PrimaryKeyConstraint('id', name='pk_notifications'),
    )
    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'is_read'])


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('cybercrime_complaints')
    op.drop_table('monitor_check_history')
    op.drop_table('monitor_configs')
    op.drop_table('takedown_status_history')
    op.drop_table('takedown_requests')
    op.drop_table('evidence_reports')
    op.drop_table('findings')
    op.drop_table('scan_requests')
    op.drop_table('audit_logs')
    op.drop_table('user_sessions')
    op.drop_table('users')
    op.drop_table('organizations')
