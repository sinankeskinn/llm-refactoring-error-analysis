from collections import defaultdict
from typing import List, Dict, Any
import fdb


DB_USER = "SYSDBA"
DB_PASSWORD = "masterkey"


def get_connection(db_path: str) -> fdb.Connection:
    """Create and return a database connection."""
    return fdb.connect(
        dsn=db_path,
        user=DB_USER,
        password=DB_PASSWORD
    )


def fetch_active_customer_orders(cursor: fdb.Cursor) -> list:
    """
    Fetch active customers with completed orders using a single optimized query.
    """
    sql_query = """
        SELECT
            c.CUSTOMER_ID,
            c.CUSTOMER_NAME,
            o.ORDER_ID,
            o.ORDER_DATE,
            o.TOTAL_PRICE
        FROM CUSTOMERS c
        INNER JOIN ORDERS o
            ON o.CUSTOMER_ID = c.CUSTOMER_ID
        WHERE c.STATUS = ?
          AND o.STATUS = ?
        ORDER BY c.CUSTOMER_ID, o.ORDER_DATE
    """

    cursor.execute(sql_query, ("ACTIVE", "COMPLETED"))
    return cursor.fetchall()


def build_report(rows: list) -> List[Dict[str, Any]]:
    """
    Transform database rows into structured customer order report.
    """
    grouped_orders = defaultdict(list)
    customer_names = {}

    for customer_id, customer_name, order_id, order_date, total_price in rows:
        customer_names[customer_id] = customer_name
        grouped_orders[customer_id].append({
            "order_id": order_id,
            "order_date": order_date,
            "total_price": total_price
        })

    report = [
        {
            "customer_id": customer_id,
            "customer": customer_names[customer_id],
            "orders": orders
        }
        for customer_id, orders in grouped_orders.items()
    ]

    return report


def process_user_orders(db_path: str) -> List[Dict[str, Any]]:
    """
    Main orchestration function.
    """
    connection = None

    try:
        connection = get_connection(db_path)

        with connection.cursor() as cursor:
            rows = fetch_active_customer_orders(cursor)
            return build_report(rows)

    finally:
        if connection:
            connection.close()