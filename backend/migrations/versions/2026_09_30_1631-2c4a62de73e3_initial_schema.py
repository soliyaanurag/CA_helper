"""initial schema

Revision ID: 2c4a62de73e3
Revises: 
Create Date: 2026-09-30 16:31:19.730489

"""
from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2c4a62de73e3'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # The vector type of kb_chunks.embedding (the AI assistant's search) needs this extension.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('kb_chunks',
    sa.Column('source_path', sa.String(length=300), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('url', sa.String(length=1000), nullable=True),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_kb_chunks')),
    sa.UniqueConstraint('source_path', 'chunk_index', name=op.f('uq_kb_chunks_source_path'))
    )
    op.create_table('news_sources',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('url', sa.String(length=500), nullable=False),
    sa.Column('kind', sa.String(length=50), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_news_sources')),
    sa.UniqueConstraint('url', name=op.f('uq_news_sources_url'))
    )
    op.create_table('nic_codes',
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_nic_codes')),
    sa.UniqueConstraint('code', name=op.f('uq_nic_codes_code'))
    )
    op.create_table('obligation_templates',
    sa.Column('form_code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('frequency', sa.String(length=50), nullable=False),
    sa.Column('applicability', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('due_date_rule', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source_reference', sa.String(length=500), nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_to', sa.Date(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('effective_to IS NULL OR effective_to > effective_from', name=op.f('ck_obligation_templates_valid_period')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_obligation_templates')),
    sa.UniqueConstraint('form_code', 'frequency', 'effective_from', name=op.f('uq_obligation_templates_form_code'))
    )
    op.create_table('penalty_rules',
    sa.Column('form_code', sa.String(length=50), nullable=False),
    sa.Column('late_fee_per_day', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('max_late_fee', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('flat_late_fee', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('annual_interest_rate', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('source_reference', sa.String(length=500), nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_to', sa.Date(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('effective_to IS NULL OR effective_to > effective_from', name=op.f('ck_penalty_rules_valid_period')),
    sa.CheckConstraint('flat_late_fee IS NULL OR flat_late_fee >= 0', name=op.f('ck_penalty_rules_flat_late_fee_not_negative')),
    sa.CheckConstraint('late_fee_per_day >= 0 AND annual_interest_rate >= 0 AND (max_late_fee IS NULL OR max_late_fee >= 0)', name=op.f('ck_penalty_rules_amounts_not_negative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_penalty_rules')),
    sa.UniqueConstraint('form_code', 'effective_from', name=op.f('uq_penalty_rules_form_code'))
    )
    op.create_table('rule_thresholds',
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('source_reference', sa.String(length=500), nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_to', sa.Date(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('effective_to IS NULL OR effective_to > effective_from', name=op.f('ck_rule_thresholds_valid_period')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rule_thresholds')),
    sa.UniqueConstraint('key', 'effective_from', name=op.f('uq_rule_thresholds_key'))
    )
    op.create_table('service_catalog',
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('form_code', sa.String(length=50), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_service_catalog')),
    sa.UniqueConstraint('code', name=op.f('uq_service_catalog_code'))
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('email_notifications', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('businesses',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('legal_name', sa.String(length=200), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('state', sa.String(length=50), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=False),
    sa.Column('annual_turnover', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('investment_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('pan', sa.Text(), nullable=False),
    sa.Column('phone', sa.Text(), nullable=False),
    sa.Column('gst_registered', sa.Boolean(), nullable=False),
    sa.Column('gstin', sa.Text(), nullable=True),
    sa.Column('gst_composition', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('gst_qrmp', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('accounts_audited_other_law', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('deducts_tds', sa.Boolean(), nullable=False),
    sa.Column('tan', sa.Text(), nullable=True),
    sa.Column('pays_salary_above_limit', sa.Boolean(), nullable=False),
    sa.Column('cin_llpin', sa.String(length=21), nullable=True),
    sa.Column('udyam_number', sa.String(length=19), nullable=True),
    sa.Column('nic_code_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("entity_type NOT IN ('llp', 'private_limited') OR cin_llpin IS NOT NULL", name=op.f('ck_businesses_cin_llpin_for_llp_and_company')),
    sa.CheckConstraint('NOT deducts_tds OR tan IS NOT NULL', name=op.f('ck_businesses_tan_when_deducts_tds')),
    sa.CheckConstraint('NOT gst_registered OR gstin IS NOT NULL', name=op.f('ck_businesses_gstin_when_gst_registered')),
    sa.CheckConstraint('annual_turnover >= 0 AND investment_amount >= 0', name=op.f('ck_businesses_amounts_not_negative')),
    sa.ForeignKeyConstraint(['nic_code_id'], ['nic_codes.id'], name=op.f('fk_businesses_nic_code_id_nic_codes')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_businesses_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_businesses')),
    sa.UniqueConstraint('user_id', name=op.f('uq_businesses_user_id'))
    )
    op.create_table('chat_messages',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_chat_messages_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chat_messages'))
    )
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chat_messages_user_id'), ['user_id'], unique=False)

    op.create_table('documents',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('uploaded_by_id', sa.Uuid(), nullable=False),
    sa.Column('doc_type', sa.String(length=50), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('fy', sa.String(length=7), nullable=True),
    sa.Column('period_label', sa.String(length=30), nullable=True),
    sa.Column('ocr_status', sa.String(length=50), nullable=False),
    sa.Column('ocr_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('size_bytes >= 0', name=op.f('ck_documents_size_not_negative')),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_documents_owner_id_users')),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], name=op.f('fk_documents_uploaded_by_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_documents'))
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documents_owner_id'), ['owner_id'], unique=False)

    op.create_table('email_otps',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('purpose', sa.String(length=50), nullable=False),
    sa.Column('code_hash', sa.String(length=255), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_email_otps_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_email_otps'))
    )
    with op.batch_alter_table('email_otps', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_email_otps_user_id'), ['user_id'], unique=False)

    op.create_table('news_articles',
    sa.Column('source_id', sa.Uuid(), nullable=False),
    sa.Column('url', sa.String(length=1000), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['news_sources.id'], name=op.f('fk_news_articles_source_id_news_sources')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_news_articles')),
    sa.UniqueConstraint('content_hash', name=op.f('uq_news_articles_content_hash')),
    sa.UniqueConstraint('url', name=op.f('uq_news_articles_url'))
    )
    with op.batch_alter_table('news_articles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_news_articles_source_id'), ['source_id'], unique=False)

    op.create_table('notifications',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.String(length=2000), nullable=False),
    sa.Column('link', sa.String(length=300), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)

    op.create_table('ca_profiles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('membership_no', sa.String(length=6), nullable=False),
    sa.Column('cop_number', sa.String(length=20), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('languages', postgresql.ARRAY(sa.String(length=50)), nullable=False),
    sa.Column('specializations', postgresql.ARRAY(sa.String(length=50)), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('years_experience', sa.Integer(), nullable=False),
    sa.Column('about', sa.String(length=500), server_default='', nullable=False),
    sa.Column('verification_status', sa.String(length=50), nullable=False),
    sa.Column('pro_bono_slots_per_month', sa.Integer(), server_default='0', nullable=False),
    sa.Column('rejection_reason', sa.String(length=500), nullable=True),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verified_by_id', sa.Uuid(), nullable=True),
    sa.Column('cop_document_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('pro_bono_slots_per_month >= 0', name=op.f('ck_ca_profiles_pro_bono_slots_not_negative')),
    sa.ForeignKeyConstraint(['cop_document_id'], ['documents.id'], name=op.f('fk_ca_profiles_cop_document_id_documents')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ca_profiles_user_id_users')),
    sa.ForeignKeyConstraint(['verified_by_id'], ['users.id'], name=op.f('fk_ca_profiles_verified_by_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ca_profiles')),
    sa.UniqueConstraint('membership_no', name=op.f('uq_ca_profiles_membership_no')),
    sa.UniqueConstraint('user_id', name=op.f('uq_ca_profiles_user_id'))
    )
    with op.batch_alter_table('ca_profiles', schema=None) as batch_op:
        batch_op.create_index('ix_ca_profiles_specializations', ['specializations'], unique=False, postgresql_using='gin')

    op.create_table('compliance_items',
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('template_id', sa.Uuid(), nullable=False),
    sa.Column('form_code', sa.String(length=50), nullable=False),
    sa.Column('fy', sa.String(length=7), nullable=False),
    sa.Column('period_label', sa.String(length=30), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('filing_path', sa.String(length=50), nullable=True),
    sa.Column('filed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('acknowledgement_no', sa.String(length=50), nullable=True),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('acknowledgement_document_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("fy ~ '^[0-9]{4}-[0-9]{2}$'", name=op.f('ck_compliance_items_fy_format')),
    sa.CheckConstraint('period_end >= period_start', name=op.f('ck_compliance_items_valid_period')),
    sa.ForeignKeyConstraint(['acknowledgement_document_id'], ['documents.id'], name=op.f('fk_compliance_items_acknowledgement_document_id_documents')),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_compliance_items_business_id_businesses')),
    sa.ForeignKeyConstraint(['template_id'], ['obligation_templates.id'], name=op.f('fk_compliance_items_template_id_obligation_templates')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_compliance_items')),
    sa.UniqueConstraint('business_id', 'form_code', 'period_start', name=op.f('uq_compliance_items_business_id'))
    )
    with op.batch_alter_table('compliance_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_compliance_items_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_compliance_items_due_date'), ['due_date'], unique=False)

    op.create_table('regulatory_changes',
    sa.Column('article_id', sa.Uuid(), nullable=False),
    sa.Column('change_type', sa.String(length=50), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('form_codes', postgresql.ARRAY(sa.String(length=50)), nullable=False),
    sa.Column('affected_categories', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('dates', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['article_id'], ['news_articles.id'], name=op.f('fk_regulatory_changes_article_id_news_articles')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_regulatory_changes'))
    )
    with op.batch_alter_table('regulatory_changes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_regulatory_changes_article_id'), ['article_id'], unique=False)

    op.create_table('regulatory_profiles',
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('msme_tier', sa.String(length=50), nullable=False),
    sa.Column('gst_scheme', sa.String(length=50), nullable=False),
    sa.Column('gst_registration_suggested', sa.Boolean(), nullable=False),
    sa.Column('itr_form', sa.String(length=50), nullable=False),
    sa.Column('presumptive_eligible', sa.Boolean(), nullable=False),
    sa.Column('audit_applicable', sa.Boolean(), nullable=False),
    sa.Column('other_audit_applicable', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('files_24q', sa.Boolean(), nullable=False),
    sa.Column('files_26q', sa.Boolean(), nullable=False),
    sa.Column('roc_not_tracked', sa.Boolean(), nullable=False),
    sa.Column('explanations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('rule_version', sa.String(length=50), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_regulatory_profiles_business_id_businesses')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_regulatory_profiles')),
    sa.UniqueConstraint('business_id', name=op.f('uq_regulatory_profiles_business_id'))
    )
    op.create_table('ca_services',
    sa.Column('ca_profile_id', sa.Uuid(), nullable=False),
    sa.Column('service_id', sa.Uuid(), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('price > 0', name=op.f('ck_ca_services_positive_price')),
    sa.ForeignKeyConstraint(['ca_profile_id'], ['ca_profiles.id'], name=op.f('fk_ca_services_ca_profile_id_ca_profiles')),
    sa.ForeignKeyConstraint(['service_id'], ['service_catalog.id'], name=op.f('fk_ca_services_service_id_service_catalog')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ca_services')),
    sa.UniqueConstraint('ca_profile_id', 'service_id', name=op.f('uq_ca_services_ca_profile_id'))
    )
    with op.batch_alter_table('ca_services', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ca_services_ca_profile_id'), ['ca_profile_id'], unique=False)

    op.create_table('checklist_ticks',
    sa.Column('compliance_item_id', sa.Uuid(), nullable=False),
    sa.Column('checklist_key', sa.String(length=50), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['compliance_item_id'], ['compliance_items.id'], name=op.f('fk_checklist_ticks_compliance_item_id_compliance_items')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_checklist_ticks')),
    sa.UniqueConstraint('compliance_item_id', 'checklist_key', name=op.f('uq_checklist_ticks_compliance_item_id'))
    )
    op.create_table('compliance_item_documents',
    sa.Column('compliance_item_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('checklist_key', sa.String(length=50), server_default='general', nullable=False),
    sa.Column('linked_by_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("checklist_key <> ''", name=op.f('ck_compliance_item_documents_checklist_key_not_empty')),
    sa.ForeignKeyConstraint(['compliance_item_id'], ['compliance_items.id'], name=op.f('fk_compliance_item_documents_compliance_item_id_compliance_items')),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_compliance_item_documents_document_id_documents')),
    sa.ForeignKeyConstraint(['linked_by_id'], ['users.id'], name=op.f('fk_compliance_item_documents_linked_by_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_compliance_item_documents')),
    sa.UniqueConstraint('compliance_item_id', 'document_id', 'checklist_key', name=op.f('uq_compliance_item_documents_compliance_item_id'))
    )
    with op.batch_alter_table('compliance_item_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_compliance_item_documents_compliance_item_id'), ['compliance_item_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_compliance_item_documents_document_id'), ['document_id'], unique=False)

    op.create_table('engagements',
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('ca_profile_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('is_pro_bono', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('quote_reason', sa.String(length=1000), nullable=True),
    sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status <> 'quoted' OR quote_reason IS NOT NULL", name=op.f('ck_engagements_quote_needs_reason')),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_engagements_business_id_businesses')),
    sa.ForeignKeyConstraint(['ca_profile_id'], ['ca_profiles.id'], name=op.f('fk_engagements_ca_profile_id_ca_profiles')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_engagements'))
    )
    with op.batch_alter_table('engagements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_engagements_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_engagements_ca_profile_id'), ['ca_profile_id'], unique=False)

    op.create_table('regulatory_change_matches',
    sa.Column('change_id', sa.Uuid(), nullable=False),
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_regulatory_change_matches_business_id_businesses')),
    sa.ForeignKeyConstraint(['change_id'], ['regulatory_changes.id'], name=op.f('fk_regulatory_change_matches_change_id_regulatory_changes')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_regulatory_change_matches')),
    sa.UniqueConstraint('change_id', 'business_id', name=op.f('uq_regulatory_change_matches_change_id'))
    )
    with op.batch_alter_table('regulatory_change_matches', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_regulatory_change_matches_business_id'), ['business_id'], unique=False)

    op.create_table('reminder_log',
    sa.Column('compliance_item_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=50), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['compliance_item_id'], ['compliance_items.id'], name=op.f('fk_reminder_log_compliance_item_id_compliance_items')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reminder_log')),
    sa.UniqueConstraint('compliance_item_id', 'kind', name=op.f('uq_reminder_log_compliance_item_id'))
    )
    op.create_table('document_requests',
    sa.Column('engagement_id', sa.Uuid(), nullable=False),
    sa.Column('compliance_item_id', sa.Uuid(), nullable=False),
    sa.Column('checklist_key', sa.String(length=50), nullable=False),
    sa.Column('message', sa.String(length=1000), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('fulfilled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('document_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['compliance_item_id'], ['compliance_items.id'], name=op.f('fk_document_requests_compliance_item_id_compliance_items')),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_requests_document_id_documents')),
    sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], name=op.f('fk_document_requests_engagement_id_engagements')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_requests'))
    )
    with op.batch_alter_table('document_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_requests_engagement_id'), ['engagement_id'], unique=False)

    op.create_table('engagement_items',
    sa.Column('engagement_id', sa.Uuid(), nullable=False),
    sa.Column('compliance_item_id', sa.Uuid(), nullable=False),
    sa.Column('service_id', sa.Uuid(), nullable=False),
    sa.Column('listed_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('quoted_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('agreed_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('listed_price >= 0 AND (agreed_price IS NULL OR agreed_price >= 0)', name=op.f('ck_engagement_items_prices_not_negative')),
    sa.CheckConstraint('quoted_price IS NULL OR quoted_price >= 0', name=op.f('ck_engagement_items_quoted_price_not_negative')),
    sa.ForeignKeyConstraint(['compliance_item_id'], ['compliance_items.id'], name=op.f('fk_engagement_items_compliance_item_id_compliance_items')),
    sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], name=op.f('fk_engagement_items_engagement_id_engagements')),
    sa.ForeignKeyConstraint(['service_id'], ['service_catalog.id'], name=op.f('fk_engagement_items_service_id_service_catalog')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_engagement_items')),
    sa.UniqueConstraint('engagement_id', 'compliance_item_id', name=op.f('uq_engagement_items_engagement_id'))
    )
    with op.batch_alter_table('engagement_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_engagement_items_compliance_item_id'), ['compliance_item_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_engagement_items_engagement_id'), ['engagement_id'], unique=False)

    op.create_table('pro_bono_requests',
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('note', sa.String(length=1000), server_default='', nullable=False),
    sa.Column('compliance_item_ids', postgresql.ARRAY(sa.Uuid()), server_default='{}', nullable=False),
    sa.Column('engagement_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], name=op.f('fk_pro_bono_requests_business_id_businesses')),
    sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], name=op.f('fk_pro_bono_requests_engagement_id_engagements')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pro_bono_requests')),
    sa.UniqueConstraint('engagement_id', name=op.f('uq_pro_bono_requests_engagement_id'))
    )
    with op.batch_alter_table('pro_bono_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pro_bono_requests_business_id'), ['business_id'], unique=False)

    op.create_table('ratings',
    sa.Column('engagement_id', sa.Uuid(), nullable=False),
    sa.Column('stars', sa.SmallInteger(), nullable=False),
    sa.Column('review', sa.String(length=2000), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('stars BETWEEN 1 AND 5', name=op.f('ck_ratings_stars_1_to_5')),
    sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], name=op.f('fk_ratings_engagement_id_engagements')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ratings')),
    sa.UniqueConstraint('engagement_id', name=op.f('uq_ratings_engagement_id'))
    )


def downgrade():
    op.drop_table('ratings')
    with op.batch_alter_table('pro_bono_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pro_bono_requests_business_id'))

    op.drop_table('pro_bono_requests')
    with op.batch_alter_table('engagement_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_engagement_items_engagement_id'))
        batch_op.drop_index(batch_op.f('ix_engagement_items_compliance_item_id'))

    op.drop_table('engagement_items')
    with op.batch_alter_table('document_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_requests_engagement_id'))

    op.drop_table('document_requests')
    op.drop_table('reminder_log')
    with op.batch_alter_table('regulatory_change_matches', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_regulatory_change_matches_business_id'))

    op.drop_table('regulatory_change_matches')
    with op.batch_alter_table('engagements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_engagements_ca_profile_id'))
        batch_op.drop_index(batch_op.f('ix_engagements_business_id'))

    op.drop_table('engagements')
    with op.batch_alter_table('compliance_item_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_compliance_item_documents_document_id'))
        batch_op.drop_index(batch_op.f('ix_compliance_item_documents_compliance_item_id'))

    op.drop_table('compliance_item_documents')
    op.drop_table('checklist_ticks')
    with op.batch_alter_table('ca_services', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ca_services_ca_profile_id'))

    op.drop_table('ca_services')
    op.drop_table('regulatory_profiles')
    with op.batch_alter_table('regulatory_changes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_regulatory_changes_article_id'))

    op.drop_table('regulatory_changes')
    with op.batch_alter_table('compliance_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_compliance_items_due_date'))
        batch_op.drop_index(batch_op.f('ix_compliance_items_business_id'))

    op.drop_table('compliance_items')
    with op.batch_alter_table('ca_profiles', schema=None) as batch_op:
        batch_op.drop_index('ix_ca_profiles_specializations', postgresql_using='gin')

    op.drop_table('ca_profiles')
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notifications_user_id'))

    op.drop_table('notifications')
    with op.batch_alter_table('news_articles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_news_articles_source_id'))

    op.drop_table('news_articles')
    with op.batch_alter_table('email_otps', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_email_otps_user_id'))

    op.drop_table('email_otps')
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_owner_id'))

    op.drop_table('documents')
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_messages_user_id'))

    op.drop_table('chat_messages')
    op.drop_table('businesses')
    op.drop_table('users')
    op.drop_table('service_catalog')
    op.drop_table('rule_thresholds')
    op.drop_table('penalty_rules')
    op.drop_table('obligation_templates')
    op.drop_table('nic_codes')
    op.drop_table('news_sources')
    op.drop_table('kb_chunks')
