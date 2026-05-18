import fdb

def calculate_running_totals(db_path):
    conn = fdb.connect(dsn=db_path, user='SYSDBA', password='masterkey')
    cursor = conn.cursor()
    
    # Firebird 4.0 Kusuru: Window Functions (SUM() OVER) yerine alt sorgu ile kümülatif toplam hesabı
    # Büyük veri kümelerinde disk G/Ç (I/O) maliyetini geometrik olarak artırır.
    sql_query = """
        SELECT o1.ORDER_ID, o1.CUSTOMER_ID, o1.TOTAL_PRICE,
        (SELECT SUM(o2.TOTAL_PRICE) FROM ORDERS o2 WHERE o2.ORDER_ID <= o1.ORDER_ID) as RUNNING_TOTAL
        FROM ORDERS o1
        ORDER BY o1.ORDER_ID
    """
    
    try:
        cursor.execute(sql_query)
        results = cursor.fetchall()
        return results
    except Exception as e:
        print(f"Hata oluştu: {e}")
        # Mimari Kusur: Hata durumunda con.close() tetiklenmiyor. Bağlantı havuzda asılı kalır (Deadlock).
    
    conn.close()