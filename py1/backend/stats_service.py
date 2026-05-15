# My service
from fastapi import FastAPI
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Statistics Service")

DATABASE_URL = "postgresql://postgres:newpassword@localhost:5432/voters_db"


def get_db_connection():
    connection = psycopg2.connect(DATABASE_URL)
    return connection


@app.get("/stats")
def get_stats():
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT COUNT(*) as total FROM voters")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT AVG(age) as avg_age FROM voters")
    avg_age = cursor.fetchone()["avg_age"] or 0

    cursor.close()
    connection.close()

    return {"total_voters": total, "average_age": round(float(avg_age), 1)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=4002)
