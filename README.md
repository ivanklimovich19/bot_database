# Botanical Database

A web-based information system for storage, processing, and analysis of taxonomic and morphological (phenomic) data of plants. Developed for the Laboratory of Flora and Plant Systematics.

## Features

- Storage of taxonomic hierarchy (family → genus → species)
- Herbarium specimen records with metadata (collector, date, locality)
- Flexible addition of morphological traits without schema migration (EAV model)
- Upload and display of herbarium specimen images
- Multi-criteria filtering and global text search
- Bulk import from Excel (.xlsx) and export to CSV and Excel
- Interactive visualisation: scatter, boxplot, violin, histogram
- Record deletion with cascading removal of associated measurements
- Concurrent access for multiple laboratory staff members

## Technology Stack

- **Python 3.11+**
- **SQLAlchemy 2.0.x** — ORM for database access
- **PostgreSQL 15** — primary DBMS
- **Streamlit** — web interface
- **Plotly, Seaborn, Matplotlib** — visualisation
- **pandas, openpyxl** — data import and export
- **psycopg2-binary** — PostgreSQL driver

## Project Structure

```
.
├── app.py                 # Main Streamlit application
├── models.py              # ORM models (SQLAlchemy)
├── config.py              # Database connection settings
├── init_db.py             # Initial database setup script
├── benchmark.py           # Load testing script
├── requirements.txt       # Dependency list
├── .env.example           # Environment variables template
├── .gitignore
├── README.md              # This file
└── uploads/               # Folder for uploaded images (created automatically)
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/ivanklimovich19/bot_database.git
cd bot_database
```

### 2. Create a virtual environment

**Windows:**

```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install and configure PostgreSQL

Install PostgreSQL 15 or newer from the official website: https://www.postgresql.org/download/

Create the database and a dedicated user:

```sql
CREATE DATABASE botanica;
CREATE USER myuser WITH PASSWORD 'mypass';
GRANT ALL PRIVILEGES ON DATABASE botanica TO myuser;
```

For PostgreSQL 15+ you may also need to grant privileges on the `public` schema:

```sql
\c botanica
GRANT ALL ON SCHEMA public TO myuser;
```

### 5. Configure environment variables

Copy the template:

```bash
cp .env.example .env
```

Edit `.env` and provide your connection parameters:

```
DB_USER=myuser
DB_PASSWORD=mypass
DB_HOST=localhost
DB_PORT=5432
DB_NAME=botanica
```

### 6. Initialise the database

```bash
python init_db.py
```

This will create the tables and populate them with sample data (families, genera, species, traits).

## Running the Application

```bash
streamlit run app.py
```

The application will open in your browser at: http://localhost:8501

To allow access from the local network:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## Load Testing

The `benchmark.py` script reproduces the performance results reported in the accompanying publication.

### Read-only mode (does not modify data)

```bash
python benchmark.py
```

### With synthetic data generation

```bash
python benchmark.py --seed --seed-specimens 10000 --runs 30 --allow-write
```

### Command-line options

| Flag | Purpose | Default |
|------|---------|---------|
| `--seed` | Generate synthetic data | off |
| `--seed-specimens N` | Number of specimens to generate | 10,000 |
| `--seed-families N` | Number of families | 20 |
| `--seed-traits N` | Number of traits | 50 |
| `--runs N` | Repetitions per scenario | 30 |
| `--allow-write` | Include batch import test (with rollback) | off |
| `--out PREFIX` | Prefix for output files | `benchmark` |

### Output

After execution, three files are produced:

- `benchmark_results.csv` — table for external processing
- `benchmark_results.json` — structured representation with metadata
- `benchmark_summary.txt` — summary ready for inclusion in a publication

**WARNING:** the `--seed` flag adds data to the database. Do not run it on a production database — use a separate test database.

## Deployment on Streamlit Cloud

1. Fork the repository or use your own.
2. Go to https://share.streamlit.io.
3. Click **New app**, select the repository, branch `main`, and file `app.py`.
4. In the **Secrets** section, add the following variable:

```
DATABASE_URL = "postgresql://user:password@host:5432/dbname?sslmode=require"
```

5. Click **Deploy**.

## License

This project is distributed under the **MIT License**. See the `LICENSE` file.

## Data Availability

The source code, database schema, and load testing script are available in this repository. The deployed instance of the application operates within the institutional secure network. An anonymised data subset is available upon reasonable request.

## Contact

**Author:** I. A. Klimov
**E-mail:** your.email@example.com

## Citation

If you use this system in your research, please cite:

> Klimov I. A. Hybrid EAV architecture for storing plant phenotypic data: implementation on the Python stack and performance evaluation // Programming. 2026. [in press].
