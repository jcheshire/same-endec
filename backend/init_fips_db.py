#!/usr/bin/env python3
"""
Initialize FIPS code database for SAME encoder/decoder
Downloads FIPS county codes and loads them into SQLite database

SPDX-License-Identifier: MIT
Copyright (c) 2025 Josh Cheshire
"""

import sqlite3
import csv
import urllib.request
import os

# Database configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'fips_codes.db')
FIPS_CSV_URL = 'https://raw.githubusercontent.com/kjhealy/fips-codes/master/state_and_county_fips_master.csv'

def create_database():
    """Create SQLite database with FIPS codes table"""
    print(f"Creating database at {DB_PATH}...")

    # Remove existing database if present
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # Create database and table
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE fips_codes (
            fips TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            state TEXT,
            type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create indexes for faster lookups
    cursor.execute('CREATE INDEX idx_state ON fips_codes(state)')
    cursor.execute('CREATE INDEX idx_name ON fips_codes(name)')
    cursor.execute('CREATE INDEX idx_type ON fips_codes(type)')

    conn.commit()
    conn.close()
    print("Database created successfully")


def download_fips_data():
    """Download FIPS codes CSV from GitHub"""
    print(f"Downloading FIPS data from {FIPS_CSV_URL}...")

    try:
        with urllib.request.urlopen(FIPS_CSV_URL) as response:
            csv_data = response.read().decode('utf-8')

        print(f"Downloaded {len(csv_data)} bytes")
        return csv_data

    except Exception as e:
        print(f"Error downloading FIPS data: {e}")
        raise


def load_fips_data(csv_data):
    """Load FIPS codes from CSV into database"""
    print("Loading FIPS data into database...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Parse CSV
    csv_reader = csv.DictReader(csv_data.splitlines())

    count = 0
    for row in csv_reader:
        fips = row['fips'].strip()
        name = row['name'].strip()
        state = row['state'].strip() if row['state'] != 'NA' else None

        # Determine type based on FIPS code and state
        if fips == '0':
            type_val = 'national'
        elif len(fips) == 4 and fips.endswith('000'):
            type_val = 'state'
        elif state:
            type_val = 'county'
        else:
            type_val = 'other'

        cursor.execute(
            'INSERT INTO fips_codes (fips, name, state, type) VALUES (?, ?, ?, ?)',
            (fips, name, state, type_val)
        )
        count += 1

    conn.commit()
    conn.close()

    print(f"Loaded {count} FIPS codes into database")


def verify_database():
    """Verify database contents"""
    print("\nVerifying database...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get counts by type
    cursor.execute('SELECT type, COUNT(*) FROM fips_codes GROUP BY type ORDER BY type')
    for type_val, count in cursor.fetchall():
        print(f"  {type_val}: {count} entries")

    # Show some sample entries
    print("\nSample county entries:")
    cursor.execute(
        'SELECT fips, name, state FROM fips_codes WHERE type = "county" LIMIT 5'
    )
    for fips, name, state in cursor.fetchall():
        print(f"  {fips}: {name}, {state}")

    conn.close()
    print("\nDatabase verification complete")


def main():
    """Main initialization function"""
    print("=" * 60)
    print("FIPS Code Database Initialization")
    print("=" * 60)
    print()

    try:
        # Create database structure
        create_database()

        # Download FIPS data
        csv_data = download_fips_data()

        # Load data into database
        load_fips_data(csv_data)

        # Verify
        verify_database()

        print()
        print("=" * 60)
        print("Initialization complete!")
        print(f"Database location: {DB_PATH}")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
