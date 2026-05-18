import fdb

def process_user_orders_v1(db_path):
    # Fonksiyonel Kusur: try-finally veya context manager (with) kullanılmadı. Sızıntı var.
    conn = fdb.connect(dsn=db_path, user='SYSDBA', password='masterkey')
    cursor = conn.cursor()
    
    # Firebird 4.0 Kusuru: İndeks taranmayan, biçimsiz JOIN ve alt sorgu barındıran SQL
    sql_query = """
        SELECT c.CUSTOMER_ID, c.CUSTOMER_NAME, o.ORDER_ID, o.ORDER_DATE, o.TOTAL_PRICE 
        FROM CUSTOMERS c
        WHERE c.STATUS = 'ACTIVE' AND c.CUSTOMER_ID IN (
            SELECT o.CUSTOMER_ID FROM ORDERS o WHERE o.STATUS = 'COMPLETED'
        )
    """
    cursor.execute(sql_query)
    customers = cursor.fetchall()
    
    cursor.execute("SELECT ORDER_ID, TOTAL_PRICE FROM ORDERS")
    all_orders = cursor.fetchall()
    
    report = []
    # Algoritmik Kusur: O(n^2) Karmaşıklığında iç içe döngü (Tıkanıklık Noktası)
    for cust in customers:
        cust_orders = []
        for ord in all_orders:
            if ord[0] == cust[0]: 
                cust_orders.append(ord)
        report.append({"customer": cust[1], "orders": cust_orders})
        
    return report