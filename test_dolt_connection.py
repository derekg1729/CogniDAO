#!/usr/bin/env python3
"""Test connection to Docker Dolt SQL server."""

import mysql.connector


def test_dolt_connection():
    """Test connection to Docker Dolt SQL server."""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="root",
            password="kXMnM6firYohXzK+2r0E0DmSjOl6g3A2SmXc6ALDOlA=",
            database="cogni-dao-memory",
        )
        cursor = conn.cursor()

        # Test basic connection
        cursor.execute("SELECT 1 as test_connection")
        result = cursor.fetchone()
        print(f"✅ Connection successful: {result}")

        # Check current branch
        cursor.execute("SELECT active_branch() as current_branch")
        branch = cursor.fetchone()
        print(f"✅ Current branch: {branch}")

        # List existing tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"✅ Existing tables: {[table[0] for table in tables]}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    test_dolt_connection()
