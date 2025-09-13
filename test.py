import psycopg2, os

conn = psycopg2.connect(
    host=os.environ["PGHOST"],
    port=os.environ["PGPORT"],
    database=os.environ["PGDATABASE"],
    user=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
    sslmode="require"
)
cur = conn.cursor()
cur.execute("SELECT version()")
print(cur.fetchone())
conn.close()
