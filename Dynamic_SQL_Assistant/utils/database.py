import sqlite3
import pandas as pd
import os

def create_database_from_csv(csv_path, table_name="data"):
    """
    Create an SQLite database from a CSV file
    
    Args:
        csv_path (str): Path to the CSV file
        table_name (str): Name of the table to create
        
    Returns:
        sqlite3.Connection: Database connection object
    """
    # Create an in-memory SQLite database
    conn = sqlite3.connect(':memory:')
    
    # Read the CSV file
    df = pd.read_csv(csv_path)
    
    # Clean column names (replace spaces with underscores, remove special characters)
    df.columns = [clean_column_name(col) for col in df.columns]
    
    # Write the dataframe to the SQLite table
    df.to_sql(table_name, conn, index=False, if_exists='replace')
    
    return conn

def clean_column_name(name):
    """
    Clean column names to be SQL-friendly
    
    Args:
        name (str): Original column name
        
    Returns:
        str: Cleaned column name
    """
    # Replace spaces with underscores
    clean_name = name.replace(' ', '_')
    
    # Remove special characters except underscores
    clean_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in clean_name)
    
    # Ensure the name doesn't start with a number
    if clean_name[0].isdigit():
        clean_name = 'col_' + clean_name
    
    return clean_name.lower()

def execute_query(conn, query):
    """
    Execute an SQL query on the database
    
    Args:
        conn (sqlite3.Connection): Database connection
        query (str): SQL query to execute
        
    Returns:
        pd.DataFrame: Query results as a dataframe
    """
    try:
        # Execute the query and return results as a dataframe
        return pd.read_sql_query(query, conn)
    except Exception as e:
        # If there's an error, try to fix common issues
        error_str = str(e).lower()
        
        if "no such column" in error_str:
            # Get the actual column names from the database
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM pragma_table_info('data')")
            actual_columns = [row[0] for row in cursor.fetchall()]
            
            # Try different quoting styles
            # First attempt: Try with backticks
            modified_query = query.replace('"', '`')
            try:
                return pd.read_sql_query(modified_query, conn)
            except:
                pass
                
            # Second attempt: Try without quotes
            for col in actual_columns:
                if ' ' in col:
                    # If column has spaces, try using the cleaned version
                    clean_col = clean_column_name(col)
                    modified_query = query.replace(f'"{col}"', clean_col)
                    try:
                        return pd.read_sql_query(modified_query, conn)
                    except:
                        pass
            
            # Third attempt: Try each column from the database
            for col in actual_columns:
                if "raw" in col.lower() and "predict" in col.lower():
                    # This might be the column we're looking for
                    modified_query = query.replace('"raw predicted"', f'"{col}"')
                    try:
                        return pd.read_sql_query(modified_query, conn)
                    except:
                        pass
        
        # If we couldn't fix it or it's another type of error, re-raise
        raise Exception(f"Query error: {e}\n\nAvailable columns: {', '.join(actual_columns)}")


def find_closest_column(problem_col, actual_columns):
    """
    Find the closest matching column name
    
    Args:
        problem_col (str): Problematic column name
        actual_columns (list): List of actual column names
        
    Returns:
        str: Closest matching column name or None
    """
    # Simple case-insensitive match
    for col in actual_columns:
        if col.lower() == problem_col.lower():
            return col
    
    # If no exact match (ignoring case), return None
    return None
