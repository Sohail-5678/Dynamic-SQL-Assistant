import streamlit as st
from langchain_groq import ChatGroq
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from utils.prompt_templates import SQL_GENERATION_TEMPLATE

def get_llm():
    """
    Initialize and return the LLM model
    
    Returns:
        ChatGroq: Initialized LLM model
    """
    # Check if Groq API key exists in Streamlit secrets
    if "GROQ_API_KEY" not in st.secrets:
        st.error("GROQ_API_KEY not found in Streamlit secrets. Please add it to .streamlit/secrets.toml")
        st.stop()
    
    # Initialize the Groq LLM with Llama 3
    return ChatGroq(
        api_key=st.secrets["GROQ_API_KEY"],
        model_name="llama3-70b-8192",  # Using Llama 3 70B model
        temperature=0.1,  # Low temperature for more deterministic outputs
        max_tokens=1024
    )

def get_sql_query(question, table_name, table_info):
    """
    Generate an SQL query from a natural language question
    
    Args:
        question (str): Natural language question
        table_name (str): Name of the table to query
        table_info (str): Information about the table schema
        
    Returns:
        str: Generated SQL query
    """
    # Initialize the LLM
    llm = get_llm()
    
    # Create prompt template
    prompt = PromptTemplate(
        template=SQL_GENERATION_TEMPLATE,
        input_variables=["question", "table_name", "table_info"]
    )
    
    # Create LLM chain
    chain = LLMChain(llm=llm, prompt=prompt)
    
    # Generate SQL query
    response = chain.run(
        question=question,
        table_name=table_name,
        table_info=table_info
    )
    
    # Extract the SQL query from the response
    # The model should return just the SQL, but we'll handle potential formatting issues
    sql_query = extract_sql_from_response(response)
    
    return sql_query

def extract_sql_from_response(response):
    """
    Extract SQL query from the LLM response
    
    Args:
        response (str): LLM response
        
    Returns:
        str: Extracted SQL query
    """
    # Check if the response contains SQL code blocks
    if "```sql" in response:
        # Extract SQL from code blocks
        parts = response.split("```sql")
        if len(parts) > 1:
            sql_part = parts[1].split("```")[0].strip()
            return sql_part
    
    # If no code blocks, check for SELECT keyword
    if "SELECT" in response.upper() or "select" in response.lower():
        # Assume the whole response is the SQL query
        return response.strip()
    
    # Fallback: return the entire response
    return response.strip()
