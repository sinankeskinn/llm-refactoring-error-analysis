"""
product_repository.py
Firebird 4.0 — Ürün Kataloğu Veri Erişim Katmanı

Refactoring Eksenleri:
  1. GÜVENLİK     — SQL Injection → Parametreli sorgular
  2. MODÜLERLİK   — Tek dev fonksiyon → SRP uyumlu katmanlı yapı
  3. FB4 UYUMU    — MySQL LIMIT → Firebird FIRST/SKIP / ROWS
  4. STORED PROC  — f-string injection → Parametreli EXECUTE PROCEDURE
  5. KAYNAK YÖN.  — Garantisiz close() → context manager
  6. KONFİGÜRASYON — Hardcoded DSN/kimlik → merkezi config nesnesi
  7. TİP GÜVENLİĞİ — Tip notasyonları + giriş doğrulama
  8. HATA YÖNETİMİ — Sessiz başarısızlık → loglama + rollback + raise
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator, Iterator, Sequence

import fdb  # pip install fdb

# ---------------------------------------------------------------------------
# Loglama
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. KONFİGÜRASYON  — tek yer, override edilebilir
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DatabaseConfig:
    """
    Bağlantı parametrelerini kapsüller.
    Üretimde ortam değişkeninden veya merkezi config servisinden besleyin:

        cfg = DatabaseConfig(
            dsn=os.environ["FB_DSN"],
            user=os.environ["FB_USER"],
            password=os.environ["FB_PASSWORD"],
        )
    """
    dsn:      str = "localhost:C:/Data/SALES.FDB"
    user:     str = "SYSDBA"
    password: str = "masterkey"
    charset:  str = "UTF8"
    page_size: int = 100          # varsayılan sayfa boyutu


# Modül düzeyinde varsayılan config — isterseniz dışarıdan geçirin.
_DEFAULT_CONFIG = DatabaseConfig()


# ---------------------------------------------------------------------------
# 2. VERİ MODELİ  — ham tuple yerine anlamlı nesne
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Product:
    """
    PRODUCTS tablosunun uygulama tarafındaki temsili.
    Sütun sırası değişirse yalnızca bu sınıf güncellenir.
    """
    product_id:  int
    category_id: int
    name:        str
    price:       float
    stock:       int

    @classmethod
    def from_row(cls, row: tuple) -> "Product":
        product_id, category_id, name, price, stock = row
        return cls(
            product_id=int(product_id),
            category_id=int(category_id),
            name=str(name),
            price=float(price),
            stock=int(stock),
        )


# ---------------------------------------------------------------------------
# 3. GİRİŞ DOĞRULAMA  — tip güvenliği + mantıksal sınırlar
# ---------------------------------------------------------------------------
def _validate_category_id(category_id: int) -> int:
    """
    category_id'nin pozitif tam sayı olduğunu doğrular.
    SQL Injection'a karşı ek katman: tip zorlaması parametreli
    sorgunun önünde devreye girer.
    """
    if not isinstance(category_id, int) or category_id <= 0:
        raise ValueError(
            f"category_id pozitif tam sayı olmalıdır, alınan: {category_id!r}"
        )
    return category_id


def _validate_price_filter(price_filter: float) -> float:
    if not isinstance(price_filter, (int, float)) or price_filter < 0:
        raise ValueError(
            f"price_filter negatif olamaz, alınan: {price_filter!r}"
        )
    return float(price_filter)


def _validate_page_size(page_size: int) -> int:
    if not isinstance(page_size, int) or not (1 <= page_size <= 1000):
        raise ValueError(
            f"page_size 1-1000 aralığında olmalıdır, alınan: {page_size!r}"
        )
    return page_size


# ---------------------------------------------------------------------------
# 4. BAĞLANTI YÖNETİMİ  — garantili kaynak serbest bırakma
# ---------------------------------------------------------------------------
@contextmanager
def _db_connection(
    cfg: DatabaseConfig = _DEFAULT_CONFIG,
) -> Generator[fdb.Connection, None, None]:
    """
    Bağlantıyı context manager olarak açar.
    - Normal çıkış  → commit + close
    - Exception     → rollback + close + yeniden fırlat
    """
    conn: fdb.Connection | None = None
    try:
        conn = fdb.connect(
            dsn=cfg.dsn,
            user=cfg.user,
            password=cfg.password,
            charset=cfg.charset,
        )
        logger.debug("Bağlantı açıldı: %s", cfg.dsn)
        yield conn
        conn.commit()
        logger.debug("Transaction commit edildi.")
    except Exception:
        if conn:
            conn.rollback()
            logger.warning("Transaction rollback edildi.")
        logger.exception("Veritabanı işlemi başarısız.")
        raise
    finally:
        if conn:
            conn.close()
            logger.debug("Bağlantı kapatıldı.")


# ---------------------------------------------------------------------------
# 5. SQL  — güvenli + Firebird 4.0 sözdizimi
# ---------------------------------------------------------------------------

# 5a. Ürün sorgulama
#
# SORUN (orijinal):
#   "SELECT * FROM PRODUCTS WHERE ... MYSQL_LIMIT 100;"
#   ↑ MySQL'e özgü sözdizimi — Firebird'de syntax error.
#   ↑ String birleştirme ile SQL Injection kapısı açık.
#
# ÇÖZÜM:
#   • Firebird 4.0 sözdizimi: FIRST/SKIP (veya ROWS N TO M).
#   • Parametreli sorgu: ? yer tutucuları, sürücü kaçış işlemi yapıyor.
#   • SELECT * yerine açık sütun listesi: şema değişikliklerine karşı dayanıklı.
#
_SQL_FETCH_PRODUCTS = """
    SELECT FIRST ? SKIP ?
        p.PRODUCT_ID,
        p.CATEGORY_ID,
        p.NAME,
        p.PRICE,
        p.STOCK
    FROM PRODUCTS p
    WHERE
        p.CATEGORY_ID = ?
        AND p.PRICE    > ?
    ORDER BY
        p.PRICE DESC,
        p.PRODUCT_ID ASC
"""
#
# Firebird 4.0 Alternatif sözdizimi (ISO SQL:2008 uyumlu, her ikisi de geçerli):
#   SELECT ... FROM PRODUCTS ... ROWS ? TO ?
# Tercih: FIRST/SKIP daha okunabilir, eski Firebird sürümleriyle de uyumlu.


# 5b. Stored procedure çağrısı
#
# SORUN (orijinal):
#   f"EXECUTE PROCEDURE UPDATE_INVENTORY_LOG('{category_id}')"
#   ↑ f-string ile parametre → SQL Injection riski aynen geçerli.
#
# ÇÖZÜM:
#   fdb sürücüsü callproc() ile stored procedure'ü doğrudan çağırır;
#   parametre kaçışı sürücü tarafından yapılır.
#
_PROC_UPDATE_INVENTORY_LOG = "UPDATE_INVENTORY_LOG"


# ---------------------------------------------------------------------------
# 6. VERİ ERİŞİM FONKSİYONLARI  — tek sorumluluk ilkesi
# ---------------------------------------------------------------------------

def _fetch_product_rows(
    cursor:      fdb.Cursor,
    category_id: int,
    price_filter: float,
    page_size:   int,
    offset:      int,
) -> Iterator[Product]:
    """
    Ürün satırlarını sorgular ve Product nesneleri üretir.
    Sorgu ve nesne dönüşümü bu fonksiyonda kapsüllenmiştir.
    """
    cursor.execute(
        _SQL_FETCH_PRODUCTS,
        (page_size, offset, category_id, price_filter),
    )
    while (row := cursor.fetchone()) is not None:
        yield Product.from_row(row)


def _call_inventory_log_procedure(
    conn:        fdb.Connection,
    category_id: int,
) -> None:
    """
    UPDATE_INVENTORY_LOG stored procedure'ünü çağırır.
    fdb.callproc() parametreyi güvenli biçimde iletir.

    fdb sürücüsü callproc() sonrası otomatik commit yapmaz;
    commit bağlantı yöneticisine bırakılmıştır (context manager).
    """
    with conn.cursor() as cur:
        cur.callproc(_PROC_UPDATE_INVENTORY_LOG, (category_id,))
    logger.info(
        "UPDATE_INVENTORY_LOG çağrıldı — category_id=%d", category_id
    )


# ---------------------------------------------------------------------------
# 7. PUBLIC API  — çağıran kodun kullandığı tek giriş noktası
# ---------------------------------------------------------------------------

def get_products_by_category(
    category_id:  int,
    price_filter: float,
    *,
    page_size: int = _DEFAULT_CONFIG.page_size,
    offset:    int = 0,
    cfg:       DatabaseConfig = _DEFAULT_CONFIG,
    log_inventory: bool = True,
) -> list[Product]:
    """
    Belirtilen kategori ve fiyat filtresine uyan ürünleri döndürür.
    Başarılı sorgunun ardından UPDATE_INVENTORY_LOG prosedürünü çağırır.

    Args:
        category_id:    Filtrelenecek kategori kimliği (pozitif tam sayı).
        price_filter:   Minimum fiyat eşiği (negatif olamaz).
        page_size:      Maksimum döndürülecek satır sayısı (1-1000).
        offset:         Sayfalama için atlanacak satır sayısı.
        cfg:            Veritabanı bağlantı konfigürasyonu.
        log_inventory:  False ise prosedür çağrısı atlanır (test kolaylığı).

    Returns:
        Product nesnelerinin listesi.

    Raises:
        ValueError:              Geçersiz giriş parametresi.
        fdb.fbcore.DatabaseError: Veritabanı erişim hatası.
    """
    # Giriş doğrulama — DB'ye gitmeden önce
    category_id  = _validate_category_id(category_id)
    price_filter = _validate_price_filter(price_filter)
    page_size    = _validate_page_size(page_size)

    logger.info(
        "Ürün sorgusu başlatılıyor — category_id=%d, price_filter=%.2f, "
        "page_size=%d, offset=%d",
        category_id, price_filter, page_size, offset,
    )

    with _db_connection(cfg) as conn:
        with conn.cursor() as cursor:
            products = list(
                _fetch_product_rows(
                    cursor, category_id, price_filter, page_size, offset
                )
            )

        if log_inventory:
            _call_inventory_log_procedure(conn, category_id)

    logger.info(
        "Sorgu tamamlandı — %d ürün döndürüldü, category_id=%d",
        len(products), category_id,
    )
    return products


# ---------------------------------------------------------------------------
# 8. SAYFALAMA YARDIMCISI  — büyük sonuç kümeleri için
# ---------------------------------------------------------------------------

def iter_all_products_by_category(
    category_id:  int,
    price_filter: float,
    *,
    page_size: int = _DEFAULT_CONFIG.page_size,
    cfg:       DatabaseConfig = _DEFAULT_CONFIG,
) -> Iterator[Product]:
    """
    Tüm eşleşen ürünleri sayfa sayfa çekerek tek bir stream olarak üretir.
    Büyük veri kümelerini belleğe tam yüklemeden işlemek için kullanın.

    Kullanım:
        for product in iter_all_products_by_category(3, 50.0):
            process(product)
    """
    offset = 0
    while True:
        page = get_products_by_category(
            category_id,
            price_filter,
            page_size=page_size,
            offset=offset,
            cfg=cfg,
            log_inventory=(offset == 0),   # sadece ilk sayfada log
        )
        yield from page
        if len(page) < page_size:
            break                          # son sayfa — döngüyü bitir
        offset += page_size


# ---------------------------------------------------------------------------
# Geliştirici çalıştırması
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    cfg = DatabaseConfig(
        dsn=sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_CONFIG.dsn
    )

    try:
        products = get_products_by_category(
            category_id=3,
            price_filter=50.0,
            page_size=10,
            cfg=cfg,
        )
        print(f"\n{'─' * 56}")
        print(f"  {'ID':<6} {'Kategori':<10} {'Ürün':<22} {'Fiyat':>8} {'Stok':>6}")
        print(f"{'─' * 56}")
        for p in products:
            print(
                f"  {p.product_id:<6} {p.category_id:<10} "
                f"{p.name[:20]:<22} {p.price:>8.2f} {p.stock:>6}"
            )
        print(f"{'─' * 56}")
        print(f"  Toplam: {len(products)} ürün\n")
    except ValueError as exc:
        print(f"Geçersiz parametre: {exc}", file=sys.stderr)
        sys.exit(1)
    except fdb.fbcore.DatabaseError as exc:
        print(f"Veritabanı hatası: {exc}", file=sys.stderr)
        sys.exit(2)