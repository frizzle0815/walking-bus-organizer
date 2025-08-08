#!/bin/bash
set -e

# PostgreSQL Host-based Authentication für Docker-Netzwerk konfigurieren
echo "Konfiguriere PostgreSQL für Docker-Netzwerk..."

# Backup der originalen pg_hba.conf
cp /var/lib/postgresql/data/pg_hba.conf /var/lib/postgresql/data/pg_hba.conf.backup

# Füge Regel für Docker-Netzwerk hinzu
echo "host    all             all             172.16.0.0/12            trust" >> /var/lib/postgresql/data/pg_hba.conf

# Konfiguration neu laden
pg_ctl reload -D /var/lib/postgresql/data

echo "PostgreSQL-Konfiguration erfolgreich aktualisiert"
