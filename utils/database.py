import sqlite3
import pandas as pd
import os
import logging
import re

logger = logging.getLogger(__name__)

# Maximum CSV file size: 50 MB
MAX_CSV_SIZE_BYTES = 50 * 1024 * 1024

# SQL keywords that indicate a write/destructive operation
DANGEROUS_SQL_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|VACUUM|REINDEX)\b',
    re.IGNORECASE
)


def create_database_from_csv(csv_path, table_name="data"):
    """
    Create an in-memory SQLite database from a CSV file.

    Args:
        csv_path (str): Path to the CSV file
        table_name (str): Name of the table to create

    Returns:
        sqlite3.Connection: Database connection object

    Raises:
        ValueError: If the CSV file exceeds size limits or is empty
        FileNotFoundError: If the CSV file doesn't exist
    """
    # --- Input validation ---
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    file_size = os.path.getsize(csv_path)
    if file_size > MAX_CSV_SIZE_BYTES:
        raise ValueError(
            f"CSV file is too large ({file_size / (1024*1024):.1f} MB). "
            f"Maximum allowed size is {MAX_CSV_SIZE_BYTES / (1024*1024):.0f} MB."
        )

    if file_size == 0:
        raise ValueError("CSV file is empty.")

    # Create an in-memory SQLite database
    conn = sqlite3.connect(':memory:')
    logger.info("Created in-memory SQLite database.")

    # Read the CSV file
    df = pd.read_csv(csv_path)

    if df.empty:
        conn.close()
        raise ValueError("CSV file contains no data rows.")

    # Clean column names (replace spaces with underscores, remove special characters)
    original_columns = list(df.columns)
    df.columns = [clean_column_name(col) for col in df.columns]
    logger.info(
        "Column name mapping: %s",
        dict(zip(original_columns, df.columns))
    )

    # Write the dataframe to the SQLite table
    df.to_sql(table_name, conn, index=False, if_exists='replace')
    logger.info(
        "Loaded %d rows and %d columns into table '%s'.",
        len(df), len(df.columns), table_name
    )

    return conn


def clean_column_name(name):
    """
    Clean column names to be SQL-friendly.

    Transformations applied:
      1. Replace spaces with underscores
      2. Replace any non-alphanumeric character (except underscore) with underscore
      3. Prefix with 'col_' if the name starts with a digit
      4. Convert to lowercase

    Args:
        name (str): Original column name

    Returns:
        str: Cleaned column name
    """
    # Replace spaces with underscores
    clean_name = name.replace(' ', '_')

    # Remove special characters except underscores
    clean_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in clean_name)

    # Collapse multiple consecutive underscores
    clean_name = re.sub(r'_+', '_', clean_name).strip('_')

    # Ensure the name doesn't start with a number
    if clean_name and clean_name[0].isdigit():
        clean_name = 'col_' + clean_name

    # Handle edge case of empty name after cleaning
    if not clean_name:
        clean_name = 'unnamed_column'

    return clean_name.lower()


def validate_sql_query(query):
    """
    Validate that a SQL query is safe to execute (read-only).

    Args:
        query (str): SQL query string

    Returns:
        bool: True if the query is safe, False otherwise.

    Raises:
        ValueError: If the query is deemed unsafe.
    """
    stripped = query.strip().rstrip(';').strip()

    # Block multiple statements
    # Split on semicolons that aren't inside quotes (simplified check)
    statements = [s.strip() for s in stripped.split(';') if s.strip()]
    if len(statements) > 1:
        raise ValueError("Multiple SQL statements are not allowed.")

    # Block dangerous keywords
    if DANGEROUS_SQL_KEYWORDS.search(stripped):
        raise ValueError(
            "Only SELECT queries are allowed. "
            "Detected a potentially destructive SQL keyword."
        )

    # Must start with SELECT (or WITH for CTEs)
    first_word = stripped.split()[0].upper() if stripped.split() else ''
    if first_word not in ('SELECT', 'WITH'):
        raise ValueError(
            f"Only SELECT queries are allowed. Query starts with '{first_word}'."
        )

    return True


def execute_query(conn, query):
    """
    Validate and execute a SQL query on the database.

    Args:
        conn (sqlite3.Connection): Database connection
        query (str): SQL query to execute

    Returns:
        pd.DataFrame: Query results as a dataframe

    Raises:
        ValueError: If the query is unsafe
        Exception: If the query fails to execute
    """
    # --- Security: validate query before execution ---
    validate_sql_query(query)

    try:
        # Execute the query and return results as a dataframe
        result = pd.read_sql_query(query, conn)
        logger.info("Query executed successfully. Returned %d rows.", len(result))
        return result
    except Exception as e:
        error_str = str(e).lower()

        # Get the actual column names from the database for error messages
        actual_columns = _get_table_columns(conn)

        if "no such column" in error_str and actual_columns:
            # Try automatic column-name fix-up
            fixed_result = _attempt_column_fix(conn, query, actual_columns)
            if fixed_result is not None:
                return fixed_result

        # Re-raise with helpful context
        col_list = ', '.join(actual_columns) if actual_columns else 'unknown'
        raise Exception(
            f"Query execution error: {e}\n\nAvailable columns: {col_list}"
        )


def _get_table_columns(conn, table_name="data"):
    """Retrieve the column names from a table."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM pragma_table_info('{table_name}')")
        return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []


def _attempt_column_fix(conn, query, actual_columns):
    """
    Attempt to fix column-name mismatches in a query.

    Tries several heuristics:
      1. Replace double-quotes with backticks
      2. Replace quoted column names with their cleaned equivalents

    Returns a DataFrame on success, or None on failure.
    """
    # Attempt 1: Replace double-quotes with backticks
    modified = query.replace('"', '`')
    try:
        validate_sql_query(modified)
        return pd.read_sql_query(modified, conn)
    except Exception:
        pass

    # Attempt 2: Replace quoted column names with cleaned versions
    for col in actual_columns:
        if ' ' in col:
            clean_col = clean_column_name(col)
            modified = query.replace(f'"{col}"', clean_col)
            try:
                validate_sql_query(modified)
                return pd.read_sql_query(modified, conn)
            except Exception:
                pass

    return None


def find_closest_column(problem_col, actual_columns):
    """
    Find the closest matching column name (case-insensitive).

    Args:
        problem_col (str): Problematic column name
        actual_columns (list): List of actual column names

    Returns:
        str or None: Closest matching column name, or None if no match
    """
    for col in actual_columns:
        if col.lower() == problem_col.lower():
            return col
    return None
