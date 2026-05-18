import logging
from typing import Dict, List, Any
import fdb

# Loglama yapılandırması
logger = logging.getLogger(__name__)

# SQL Sorgusu: Veri birleştirme ve filtreleme tamamen veritabanı motoruna devredildi.
FETCH_ACTIVE_CUSTOMER_ORDERS_SQL = """
    SELECT 
        c.CUSTOMER_NAME, 
        o.ORDER_ID, 
        o.TOTAL_PRICE
    FROM CUSTOMERS c
    INNER JOIN ORDERS o ON c.CUSTOMER_ID = o.CUSTOMER_ID
    WHERE c.STATUS = 'ACTIVE' 
      AND o.STATUS = 'COMPLETED'
    ORDER BY c.CUSTOMER_NAME;
"""

def get_active_customer_orders_report(
    db_path: str, 
    user: str = 'SYSDBA', 
    password: str = 'masterkey'
) -> List[Dict[str, Any]]:
    """
    Aktif müşterilerin tamamlanmış siparişlerini raporlar.
    
    Bellek dostudur ve tüm eşleştirme işlemini veritabanı seviyesinde çözer.
    """
    report: List[Dict[str, Any]] = []
    
    # Python 'with' ifadesi (Context Manager) kullanımı:
    # Bağlantı ve imleç (cursor) işlem bittiğinde veya hata anında otomatik kapatılır.
    try:
        with fdb.connect(dsn=db_path, user=user, password=password) as conn:
            with conn.cursor() as cursor:
                cursor.execute(FETCH_ACTIVE_CUSTOMER_ORDERS_SQL)
                
                current_customer = None
                customer_orders = []

                # fetchall() yerine verileri satır satır (stream) işleyerek bellek tasarrufu sağlıyoruz.
                for row in cursor:
                    customer_name, order_id, total_price = row
                    
                    # Yeni bir müşteriye geçildiğinde bir öncekini rapora ekle
                    if current_customer and current_customer != customer_name:
                        report.append({
                            "customer": current_customer, 
                            "orders": customer_orders
                        })
                        customer_orders = []
                    
                    current_customer = customer_name
                    customer_orders.append((order_id, total_price))
                
                # Döngü bittiğinde eldeki son müşteriyi de rapora ekle
                if current_customer:
                    report.append({
                        "customer": current_customer, 
                        "orders": customer_orders
                    })
                    
    except fdb.Error as e:
        logger.error(f"Veritabanı hatası oluştu: {e}")
        raise
        
    return report