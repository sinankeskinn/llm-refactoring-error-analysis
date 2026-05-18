import logging
from typing import List, Tuple, Any
import fdb

# Loglama altyapısı (print yerine logging kullanımı Clean Code standardıdır)
logger = logging.getLogger(__name__)

def calculate_running_totals_v2(db_path: str) -> List[Tuple[Any, ...]]:
    """
    Firebird 4.0 Window fonksiyonlarını kullanarak veritabanını yormadan
    ve bellek sızıntısı oluşturmadan kümülatif toplam hesaplar.
    """
    
    # Analitik SQL mimarisi kullanan optimize sorgu
    sql_query = """
        SELECT 
            ORDER_ID, 
            CUSTOMER_ID, 
            TOTAL_PRICE,
            SUM(TOTAL_PRICE) OVER(ORDER BY ORDER_ID) as RUNNING_TOTAL
        FROM ORDERS
        ORDER BY ORDER_ID;
    """
    
    # Güvenli kaynak yönetimi için içiçe context manager yapıları
    try:
        with fdb.connect(dsn=db_path, user='SYSDBA', password='masterkey') as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_query)
                # fetchall() büyük verilerde memory harcar, ancak mevcut mimari 
                # liste dönmeyi beklediği için korunmuştur.
                results = cursor.fetchall() 
                return results
                
    except fdb.DatabaseError as db_err:
        logger.error(f"Veritabanı hatası (Kilitlenme veya Sözdizimi): {db_err}")
        raise db_err
    except Exception as e:
        logger.critical(f"Beklenmeyen sistem hatası: {e}")
        raise e