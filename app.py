import streamlit as st
import pandas as pd
import os
import tempfile
import logging
from io import StringIO
import urllib.request
from utils.database import create_database_from_csv, execute_query, clean_column_name
from utils.llm_service import get_sql_query

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Page Configuration ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dynamic SQL Assistant",
    page_icon="🔍",
    layout="wide",
)

# ─── Session-state initialisation ──────────────────────────────────────────────
# Using session_state for persistence across Streamlit reruns instead of locals()
if "db_conn" not in st.session_state:
    st.session_state.db_conn = None
if "df" not in st.session_state:
    st.session_state.df = None
if "temp_path" not in st.session_state:
    st.session_state.temp_path = None
if "query_history" not in st.session_state:
    st.session_state.query_history = []

# ─── App Title ─────────────────────────────────────────────────────────────────
st.title("Dynamic SQL Assistant 🎯")
st.markdown("### Text-to-SQL Made Effortless!")
st.write(
    "Upload a CSV file or enter a URL, then ask questions in plain English "
    "to get insights from your data."
)

# ─── Sidebar: Data Source ──────────────────────────────────────────────────────
TABLE_NAME = "data"

with st.sidebar:
    st.header("Data Source")
    data_source = st.radio(
        "Choose your data source:", ["Upload CSV", "Enter CSV URL"]
    )

    if data_source == "Upload CSV":
        uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".csv"
                ) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    temp_path = tmp.name

                st.session_state.db_conn = create_database_from_csv(
                    temp_path, TABLE_NAME
                )
                st.session_state.df = df
                st.session_state.temp_path = temp_path
                st.success(
                    f"✅ Loaded CSV — {df.shape[0]} rows × {df.shape[1]} columns."
                )
                logger.info("CSV uploaded: %s rows, %s cols", *df.shape)
            except Exception as e:
                st.error(f"Error loading CSV: {e}")
                logger.exception("CSV upload failed")
    else:
        url = st.text_input("Enter the URL of a CSV file:")
        if url:
            try:
                with urllib.request.urlopen(url, timeout=30) as response:
                    csv_data = response.read().decode("utf-8")
                    df = pd.read_csv(StringIO(csv_data))
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".csv"
                    ) as tmp:
                        tmp.write(csv_data.encode())
                        temp_path = tmp.name

                    st.session_state.db_conn = create_database_from_csv(
                        temp_path, TABLE_NAME
                    )
                    st.session_state.df = df
                    st.session_state.temp_path = temp_path
                    st.success(
                        f"✅ Loaded CSV — {df.shape[0]} rows × {df.shape[1]} columns."
                    )
                    logger.info("CSV from URL: %s rows, %s cols", *df.shape)
            except Exception as e:
                st.error(f"Error loading CSV from URL: {e}")
                logger.exception("CSV URL load failed")

    # Display database schema if data is loaded
    if st.session_state.df is not None:
        st.subheader("Database Schema")
        schema_lines = [f"Table: {TABLE_NAME}\n\nColumns:"]
        for col in st.session_state.df.columns:
            dtype = str(st.session_state.df[col].dtype)
            schema_lines.append(f"- {col} ({dtype})")
        st.text("\n".join(schema_lines))


# ─── Main Area ─────────────────────────────────────────────────────────────────
if st.session_state.df is not None:
    df = st.session_state.df
    db_conn = st.session_state.db_conn

    st.header("Ask Questions About Your Data")

    # Query input
    query = st.text_area("Enter your question in plain English:", height=100)

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Generate SQL & Execute", type="primary"):
            if query:
                with st.spinner("Generating SQL query..."):
                    # Build table schema string for the LLM prompt
                    table_info = "\n".join(
                        [f"- {clean_column_name(col)} ({df[col].dtype})" for col in df.columns]
                    )

                    # Generate SQL from natural language
                    sql_query = get_sql_query(query, TABLE_NAME, table_info)

                    # Display the generated SQL
                    st.subheader("Generated SQL Query")
                    st.code(sql_query, language="sql")

                    # Execute the query
                    with st.spinner("Executing query..."):
                        try:
                            result_df = execute_query(db_conn, sql_query)

                            # Save to history
                            st.session_state.query_history.append({
                                "question": query,
                                "sql": sql_query,
                                "rows_returned": len(result_df),
                            })

                            # Display results
                            st.subheader("Query Results")
                            st.dataframe(result_df, use_container_width=True)

                            # Download button
                            csv_out = result_df.to_csv(index=False)
                            st.download_button(
                                label="Download Results as CSV",
                                data=csv_out,
                                file_name="query_results.csv",
                                mime="text/csv",
                            )
                        except ValueError as ve:
                            st.error(f"🛡️ Security check failed: {ve}")
                            logger.warning("Query blocked: %s", ve)
                        except Exception as e:
                            st.error(f"Error executing query: {e}")
                            logger.exception("Query execution error")
            else:
                st.warning("Please enter a question first.")

    # Example queries
    with st.expander("Example Questions"):
        st.markdown("""
        Try asking questions like:
        - What is the total count of records in the dataset?
        - Show me the top 5 rows with the highest values in [column]
        - What is the average of [column] grouped by [another column]?
        - How many unique values are there in [column]?
        - Show me all records where [column] contains [value]
        """)

    # Sample data viewer
    with st.expander("View Sample Data (with processed column names)"):
        display_df = df.copy()
        processed_columns = [clean_column_name(col) for col in df.columns]
        column_mapping = dict(zip(df.columns, processed_columns))
        display_df.columns = processed_columns

        st.write("#### Column Name Mapping")
        mapping_data = pd.DataFrame({
            "Original Column Name": list(column_mapping.keys()),
            "Processed Column Name (use this in queries)": list(column_mapping.values()),
        })
        st.dataframe(mapping_data, use_container_width=True)

        st.write("#### Sample Data (first 10 rows)")
        st.dataframe(display_df.head(10), use_container_width=True)

    # Query history
    if st.session_state.query_history:
        with st.expander("Query History"):
            for i, entry in enumerate(reversed(st.session_state.query_history), 1):
                st.markdown(f"**{i}. {entry['question']}**")
                st.code(entry["sql"], language="sql")
                st.caption(f"Returned {entry['rows_returned']} rows")

else:
    # Instructions when no data is loaded
    st.info("👈 Please upload a CSV file or provide a URL in the sidebar to get started.")

    st.header("Example Use Cases")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Educational Data Analysis")
        st.write("Upload student data and ask questions like:")
        st.write("- List all students whose nationality is Jordan")
        st.write("- What's the average grade by department?")
        st.write("- Show me students with GPA higher than 3.5")

    with col2:
        st.subheader("Titanic Dataset Insights")
        st.write("Upload the Titanic dataset and ask questions like:")
        st.write("- How many children (age < 18) survived?")
        st.write("- What was the survival rate by passenger class?")
        st.write("- Show the average age of passengers by gender")

# ─── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "Built with Streamlit, SQLite, LangChain, and Groq Llama 3 | "
    "[GitHub Repository](https://github.com/yourusername/dynamic-sql-assistant)"
)

# ─── Cleanup ───────────────────────────────────────────────────────────────────
# Clean up temp files using session_state (fixes the broken locals() approach)
import atexit

def cleanup():
    """Remove temporary CSV files created during the session."""
    temp = st.session_state.get("temp_path")
    if temp and os.path.exists(temp):
        try:
            os.unlink(temp)
            logger.info("Cleaned up temp file: %s", temp)
        except Exception:
            pass

atexit.register(cleanup)
