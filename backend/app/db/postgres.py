import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://chainmind:chainmind_dev@localhost:5432/chainmind")

def get_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
