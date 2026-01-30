"""Initial migration - create price collection tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create store_type enum
    store_type = postgresql.ENUM('ebay', 'amazon', 'walmart', name='storetype')
    store_type.create(op.get_bind(), checkfirst=True)
    
    # Create item_condition enum
    item_condition = postgresql.ENUM('new', 'used', 'refurbished', 'for_parts', 'unknown', name='itemcondition')
    item_condition.create(op.get_bind(), checkfirst=True)
    
    # Create listing_type enum
    listing_type = postgresql.ENUM('buy_it_now', 'auction', 'auction_with_bin', name='listingtype')
    listing_type.create(op.get_bind(), checkfirst=True)
    
    # Create tracked_items table
    op.create_table(
        'tracked_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('store', sa.Enum('ebay', 'amazon', 'walmart', name='storetype'), nullable=False),
        sa.Column('item_id', sa.String(50), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('seller_id', sa.String(100), nullable=True),
        sa.Column('seller_name', sa.String(255), nullable=True),
        sa.Column('condition', sa.Enum('new', 'used', 'refurbished', 'for_parts', 'unknown', name='itemcondition'), nullable=True),
        sa.Column('listing_type', sa.Enum('buy_it_now', 'auction', 'auction_with_bin', name='listingtype'), nullable=True),
        sa.Column('item_url', sa.Text(), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_collected_at', sa.DateTime(), nullable=True),
        sa.Column('collection_error_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_tracked_items_store_item', 'tracked_items', ['store', 'item_id'], unique=True)
    op.create_index('idx_tracked_items_active', 'tracked_items', ['is_active'])
    op.create_index('idx_tracked_items_last_collected', 'tracked_items', ['last_collected_at'])
    
    # Create price_history table
    op.create_table(
        'price_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('store', sa.Enum('ebay', 'amazon', 'walmart', name='storetype'), nullable=False),
        sa.Column('item_id', sa.String(50), nullable=False),
        sa.Column('price', sa.Numeric(12, 2), nullable=False),
        sa.Column('shipping_fee', sa.Numeric(12, 2), nullable=True, default=0),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('normalized_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('normalized_total', sa.Numeric(12, 2), nullable=False),
        sa.Column('normalized_currency', sa.String(3), nullable=True, default='USD'),
        sa.Column('includes_shipping', sa.Boolean(), nullable=True, default=False),
        sa.Column('includes_tax', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_sale_price', sa.Boolean(), nullable=True, default=False),
        sa.Column('original_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('bid_count', sa.Integer(), nullable=True),
        sa.Column('auction_end_time', sa.DateTime(), nullable=True),
        sa.Column('collected_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('collection_method', sa.String(20), nullable=True, default='api'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_price_history_store_item', 'price_history', ['store', 'item_id'])
    op.create_index('idx_price_history_collected', 'price_history', ['collected_at'])
    op.create_index('idx_price_history_item_time', 'price_history', ['store', 'item_id', 'collected_at'])
    
    # Create price_alerts table
    op.create_table(
        'price_alerts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('store', sa.Enum('ebay', 'amazon', 'walmart', name='storetype'), nullable=False),
        sa.Column('item_id', sa.String(50), nullable=False),
        sa.Column('target_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('price_drop_percentage', sa.Numeric(5, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('triggered_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.String(50), nullable=True),
        sa.Column('notification_email', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_price_alerts_store_item', 'price_alerts', ['store', 'item_id'])
    op.create_index('idx_price_alerts_active', 'price_alerts', ['is_active'])


def downgrade() -> None:
    op.drop_table('price_alerts')
    op.drop_table('price_history')
    op.drop_table('tracked_items')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS listingtype')
    op.execute('DROP TYPE IF EXISTS itemcondition')
    op.execute('DROP TYPE IF EXISTS storetype')
