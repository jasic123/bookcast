"""Initial schema - book lists, books, research, and assessments

Revision ID: 001
Revises:
Create Date: 2026-11-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create book_lists table
    op.create_table('book_lists',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('source_type', sa.String(length=50), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('list_date', sa.DateTime(), nullable=True),
    sa.Column('fetched_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_booklist_source', 'book_lists', ['source_type', 'list_date'], unique=False)
    op.create_index(op.f('ix_book_lists_id'), 'book_lists', ['id'], unique=False)

    # Create books table
    op.create_table('books',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('book_list_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('author', sa.String(length=500), nullable=True),
    sa.Column('isbn', sa.String(length=20), nullable=True),
    sa.Column('asin', sa.String(length=20), nullable=True),
    sa.Column('rank', sa.Integer(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('platform_id', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['book_list_id'], ['book_lists.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_book_asin', 'books', ['asin'], unique=False)
    op.create_index('idx_book_isbn', 'books', ['isbn'], unique=False)
    op.create_index('idx_book_title_author', 'books', ['title', 'author'], unique=False)
    op.create_index(op.f('ix_books_id'), 'books', ['id'], unique=False)

    # Create researches table
    op.create_table('researches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('book_id', sa.Integer(), nullable=False),
    sa.Column('themes', sa.JSON(), nullable=False),
    sa.Column('match_mode', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('progress', sa.Float(), nullable=True),
    sa.Column('current_step', sa.String(length=100), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('overall_assessment', sa.Enum('RECOMMENDED', 'INSUFFICIENT', 'NEEDS_REVIEW', 'NO_THEME_EVIDENCE', name='sufficiencylevel'), nullable=True),
    sa.Column('assessment_reasoning', sa.Text(), nullable=True),
    sa.Column('material_gaps', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['book_id'], ['books.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_researches_id'), 'researches', ['id'], unique=False)

    # Create theme_matches table
    op.create_table('theme_matches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('research_id', sa.Integer(), nullable=False),
    sa.Column('theme', sa.String(length=200), nullable=False),
    sa.Column('status', sa.Enum('CANDIDATE', 'PENDING', 'NO_EVIDENCE', name='matchstatus'), nullable=False),
    sa.Column('reasoning', sa.Text(), nullable=False),
    sa.Column('supporting_sources', sa.JSON(), nullable=True),
    sa.Column('evidence_quotes', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['research_id'], ['researches.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_theme_matches_id'), 'theme_matches', ['id'], unique=False)

    # Create sources table
    op.create_table('sources',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('research_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('source_type', sa.Enum('PROFESSIONAL_REVIEW', 'READER_REVIEW', 'PUBLISHER_DESCRIPTION', 'AUTHOR_INTERVIEW', 'NEWS_ARTICLE', 'ENCYCLOPEDIA', 'OTHER', 'IRRELEVANT', name='sourcetype'), nullable=False),
    sa.Column('source_classification_reasoning', sa.Text(), nullable=True),
    sa.Column('raw_content', sa.Text(), nullable=True),
    sa.Column('cleaned_content', sa.Text(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('key_points', sa.JSON(), nullable=True),
    sa.Column('fetch_status', sa.String(length=50), nullable=True),
    sa.Column('fetch_error', sa.Text(), nullable=True),
    sa.Column('fetched_at', sa.DateTime(), nullable=True),
    sa.Column('is_duplicate', sa.Integer(), nullable=True),
    sa.Column('duplicate_of', sa.Integer(), nullable=True),
    sa.Column('relevance_score', sa.Float(), nullable=True),
    sa.Column('is_about_target_book', sa.Integer(), nullable=True),
    sa.Column('book_identity_reasoning', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['duplicate_of'], ['sources.id'], ),
    sa.ForeignKeyConstraint(['research_id'], ['researches.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sources_id'), 'sources', ['id'], unique=False)

    # Create material_assessments table
    op.create_table('material_assessments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('research_id', sa.Integer(), nullable=False),
    sa.Column('book_identity_confirmed', sa.Integer(), nullable=True),
    sa.Column('book_identity_notes', sa.Text(), nullable=True),
    sa.Column('has_plot_summary', sa.Integer(), nullable=True),
    sa.Column('has_independent_reviews', sa.Integer(), nullable=True),
    sa.Column('has_author_background', sa.Integer(), nullable=True),
    sa.Column('has_multiple_perspectives', sa.Integer(), nullable=True),
    sa.Column('professional_review_count', sa.Integer(), nullable=True),
    sa.Column('independent_review_count', sa.Integer(), nullable=True),
    sa.Column('total_unique_sources', sa.Integer(), nullable=True),
    sa.Column('source_diversity_score', sa.Float(), nullable=True),
    sa.Column('content_depth_score', sa.Float(), nullable=True),
    sa.Column('identified_gaps', sa.JSON(), nullable=True),
    sa.Column('suggested_searches', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['research_id'], ['researches.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('research_id')
    )
    op.create_index(op.f('ix_material_assessments_id'), 'material_assessments', ['id'], unique=False)

    # Create scripts table (if needed for future podcast generation)
    op.create_table('scripts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('research_id', sa.Integer(), nullable=False),
    sa.Column('language', sa.String(length=10), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('word_count', sa.Integer(), nullable=True),
    sa.Column('estimated_duration_seconds', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['research_id'], ['researches.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scripts_id'), 'scripts', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scripts_id'), table_name='scripts')
    op.drop_table('scripts')
    op.drop_index(op.f('ix_material_assessments_id'), table_name='material_assessments')
    op.drop_table('material_assessments')
    op.drop_index(op.f('ix_sources_id'), table_name='sources')
    op.drop_table('sources')
    op.drop_index(op.f('ix_theme_matches_id'), table_name='theme_matches')
    op.drop_table('theme_matches')
    op.drop_index(op.f('ix_researches_id'), table_name='researches')
    op.drop_table('researches')
    op.drop_index(op.f('ix_books_id'), table_name='books')
    op.drop_index('idx_book_title_author', table_name='books')
    op.drop_index('idx_book_isbn', table_name='books')
    op.drop_index('idx_book_asin', table_name='books')
    op.drop_table('books')
    op.drop_index(op.f('ix_book_lists_id'), table_name='book_lists')
    op.drop_index('idx_booklist_source', table_name='book_lists')
    op.drop_table('book_lists')
