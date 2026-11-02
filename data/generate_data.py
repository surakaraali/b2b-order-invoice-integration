#!/usr/bin/env python3
"""Generate the synthetic integration dataset of the B2B order, stock and invoice case.

The data covers the first 13 weeks after go-live, Monday 5 April to Saturday 3 July 2027, for 120 dealers. It is
deterministic: the fixed seed gives identical CSV files on every run. Problems are planted at known rates (see
data/README.md) so that the SQL results in sql/ can be checked against what was put in.

Usage, from the repository root:
    python3 data/generate_data.py

Output: data/raw/*.csv. All timestamps are Türkiye local time (UTC+3), written as YYYY-MM-DD HH:MM:SS.
Standard library only. All companies, people and figures are fictional.
"""
import csv
import math
import random
from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SEED = 20270405
rng = random.Random(SEED)
OUT = Path(__file__).resolve().parent / "raw"

START, END = date(2027, 4, 5), date(2027, 7, 3)           # go-live Monday to the last Saturday of week 13
AS_OF = datetime(2027, 7, 5, 7, 0)                         # the daily exception report runs on Monday 5 July at 07:00
WORK_START, WORK_END = 8, 20                               # business hours, Monday to Saturday (NFR section 2)
HOLIDAYS = {
    date(2027, 4, 23): "Ulusal Egemenlik ve Çocuk Bayramı",
    date(2027, 5, 1): "Emek ve Dayanışma Günü",
    date(2027, 5, 17): "Kurban Bayramı (assumed date)",
    date(2027, 5, 18): "Kurban Bayramı (assumed date)",
    date(2027, 5, 19): "Gençlik ve Spor Bayramı; Kurban Bayramı (assumed date)",
}
INCIDENTS = [
    ("INC-2027-014", "ERP", datetime(2027, 5, 11, 10, 5), datetime(2027, 5, 11, 11, 50),
     "ERP database failover; business rules could not read credit and stock data"),
    ("INC-2027-022", "INTEGRATOR", datetime(2027, 6, 8, 14, 0), datetime(2027, 6, 8, 16, 10),
     "Köprü e-Belge SOAP service unreachable after a certificate change on the integrator side"),
]
WEBHOOK_OUTAGES = {  # dealer endpoint outages: dealer -> list of (start, end); end None = still down at AS_OF
    "D00031": [(datetime(2027, 6, 14, 8, 0), datetime(2027, 6, 16, 18, 0))],
    "D00087": [(datetime(2027, 7, 2, 8, 0), None)],
}

# Planted rates (documented in data/README.md)
RATES = {
    "rules_invalid_sku": 0.005, "rules_below_moq": 0.003,
    "pending_credit_limit": 0.05, "pending_partial_stock": 0.06,
    "approval_late": 0.13,
    "decision_approve": 0.68, "decision_reduce": 0.17,               # rest: reject
    "late_shipment_confirmation": 0.025,
    "invoice_stuck_in_erp": 0.002, "invoice_held": 0.0025, "invoice_send_failed": 0.0035,
    "invoice_error_after_send": 0.002, "invoice_slow_delivery": 0.0015,
    "webhook_transient_failure": 0.02,
    "ack_late": 0.06, "ack_never": 0.01, "ack_mismatch": 0.004,
    "submission_failed_api": 0.05, "submission_failed_portal": 0.015, "submission_replay_api": 0.015,
    "manual_after_live_api": 0.03,
    "corrected_manual": 0.035, "corrected_portal": 0.006, "corrected_api": 0.002,
}


# ---------------------------------------------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------------------------------------------
def is_working(d):
    return d.weekday() != 6 and d not in HOLIDAYS


def next_working_day(d):
    d += timedelta(days=1)
    while not is_working(d):
        d += timedelta(days=1)
    return d


def add_working_days(d, n):
    for _ in range(n):
        d = next_working_day(d)
    return d


def to_business(dt):
    d = dt.date()
    if is_working(d) and dt.time() < time(WORK_START):
        return datetime.combine(d, time(WORK_START))
    if is_working(d) and dt.time() < time(WORK_END):
        return dt
    return datetime.combine(next_working_day(d), time(WORK_START))


def add_business_minutes(dt, minutes):
    dt = to_business(dt)
    remaining = minutes
    while True:
        available = (datetime.combine(dt.date(), time(WORK_END)) - dt).total_seconds() / 60
        if remaining <= available:
            return dt + timedelta(minutes=remaining)
        remaining -= available
        dt = datetime.combine(next_working_day(dt.date()), time(WORK_START))


def lognormal(median, p95):
    sigma = math.log(p95 / median) / 1.645
    return rng.lognormvariate(math.log(median), sigma)


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""


def money(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def chance(p):
    return rng.random() < p


WORKING_DAYS = []
d = START
while d <= END:
    if is_working(d):
        WORKING_DAYS.append(d)
    d += timedelta(days=1)


# ---------------------------------------------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------------------------------------------
CITIES = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Konya", "Kocaeli", "Kayseri", "Eskişehir", "Gaziantep",
          "Adana", "Mersin", "Samsun", "Trabzon", "Denizli", "Manisa", "Sakarya", "Tekirdağ", "Malatya", "Aydın"]
WORDS = ["Elektronik", "Teknoloji", "Bilişim", "Ev Aletleri", "Dijital", "Elektrik", "Medya"]
WAREHOUSE_BY_CITY = {"Ankara": "ANK", "Konya": "ANK", "Kayseri": "ANK", "Eskişehir": "ANK", "Samsun": "ANK",
                     "Trabzon": "ANK", "Malatya": "ANK", "Gaziantep": "ANK", "Adana": "ANK",
                     "İzmir": "IZM", "Manisa": "IZM", "Denizli": "IZM", "Aydın": "IZM", "Antalya": "IZM", "Mersin": "IZM"}


def build_dealers():
    dealers = []
    profiles = ["LARGE"] * 15 + ["MID"] * 45 + ["SMALL"] * 60
    rng.shuffle(profiles)
    for n in range(1, 121):
        code = f"D{n:05d}"
        profile = profiles[n - 1]
        city = rng.choice(CITIES)
        name = f"{city} {rng.choice(WORDS)} {'A.Ş.' if profile == 'LARGE' else 'Ltd. Şti.'}"
        erp = {"LARGE": "SAP_B1" if chance(0.6) else "LOGO",
               "MID": rng.choices(["LOGO", "SAP_B1", "NONE"], [30, 5, 10])[0],
               "SMALL": "NONE"}[profile]
        dealers.append({"dealer_code": code, "dealer_name": name, "city": city, "profile": profile, "erp": erp})
    case = {"D00042": ("Marmara Teknoloji Ürünleri Ticaret A.Ş.", "Kocaeli", "LARGE", "SAP_B1"),
            "D00077": ("Ege Bilişim Sistemleri Ltd. Şti.", "İzmir", "MID", "LOGO"),
            "D00099": ("Çınar Elektronik", "İstanbul", "SMALL", "NONE")}
    for dealer in dealers:
        if dealer["dealer_code"] in case:
            dealer["dealer_name"], dealer["city"], dealer["profile"], dealer["erp"] = case[dealer["dealer_code"]]
    # the two dealers whose webhook endpoints fail are large ERP-connected dealers
    next(x for x in dealers if x["dealer_code"] == "D00031").update(profile="LARGE", erp="LOGO")
    next(x for x in dealers if x["dealer_code"] == "D00087").update(profile="LARGE", erp="SAP_B1")

    reps = [f"R{i:02d}" for i in range(1, 9)]
    for i, dealer in enumerate(dealers):
        dealer["channel"] = "API" if dealer["erp"] != "NONE" else "PORTAL"
        dealer["warehouse"] = WAREHOUSE_BY_CITY.get(dealer["city"], "IST")
        dealer["sales_rep"] = reps[i % 8]
        week = lambda lo, hi: START + timedelta(days=7 * rng.randint(lo, hi) + rng.randint(0, 5))
        if dealer["dealer_code"] in ("D00042", "D00077"):
            live = date(2027, 2, 15)                                       # pilot dealers
        elif dealer["dealer_code"] == "D00031":
            live = date(2027, 4, 26)
        elif dealer["dealer_code"] == "D00087":
            live = date(2027, 5, 10)
        elif dealer["profile"] == "LARGE":
            live = week(0, 8)
        elif dealer["channel"] == "API":
            live = week(2, 17)                                             # some go live after week 13
        else:
            live = week(1, 20)
        dealer["integration_live_date"] = live if live <= END else None
        dealer["webhook_registered"] = dealer["channel"] == "API" and (dealer["dealer_code"] in ("D00031", "D00087") or chance(0.95))
        dealer["acknowledges_invoices"] = dealer["channel"] == "API" and (dealer["erp"] == "SAP_B1" or chance(0.7))
        dealer["status"] = "ACTIVE"
        dealer["suspended_from"] = None
    d99 = next(x for x in dealers if x["dealer_code"] == "D00099")
    d99.update(status="SUSPENDED", suspended_from=date(2027, 6, 21), integration_live_date=date(2027, 4, 19))
    return dealers


PRODUCTS = [  # sku, name, category, unit, moq, price, status
    ("100234", "VX-55Q 55-inch 4K television", "Television", "C62", 2, "18450.00", "ACTIVE"),
    ("100235", "VX-65Q 65-inch 4K television", "Television", "C62", 1, "27900.00", "ACTIVE"),
    ("100236", "VX-43F 43-inch Full HD television", "Television", "C62", 2, "11990.00", "ACTIVE"),
    ("100237", "VX-50Q 50-inch 4K television", "Television", "C62", 2, "15490.00", "ACTIVE"),
    ("100238", "VX-75Q 75-inch 4K television", "Television", "C62", 1, "41900.00", "ACTIVE"),
    ("200117", "VX-300 soundbar", "Audio", "C62", 4, "2890.00", "ACTIVE"),
    ("200118", "VX-500 soundbar with subwoofer", "Audio", "C62", 2, "5490.00", "ACTIVE"),
    ("200120", "S1 Bluetooth speaker", "Audio", "C62", 6, "1290.00", "ACTIVE"),
    ("200121", "E2 wireless earbuds", "Audio", "C62", 6, "1690.00", "ACTIVE"),
    ("200122", "H5 over-ear headphones", "Audio", "C62", 4, "3290.00", "ACTIVE"),
    ("300410", "KT-17 1.7 L kettle", "Small appliances", "C62", 6, "899.00", "ACTIVE"),
    ("300411", "TS-2 toaster", "Small appliances", "C62", 6, "1190.00", "ACTIVE"),
    ("300412", "BL-8 blender", "Small appliances", "C62", 4, "1690.00", "ACTIVE"),
    ("300413", "AF-5 air fryer", "Small appliances", "C62", 4, "3490.00", "ACTIVE"),
    ("300414", "VS-1 stick vacuum", "Small appliances", "C62", 2, "6490.00", "ACTIVE"),
    ("300415", "SI-3 steam iron", "Small appliances", "C62", 6, "1390.00", "ACTIVE"),
    ("300555", "KT-15 1.5 L kettle (discontinued)", "Small appliances", "C62", 6, "749.00", "INACTIVE"),
    ("400020", "HDMI 2.1 cable, 2 m", "Accessories", "C62", 10, "149.90", "ACTIVE"),
    ("400021", "Tilting wall mount 32-65 inch", "Accessories", "C62", 5, "549.00", "ACTIVE"),
    ("400022", "Surge protected power strip", "Accessories", "C62", 10, "399.00", "ACTIVE"),
    ("400023", "Universal remote control", "Accessories", "C62", 10, "329.00", "ACTIVE"),
    ("400024", "65 W USB-C charger", "Accessories", "C62", 10, "449.00", "ACTIVE"),
    ("500100", "BR-1 barista set", "Small appliances", "SET", 1, "12990.00", "ACTIVE"),
    ("600100", "KB-2 wireless keyboard", "Peripherals", "C62", 5, "799.00", "ACTIVE"),
    ("600101", "MS-1 wireless mouse", "Peripherals", "C62", 10, "449.00", "ACTIVE"),
    ("600102", "WC-4 full HD webcam", "Peripherals", "C62", 4, "1590.00", "ACTIVE"),
    ("600103", "MN-27 27-inch monitor", "Peripherals", "C62", 2, "8990.00", "ACTIVE"),
    ("600104", "RT-6 Wi-Fi 6 router", "Peripherals", "C62", 4, "2190.00", "ACTIVE"),
]
ACTIVE_PRODUCTS = [p for p in PRODUCTS if p[6] == "ACTIVE"]
PRODUCT = {p[0]: p for p in PRODUCTS}
PROFILE_WEIGHT = {"LARGE": 3.0, "MID": 1.2, "SMALL": 0.45}
PROFILE_LINES = {"LARGE": (12, 4), "MID": (7, 3), "SMALL": (4, 2)}
PROFILE_MULT = {"LARGE": (2, 6), "MID": (1, 4), "SMALL": (1, 2)}
HOUR_WEIGHTS = {8: 5, 9: 12, 10: 14, 11: 13, 12: 9, 13: 8, 14: 10, 15: 10, 16: 8, 17: 6, 18: 3, 19: 2}
WEEKDAY_FACTOR = {0: 1.15, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.05, 5: 0.55}


# ---------------------------------------------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------------------------------------------
def in_window(dt, start, end):
    return start <= dt < end


def incident(system, dt):
    for inc_id, sys_name, start, end, _ in INCIDENTS:
        if sys_name == system and in_window(dt, start, end):
            return end
    return None


def webhook_down(dealer, dt):
    for start, end in WEBHOOK_OUTAGES.get(dealer, []):
        if dt >= start and (end is None or dt < end):
            return True
    return False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dealers = build_dealers()
    by_code = {x["dealer_code"]: x for x in dealers}
    tables = {k: [] for k in ("orders", "order_lines", "order_status_history", "approval_tasks", "shipments",
                              "invoices", "integrator_calls", "webhook_deliveries", "acknowledgements",
                              "order_submissions", "api_daily_traffic", "support_tally_weekly")}
    planted = Counter()
    order_seq = 1000
    dealer_seq = Counter()
    event_seq = 0
    submission_seq = 0
    receipt_seq = 0
    call_seq = 0

    order_history = []

    def add_history(order_id, seq, status, at, reason="", decided_by=""):
        row = {"order_id": order_id, "sequence": seq, "status": status, "reason_code": reason,
               "decided_by": decided_by, "occurred_at": ts(at)}
        tables["order_status_history"].append(row)
        order_history.append((status, at))

    def add_event(dealer, order_id, event_type, status, created):
        nonlocal event_seq
        event_seq += 1
        event_id = f"EVT-{event_seq:07d}"
        attempt_at = created + timedelta(seconds=rng.randint(1, 6))
        transient = chance(RATES["webhook_transient_failure"])
        for attempt, delay in enumerate([0, 1, 5, 15, 60, 240]):
            at = attempt_at + timedelta(minutes=delay)
            if at > AS_OF:
                break
            down = webhook_down(dealer, at)
            fails = down or (transient and attempt == 0)
            result = "DELIVERED"
            http = 200
            if fails:
                result, http = rng.choice([("TIMEOUT", ""), ("REJECTED", 503), ("UNREACHABLE", "")]) if not down else ("UNREACHABLE", "")
            tables["webhook_deliveries"].append({"event_id": event_id, "dealer_code": dealer, "order_id": order_id,
                                                 "event_type": event_type, "order_status": status,
                                                 "event_created_at": ts(created), "attempt": attempt + 1,
                                                 "attempted_at": ts(at), "result": result, "http_status": http})
            if result == "DELIVERED":
                return
            if attempt == 5:
                planted["webhook_events_exhausted"] += 1
                tables["webhook_deliveries"][-1]["result"] = "EXHAUSTED"
                return

    for day in WORKING_DAYS:
        mean = 47 * WEEKDAY_FACTOR[day.weekday()]
        n_orders = max(5, round(rng.gauss(mean, math.sqrt(mean))))
        eligible = [x for x in dealers if not (x["suspended_from"] and day >= x["suspended_from"])]
        weights = [PROFILE_WEIGHT[x["profile"]] for x in eligible]
        for _ in range(n_orders):
            dealer = rng.choices(eligible, weights)[0]
            code = dealer["dealer_code"]
            hour = rng.choices(list(HOUR_WEIGHTS), list(HOUR_WEIGHTS.values()))[0]
            received = datetime.combine(day, time(hour, rng.randint(0, 59), rng.randint(0, 59)))
            live = dealer["integration_live_date"]
            channel = dealer["channel"] if live and day >= live else "MANUAL"
            if channel == "API" and chance(RATES["manual_after_live_api"]):
                channel = "MANUAL"
            order_seq += 1
            order_id = f"VO-2027-{order_seq:06d}"
            dealer_seq[code] += 1
            if channel == "PORTAL":
                dealer_no = f"P-{day:%Y%m%d}-{dealer_seq[code]:04d}"
            elif channel == "MANUAL":
                dealer_no = f"EM-{code[-3:]}-{dealer_seq[code]:05d}"
            else:
                dealer_no = f"{'PO' if dealer['erp'] == 'SAP_B1' else 'SIP'}-2027-{dealer_seq[code]:05d}"

            # ---- submissions (API and portal only) ----
            if channel in ("API", "PORTAL"):
                fail_rate = RATES["submission_failed_api"] if channel == "API" else RATES["submission_failed_portal"]
                if chance(fail_rate):
                    submission_seq += 1
                    code_, http, field = rng.choices(
                        [("VALIDATION_FAILED", 400, "INVALID_UNIT"), ("VALIDATION_FAILED", 400, "QUANTITY_NOT_INTEGER"),
                         ("VALIDATION_FAILED", 400, "FIELD_REQUIRED"), ("VALIDATION_FAILED", 400, "DATE_OUT_OF_RANGE"),
                         ("VALIDATION_FAILED", 400, "DUPLICATE_LINE_SKU"), ("UNAUTHORIZED", 401, ""),
                         ("DUPLICATE_DEALER_ORDER_NO", 409, ""), ("IDEMPOTENCY_KEY_REUSED", 422, ""),
                         ("RATE_LIMIT_EXCEEDED", 429, ""), ("REQUEST_IN_PROGRESS", 409, "")],
                        [18, 12, 14, 8, 8, 15, 10, 5, 5, 5])[0]
                    tables["order_submissions"].append({
                        "submission_id": f"SUB-{submission_seq:07d}", "dealer_code": code, "channel": channel,
                        "submitted_at": ts(received - timedelta(seconds=rng.randint(30, 600))), "http_status": http,
                        "result_code": code_, "field_error_code": field, "order_id": ""})
                    planted["submissions_failed"] += 1
                submission_seq += 1
                tables["order_submissions"].append({
                    "submission_id": f"SUB-{submission_seq:07d}", "dealer_code": code, "channel": channel,
                    "submitted_at": ts(received), "http_status": 202, "result_code": "ACCEPTED", "field_error_code": "",
                    "order_id": order_id})
                if channel == "API" and chance(RATES["submission_replay_api"]):
                    submission_seq += 1
                    tables["order_submissions"].append({
                        "submission_id": f"SUB-{submission_seq:07d}", "dealer_code": code, "channel": channel,
                        "submitted_at": ts(received + timedelta(seconds=rng.randint(15, 90))), "http_status": 202,
                        "result_code": "REPLAYED", "field_error_code": "", "order_id": order_id})
                    planted["submissions_replayed"] += 1

            # ---- lines ----
            mean_lines, sd_lines = PROFILE_LINES[dealer["profile"]]
            n_lines = max(1, min(len(ACTIVE_PRODUCTS), round(rng.gauss(mean_lines, sd_lines))))
            skus = rng.sample(ACTIVE_PRODUCTS, n_lines)
            rule_reject = None
            if chance(RATES["rules_invalid_sku"]):
                skus[-1] = PRODUCT["300555"]
                rule_reject = "INVALID_SKU"
            lines = []
            for i, p in enumerate(skus, start=1):
                lo, hi = PROFILE_MULT[dealer["profile"]]
                qty = p[4] * rng.randint(lo, hi)
                lines.append({"order_id": order_id, "line_no": i, "sku": p[0], "requested_qty": qty, "approved_qty": qty,
                              "unit_price": Decimal(p[5])})
            if rule_reject is None and chance(RATES["rules_below_moq"]):
                target = next((ln for ln in lines if PRODUCT[ln["sku"]][4] > 1), None)
                if target:
                    target["requested_qty"] = target["approved_qty"] = PRODUCT[target["sku"]][4] - 1
                    rule_reject = "BELOW_MOQ"

            # ---- decision ----
            order_history.clear()
            seq = 1
            add_history(order_id, seq, "RECEIVED", received)
            erp_back = incident("ERP", received)
            decided = (erp_back or received) + timedelta(seconds=max(2, lognormal(8, 40)))
            if erp_back:
                planted["orders_delayed_by_erp_incident"] += 1
            status = None
            task = None
            if rule_reject:
                for ln in lines:
                    ln["approved_qty"] = 0
                seq += 1
                add_history(order_id, seq, "REJECTED", decided, rule_reject, "SYSTEM")
                status = "REJECTED"
                planted["rejected_" + rule_reject] += 1
            else:
                r = rng.random()
                reason = "CREDIT_LIMIT" if r < RATES["pending_credit_limit"] else \
                         "PARTIAL_STOCK" if r < RATES["pending_credit_limit"] + RATES["pending_partial_stock"] else None
                if reason:
                    seq += 1
                    add_history(order_id, seq, "PENDING_APPROVAL", decided, reason, "SYSTEM")
                    due = add_business_minutes(decided, 240)
                    late = chance(RATES["approval_late"])
                    if late:
                        escalated = due
                        decided_at = add_business_minutes(due, rng.randint(20, 120))
                        role = "SALES_MANAGER"
                    else:
                        escalated = None
                        decided_at = add_business_minutes(decided, min(235, max(5, lognormal(70, 200))))
                        role = "SALES_REPRESENTATIVE"
                    task = {"task_id": f"TSK-{order_seq:06d}", "order_id": order_id, "reason_code": reason,
                            "sales_rep": dealer["sales_rep"], "created_at": ts(decided), "due_at": ts(due),
                            "escalated_at": ts(escalated), "decided_at": "", "decided_by_role": "", "decision": ""}
                    tables["approval_tasks"].append(task)
                    planted["pending_" + reason] += 1
                    if decided_at > AS_OF:
                        status = "PENDING_APPROVAL"
                        task["escalated_at"] = ts(escalated) if escalated and escalated <= AS_OF else ""
                        planted["approvals_open_at_as_of"] += 1
                    else:
                        planted["approvals_late" if late else "approvals_on_time"] += 1
                        x = rng.random()
                        decision = "APPROVED" if x < RATES["decision_approve"] else \
                                   "APPROVED_REDUCED" if x < RATES["decision_approve"] + RATES["decision_reduce"] else "REJECTED"
                        task.update(decided_at=ts(decided_at), decided_by_role=role, decision=decision)
                        seq += 1
                        if decision == "REJECTED":
                            for ln in lines:
                                ln["approved_qty"] = 0
                            add_history(order_id, seq, "REJECTED", decided_at,
                                        "CREDIT_LIMIT_REJECTED" if reason == "CREDIT_LIMIT" else "STOCK_UNAVAILABLE", role)
                            status = "REJECTED"
                        else:
                            if decision == "APPROVED_REDUCED":
                                for ln in rng.sample(lines, max(1, len(lines) // 3)):
                                    ln["approved_qty"] = max(PRODUCT[ln["sku"]][4], ln["requested_qty"] // 2)
                            add_history(order_id, seq, "APPROVED", decided_at, "", role)
                            decided = decided_at
                if status is None:
                    if not reason:
                        seq += 1
                        add_history(order_id, seq, "APPROVED", decided, "", "SYSTEM")
                    seq += 1
                    allocated = decided + timedelta(seconds=rng.randint(1, 4))
                    add_history(order_id, seq, "ALLOCATED", allocated)
                    status = "ALLOCATED"

            # ---- totals and corrections ----
            net = sum(money(ln["approved_qty"] * ln["unit_price"]) for ln in lines)
            vat = sum(money(money(ln["approved_qty"] * ln["unit_price"]) * Decimal("0.20")) for ln in lines)
            corrected = chance(RATES["corrected_" + channel.lower()])
            for ln in lines:
                tables["order_lines"].append({**ln, "unit_price": f"{ln['unit_price']:.2f}",
                                              "line_net": f"{money(ln['approved_qty'] * ln['unit_price']):.2f}"})
            order_row = {"order_id": order_id, "dealer_code": code, "dealer_order_no": dealer_no, "channel": channel,
                         "received_at": ts(received), "line_count": len(lines), "net_amount": f"{net:.2f}",
                         "vat_amount": f"{vat:.2f}", "gross_amount": f"{net + vat:.2f}",
                         "corrected_after_entry": str(corrected).lower(), "current_status": status}
            tables["orders"].append(order_row)
            webhooks = channel == "API" and dealer["webhook_registered"]
            if webhooks:
                for hist_status, created in order_history[1:]:
                    if created <= AS_OF:
                        add_event(code, order_id, "order.status.changed", hist_status, created)
            if status != "ALLOCATED":
                continue

            # ---- shipment ----
            allocated_at = order_history[-1][1]
            ship_day = allocated_at.date() if allocated_at.time() < time(10) and is_working(allocated_at.date()) \
                else next_working_day(allocated_at.date())
            pickup = datetime.combine(ship_day, time(15)) + timedelta(minutes=rng.randint(-90, 90))
            if chance(RATES["late_shipment_confirmation"]):
                confirmed = to_business(datetime.combine(add_working_days(ship_day, rng.randint(1, 3)),
                                                         time(rng.randint(9, 17), rng.randint(0, 59))))
                planted["shipments_confirmed_late"] += 1
            else:
                confirmed = pickup + timedelta(minutes=rng.randint(5, 40))
            if pickup > AS_OF:
                continue
            note_no = f"IRS2027{order_seq:09d}"
            tables["shipments"].append({"order_id": order_id, "warehouse_code": dealer["warehouse"],
                                        "carrier_pickup_at": ts(pickup),
                                        "confirmed_at": ts(confirmed) if confirmed <= AS_OF else "",
                                        "delivery_note_no": note_no})
            if confirmed > AS_OF:
                continue
            seq += 1
            add_history(order_id, seq, "SHIPPED", confirmed)
            order_row["current_status"] = "SHIPPED"
            if webhooks:
                add_event(code, order_id, "order.status.changed", "SHIPPED", confirmed)

            # ---- invoice ----
            open_stuck = ship_day in (date(2027, 7, 1), date(2027, 7, 2)) and planted["invoices_missing_at_as_of"] < 3 \
                and chance(0.06)
            stuck = open_stuck or chance(RATES["invoice_stuck_in_erp"])
            if stuck:
                planted["invoices_stuck_in_erp"] += 1
                created_inv = add_business_minutes(confirmed, 60 * 12 * rng.randint(2, 3))
            else:
                created_inv = confirmed + timedelta(minutes=rng.randint(1, 4))
            if open_stuck or created_inv > AS_OF:
                planted["invoices_missing_at_as_of"] += 1
                continue
            ettn = "%08x-%04x-4%03x-%04x-%012x" % (rng.getrandbits(32), rng.getrandbits(16), rng.getrandbits(12),
                                                   0x8000 | rng.getrandbits(14), rng.getrandbits(48))
            invoice_no = f"VKT2027{order_seq:09d}"
            inv = {"ettn": ettn, "invoice_no": invoice_no, "order_id": order_id, "dealer_code": code,
                   "invoice_date": created_inv.date().isoformat(), "created_at": ts(created_inv), "held_at": "",
                   "released_at": "", "first_send_at": "", "accepted_at": "", "receipt_id": "", "delivered_at": "",
                   "final_state": "", "status_polls": 0, "net_amount": f"{net:.2f}", "vat_amount": f"{vat:.2f}",
                   "gross_amount": f"{net + vat:.2f}"}
            tables["invoices"].append(inv)

            def call(op, at, result, fault="", status_=""):
                nonlocal call_seq
                call_seq += 1
                tables["integrator_calls"].append({"call_id": f"CALL-{call_seq:07d}", "ettn": ettn, "operation": op,
                                                   "called_at": ts(at), "result": result, "fault_code": fault,
                                                   "status_returned": status_})

            check_at = created_inv + timedelta(seconds=rng.randint(20, 60))
            outage_end = incident("INTEGRATOR", check_at)
            if outage_end:
                at = check_at
                while at < outage_end:
                    call("CheckUser", at, "TIMEOUT")
                    at += timedelta(minutes=5)
                check_at = outage_end + timedelta(seconds=rng.randint(10, 300))
                planted["invoices_delayed_by_integrator_incident"] += 1
            if chance(RATES["invoice_held"]):
                call("CheckUser", check_at, "OK", status_="NOT_REGISTERED")
                inv["held_at"] = ts(check_at)
                release = add_business_minutes(check_at, 60 * rng.randint(4, 30))
                planted["invoices_held"] += 1
                if release > AS_OF:
                    inv["final_state"] = "HELD"
                    continue
                inv["released_at"] = ts(release)
                check_at = release + timedelta(seconds=rng.randint(20, 60))
            call("CheckUser", check_at, "OK", status_="REGISTERED")
            send_at = check_at + timedelta(seconds=rng.randint(30, 150))
            inv["first_send_at"] = ts(send_at)
            if chance(RATES["invoice_send_failed"]):
                call("SendInvoice", send_at, "FAULT", fault=rng.choice(["2000", "2001"]))
                send_at = add_business_minutes(send_at, rng.randint(120, 360))
                planted["invoices_send_failed"] += 1
                if send_at > AS_OF:
                    inv["final_state"] = "SEND_FAILED"
                    continue
            outage_end = incident("INTEGRATOR", send_at)
            if outage_end:
                while send_at < outage_end:
                    call("SendInvoice", send_at, "TIMEOUT")
                    send_at += timedelta(minutes=5)
                send_at = outage_end + timedelta(seconds=rng.randint(10, 300))
                planted["invoices_delayed_by_integrator_incident"] += 1
            call("SendInvoice", send_at, "OK", status_="QUEUED")
            receipt_seq += 1
            inv["accepted_at"] = ts(send_at)
            inv["receipt_id"] = f"RCP-{send_at:%Y-%m%d}-{receipt_seq:06d}"
            if chance(RATES["invoice_error_after_send"]):
                error_at = send_at + timedelta(minutes=rng.randint(20, 90))
                call("GetInvoiceStatus", error_at, "OK", status_="ERROR")
                send_at = add_business_minutes(error_at, rng.randint(240, 600))
                call("SendInvoice", send_at, "OK", status_="QUEUED")
                planted["invoices_error_after_send"] += 1
            slow = chance(RATES["invoice_slow_delivery"])
            delay = timedelta(hours=rng.uniform(26, 50)) if slow else timedelta(minutes=max(2, lognormal(9, 35)))
            delivered = send_at + delay
            if slow:
                planted["invoices_slow_delivery"] += 1
            if ship_day >= date(2027, 7, 2) and not slow and planted["invoices_open_at_integrator"] < 2 and chance(0.08):
                delivered = AS_OF + timedelta(days=1)
                planted["invoices_open_at_integrator"] += 1
            inv["status_polls"] = max(1, int((min(delivered, AS_OF) - send_at).total_seconds() // 300) + 1)
            if delivered > AS_OF:
                inv["final_state"] = "AT_INTEGRATOR"
                continue
            call("GetInvoiceStatus", delivered, "OK", status_="DELIVERED")
            inv["delivered_at"] = ts(delivered)
            inv["final_state"] = "DELIVERED"
            if (delivered.date() - ship_day).days >= 5:
                planted["invoices_reached_day5"] += 1
            seq += 1
            add_history(order_id, seq, "INVOICED", delivered)
            order_row["current_status"] = "INVOICED"
            if webhooks:
                add_event(code, order_id, "order.status.changed", "INVOICED", delivered)
                add_event(code, order_id, "invoice.issued", "INVOICED", delivered + timedelta(seconds=rng.randint(1, 5)))

            # ---- acknowledgement and closing ----
            if dealer["acknowledges_invoices"] and channel == "API":
                r = rng.random()
                if r < RATES["ack_never"]:
                    ack = None
                    planted["acks_never"] += 1
                elif r < RATES["ack_never"] + RATES["ack_late"]:
                    ack = add_business_minutes(delivered, 60 * 12 * rng.uniform(1.2, 4.8))
                    planted["acks_late"] += 1
                else:
                    ack = add_business_minutes(delivered, max(10, lognormal(180, 600)))
                if ack and ack <= AS_OF:
                    mismatch = chance(RATES["ack_mismatch"])
                    tables["acknowledgements"].append({
                        "ettn": ettn, "dealer_code": code, "acknowledged_at": ts(ack),
                        "match_result": "MISMATCH" if mismatch else "MATCHED",
                        "dealer_booked_gross": f"{(net + vat + (Decimal('0.01') * rng.choice([-3, -2, -1, 1, 2]) if mismatch else 0)):.2f}"})
                    if mismatch:
                        planted["acks_mismatch"] += 1
                    seq += 1
                    add_history(order_id, seq, "CLOSED", ack, "", "DEALER")
                    order_row["current_status"] = "CLOSED"
                    if webhooks:
                        add_event(code, order_id, "order.status.changed", "CLOSED", ack)
                    continue
            auto_close = delivered + timedelta(days=30)
            if auto_close <= AS_OF:
                seq += 1
                add_history(order_id, seq, "CLOSED", auto_close, "", "TIMER")
                order_row["current_status"] = "CLOSED"

    # ---- API traffic per day and endpoint (aggregated monitoring export) ----
    for day in WORKING_DAYS:
        live_api = [x for x in dealers if x["channel"] == "API" and x["integration_live_date"] and x["integration_live_date"] <= day]
        live_portal = [x for x in dealers if x["channel"] == "PORTAL" and x["integration_live_date"] and x["integration_live_date"] <= day
                       and not (x["suspended_from"] and day >= x["suspended_from"])]
        no_hook = [x for x in live_api if not x["webhook_registered"]]
        base = {
            "GET /stock": sum(40 if x["profile"] == "LARGE" else 12 for x in live_api) + 6 * len(live_portal),
            "GET /products": 2 * len(live_api) + len(live_portal),
            "GET /orders": 15 * len(no_hook) + 8 * len(live_portal),
            "GET /orders/{orderId}": 4 * len(live_api) + 5 * len(live_portal),
            "GET /invoices": 3 * len(live_api) + 2 * len(live_portal),
            "POST /invoices/{ettn}/acknowledge": 0,
        }
        acks = sum(1 for a in tables["acknowledgements"] if a["acknowledged_at"].startswith(day.isoformat()))
        base["POST /invoices/{ettn}/acknowledge"] = acks
        factor = WEEKDAY_FACTOR[day.weekday()]
        for endpoint, value in base.items():
            n = max(0, round(value * factor * rng.uniform(0.9, 1.1))) if endpoint != "POST /invoices/{ettn}/acknowledge" else value
            erp_down = any(s == "ERP" and st.date() == day for _, s, st, _, _ in INCIDENTS)
            r5 = round(n * (0.012 if erp_down and endpoint == "GET /stock" else 0.0004))
            r429 = round(n * (0.004 if endpoint == "GET /stock" else 0.0005))
            r4 = round(n * 0.006)
            p95 = {"GET /stock": 320, "GET /products": 410, "GET /orders": 380, "GET /orders/{orderId}": 190,
                   "GET /invoices": 260, "POST /invoices/{ettn}/acknowledge": 150}[endpoint]
            tables["api_daily_traffic"].append({"day": day.isoformat(), "endpoint": endpoint, "requests": n,
                                                "status_2xx": n - r5 - r429 - r4, "status_4xx": r4, "status_429": r429,
                                                "status_5xx": r5, "p95_ms": round(p95 * rng.uniform(0.85, 1.2) * (2.6 if erp_down else 1))})

    # ---- sales support tally (weekly, kept by the team) ----
    for week in range(13):
        week_start = START + timedelta(days=7 * week)
        days = sum(1 for d in WORKING_DAYS if week_start <= d < week_start + timedelta(days=7))
        share_live = sum(1 for x in dealers if x["integration_live_date"] and x["integration_live_date"] <= week_start + timedelta(days=6)) / len(dealers)
        stock = round(days * (60 * (1 - share_live) + 3.5) * rng.uniform(0.9, 1.1))
        status_calls = round(days * (25 * (1 - share_live) + 2.5) * rng.uniform(0.9, 1.1))
        invoice_q = round(days * (12 * (1 - share_live) + 1) * rng.uniform(0.85, 1.15))
        tables["support_tally_weekly"].append({"week_start": week_start.isoformat(), "working_days": days,
                                               "phone_stock_questions": stock, "order_status_calls": status_calls,
                                               "invoice_queries": invoice_q})

    # ---- static tables ----
    calendar = []
    d = date(2027, 3, 29)
    index = 0
    while d <= date(2027, 7, 17):
        if is_working(d):
            index += 1
        calendar.append({"day": d.isoformat(), "weekday": d.strftime("%A"), "is_working_day": str(is_working(d)).lower(),
                         "holiday_name": HOLIDAYS.get(d, ""), "working_day_index": index,
                         "period_week": ((d - START).days // 7 + 1) if START <= d <= END else ""})
        d += timedelta(days=1)
    dealer_rows = [{"dealer_code": x["dealer_code"], "dealer_name": x["dealer_name"], "city": x["city"],
                    "profile": x["profile"], "erp": x["erp"], "integration_channel": x["channel"],
                    "integration_live_date": x["integration_live_date"].isoformat() if x["integration_live_date"] else "",
                    "webhook_registered": str(x["webhook_registered"]).lower(),
                    "acknowledges_invoices": str(x["acknowledges_invoices"]).lower(), "shipping_warehouse": x["warehouse"],
                    "sales_rep": x["sales_rep"], "status": x["status"],
                    "suspended_from": x["suspended_from"].isoformat() if x["suspended_from"] else ""} for x in dealers]
    product_rows = [{"sku": p[0], "name": p[1], "category": p[2], "unit_code": p[3], "minimum_order_quantity": p[4],
                     "vat_rate": 20, "unit_price": p[5], "status": p[6]} for p in PRODUCTS]
    incident_rows = [{"incident_id": i, "system": s, "started_at": ts(a), "ended_at": ts(b), "description": t}
                     for i, s, a, b, t in INCIDENTS]
    outage_rows = [{"dealer_code": k, "started_at": ts(a), "ended_at": ts(b) if b else ""}
                   for k, spans in WEBHOOK_OUTAGES.items() for a, b in spans]

    write("calendar", calendar)
    write("dealers", dealer_rows)
    write("products", product_rows)
    write("incidents", incident_rows)
    write("webhook_endpoint_outages", outage_rows)
    for name, rows in tables.items():
        if name == "order_lines":
            rows = [{k: r[k] for k in ("order_id", "line_no", "sku", "requested_qty", "approved_qty", "unit_price", "line_net")} for r in rows]
        write(name, rows)

    print(f"\nperiod {START} to {END}, {len(WORKING_DAYS)} working days, report as of {AS_OF}")
    for key in sorted(planted):
        print(f"  planted {key:42} {planted[key]}")


def write(name, rows):
    path = OUT / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name + '.csv':30} {len(rows):>7} rows  {path.stat().st_size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
