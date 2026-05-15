from fastapi import FastAPI, HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, EmailStr
import hashlib
import re

app = FastAPI(title="Voter Service")

DATABASE_URL = "postgresql://postgres:newpassword@localhost:5432/voters_db"


class Voter(BaseModel):
    name: str
    email: EmailStr
    age: int
    phone: str
    address: str
    password: str


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_db_connection():
    connection = psycopg2.connect(DATABASE_URL)
    return connection


@app.post("/register")
def register_voter(voter: Voter):
    if voter.age < 18:
        raise HTTPException(status_code=400, detail="NOT ELIGIBLE FOR VOTING")

    phone_digits = re.sub(r"\D", "", voter.phone)
    if len(phone_digits) != 10:
        raise HTTPException(
            status_code=400,
            detail="Provide valid phone number",
        )

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        password_hash = hash_password(voter.password)
        cursor.execute(
            (
                "INSERT INTO voters (name, email, age, phone, address, "
                "password_hash) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
            ),
            (
                voter.name,
                voter.email,
                voter.age,
                voter.phone,
                voter.address,
                password_hash,
            ),
        )
        voter_id = cursor.fetchone()["id"]
        connection.commit()

        cursor.close()
        connection.close()
        return {
            "message": "Voter registered successfully!",
            "voter_id": voter_id,
        }

    except psycopg2.IntegrityError:
        cursor.close()
        connection.close()
        raise HTTPException(status_code=400, detail="Email already registered")


@app.get("/voters")
def get_voters(
    search: str = None,
    page: int = 1,
    limit: int = 10,
    sort_by: str = "name",
):
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    base_query = (
        "SELECT id, name, email, age, phone, address, created_at "
        "FROM voters"
    )
    count_query = "SELECT COUNT(*) FROM voters"

    where_clause = ""
    params = []

    if search:
        where_clause = (
            " WHERE name ILIKE %s OR email ILIKE %s"
        )
        search_param = f"%{search}%"
        params = [search_param, search_param]

    if where_clause:
        base_query += where_clause
        count_query += where_clause

    if sort_by in ["name", "age", "created_at"]:
        base_query += f" ORDER BY {sort_by}"

    offset = (page - 1) * limit
    base_query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    count_params = params[:-2] if search else []
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()["count"]

    cursor.execute(base_query, params)
    voters = [dict(row) for row in cursor.fetchall()]

    cursor.close()
    connection.close()

    return {
        "voters": voters,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit,
    }


@app.get("/voters/{voter_id}")
def get_voter_by_id(voter_id: int):
    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    cursor.execute(
        (
            "SELECT id, name, email, age, phone, address, created_at "
            "FROM voters WHERE id = %s"
        ),
        (voter_id,),
    )
    voter = cursor.fetchone()

    cursor.close()
    connection.close()

    if not voter:
        raise HTTPException(status_code=404, detail="Voter not found")

    return dict(voter)


@app.put("/voters/{voter_id}")
def update_voter(voter_id: int, voter: Voter):
    if voter.age < 18:
        raise HTTPException(status_code=400, detail="NOT ELIGIBLE FOR VOTING")

    phone_digits = re.sub(r"\D", "", voter.phone)
    if len(phone_digits) != 10:
        raise HTTPException(
            status_code=400,
            detail="Provide valid phone number",
        )

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        password_hash = hash_password(voter.password)
        cursor.execute(
            """
            UPDATE voters
            SET name = %s, email = %s, age = %s, phone = %s,
                address = %s, password_hash = %s
            WHERE id = %s
            """,
            (
                voter.name,
                voter.email,
                voter.age,
                voter.phone,
                voter.address,
                password_hash,
                voter_id,
            ),
        )

        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            raise HTTPException(status_code=404, detail="Voter not found")

        connection.commit()
        cursor.close()
        connection.close()
        return {"message": "Voter updated successfully!"}

    except psycopg2.IntegrityError:
        cursor.close()
        connection.close()
        raise HTTPException(status_code=400, detail="Email already registered")


@app.delete("/voters/{voter_id}")
def delete_voter(voter_id: int):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM voters WHERE id = %s", (voter_id,))

    if cursor.rowcount == 0:
        cursor.close()
        connection.close()
        raise HTTPException(status_code=404, detail="Voter not found")

    connection.commit()
    cursor.close()
    connection.close()

    return {"message": "Voter deleted successfully!"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=4001)
