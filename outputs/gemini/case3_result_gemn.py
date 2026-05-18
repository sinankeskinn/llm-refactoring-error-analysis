import logging
from typing import List, Dict, Any, Tuple
import fdb

# Loglama Yapılandırması
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Veritabanı bağlantı yönetiminden sorumlu context sınıfı."""
    def __init__(self, db_path: str, user: str = 'SYSDBA', password: str = 'masterkey'):
        self.db_path = db_path
        self.user = user
        self.password = password

    def get_connection(self) -> fdb.Connection:
        return fdb.connect(dsn=self.db_path, user=self.user, password=self.password)


class ProductRepository:
    """Ürünler ve stok logları ile ilgili veritabanı operasyonlarını yönetir."""
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def fetch_active_products_by_category(self, category_id: int, min_price: float, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Kategoriye ve fiyat filtresine göre ürünleri güvenli (Parametrik) ve 
        Firebird 4.0 uyumlu pagination sözdizimi ile getirir.
        """
        # Firebird 4.0 standart SQL limit sözdizimi (OFFSET/FETCH FIRST)
        sql_query = """
            SELECT PRODUCT_ID, PRODUCT_NAME, CATEGORY_ID, PRICE, STOCK_COUNT 
            FROM PRODUCTS 
            WHERE CATEGORY_ID = ? AND PRICE > ?
            OFFSET 0 ROWS FETCH FIRST ? ROWS ONLY;
        """
        
        products = []
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    # SQL Injection engellendi. Parametreler tuple olarak güvenle geçildi.
                    cursor.execute(sql_query, (category_id, min_price, limit))
                    
                    # SELECT * yerine sütun bazlı mapping (Clean Code)
                    columns = [desc[0] for desc in cursor.description]
                    for row in cursor.fetchall():
                        products.append(dict(zip(columns, row)))
                        
        except fdb.Error as e:
            logger.error(f"Ürün listeleme esnasında SQL hatası: {e}")
            raise
        return products

    def log_inventory_update(self, category_id: int) -> None:
        """Kategori bazlı stok güncelleme prosedürünü güvenli şekilde tetikler."""
        sql_procedure = "EXECUTE PROCEDURE UPDATE_INVENTORY_LOG(?)"
        
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql_procedure, (category_id,))
                    conn.commit()  # Değişiklikleri kalıcı kıl
                    logger.info(f"Kategori {category_id} için envanter logu güncellendi.")
        except fdb.Error as e:
            logger.error(f"Prosedür çalıştırma hatası (UPDATE_INVENTORY_LOG): {e}")
            raise


# ORKESTRASYON KATMANI (Service Layer)
def process_product_pipeline(db_path: str, category_id: int, price_filter: float) -> List[Dict[str, Any]]:
    """
    Eski 'do_everything' fonksiyonunun yerine geçen, iş akışını yöneten
    ve Single Responsibility kuralına uyan servis fonksiyonu.
    """
    db_manager = DatabaseManager(db_path=db_path)
    product_repo = ProductRepository(db_manager)
    
    # 1. Ürünleri Getir
    products = product_repo.fetch_active_products_by_category(category_id, price_filter)
    
    # 2. Stok Logunu Güncelle
    product_repo.log_inventory_update(category_id)
    
    return products