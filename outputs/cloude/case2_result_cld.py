import fdb
import logging

logger = logging.getLogger(__name__)

_SQL_RUNNING_TOTALS = """
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

def iter_running_totals(db_path: str, user: str = "SYSDBA", password: str = "masterkey"):
    """
    Her satırı (order_id, customer_id, total_price, running_total)
    tuple olarak yield eder. Belleğe tüm tablo yüklenmez.
    """
    conn = fdb.connect(dsn=db_path, user=user, password=password, charset="UTF8")
    cursor = conn.cursor()
    try:
        cursor.execute(_SQL_RUNNING_TOTALS)
        while (row := cursor.fetchone()) is not None:
            yield row
        conn.commit()
    except fdb.fbcore.DatabaseError:
        conn.rollback()
        logger.exception("Sorgulama başarısız, rollback yapıldı.")
        raise
    finally:
        cursor.close()
        conn.close()