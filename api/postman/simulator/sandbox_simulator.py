#!/usr/bin/env python3
"""Sandbox simulator for the Vektör dealer API and the Köprü e-Belge SOAP service.

This is a test double, not the product. It implements just enough of the behaviour described in
api/openapi/vektor-dealer-api.v1.yaml and api/soap/kopru-ebelge-einvoice-v1.wsdl for the Postman
collection in this folder to run end to end: OAuth2 client credentials, validation with the error
catalogue, idempotency, rate limits, dealer isolation, the order business rules, invoices and the three
integrator operations. State lives in memory and resets on every start.

Standard library only. Run:  python3 sandbox_simulator.py --port 8040
All companies, people, credentials and figures are fictional.
"""
import argparse
import base64
import hashlib
import io
import json
import math
import re
import sys
import threading
import time
import traceback
import uuid
import zipfile
import xml.etree.ElementTree as ET
from collections import deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from xml.sax.saxutils import escape

TZ = timezone(timedelta(hours=3))          # Europe/Istanbul, no daylight saving time since 2016
MAX_BODY = 256 * 1024
TOKEN_TTL = 3600
ORDER_PROCESSING_SECONDS = 0.25            # simulated storage latency; makes concurrent duplicates observable
LIMITS = {"stock": 60, "orders_post": 30, "other": 120}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ORDER_ID_RE = re.compile(r"^VO-\d{4}-\d{6}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UNITS = {"C62", "SET", "KGM", "MTR", "LTR"}
PIECE_UNITS = {"C62", "SET"}
STATUSES = ["RECEIVED", "PENDING_APPROVAL", "APPROVED", "ALLOCATED", "SHIPPED", "INVOICED", "CLOSED", "REJECTED"]


def now():
    return datetime.now(TZ)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def today():
    return now().date()


def money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def num(value):
    value = Decimal(value)
    return int(value) if value == value.to_integral_value() else float(value)


def turkish_fold(text):
    text = text.replace("İ", "i").replace("I", "ı").lower()
    return text.translate(str.maketrans("çğıöşü", "cgiosu")).strip()


PROVINCES = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın", "Balıkesir",
    "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli",
    "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane",
    "Hakkari", "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli",
    "Kırşehir", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Tekirdağ", "Tokat",
    "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman",
    "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük", "Kilis", "Osmaniye", "Düzce",
]
assert len(PROVINCES) == 81
PROVINCE_KEYS = {turkish_fold(p) for p in PROVINCES}

# ---------------------------------------------------------------------------------------------------------------
# Master data (fictional)
# ---------------------------------------------------------------------------------------------------------------
DEALERS = {
    "D00042": {"name": "Marmara Teknoloji Ürünleri Ticaret A.Ş.", "clientId": "sim-d00042", "clientSecret": "sim-secret-d00042",
               "status": "ACTIVE", "creditLimit": Decimal("500000"), "openBalance": Decimal("120000"), "warehouse": "IST",
               "addresses": {"MAIN": {"addressLine1": "Sanayi Cad. No 18", "district": "Çayırova", "city": "Kocaeli",
                                      "postalCode": "41420", "countryCode": "TR"}}},
    "D00077": {"name": "Ege Bilişim Sistemleri Ltd. Şti.", "clientId": "sim-d00077", "clientSecret": "sim-secret-d00077",
               "status": "ACTIVE", "creditLimit": Decimal("200000"), "openBalance": Decimal("60000"), "warehouse": "IZM",
               "addresses": {"MAIN": {"addressLine1": "Kazımdirik Mah. 372 Sok. No 5", "district": "Bornova", "city": "İzmir",
                                      "postalCode": "35100", "countryCode": "TR"}}},
    "D00099": {"name": "Çınar Elektronik", "clientId": "sim-d00099", "clientSecret": "sim-secret-d00099",
               "status": "SUSPENDED", "creditLimit": Decimal("50000"), "openBalance": Decimal("0"), "warehouse": "IST",
               "addresses": {"MAIN": {"addressLine1": "Cumhuriyet Cad. No 41", "district": "Kadıköy", "city": "İstanbul",
                                      "postalCode": "34710", "countryCode": "TR"}}},
}

PRODUCT_ROWS = [  # sku, name, brand, category, unit, minimum order quantity, VAT %, unit price, status
    ("100234", "VX-55Q 55-inch 4K television", "Vektör Home", "Television", "C62", 2, 20, "18450.00", "ACTIVE"),
    ("100235", "VX-65Q 65-inch 4K television", "Vektör Home", "Television", "C62", 1, 20, "27900.00", "ACTIVE"),
    ("200117", "VX-300 soundbar", "Vektör Home", "Audio", "C62", 4, 20, "2890.00", "ACTIVE"),
    ("200118", "VX-500 soundbar with subwoofer", "Vektör Home", "Audio", "C62", 2, 20, "5490.00", "ACTIVE"),
    ("300410", "KT-17 1.7 L kettle", "Vektör Home", "Small appliances", "C62", 6, 20, "899.00", "ACTIVE"),
    ("300555", "KT-15 1.5 L kettle (discontinued)", "Vektör Home", "Small appliances", "C62", 6, 20, "749.00", "INACTIVE"),
    ("400020", "HDMI 2.1 cable, 2 m", "Vektör Cable", "Accessories", "C62", 10, 20, "149.90", "ACTIVE"),
    ("500100", "BR-1 barista set", "Vektör Home", "Small appliances", "SET", 1, 20, "12990.00", "ACTIVE"),
]
ON_HAND = {
    "100234": {"IST": 48, "ANK": 15, "IZM": 0}, "100235": {"IST": 0, "ANK": 3, "IZM": 7},
    "200117": {"IST": 120, "ANK": 40, "IZM": 60}, "200118": {"IST": 30, "ANK": 12, "IZM": 18},
    "300410": {"IST": 400, "ANK": 150, "IZM": 200}, "300555": {"IST": 0, "ANK": 0, "IZM": 0},
    "400020": {"IST": 1200, "ANK": 300, "IZM": 450}, "500100": {"IST": 25, "ANK": 5, "IZM": 10},
}
EXPECTED_RECEIPTS = {("100234", "IZM"): (10, 40), ("100235", "IST"): (7, 20)}   # (days from today, quantity)
WAREHOUSES = ["IST", "ANK", "IZM"]

# Köprü e-Belge registered users: VKN -> (title, mailbox domain)
REGISTERED_USERS = {
    "6120345678": ("MARMARA TEKNOLOJİ ÜRÜNLERİ TİCARET A.Ş.", "marmarateknoloji.example"),
    "4810067321": ("EGE BİLİŞİM SİSTEMLERİ LTD. ŞTİ.", "egebilisim.example"),
    "3330012345": ("ÇINAR ELEKTRONİK", "cinarelektronik.example"),
    "9240018850": ("VEKTÖR ELEKTRONİK DAĞITIM A.Ş.", "vektor-elektronik.example"),
}
INTEGRATOR_USER, INTEGRATOR_PASSWORD = "sim-vektor-integration", "sim-integrator-password"

# ---------------------------------------------------------------------------------------------------------------
# Error catalogue (analysis/05_error_scenarios.md, sections 3.1 and 3.2)
# ---------------------------------------------------------------------------------------------------------------
ERRORS = {
    "UNAUTHORIZED": (401, "Unauthorized", "Erişim belirteci eksik, geçersiz veya süresi dolmuş.", "The access token is missing, invalid or expired."),
    "DEALER_SUSPENDED": (403, "Dealer suspended", "Bayi hesabı askıya alınmış; satış destek ile iletişime geçin.", "The dealer account is suspended; contact sales support."),
    "DEALER_MISMATCH": (403, "Dealer mismatch", "dealerCode, kimlik bilgilerinizle eşleşmiyor.", "dealerCode does not match your credentials."),
    "FORBIDDEN_RESOURCE": (403, "Access denied", "Bu kayda erişim yetkiniz yok.", "You do not have access to this record."),
    "NOT_FOUND": (404, "Not found", "Kayıt bulunamadı.", "Record not found."),
    "VALIDATION_FAILED": (400, "Validation failed", "İstek {n} alanda doğrulamadan geçemedi.", "The request failed validation in {n} field{s}."),
    "MISSING_IDEMPOTENCY_KEY": (400, "Idempotency key missing", "Idempotency-Key başlığı zorunludur.", "The Idempotency-Key header is required."),
    "INVALID_IDEMPOTENCY_KEY": (400, "Idempotency key invalid", "Idempotency-Key geçerli bir UUID değil.", "Idempotency-Key is not a valid UUID."),
    "IDEMPOTENCY_KEY_REUSED": (422, "Idempotency key reused", "Idempotency-Key daha önce farklı bir istekle kullanılmış.", "Idempotency-Key was already used with a different request."),
    "REQUEST_IN_PROGRESS": (409, "Request in progress", "Aynı istek işlenmekte; Retry-After süresi sonra tekrar deneyin.", "The same request is being processed; retry after the Retry-After period."),
    "DUPLICATE_DEALER_ORDER_NO": (409, "Dealer order number already used", "Bu bayi sipariş numarası daha önce gönderilmiş.", "This dealer order number was already submitted."),
    "INVALID_STATE": (409, "Invalid state", "İşlem, kaydın mevcut durumunda yapılamaz.", "The operation is not allowed in the record's current state."),
    "PAYLOAD_TOO_LARGE": (413, "Payload too large", "İstek gövdesi 256 KB sınırını aşıyor.", "The request body exceeds the 256 KB limit."),
    "UNSUPPORTED_MEDIA_TYPE": (415, "Unsupported media type", "Content-Type application/json olmalıdır.", "Content-Type must be application/json."),
    "RATE_LIMIT_EXCEEDED": (429, "Rate limit exceeded", "İstek limiti aşıldı; Retry-After süresi sonra tekrar deneyin.", "Rate limit exceeded; retry after the Retry-After period."),
    "INTERNAL_ERROR": (500, "Internal error", "Beklenmeyen bir hata oluştu; requestId ile destek ekibine başvurun.", "An unexpected error occurred; contact support with the requestId."),
    "SERVICE_UNAVAILABLE": (503, "Service unavailable", "Servis geçici olarak kullanılamıyor; Retry-After süresi sonra tekrar deneyin.", "The service is temporarily unavailable; retry after the Retry-After period."),
}
FIELD_MESSAGES = {
    "FIELD_REQUIRED": ("{field} alanı zorunludur.", "{field} is required."),
    "FIELD_TOO_LONG": ("{field} alanı en fazla {max} karakter olabilir.", "{field} can be at most {max} characters."),
    "INVALID_FORMAT": ("{field} alanı beklenen biçimde değil.", "{field} is not in the expected format."),
    "INVALID_DATE": ("{field} geçerli bir tarih değil.", "{field} is not a valid date."),
    "DATE_OUT_OF_RANGE": ("{field} izin verilen aralığın dışında.", "{field} is outside the allowed range."),
    "NO_LINES": ("Sipariş en az bir satır içermelidir.", "The order must contain at least one line."),
    "TOO_MANY_LINES": ("Sipariş en fazla 200 satır içerebilir.", "The order can contain at most 200 lines."),
    "DUPLICATE_LINE_SKU": ("{sku} birden fazla satırda tekrar ediyor.", "{sku} appears on more than one line."),
    "QUANTITY_NOT_POSITIVE": ("Miktar sıfırdan büyük olmalıdır.", "Quantity must be greater than zero."),
    "QUANTITY_NOT_INTEGER": ("Adet birimi için miktar tam sayı olmalıdır.", "Quantity must be a whole number for piece units."),
    "INVALID_UNIT": ("{unit} birimi tanınmıyor veya ürünün satış birimiyle uyuşmuyor.", "Unit {unit} is unknown or does not match the product's sales unit."),
    "INVALID_CITY": ("{city} geçerli bir il değil.", "{city} is not a valid province."),
    "INVALID_COUNTRY": ("Bu sürümde yalnızca TR desteklenir.", "Only TR is supported in this version."),
    "INVALID_ADDRESS_CODE": ("{addressCode} bu bayi için tanımlı değil.", "{addressCode} is not defined for this dealer."),
    "TOO_MANY_SKUS": ("Stok sorgusu en fazla 50 SKU içerebilir.", "A stock query can contain at most 50 SKUs."),
    "UNKNOWN_FIELD": ("{field} tanınmayan bir alan.", "{field} is not a recognised field."),
}


def field_error(code, field, **params):
    return {"code": code, "field": field, "params": params}


# ---------------------------------------------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------------------------------------------
class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.started = now()
        self.tokens = {"sim-expired-token": ("D00042", 0.0)}
        self.calls = {}
        self.idempotency = {}
        self.orders = {}
        self.order_seq = 200
        self.reserved = {}
        self.invoices = {}
        self.integrator = {}
        self.receipt_seq = 480
        self.products = {}
        for sku, name, brand, category, unit, moq, vat, price, status in PRODUCT_ROWS:
            self.products[sku] = {"sku": sku, "name": name, "brand": brand, "category": category, "unitCode": unit,
                                  "minimumOrderQuantity": moq, "vatRate": vat, "price": Decimal(price), "status": status,
                                  "updatedAt": iso((self.started - timedelta(days=30)).replace(hour=8, minute=0, second=0, microsecond=0))}
        self.seed_case_orders()

    def seed_case_orders(self):
        """Orders and invoices of the case examples (OpenAPI and SOAP samples), dated in the 2027 case timeline."""
        case_lines = [("100234", "TV-VX55Q", 6, "18450.00"), ("200117", "SB-VX300", 12, "2890.00")]
        self.orders["VO-2027-000123"] = self.case_order(
            "VO-2027-000123", "PO-2027-00891", "2027-03-05", case_lines, "INVOICED",
            created="2027-03-05T09:14:07+03:00", shipped="2027-03-06T14:05:00+03:00", note="IRS2027000000987",
            invoice=("8f7a9c2e-1b3d-4e5f-9a6b-7c8d9e0f1a2b", "VKT2027000001234"), invoiced="2027-03-06T15:42:10+03:00")
        self.invoices["8f7a9c2e-1b3d-4e5f-9a6b-7c8d9e0f1a2b"] = {
            "ettn": "8f7a9c2e-1b3d-4e5f-9a6b-7c8d9e0f1a2b", "invoiceNo": "VKT2027000001234", "invoiceDate": "2027-03-06",
            "orderId": "VO-2027-000123", "deliveryNoteNo": "IRS2027000000987", "state": "DELIVERED",
            "deliveredAt": "2027-03-06T15:42:10+03:00", "acknowledgedAt": None}
        self.orders["VO-2027-000124"] = self.case_order(
            "VO-2027-000124", "PO-2027-00902", "2027-03-08", [("300410", None, 24, "899.00")], "SHIPPED",
            created="2027-03-08T10:02:44+03:00", shipped="2027-03-09T13:40:00+03:00", note="IRS2027000001012")
        self.invoices["2b6e1f0a-5c3d-4e7f-8a9b-0c1d2e3f4a5b"] = {
            "ettn": "2b6e1f0a-5c3d-4e7f-8a9b-0c1d2e3f4a5b", "invoiceNo": "VKT2027000001288", "invoiceDate": "2027-03-09",
            "orderId": "VO-2027-000124", "deliveryNoteNo": "IRS2027000001012", "state": "AT_INTEGRATOR",
            "deliveredAt": None, "acknowledgedAt": None}

    def case_order(self, order_id, dealer_no, order_date, rows, status, created, shipped, note, invoice=None, invoiced=None):
        lines = []
        for i, (sku, dealer_item, qty, price) in enumerate(rows, start=1):
            line = {"lineNo": i, "sku": sku, "requestedQuantity": qty, "approvedQuantity": qty, "unitCode": "C62",
                    "unitPrice": Decimal(price), "currency": "TRY", "vatRate": 20}
            if dealer_item:
                line["dealerItemCode"] = dealer_item
            lines.append(line)
        order = {"orderId": order_id, "dealerCode": "D00042", "dealerOrderNo": dealer_no, "status": "RECEIVED",
                 "orderDate": order_date, "deliveryAddress": dict(DEALERS["D00042"]["addresses"]["MAIN"], addressCode="MAIN"),
                 "lines": lines, "createdAt": created, "updatedAt": created, "history": [], "decidedBy": "SYSTEM"}
        price_order(order)
        add_history(order, "RECEIVED", at=created)
        add_history(order, "APPROVED", at=created, decided_by="SYSTEM")
        add_history(order, "ALLOCATED", at=created)
        order["shipment"] = {"shippedAt": shipped, "warehouseCode": "IST", "deliveryNoteNo": note,
                             "carrier": "Hızlı Lojistik", "trackingNo": "HL" + note[-9:], "packages": 4}
        add_history(order, "SHIPPED", at=shipped)
        if status == "INVOICED":
            order["invoice"] = {"ettn": invoice[0], "invoiceNo": invoice[1]}
            add_history(order, "INVOICED", at=invoiced)
        return order


def add_history(order, status, at=None, reason=None, decided_by=None):
    entry = {"sequence": len(order["history"]) + 1, "status": status, "occurredAt": at or iso(now())}
    if order["history"]:
        entry["previousStatus"] = order["history"][-1]["status"]
    if reason:
        entry["reasonCode"] = reason
    if decided_by:
        entry["decidedBy"] = decided_by
    order["history"].append(entry)
    order["status"] = status
    order["updatedAt"] = entry["occurredAt"]


def price_order(order):
    net = Decimal("0")
    vat = Decimal("0")
    for line in order["lines"]:
        line_net = money(Decimal(line["approvedQuantity"]) * line["unitPrice"])
        net += line_net
        vat += money(line_net * Decimal(line["vatRate"]) / 100)
    order["totals"] = {"netAmount": net, "vatAmount": vat, "grossAmount": net + vat, "currency": "TRY"}


STATE = None

# ---------------------------------------------------------------------------------------------------------------
# Representations
# ---------------------------------------------------------------------------------------------------------------
def order_view(order):
    out = {k: order[k] for k in ("orderId", "dealerCode", "dealerOrderNo", "status") if k in order}
    for k in ("reasonCode", "reasonText", "decidedBy", "orderDate", "requestedDeliveryDate", "deliveryAddress", "dealerNote"):
        if order.get(k) is not None:
            out[k] = order[k]
    lines = []
    for line in order["lines"]:
        item = {"lineNo": line["lineNo"], "sku": line["sku"], "requestedQuantity": num(line["requestedQuantity"]),
                "approvedQuantity": num(line["approvedQuantity"]), "unitCode": line["unitCode"]}
        for k in ("dealerItemCode", "lineReasonCode", "dealerLineRef"):
            if line.get(k):
                item[k] = line[k]
        if "unitPrice" in line:
            item.update(unitPrice=num(line["unitPrice"]), currency=line["currency"], vatRate=line["vatRate"])
        lines.append(item)
    out["lines"] = lines
    if order.get("totals"):
        t = order["totals"]
        out["totals"] = {"netAmount": num(t["netAmount"]), "vatAmount": num(t["vatAmount"]),
                         "grossAmount": num(t["grossAmount"]), "currency": t["currency"]}
    for k in ("shipment", "invoice"):
        if order.get(k):
            out[k] = order[k]
    out.update(createdAt=order["createdAt"], updatedAt=order["updatedAt"], history=order["history"],
               links={"self": f"/v1/orders/{order['orderId']}"})
    return out


def invoice_view(inv):
    order = STATE.orders[inv["orderId"]]
    lines = []
    for line in order["lines"]:
        item = {"lineNo": line["lineNo"], "sku": line["sku"], "quantity": num(line["approvedQuantity"]),
                "unitCode": line["unitCode"], "unitPrice": num(line["unitPrice"]), "vatRate": line["vatRate"],
                "lineTotal": num(money(Decimal(line["approvedQuantity"]) * line["unitPrice"]))}
        if line.get("dealerItemCode"):
            item["dealerItemCode"] = line["dealerItemCode"]
        lines.append(item)
    t = order["totals"]
    out = {"ettn": inv["ettn"], "invoiceNo": inv["invoiceNo"], "invoiceDate": inv["invoiceDate"], "profile": "TEMELFATURA",
           "invoiceType": "SATIS", "orderId": order["orderId"], "dealerOrderNo": order["dealerOrderNo"],
           "deliveryNoteNo": inv["deliveryNoteNo"], "currency": "TRY", "lineExtensionAmount": num(t["netAmount"]),
           "taxAmount": num(t["vatAmount"]), "payableAmount": num(t["grossAmount"]), "lines": lines,
           "deliveredAt": inv["deliveredAt"]}
    if inv.get("acknowledgedAt"):
        out["acknowledgedAt"] = inv["acknowledgedAt"]
    out["links"] = {"self": f"/v1/invoices/{inv['ettn']}", "acknowledge": f"/v1/invoices/{inv['ettn']}/acknowledge"}
    return out


def sellable(sku, warehouse):
    return max(0, ON_HAND.get(sku, {}).get(warehouse, 0) - STATE.reserved.get((sku, warehouse), 0))


# ---------------------------------------------------------------------------------------------------------------
# Order validation (field mapping section 3) and business rules (BRD RULE-01 to RULE-07)
# ---------------------------------------------------------------------------------------------------------------
TOP_FIELDS = {"dealerCode", "dealerOrderNo", "orderDate", "requestedDeliveryDate", "deliveryAddress", "dealerNote", "lines"}
ADDRESS_FIELDS = {"addressCode", "addressLine1", "addressLine2", "district", "city", "postalCode", "countryCode", "contactName", "contactPhone"}
LINE_FIELDS = {"lineNo", "sku", "dealerItemCode", "quantity", "unitCode", "dealerLineRef"}


def check_string(errors, obj, name, path, max_len, required):
    if name not in obj or obj[name] is None or (isinstance(obj[name], str) and not obj[name].strip()):
        if required:
            errors.append(field_error("FIELD_REQUIRED", path))
        return None
    value = obj[name]
    if not isinstance(value, str):
        errors.append(field_error("INVALID_FORMAT", path))
        return None
    if len(value) > max_len:
        errors.append(field_error("FIELD_TOO_LONG", path, max=max_len))
        return None
    return value.strip()


def check_date(errors, obj, name, path, required):
    value = check_string(errors, obj, name, path, 10, required)
    if value is None:
        return None
    try:
        if not DATE_RE.match(value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        errors.append(field_error("INVALID_DATE", path))
        return None


def validate_order(body, dealer):
    errors = []
    for key in body:
        if key not in TOP_FIELDS:
            errors.append(field_error("UNKNOWN_FIELD", key))
    check_string(errors, body, "dealerCode", "dealerCode", 10, True)
    check_string(errors, body, "dealerOrderNo", "dealerOrderNo", 30, True)
    order_date = check_date(errors, body, "orderDate", "orderDate", True)
    if order_date and (order_date > today() or order_date < today() - timedelta(days=30)):
        errors.append(field_error("DATE_OUT_OF_RANGE", "orderDate"))
    delivery = check_date(errors, body, "requestedDeliveryDate", "requestedDeliveryDate", False)
    if delivery and order_date and delivery < order_date:
        errors.append(field_error("DATE_OUT_OF_RANGE", "requestedDeliveryDate"))
    check_string(errors, body, "dealerNote", "dealerNote", 500, False)

    address = body.get("deliveryAddress")
    if address is None:
        errors.append(field_error("FIELD_REQUIRED", "deliveryAddress"))
    elif not isinstance(address, dict):
        errors.append(field_error("INVALID_FORMAT", "deliveryAddress"))
    else:
        for key in address:
            if key not in ADDRESS_FIELDS:
                errors.append(field_error("UNKNOWN_FIELD", f"deliveryAddress.{key}"))
        code = check_string(errors, address, "addressCode", "deliveryAddress.addressCode", 20, False)
        if code is not None:
            if code not in dealer["addresses"]:
                errors.append(field_error("INVALID_ADDRESS_CODE", "deliveryAddress.addressCode", addressCode=code))
        else:
            check_string(errors, address, "addressLine1", "deliveryAddress.addressLine1", 120, True)
            check_string(errors, address, "addressLine2", "deliveryAddress.addressLine2", 120, False)
            check_string(errors, address, "district", "deliveryAddress.district", 50, True)
            city = check_string(errors, address, "city", "deliveryAddress.city", 50, True)
            if city and turkish_fold(city) not in PROVINCE_KEYS:
                errors.append(field_error("INVALID_CITY", "deliveryAddress.city", city=city))
            postal = check_string(errors, address, "postalCode", "deliveryAddress.postalCode", 5, False)
            if postal and not re.fullmatch(r"\d{5}", postal):
                errors.append(field_error("INVALID_FORMAT", "deliveryAddress.postalCode"))
            country = check_string(errors, address, "countryCode", "deliveryAddress.countryCode", 2, False)
            if country and country != "TR":
                errors.append(field_error("INVALID_COUNTRY", "deliveryAddress.countryCode"))
            check_string(errors, address, "contactName", "deliveryAddress.contactName", 100, False)
            phone = check_string(errors, address, "contactPhone", "deliveryAddress.contactPhone", 20, False)
            if phone and not re.fullmatch(r"[+0-9 ]+", phone):
                errors.append(field_error("INVALID_FORMAT", "deliveryAddress.contactPhone"))

    lines = body.get("lines")
    if lines is None:
        errors.append(field_error("FIELD_REQUIRED", "lines"))
    elif not isinstance(lines, list):
        errors.append(field_error("INVALID_FORMAT", "lines"))
    elif not lines:
        errors.append(field_error("NO_LINES", "lines"))
    elif len(lines) > 200:
        errors.append(field_error("TOO_MANY_LINES", "lines"))
    else:
        seen = set()
        for i, line in enumerate(lines):
            path = f"lines[{i}]"
            if not isinstance(line, dict):
                errors.append(field_error("INVALID_FORMAT", path))
                continue
            for key in line:
                if key not in LINE_FIELDS:
                    errors.append(field_error("UNKNOWN_FIELD", f"{path}.{key}"))
            line_no = line.get("lineNo")
            if line_no is None:
                errors.append(field_error("FIELD_REQUIRED", f"{path}.lineNo"))
            elif isinstance(line_no, bool) or not isinstance(line_no, int) or line_no != i + 1:
                errors.append(field_error("INVALID_FORMAT", f"{path}.lineNo"))
            sku = check_string(errors, line, "sku", f"{path}.sku", 20, True)
            check_string(errors, line, "dealerItemCode", f"{path}.dealerItemCode", 50, False)
            check_string(errors, line, "dealerLineRef", f"{path}.dealerLineRef", 30, False)
            if sku:
                if sku in seen:
                    errors.append(field_error("DUPLICATE_LINE_SKU", f"{path}.sku", sku=sku))
                seen.add(sku)
            product = STATE.products.get(sku) if sku else None
            unit = line.get("unitCode")
            if unit is not None:
                if not isinstance(unit, str) or unit not in UNITS or (product and unit != product["unitCode"]):
                    errors.append(field_error("INVALID_UNIT", f"{path}.unitCode", unit=str(unit)))
                    unit = None
            elif product:
                unit = product["unitCode"]
            qty = line.get("quantity")
            if qty is None:
                errors.append(field_error("FIELD_REQUIRED", f"{path}.quantity"))
            elif isinstance(qty, bool) or not isinstance(qty, (int, Decimal)):
                errors.append(field_error("INVALID_FORMAT", f"{path}.quantity"))
            elif qty <= 0:
                errors.append(field_error("QUANTITY_NOT_POSITIVE", f"{path}.quantity"))
            elif Decimal(qty).as_tuple().exponent < -3:
                errors.append(field_error("INVALID_FORMAT", f"{path}.quantity"))
            elif unit in PIECE_UNITS and Decimal(qty) != Decimal(qty).to_integral_value():
                errors.append(field_error("QUANTITY_NOT_INTEGER", f"{path}.quantity"))
    return errors


def evaluate_rules(order, dealer):
    """RULE-02 to RULE-07: runs right after acceptance; the 202 response already reported RECEIVED."""
    for line in order["lines"]:
        product = STATE.products.get(line["sku"])
        if not product or product["status"] != "ACTIVE":
            return reject(order, "INVALID_SKU", "SKU satışa açık değil veya fiyat listesinde yok: " + line["sku"])
    for line in order["lines"]:
        if Decimal(line["requestedQuantity"]) < STATE.products[line["sku"]]["minimumOrderQuantity"]:
            return reject(order, "BELOW_MOQ", "Minimum sipariş miktarının altında: " + line["sku"])
    for line in order["lines"]:
        product = STATE.products[line["sku"]]
        line.update(unitPrice=product["price"], currency="TRY", vatRate=product["vatRate"])
    price_order(order)
    warehouse = dealer["warehouse"]
    if dealer["openBalance"] + order["totals"]["grossAmount"] > dealer["creditLimit"]:
        order["reasonCode"] = "CREDIT_LIMIT"
        add_history(order, "PENDING_APPROVAL", reason="CREDIT_LIMIT")
        return
    short = [line for line in order["lines"] if Decimal(line["requestedQuantity"]) > sellable(line["sku"], warehouse)]
    if short:
        for line in short:
            line["lineReasonCode"] = "PARTIAL_STOCK"
        order["reasonCode"] = "PARTIAL_STOCK"
        add_history(order, "PENDING_APPROVAL", reason="PARTIAL_STOCK")
        return
    order["decidedBy"] = "SYSTEM"
    add_history(order, "APPROVED", decided_by="SYSTEM")
    for line in order["lines"]:
        key = (line["sku"], warehouse)
        STATE.reserved[key] = STATE.reserved.get(key, 0) + int(Decimal(line["requestedQuantity"]))
    add_history(order, "ALLOCATED")


def reject(order, reason, text):
    for line in order["lines"]:
        line["approvedQuantity"] = 0
    order.update(reasonCode=reason, reasonText=text, decidedBy="SYSTEM")
    add_history(order, "REJECTED", reason=reason, decided_by="SYSTEM")


# ---------------------------------------------------------------------------------------------------------------
# SOAP helpers
# ---------------------------------------------------------------------------------------------------------------
NS = {"soapenv": "http://schemas.xmlsoap.org/soap/envelope/", "ein": "https://ws.kopru-ebelge.example/einvoice/v1",
      "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
      "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
FAULT_STRINGS = {1000: "Authentication failed", 2000: "Schema validation failed", 2002: "Hash mismatch",
                 2005: "ETTN already received", 3000: "Receiver not registered", 3001: "Receiver alias not found",
                 4004: "ETTN not found", 5000: "Internal error"}


def soap_envelope(body):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n'
            '    xmlns:ein="https://ws.kopru-ebelge.example/einvoice/v1">\n'
            f'  <soapenv:Body>\n{body}  </soapenv:Body>\n</soapenv:Envelope>\n').encode("utf-8")


class SoapFault(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def soap_text(parent, name):
    node = parent.find(f"ein:{name}", NS)
    if node is None or node.text is None or not node.text.strip():
        raise SoapFault(2000, f"Zorunlu alan eksik: {name}")
    return node.text.strip()


# ---------------------------------------------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "VektorSandboxSimulator/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    # ----- plumbing -----
    def dispatch(self, method):
        self.request_id = (self.headers.get("X-Request-Id") or "").strip()[:64] or "req_" + uuid.uuid4().hex[:12]
        self.lang = "en" if (self.headers.get("Accept-Language") or "").lower().startswith("en") else "tr"
        self.extra = {}
        parts = urlsplit(self.path)
        self.route = parts.path.rstrip("/") or "/"
        self.query = parse_qs(parts.query, keep_blank_values=True)
        length = int(self.headers.get("Content-Length") or 0)
        self.raw = self.rfile.read(length) if length else b""
        try:
            if self.route == "/" and method == "GET":
                return self.send(200, {"service": "Vektör sandbox simulator", "dealerApi": "/v1", "token": "/oauth2/token",
                                       "integratorSoap": "/kopru/einvoice/v1", "note": "Test double for the Postman collection."})
            if self.route == "/oauth2/token" and method == "POST":
                return self.token()
            if self.route == "/kopru/einvoice/v1" and method == "POST":
                return self.soap()
            if self.route == "/v1" or self.route.startswith("/v1/"):
                return self.api(method, self.route[3:] or "/")
            return self.send(*self.problem("NOT_FOUND"))
        except Exception:
            traceback.print_exc()
            return self.send(*self.problem("INTERNAL_ERROR"))

    def send(self, status, payload, content_type="application/json; charset=utf-8", headers=None):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False, default=num).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Request-Id", self.request_id)
        for key, value in {**self.extra, **(headers or {})}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def problem(self, code, errors=None, headers=None, instance=None):
        status, title, tr, en = ERRORS[code]
        if code == "VALIDATION_FAILED":
            n = len(errors)
            detail = tr.format(n=n) if self.lang == "tr" else en.format(n=n, s="" if n == 1 else "s")
        else:
            detail = tr if self.lang == "tr" else en
        body = {"type": "https://api.vektor-elektronik.example/problems/" + code.lower().replace("_", "-"),
                "title": title, "status": status, "detail": detail, "instance": instance or urlsplit(self.path).path,
                "code": code, "requestId": self.request_id, "timestamp": iso(now())}
        if errors is not None:
            body["errors"] = []
            for err in errors:
                template = FIELD_MESSAGES[err["code"]][0 if self.lang == "tr" else 1]
                label = err["field"] if err["code"] == "UNKNOWN_FIELD" else err["field"].split(".")[-1].split("[")[0]
                body["errors"].append({"code": err["code"], "field": err["field"],
                                       "message": template.format(field=label, **err["params"])})
        return status, body, "application/problem+json; charset=utf-8", headers

    def validation(self, errors):
        return self.problem("VALIDATION_FAILED", errors=errors)

    # ----- OAuth2 -----
    def token(self):
        form = parse_qs(self.raw.decode("utf-8", "replace"))
        client_id = (form.get("client_id") or [None])[0]
        secret = (form.get("client_secret") or [None])[0]
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Basic "):
            try:
                client_id, secret = base64.b64decode(auth[6:]).decode("utf-8").split(":", 1)
            except (ValueError, UnicodeDecodeError):
                pass
        if (form.get("grant_type") or [None])[0] != "client_credentials":
            return self.send(400, {"error": "unsupported_grant_type"})
        dealer = next((c for c, d in DEALERS.items() if d["clientId"] == client_id and d["clientSecret"] == secret), None)
        if dealer is None:
            return self.send(401, {"error": "invalid_client"})
        token = "sim_" + uuid.uuid4().hex
        with STATE.lock:
            STATE.tokens[token] = (dealer, time.time() + TOKEN_TTL)
        return self.send(200, {"access_token": token, "token_type": "Bearer", "expires_in": TOKEN_TTL,
                               "scope": "orders:write orders:read stock:read products:read invoices:read invoices:acknowledge"})

    def authenticate(self):
        auth = self.headers.get("Authorization") or ""
        if not auth.startswith("Bearer "):
            return None
        entry = STATE.tokens.get(auth[7:].strip())
        if not entry or entry[1] < time.time():
            return None
        return entry[0]

    def rate_limit(self, dealer, bucket):
        limit = LIMITS[bucket]
        t = time.time()
        with STATE.lock:
            calls = STATE.calls.setdefault((dealer, bucket), deque())
            while calls and calls[0] <= t - 60:
                calls.popleft()
            allowed = len(calls) < limit
            if allowed:
                calls.append(t)
            oldest = calls[0] if calls else t
        self.extra.update({"X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": str(max(0, limit - len(calls))),
                           "X-RateLimit-Reset": str(math.ceil(oldest + 60))})
        if not allowed:
            self.extra["Retry-After"] = str(max(1, math.ceil(oldest + 60 - t)))
        return allowed

    # ----- dealer API -----
    def api(self, method, path):
        if path == "/health" and method == "GET":
            return self.send(200, {"status": "ok", "time": iso(now()), "version": "1.0.0-simulator"})
        dealer_code = self.authenticate()
        if dealer_code is None:
            return self.send(*self.problem("UNAUTHORIZED"))
        dealer = DEALERS[dealer_code]
        if dealer["status"] != "ACTIVE":
            return self.send(*self.problem("DEALER_SUSPENDED"))
        bucket = "stock" if path == "/stock" else "orders_post" if (path == "/orders" and method == "POST") else "other"
        if not self.rate_limit(dealer_code, bucket):
            return self.send(*self.problem("RATE_LIMIT_EXCEEDED"))
        if path == "/orders" and method == "POST":
            return self.submit_order(dealer_code)
        if path == "/orders" and method == "GET":
            return self.list_orders(dealer_code)
        match = re.fullmatch(r"/orders/([^/]+)", path)
        if match and method == "GET":
            return self.get_order(dealer_code, match.group(1))
        if path == "/stock" and method == "GET":
            return self.stock(dealer_code)
        if path == "/products" and method == "GET":
            return self.products()
        if path == "/invoices" and method == "GET":
            return self.list_invoices(dealer_code)
        match = re.fullmatch(r"/invoices/([^/]+)", path)
        if match and method == "GET":
            return self.get_invoice(dealer_code, match.group(1))
        match = re.fullmatch(r"/invoices/([^/]+)/acknowledge", path)
        if match and method == "POST":
            return self.acknowledge(dealer_code, match.group(1))
        return self.send(*self.problem("NOT_FOUND"))

    def submit_order(self, dealer_code):
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            return self.send(*self.problem("UNSUPPORTED_MEDIA_TYPE"))
        if len(self.raw) > MAX_BODY:
            return self.send(*self.problem("PAYLOAD_TOO_LARGE"))
        key = (self.headers.get("Idempotency-Key") or "").strip().lower()
        if not key:
            return self.send(*self.problem("MISSING_IDEMPOTENCY_KEY"))
        if not UUID_RE.match(key):
            return self.send(*self.problem("INVALID_IDEMPOTENCY_KEY"))
        try:
            parsed = json.loads(self.raw.decode("utf-8"), parse_float=Decimal)
            digest = hashlib.sha256(json.dumps(parsed, sort_keys=True, default=str).encode()).hexdigest()
        except (ValueError, UnicodeDecodeError):
            parsed, digest = None, hashlib.sha256(self.raw).hexdigest()
        slot = (dealer_code, key)
        with STATE.lock:
            entry = STATE.idempotency.get(slot)
            if entry and entry["state"] == "in_progress":
                return self.send(*self.problem("REQUEST_IN_PROGRESS", headers={"Retry-After": "2"}))
            if entry and entry["hash"] != digest:
                return self.send(*self.problem("IDEMPOTENCY_KEY_REUSED"))
            if entry:
                return self.send(*entry["response"])
            STATE.idempotency[slot] = {"state": "in_progress", "hash": digest, "at": time.time()}
        try:
            time.sleep(ORDER_PROCESSING_SECONDS)
            response = self.create_order(dealer_code, parsed)
        except Exception:
            with STATE.lock:
                STATE.idempotency.pop(slot, None)
            raise
        with STATE.lock:
            STATE.idempotency[slot] = {"state": "done", "hash": digest, "at": time.time(), "response": response}
        return self.send(*response)

    def create_order(self, dealer_code, body):
        dealer = DEALERS[dealer_code]
        if not isinstance(body, dict):
            return self.validation([field_error("INVALID_FORMAT", "body")])
        errors = validate_order(body, dealer)
        if errors:
            return self.validation(errors)
        if body["dealerCode"].strip() != dealer_code:
            return self.problem("DEALER_MISMATCH")
        with STATE.lock:
            dealer_no = body["dealerOrderNo"].strip()
            if any(o["dealerCode"] == dealer_code and o["dealerOrderNo"] == dealer_no and o["status"] != "REJECTED"
                   for o in STATE.orders.values()):
                return self.problem("DUPLICATE_DEALER_ORDER_NO")
            STATE.order_seq += 1
            order_id = f"VO-{today().year}-{STATE.order_seq:06d}"
            address = body["deliveryAddress"]
            if address.get("addressCode"):
                address = dict(dealer["addresses"][address["addressCode"]], addressCode=address["addressCode"])
            else:
                address = dict(address)
                address.setdefault("countryCode", "TR")
            lines = []
            for line in body["lines"]:
                product = STATE.products.get(line["sku"].strip())
                item = {"lineNo": line["lineNo"], "sku": line["sku"].strip(), "requestedQuantity": line["quantity"],
                        "approvedQuantity": line["quantity"],
                        "unitCode": line.get("unitCode") or (product["unitCode"] if product else "C62")}
                for k in ("dealerItemCode", "dealerLineRef"):
                    if line.get(k):
                        item[k] = line[k]
                lines.append(item)
            created = iso(now())
            order = {"orderId": order_id, "dealerCode": dealer_code, "dealerOrderNo": dealer_no, "status": "RECEIVED",
                     "orderDate": body["orderDate"], "requestedDeliveryDate": body.get("requestedDeliveryDate"),
                     "deliveryAddress": address, "dealerNote": body.get("dealerNote"), "lines": lines,
                     "createdAt": created, "updatedAt": created, "history": []}
            add_history(order, "RECEIVED", at=created)
            STATE.orders[order_id] = order
            accepted = {"orderId": order_id, "dealerOrderNo": dealer_no, "status": "RECEIVED", "receivedAt": created,
                        "links": {"self": f"/v1/orders/{order_id}"}}
            evaluate_rules(order, dealer)
        return 202, accepted, "application/json; charset=utf-8", {"Location": f"/v1/orders/{order_id}"}

    def page(self, items):
        errors = []
        size_raw = (self.query.get("pageSize") or ["50"])[0]
        try:
            size = int(size_raw)
            if not 1 <= size <= 100:
                raise ValueError
        except ValueError:
            errors.append(field_error("INVALID_FORMAT", "pageSize"))
            size = 50
        offset = 0
        token = (self.query.get("pageToken") or [""])[0]
        if token:
            try:
                offset = int(json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))["offset"])
            except (ValueError, KeyError, TypeError):
                errors.append(field_error("INVALID_FORMAT", "pageToken"))
        if errors:
            return None, errors
        out = {"items": items[offset:offset + size]}
        if offset + size < len(items):
            out["nextPageToken"] = base64.urlsafe_b64encode(json.dumps({"offset": offset + size}).encode()).decode().rstrip("=")
        return out, None

    def parse_datetime_param(self, name, errors):
        raw = (self.query.get(name) or [""])[0]
        if not raw:
            return None
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return value if value.tzinfo else value.replace(tzinfo=TZ)
        except ValueError:
            errors.append(field_error("INVALID_FORMAT", name))
            return None

    def list_orders(self, dealer_code):
        errors = []
        statuses = [s for s in ",".join(self.query.get("status") or []).split(",") if s]
        if any(s not in STATUSES for s in statuses):
            errors.append(field_error("INVALID_FORMAT", "status"))
        created_from = self.parse_datetime_param("createdFrom", errors)
        created_to = self.parse_datetime_param("createdTo", errors)
        if errors:
            return self.send(*self.validation(errors))
        dealer_no = (self.query.get("dealerOrderNo") or [""])[0]
        with STATE.lock:
            orders = [o for o in STATE.orders.values() if o["dealerCode"] == dealer_code]
            if dealer_no:
                orders = [o for o in orders if o["dealerOrderNo"] == dealer_no]
            if statuses:
                orders = [o for o in orders if o["status"] in statuses]
            if created_from:
                orders = [o for o in orders if datetime.fromisoformat(o["createdAt"]) >= created_from]
            if created_to:
                orders = [o for o in orders if datetime.fromisoformat(o["createdAt"]) < created_to]
            orders.sort(key=lambda o: (o["createdAt"], o["orderId"]), reverse=True)
            views = [order_view(o) for o in orders]
        page, errors = self.page(views)
        return self.send(*self.validation(errors)) if errors else self.send(200, page)

    def get_order(self, dealer_code, order_id):
        with STATE.lock:
            order = STATE.orders.get(order_id) if ORDER_ID_RE.match(order_id) else None
            if order is None:
                return self.send(*self.problem("NOT_FOUND"))
            if order["dealerCode"] != dealer_code:
                return self.send(*self.problem("FORBIDDEN_RESOURCE"))
            return self.send(200, order_view(order))

    def stock(self, dealer_code):
        skus = [s.strip() for s in ",".join(self.query.get("sku") or []).split(",") if s.strip()]
        if not skus:
            return self.send(*self.validation([field_error("FIELD_REQUIRED", "sku")]))
        if len(skus) > 50:
            return self.send(*self.validation([field_error("TOO_MANY_SKUS", "sku")]))
        too_long = [i for i, s in enumerate(skus) if len(s) > 20]
        if too_long:
            return self.send(*self.validation([field_error("FIELD_TOO_LONG", f"sku[{i}]", max=20) for i in too_long]))
        shipping = DEALERS[dealer_code]["warehouse"]
        items = []
        with STATE.lock:
            for sku in skus:
                product = STATE.products.get(sku)
                if product is None:
                    items.append({"sku": sku, "status": "UNKNOWN"})
                    continue
                if product["status"] != "ACTIVE":
                    items.append({"sku": sku, "status": "INACTIVE"})
                    continue
                warehouses = []
                for wh in WAREHOUSES:
                    entry = {"warehouseCode": wh, "isShippingWarehouse": wh == shipping, "sellableQuantity": sellable(sku, wh)}
                    if (sku, wh) in EXPECTED_RECEIPTS:
                        days, qty = EXPECTED_RECEIPTS[(sku, wh)]
                        entry.update(expectedReceiptDate=(today() + timedelta(days=days)).isoformat(), expectedReceiptQuantity=qty)
                    warehouses.append(entry)
                items.append({"sku": sku, "status": "OK", "unitCode": product["unitCode"],
                              "minimumOrderQuantity": product["minimumOrderQuantity"], "warehouses": warehouses})
        return self.send(200, {"asOf": iso(now()), "items": items})

    def products(self):
        errors = []
        status = (self.query.get("status") or [""])[0]
        if status and status not in ("ACTIVE", "INACTIVE"):
            errors.append(field_error("INVALID_FORMAT", "status"))
        since = self.parse_datetime_param("updatedSince", errors)
        if errors:
            return self.send(*self.validation(errors))
        items = []
        for p in STATE.products.values():
            if status and p["status"] != status:
                continue
            if since and datetime.fromisoformat(p["updatedAt"]) < since:
                continue
            items.append({"sku": p["sku"], "name": p["name"], "brand": p["brand"], "category": p["category"],
                          "unitCode": p["unitCode"], "minimumOrderQuantity": p["minimumOrderQuantity"],
                          "vatRate": p["vatRate"], "status": p["status"],
                          "price": {"unitPrice": num(p["price"]), "currency": "TRY", "validFrom": f"{STATE.started.year}-01-01"},
                          "updatedAt": p["updatedAt"]})
        page, errors = self.page(items)
        return self.send(*self.validation(errors)) if errors else self.send(200, page)

    def visible_invoices(self, dealer_code):
        return [inv for inv in STATE.invoices.values()
                if inv["state"] == "DELIVERED" and STATE.orders[inv["orderId"]]["dealerCode"] == dealer_code]

    def list_invoices(self, dealer_code):
        errors = []
        order_id = (self.query.get("orderId") or [""])[0]
        if order_id and not ORDER_ID_RE.match(order_id):
            errors.append(field_error("INVALID_FORMAT", "orderId"))
        bounds = {}
        for name in ("issuedFrom", "issuedTo"):
            raw = (self.query.get(name) or [""])[0]
            if raw:
                try:
                    if not DATE_RE.match(raw):
                        raise ValueError
                    bounds[name] = date.fromisoformat(raw).isoformat()
                except ValueError:
                    errors.append(field_error("INVALID_DATE", name))
        if errors:
            return self.send(*self.validation(errors))
        dealer_no = (self.query.get("dealerOrderNo") or [""])[0]
        with STATE.lock:
            invoices = self.visible_invoices(dealer_code)
            if order_id:
                invoices = [i for i in invoices if i["orderId"] == order_id]
            if dealer_no:
                invoices = [i for i in invoices if STATE.orders[i["orderId"]]["dealerOrderNo"] == dealer_no]
            if "issuedFrom" in bounds:
                invoices = [i for i in invoices if i["invoiceDate"] >= bounds["issuedFrom"]]
            if "issuedTo" in bounds:
                invoices = [i for i in invoices if i["invoiceDate"] <= bounds["issuedTo"]]
            invoices.sort(key=lambda i: (i["invoiceDate"], i["invoiceNo"]), reverse=True)
            views = [invoice_view(i) for i in invoices]
        page, errors = self.page(views)
        return self.send(*self.validation(errors)) if errors else self.send(200, page)

    def get_invoice(self, dealer_code, ettn):
        with STATE.lock:
            inv = STATE.invoices.get(ettn.lower())
            if inv is None or inv["state"] != "DELIVERED":
                return self.send(*self.problem("NOT_FOUND"))
            if STATE.orders[inv["orderId"]]["dealerCode"] != dealer_code:
                return self.send(*self.problem("FORBIDDEN_RESOURCE"))
            return self.send(200, invoice_view(inv))

    def acknowledge(self, dealer_code, ettn):
        if self.raw.strip():
            try:
                body = json.loads(self.raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self.send(*self.validation([field_error("INVALID_FORMAT", "body")]))
            if not isinstance(body, dict):
                return self.send(*self.validation([field_error("INVALID_FORMAT", "body")]))
            errors = [field_error("UNKNOWN_FIELD", k) for k in body if k != "dealerDocumentNo"]
            check_string(errors, body, "dealerDocumentNo", "dealerDocumentNo", 30, False)
            if errors:
                return self.send(*self.validation(errors))
        with STATE.lock:
            inv = STATE.invoices.get(ettn.lower())
            if inv is None:
                return self.send(*self.problem("NOT_FOUND"))
            order = STATE.orders[inv["orderId"]]
            if order["dealerCode"] != dealer_code:
                return self.send(*self.problem("FORBIDDEN_RESOURCE"))
            if order["status"] not in ("INVOICED", "CLOSED"):
                return self.send(*self.problem("INVALID_STATE"))
            if order["status"] == "INVOICED":
                inv["acknowledgedAt"] = iso(now())
                add_history(order, "CLOSED")
            return self.send(200, {"ettn": inv["ettn"], "orderId": order["orderId"], "orderStatus": order["status"],
                                   "acknowledgedAt": inv["acknowledgedAt"]})

    # ----- Köprü e-Belge SOAP service -----
    def soap(self):
        try:
            try:
                root = ET.fromstring(self.raw)
            except ET.ParseError:
                raise SoapFault(2000, "XML ayrıştırılamadı.")
            user = root.find(".//wsse:Username", NS)
            password = root.find(".//wsse:Password", NS)
            if user is None or password is None or user.text != INTEGRATOR_USER or password.text != INTEGRATOR_PASSWORD:
                raise SoapFault(1000, "Kimlik doğrulama başarısız: kullanıcı adı veya parola hatalı.")
            body = root.find("soapenv:Body", NS)
            if body is None or not len(body):
                raise SoapFault(2000, "SOAP Body boş.")
            request = body[0]
            operation = request.tag.split("}")[-1]
            action = (self.headers.get("SOAPAction") or "").strip('"')
            if action and not action.endswith("/" + operation.replace("Request", "")):
                raise SoapFault(2000, f"SOAPAction ({action}) gövdeyle uyuşmuyor.")
            if operation == "CheckUserRequest":
                xml = self.check_user(request)
            elif operation == "SendInvoiceRequest":
                xml = self.send_invoice(request)
            elif operation == "GetInvoiceStatusRequest":
                xml = self.invoice_status(request)
            else:
                raise SoapFault(2000, f"Bilinmeyen operasyon: {operation}")
            return self.send(200, soap_envelope(xml), "text/xml; charset=utf-8")
        except SoapFault as fault:
            fault_code = "soapenv:Server" if fault.code >= 5000 else "soapenv:Client"
            xml = ("    <soapenv:Fault>\n"
                   f"      <faultcode>{fault_code}</faultcode>\n"
                   f"      <faultstring>{escape(FAULT_STRINGS.get(fault.code, 'Error'))}</faultstring>\n"
                   "      <detail>\n        <ein:ServiceFault>\n"
                   f"          <ein:code>{fault.code}</ein:code>\n"
                   f"          <ein:message>{escape(fault.message)}</ein:message>\n"
                   f"          <ein:requestId>kopru-{uuid.uuid4().hex[:8]}</ein:requestId>\n"
                   "        </ein:ServiceFault>\n      </detail>\n    </soapenv:Fault>\n")
            return self.send(500, soap_envelope(xml), "text/xml; charset=utf-8")

    def check_user(self, request):
        vkn = soap_text(request, "vkn")
        if not re.fullmatch(r"\d{10}", vkn):
            raise SoapFault(2000, "vkn 10 haneli olmalıdır.")
        if vkn not in REGISTERED_USERS:
            return (f"    <ein:CheckUserResponse>\n      <ein:vkn>{vkn}</ein:vkn>\n"
                    "      <ein:registered>false</ein:registered>\n    </ein:CheckUserResponse>\n")
        title, domain = REGISTERED_USERS[vkn]
        aliases = "".join(
            f"        <ein:alias>\n          <ein:alias>urn:mail:default{kind.lower()}@{domain}</ein:alias>\n"
            f"          <ein:kind>{kind}</ein:kind>\n          <ein:registeredAt>2019-04-01</ein:registeredAt>\n"
            "        </ein:alias>\n" for kind in ("PK", "GB"))
        return (f"    <ein:CheckUserResponse>\n      <ein:vkn>{vkn}</ein:vkn>\n      <ein:registered>true</ein:registered>\n"
                f"      <ein:title>{escape(title)}</ein:title>\n      <ein:firstRegisteredAt>2019-04-01</ein:firstRegisteredAt>\n"
                f"      <ein:aliases>\n{aliases}      </ein:aliases>\n    </ein:CheckUserResponse>\n")

    def send_invoice(self, request):
        doc = request.find("ein:document", NS)
        if doc is None:
            raise SoapFault(2000, "document alanı eksik.")
        ettn = soap_text(doc, "ettn").lower()
        invoice_no = soap_text(doc, "invoiceNo")
        profile = soap_text(doc, "profile")
        receiver_vkn = soap_text(doc, "receiverVkn")
        receiver_alias = soap_text(doc, "receiverAlias")
        if soap_text(doc, "hashAlgorithm") != "SHA-256" or soap_text(doc, "contentType") != "application/zip":
            raise SoapFault(2000, "contentType application/zip ve hashAlgorithm SHA-256 olmalıdır.")
        expected_hash = soap_text(doc, "hash").lower()
        try:
            data = base64.b64decode("".join(soap_text(doc, "content").split()), validate=True)
        except ValueError:
            raise SoapFault(2000, "content geçerli base64 değil.")
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise SoapFault(2002, "hash, content ile eşleşmiyor.")
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
            document = archive.read(f"{ettn}.xml")
        except (zipfile.BadZipFile, KeyError):
            raise SoapFault(2000, f"Zip içinde {ettn}.xml bulunamadı.")
        try:
            invoice = ET.fromstring(document)
        except ET.ParseError:
            raise SoapFault(2000, "UBL-TR belgesi ayrıştırılamadı.")
        header = {name: (invoice.findtext(f"cbc:{name}", namespaces=NS) or "").strip() for name in ("UUID", "ID", "ProfileID")}
        if header["UUID"].lower() != ettn or header["ID"] != invoice_no or header["ProfileID"] != profile:
            raise SoapFault(2000, "Belge başlığı (UUID, ID, ProfileID) mesajla uyuşmuyor.")
        if receiver_vkn not in REGISTERED_USERS:
            raise SoapFault(3000, f"Alıcı {receiver_vkn} kayıtlı e-Fatura kullanıcısı değil.")
        if receiver_alias != f"urn:mail:defaultpk@{REGISTERED_USERS[receiver_vkn][1]}":
            raise SoapFault(3001, f"Alıcı posta kutusu bulunamadı: {receiver_alias}")
        with STATE.lock:
            if ettn in STATE.integrator:
                raise SoapFault(2005, f"ETTN daha önce alındı; özgün makbuz: {STATE.integrator[ettn]['receiptId']}")
            STATE.receipt_seq += 1
            received = now()
            receipt = f"RCP-{received:%Y-%m%d}-{STATE.receipt_seq:06d}"
            STATE.integrator[ettn] = {"receiptId": receipt, "receivedAt": iso(received), "polls": 0,
                                      "envelopeId": str(uuid.uuid4())}
        return (f"    <ein:SendInvoiceResponse>\n      <ein:receiptId>{receipt}</ein:receiptId>\n"
                f"      <ein:ettn>{ettn}</ein:ettn>\n      <ein:receivedAt>{iso(received)}</ein:receivedAt>\n"
                "      <ein:status>QUEUED</ein:status>\n    </ein:SendInvoiceResponse>\n")

    def invoice_status(self, request):
        ettn = soap_text(request, "ettn").lower()
        with STATE.lock:
            entry = STATE.integrator.get(ettn)
            if entry is None:
                raise SoapFault(4004, f"ETTN bulunamadı: {ettn}")
            entry["polls"] += 1
            delivered = entry["polls"] >= 2      # first poll: sent to GİB, second poll: delivered
        status, code, text = ("DELIVERED", 1300, "Zarf başarıyla alıcıya iletildi") if delivered else \
                             ("SENT", 1200, "Zarf GİB'e iletildi, alıcı yanıtı bekleniyor")
        return (f"    <ein:GetInvoiceStatusResponse>\n      <ein:ettn>{ettn}</ein:ettn>\n      <ein:status>{status}</ein:status>\n"
                f"      <ein:stateCode>{code}</ein:stateCode>\n      <ein:stateDescription>{escape(text)}</ein:stateDescription>\n"
                f"      <ein:envelopeId>{entry['envelopeId']}</ein:envelopeId>\n      <ein:updatedAt>{iso(now())}</ein:updatedAt>\n"
                "    </ein:GetInvoiceStatusResponse>\n")


def main():
    global STATE
    parser = argparse.ArgumentParser(description="Vektör sandbox simulator (test double for the Postman collection)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8040)
    args = parser.parse_args()
    STATE = State()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print(f"Vektör sandbox simulator on http://{args.host}:{args.port}  (dealer API /v1, token /oauth2/token, "
          f"integrator SOAP /kopru/einvoice/v1)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
