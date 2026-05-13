# Dynamic SQL Assistant 🎯

A **Text-to-SQL** application that lets users upload any CSV dataset and query it using plain English. The app converts natural language questions into SQL queries using **Groq's Llama 3 70B** model, executes them against an in-memory **SQLite** database, and displays results in an interactive **Streamlit** dashboard.

## Architecture

```
User (Plain English Question)
        │
        ▼
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Streamlit UI   │────▶│  LLM Service     │────▶│  Groq API      │
│  (app.py)       │     │  (llm_service.py)│     │  (Llama 3 70B) │
└─────────────────┘     └──────────────────┘     └────────────────┘
        │                        │
        │                  SQL Query (generated)
        ▼                        │
┌─────────────────┐              │
│  SQL Validator   │◀────────────┘
│  (database.py)   │
└─────────────────┘
        │
        ▼ (if safe)
┌─────────────────┐
│  SQLite (in-mem) │
│  (database.py)   │
└─────────────────┘
        │
        ▼
   Query Results (DataFrame)
```

## Features

- **CSV Upload or URL**: Load data from a local file or a remote URL
- **Natural Language to SQL**: Ask questions in plain English — get SQL automatically
- **In-Memory SQLite**: Fast, ephemeral database created from your CSV
- **SQL Injection Protection**: Validates all generated queries are read-only SELECT statements
- **Query History**: Track all questions and generated SQL in the session
- **Download Results**: Export query results as CSV
- **Schema Viewer**: See the database schema and column name mappings

## Tech Stack

| Component       | Technology                        |
|-----------------|-----------------------------------|
| Frontend / UI   | Streamlit                         |
| LLM             | Groq Llama 3 70B (via LangChain) |
| Database        | SQLite (in-memory)                |
| Orchestration   | LangChain (LCEL)                  |
| Language        | Python 3.10+                      |

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/dynamic-sql-assistant.git
cd dynamic-sql-assistant
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API key
Create `.streamlit/secrets.toml`:
```toml
GROQ_API_KEY = "your_groq_api_key_here"
```
> ⚠️ **Never commit this file to git.** It is listed in `.gitignore`.

### 5. Run the application
```bash
streamlit run app.py
```

## Project Structure

```
Dynamic_SQL_Assistant/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Pinned Python dependencies
├── .gitignore                  # Git ignore rules
├── .streamlit/
│   └── secrets.toml            # API key (NOT committed)
└── utils/
    ├── __init__.py             # Package marker
    ├── database.py             # SQLite operations & SQL validation
    ├── llm_service.py          # LLM integration (Groq/LangChain)
    └── prompt_templates.py     # Prompt engineering templates
```

## Security

- All LLM-generated SQL is validated before execution
- Only `SELECT` and `WITH` (CTE) statements are allowed
- Destructive keywords (`DROP`, `DELETE`, `INSERT`, etc.) are blocked
- Multiple statements (`;` separated) are rejected
- CSV file size is capped at 50 MB

## License

MIT
