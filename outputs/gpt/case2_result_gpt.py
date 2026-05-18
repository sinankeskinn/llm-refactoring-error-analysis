import os
import fdb


def calculate_running_totals(db_path: str):
    sql_query = """
        SELECT
            ORDER_ID,
            CUSTOMER_ID,
            TOTAL_PRICE,
            SUM(TOTAL_PRICE) OVER (
                ORDER BY ORDER_ID
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS RUNNING_TOTAL
        FROM ORDERS
        ORDER BY ORDER_ID
    """

    connection = None
    cursor = None

    try:
        connection = fdb.connect(
            dsn=db_path,
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )

        cursor = connection.cursor()
        cursor.execute(sql_query)

        return cursor.fetchall()

    except fdb.DatabaseError as exc:
        error_message = str(exc).lower()

        if "deadlock" in error_message:
            raise RuntimeError("Database deadlock detected") from exc

        raise RuntimeError(f"Database error: {exc}") from exc

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()