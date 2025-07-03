#!/usr/bin/env python3
"""
Script zum Erstellen der Migration für die Prospects-Tabelle
"""
import os
import sys

# Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

app = create_app()

# Migration manuell erstellen
migration_content = '''"""Add prospects table for registration app

Revision ID: add_prospects_table
Revises: 
Create Date: 2025-01-07 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_prospects_table'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create prospects table
    op.create_table('prospects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('address', sa.String(length=200), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('email', sa.String(length=100), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('geocoded_address', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    # Drop prospects table
    op.drop_table('prospects')
'''

# Migration-Datei erstellen
migrations_dir = 'migrations/versions'
os.makedirs(migrations_dir, exist_ok=True)

migration_file = os.path.join(migrations_dir, 'add_prospects_table.py')
with open(migration_file, 'w') as f:
    f.write(migration_content)

print(f"Migration erstellt: {migration_file}")
