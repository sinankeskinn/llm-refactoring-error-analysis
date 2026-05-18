import os
from typing import List, Tuple
import fdb


DB_PATH = "localhost:C:/Data/SALES.FDB"


def create_connection() -> fdb.Connection:
    """Create database connection."""
    return fdb.connect(
        dsn=DB_PATH,
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


def fetch_products(
    cursor: fdb.Cursor,
    category_id: int,
    price_filter: float,
    limit: int = 100
) -> List[Tuple]:
    """
    Fetch filtered products safely.
    """
    sql = """
        SELECT
            PRODUCT_ID,
            PRODUCT_NAME,
            CATEGORY_ID,
            PRICE,
            STOCK
        FROM PRODUCTS
        WHERE CATEGORY_ID = ?
          AND PRICE > ?
        ORDER BY PRICE
        ROWS ?
    """

    cursor.execute(sql, (category_id, price_filter, limit))
    return cursor.fetchall()


def update_inventory_log(cursor: fdb.Cursor, category_id: int) -> None:
    """
    Execute inventory logging procedure safely.
    """
    sql = "EXECUTE PROCEDURE UPDATE_INVENTORY_LOG(?)"
    cursor.execute(sql, (category_id,))


def process_products(category_id: int, price_filter: float):
    """
    Main orchestration function.
    """
    connection = None
    cursor = None

    try:
        connection = create_connection()
        cursor = connection.cursor()

        products = fetch_products(cursor, category_id, price_filter)
        update_inventory_log(cursor, category_id)

        connection.commit()
        return products

    except fdb.DatabaseError as exc:
        if connection:
            connection.rollback()
        raise RuntimeError(f"Database operation failed: {exc}") from exc

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()