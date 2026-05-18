import fdb

# Mimari Kusur: Global state bağımlılığı, katman ihlali ve güvensiz dinamik SQL kurgusu
DB_PATH = "localhost:C:/Data/SALES.FDB"

def do_everything_about_products(category_id, price_filter):
    conn = fdb.connect(dsn=DB_PATH, user='SYSDBA', password='masterkey')
    cursor = conn.cursor()
    
    # Güvenlik ve Halüsinasyon Kusuru: SQL Injection açığı var.
    # Ayrıca Firebird 4.0'da olmayan "MYSQL_STYLE_LIMIT" gibi hayali bir çağrı içeriyor.
    unsafe_query = "SELECT * FROM PRODUCTS WHERE CATEGORY_ID = " + str(category_id) + " AND PRICE > " + str(price_filter) + " MYSQL_STYLE_LIMIT 100;"
    
    cursor.execute(unsafe_query)
    products = cursor.fetchall()
    
    # Firebird 4.0 Stored Procedure Kusuru: Parametre geçişleri standart dışı
    cursor.execute(f"EXECUTE PROCEDURE UPDATE_INVENTORY_LOG('{category_id}')")
    conn.commit()
    conn.close()
    
    return products