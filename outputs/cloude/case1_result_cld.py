"""
user_orders_repository.py
Firebird 4.0 – Müşteri Sipariş Raporu Veri Erişim Katmanı

Refactoring Gerekçeleri:
  - Tek sorumluluk: bağlantı yönetimi, sorgu, iş mantığı ayrıldı
  - Context manager ile garantili kaynak serbest bırakma
  - N+1 sorunu ortadan kaldırıldı: tek JOIN sorgusu
  - fetchall() yerine iterator tabanlı akış ile bellek verimliliği
  - Parametreli sabitler ve tip notasyonları
  - Yapılandırılmış loglama
"""

from __future__ import annotations

import logging
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator, Iterator

import fdb  # pip install fdb

# ---------------------------------------------------------------------------
# Loglama
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Yapılandırma sabitleri  (isterseniz ortam değişkenine veya config.py'ye taşıyın)
# ---------------------------------------------------------------------------
_DEFAULT_USER     = "SYSDBA"
_DEFAULT_PASSWORD = "masterkey"
_DEFAULT_CHARSET  = "UTF8"

_ACTIVE_STATUS    = "ACTIVE"
_COMPLETED_STATUS = "COMPLETED"

# ---------------------------------------------------------------------------
# Veri modelleri
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OrderRow:
    order_id:    int
    order_date:  object          # datetime.date veya str – sürücüye bırakıldı
    total_price: float


@dataclass
class CustomerReport:
    customer_id:   int
    customer_name: str
    orders:        list[OrderRow] = field(default_factory=list)

    @property
    def total_revenue(self) -> float:
        return sum(o.total_price for o in self.orders)


# ---------------------------------------------------------------------------
# Bağlantı yönetimi
# ---------------------------------------------------------------------------
@contextmanager
def _db_connection(
    db_path: str,
    user:     str = _DEFAULT_USER,
    password: str = _DEFAULT_PASSWORD,
    charset:  str = _DEFAULT_CHARSET,
) -> Generator[fdb.Connection, None, None]:
    """
    Firebird bağlantısını context manager olarak açar.
    Blok sonunda commit, hata durumunda rollback ve her durumda close() çağrılır.
    """
    conn: fdb.Connection | None = None
    try:
        conn = fdb.connect(
            dsn=db_path,
            user=user,
            password=password,
            charset=charset,
        )
        logger.debug("Veritabanı bağlantısı açıldı: %s", db_path)
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("Veritabanı işlemi sırasında hata oluştu.")
        raise
    finally:
        if conn:
            conn.close()
            logger.debug("Veritabanı bağlantısı kapatıldı.")


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
_SQL_ACTIVE_CUSTOMERS_WITH_COMPLETED_ORDERS = """
    SELECT
        c.CUSTOMER_ID,
        c.CUSTOMER_NAME,
        o.ORDER_ID,
        o.ORDER_DATE,
        o.TOTAL_PRICE
    FROM
        CUSTOMERS c
        JOIN ORDERS o ON o.CUSTOMER_ID = c.CUSTOMER_ID
    WHERE
        c.STATUS  = ?
        AND o.STATUS = ?
    ORDER BY
        c.CUSTOMER_ID,
        o.ORDER_DATE
"""
#
# Neden tek JOIN?
#   Orijinal kodda:
#     1) Subquery ile filtrelenmiş müşteriler çekiliyordu  (sorgu #1)
#     2) TÜM siparişler bellekte tutuluyordu               (sorgu #2 – N*M döngüsü)
#   Yeni yaklaşım:
#     Tek JOIN, veritabanı motorunun indeks / hash-join optimizasyonundan yararlanır;
#     uygulama belleğine yalnızca sonuç kümesi yüklenir.


# ---------------------------------------------------------------------------
# Veri erişim fonksiyonları
# ---------------------------------------------------------------------------
def _iter_rows(
    cursor: fdb.Cursor,
    customer_status: str,
    order_status:    str,
) -> Iterator[tuple]:
    """
    Satırları birer birer üretir; tüm sonuç kümesini bellekte tutmaz.
    fetchmany() / server-side cursor için fdb'nin scroll cursor'ını tercih edin.
    """
    cursor.execute(
        _SQL_ACTIVE_CUSTOMERS_WITH_COMPLETED_ORDERS,
        (customer_status, order_status),
    )
    while True:
        row = cursor.fetchone()
        if row is None:
            break
        yield row


def _build_report(rows: Iterator[tuple]) -> list[CustomerReport]:
    """
    Ham satırları CustomerReport listesine dönüştürür.
    defaultdict ile tek geçişte gruplama yapılır – O(n) karmaşıklık.
    """
    customers: dict[int, CustomerReport] = {}
    order_sets: dict[int, set[int]] = defaultdict(set)   # tekrar koruma

    for customer_id, customer_name, order_id, order_date, total_price in rows:
        if customer_id not in customers:
            customers[customer_id] = CustomerReport(
                customer_id=customer_id,
                customer_name=customer_name,
            )

        if order_id not in order_sets[customer_id]:
            order_sets[customer_id].add(order_id)
            customers[customer_id].orders.append(
                OrderRow(
                    order_id=order_id,
                    order_date=order_date,
                    total_price=float(total_price),
                )
            )

    return list(customers.values())


# ---------------------------------------------------------------------------
# Genel arayüz (public API)
# ---------------------------------------------------------------------------
def get_active_customer_order_report(
    db_path:         str,
    user:            str = _DEFAULT_USER,
    password:        str = _DEFAULT_PASSWORD,
    customer_status: str = _ACTIVE_STATUS,
    order_status:    str = _COMPLETED_STATUS,
) -> list[CustomerReport]:
    """
    Aktif müşterilerin tamamlanmış siparişlerini döndürür.

    Args:
        db_path:         Firebird DSN veya yerel dosya yolu.
        user:            Veritabanı kullanıcısı.
        password:        Parola.
        customer_status: Filtrelenecek müşteri durumu (varsayılan: 'ACTIVE').
        order_status:    Filtrelenecek sipariş durumu (varsayılan: 'COMPLETED').

    Returns:
        CustomerReport nesnelerinin listesi.
        Her nesne: customer_id, customer_name, orders listesi ve
        hesaplanmış total_revenue özelliği içerir.

    Raises:
        fdb.fbcore.DatabaseError: Bağlantı veya sorgu hatası.
    """
    with _db_connection(db_path, user=user, password=password) as conn:
        with conn.cursor() as cursor:
            rows = _iter_rows(cursor, customer_status, order_status)
            report = _build_report(rows)

    logger.info(
        "Rapor oluşturuldu: %d aktif müşteri, %d toplam sipariş.",
        len(report),
        sum(len(c.orders) for c in report),
    )
    return report


# ---------------------------------------------------------------------------
# Hızlı test / geliştirici çalıştırması
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    )

    db = sys.argv[1] if len(sys.argv) > 1 else "localhost:/var/lib/firebird/data/mydb.fdb"
    results = get_active_customer_order_report(db)

    for c in results:
        print(f"\n{'─'*50}")
        print(f"  Müşteri : {c.customer_name}  (ID={c.customer_id})")
        print(f"  Toplam  : {c.total_revenue:,.2f} TL  |  {len(c.orders)} sipariş")
        for o in c.orders:
            print(f"    › #{o.order_id}  {o.order_date}  {o.total_price:,.2f} TL")