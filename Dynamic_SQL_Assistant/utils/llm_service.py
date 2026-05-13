import streamlit as st
import logging
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.prompt_templates import SQL_GENERATION_TEMPLATE

logger = logging.getLogger(__name__)


def get_llm():
    """
    Initialize and return the Groq LLM (Llama 3 70B).

    Reads the API key from Streamlit secrets and returns a configured
    ChatGroq instance with low temperature for deterministic SQL generation.

    Returns:
        ChatGroq: Initialized LLM model

    Raises:
        SystemExit: If the GROQ_API_KEY is missing (via st.stop())
    """
    # Check if Groq API key exists in Streamlit secrets
    if "GROQ_API_KEY" not in st.secrets:
        st.error(
            "GROQ_API_KEY not found in Streamlit secrets. "
            "Please add it to `.streamlit/secrets.toml`."
        )
        st.stop()

    api_key = st.secrets["GROQ_API_KEY"]
    if not api_key or not api_key.strip():
        st.error("GROQ_API_KEY is empty. Please provide a valid API key.")
        st.stop()

    # Initialize the Groq LLM with Llama 3
    return ChatGroq(
        api_key=api_key,
        model_name="llama3-70b-8192",  # Llama 3 70B model
        temperature=0.1,  # Low temperature for more deterministic SQL output
        max_tokens=1024,
    )


def get_sql_query(question, table_name, table_info):
    """
    Generate an SQL query from a natural language question using LCEL.

    Pipeline:  PromptTemplate → ChatGroq → StrOutputParser → SQL extraction

    Args:
        question (str): Natural language question from the user
        table_name (str): Name of the SQLite table to query
        table_info (str): Schema description (column names and types)

    Returns:
        str: Generated SQL query string
    """
    llm = get_llm()

    # Build the LCEL chain: Prompt → LLM → Output Parser
    prompt = PromptTemplate(
        template=SQL_GENERATION_TEMPLATE,
        input_variables=["question", "table_name", "table_info"],
    )
    chain = prompt | llm | StrOutputParser()

    logger.info("Generating SQL for question: %s", question)

    # Invoke the chain
    response = chain.invoke({
        "question": question,
        "table_name": table_name,
        "table_info": table_info,
    })

    logger.info("Raw LLM response: %s", response)

    # Extract the SQL query from the response
    sql_query = extract_sql_from_response(response)
    logger.info("Extracted SQL query: %s", sql_query)

    return sql_query


def extract_sql_from_response(response):
    """
    Extract a SQL query from the LLM's response text.

    Handles three cases:
      1. Response contains a ```sql ... ``` fenced code block → extract it
      2. Response contains a SELECT/WITH keyword → use as-is
      3. Fallback → return the raw response stripped of whitespace

    Args:
        response (str): Raw LLM response text

    Returns:
        str: Cleaned SQL query string
    """
    response = response.strip()

    # Case 1: SQL fenced code block
    if "```sql" in response:
        parts = response.split("```sql")
        if len(parts) > 1:
            sql_part = parts[1].split("```")[0].strip()
            if sql_part:
                return sql_part

    # Case 2: Generic fenced code block
    if "```" in response:
        parts = response.split("```")
        if len(parts) >= 3:
            sql_part = parts[1].strip()
            # Remove optional language identifier on the first line
            lines = sql_part.split('\n')
            if lines and lines[0].strip().isalpha():
                sql_part = '\n'.join(lines[1:]).strip()
            if sql_part:
                return sql_part

    # Case 3: Look for SELECT or WITH keyword
    upper = response.upper()
    if "SELECT" in upper or "WITH" in upper:
        return response.strip()

    # Fallback
    return response.strip()
