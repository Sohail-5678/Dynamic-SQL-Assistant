import streamlit as st
import pandas as pd
import os
import tempfile
from io import StringIO
import urllib.request
from utils.database import create_database_from_csv, execute_query, clean_column_name
from utils.llm_service import get_sql_query

# Page configuration
st.set_page_config(
    page_title="Dynamic SQL Assistant",
    page_icon="🔍",
    layout="wide"
)

# App title and description
st.title("Dynamic SQL Assistant 🎯")
st.markdown("### Text-to-SQL Made Effortless!")
st.write("Upload a CSV file or enter a URL, then ask questions in plain English to get insights from your data.")

# Sidebar for data input
with st.sidebar:
    st.header("Data Source")
    data_source = st.radio("Choose your data source:", ["Upload CSV", "Enter CSV URL"])
    
    db_conn = None
    table_name = "data"
    df = None
    
    if data_source == "Upload CSV":
        uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                    tmp.write(uploaded_file.getvalue())
                    temp_path = tmp.name
                db_conn = create_database_from_csv(temp_path, table_name)
                st.success(f"Successfully loaded CSV with {df.shape[0]} rows and {df.shape[1]} columns.")
            except Exception as e:
                st.error(f"Error loading CSV: {e}")
    else:
        url = st.text_input("Enter the URL of a CSV file:")
        if url:
            try:
                with urllib.request.urlopen(url) as response:
                    csv_data = response.read().decode('utf-8')
                    df = pd.read_csv(StringIO(csv_data))
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                        tmp.write(csv_data.encode())
                        temp_path = tmp.name
                    db_conn = create_database_from_csv(temp_path, table_name)
                    st.success(f"Successfully loaded CSV with {df.shape[0]} rows and {df.shape[1]} columns.")
            except Exception as e:
                st.error(f"Error loading CSV from URL: {e}")
    
    # Display database schema if data is loaded
    if df is not None:
        st.subheader("Database Schema")
        schema_text = f"Table: {table_name}\n\nColumns:\n"
        for col in df.columns:
            dtype = str(df[col].dtype)
            schema_text += f"- {col} ({dtype})\n"
        st.text(schema_text)


# Main area for query input and results
if 'df' in locals() and df is not None:
    st.header("Ask Questions About Your Data")
    
    # Query input
    query = st.text_area("Enter your question in plain English:", height=100)
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Generate SQL & Execute", type="primary"):
            if query:
                with st.spinner("Generating SQL query..."):
                    # Get table info for context
                    table_info = "\n".join([f"- {col} ({df[col].dtype})" for col in df.columns])
                    
                    # Generate SQL from natural language
                    sql_query = get_sql_query(query, table_name, table_info)
                    
                    # Display the generated SQL
                    st.subheader("Generated SQL Query")
                    st.code(sql_query, language="sql")
                    
                    # Executing the query
                    with st.spinner("Executing query..."):
                        try:
                            result_df = execute_query(db_conn, sql_query)
                            
                            # Display results
                            st.subheader("Query Results")
                            st.dataframe(result_df, use_container_width=True)
                            
                            # Add download button for results
                            csv = result_df.to_csv(index=False)
                            st.download_button(
                                label="Download Results as CSV",
                                data=csv,
                                file_name="query_results.csv",
                                mime="text/csv"
                            )
                        except Exception as e:
                            st.error(f"Error executing query: {e}")
            else:
                st.warning("Please enter a question first.")
    
    # Example queries for user reference
    with st.expander("Example Questions"):
        st.markdown("""
        Try asking questions like:
        - What is the total count of records in the dataset?
        - Show me the top 5 rows with the highest values in [column]
        - What is the average of [column] grouped by [another column]?
        - How many unique values are there in [column]?
        - Show me all records where [column] contains [value]
        """)

    # Display s ample data with processed column names
    with st.expander("View Sample Data (with processed column names)"):
        # Create a copy of the dataframe with renamed columns
        display_df = df.copy()
        
        # Process column names the same way they're processed for the database
        processed_columns = [clean_column_name(col) for col in df.columns]
        
        # Create a mapping from original to processed column names
        column_mapping = {original: processed for original, processed in zip(df.columns, processed_columns)}
        
        # Rename the columns in the display dataframe
        display_df.columns = processed_columns
        
        # Show the mapping between original and processed column names
        st.write("#### Column Name Mapping")
        mapping_data = pd.DataFrame({
            "Original Column Name": column_mapping.keys(),
            "Processed Column Name (use this in queries)": column_mapping.values()
        })
        st.dataframe(mapping_data, use_container_width=True)
        
        # Show the sample data with processed column names
        st.write("#### Sample Data (first 10 rows)")
        st.dataframe(display_df.head(10), use_container_width=True)

else:
    # Display instructions when no data is loaded
    st.info("👈 Please upload a CSV file or provide a URL in the sidebar to get started.")
    
    # Example use cases
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

# Footer
st.markdown("---")
st.markdown(
    "Built with Streamlit, SQLite, LangChain, and Groq Llama 3 | "
    "[GitHub Repository](https://github.com/yourusername/dynamic-sql-assistant)"
)

# Clean up temporary files when the app is closed
def cleanup():
    if 'temp_path' in locals():
        try:
            os.unlink(temp_path)
        except:
            pass

# Register the cleanup function
import atexit
atexit.register(cleanup)
