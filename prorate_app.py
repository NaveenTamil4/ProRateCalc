import streamlit as st
from datetime import datetime, timedelta, date
import pandas as pd
from io import StringIO

# ---------- Pricing ----------
PRICING = {
    "Pro_Monthly": 2.49,
    "Pro_Annual": 2.24,
    "Premium_Monthly": 3.99,
    "Premium_Annual": 3.59
}

# ---------- Functions (Prorate1) ----------
def is_annual(plan):
    return "Annual" in plan

def cycle_days(plan):
    return 365 if is_annual(plan) else 30

def add_period(start, plan):
    if is_annual(plan):
        return start + timedelta(days=365)
    else:
        return start + timedelta(days=30)

def per_day(plan):
    return PRICING[plan] / cycle_days(plan)

def prorate(plan, start, end, licenses):
    total_days = (end - start).days + 1
    return round(total_days * per_day(plan) * licenses, 2)

# ---------- Functions (Prorate2) ----------
def prorate_adjustments(start_date, end_date, base_price, events, existing_licenses, price_per_license=1.0):
    total_days = (end_date - start_date).days
    adjustments = []
    total_adjustment = 0
    total_licenses_change = 0

    for event_date, change in events:
        remaining_days = (end_date - event_date).days
        prorated_amount = (change * price_per_license) * (remaining_days / total_days)
        total_adjustment += prorated_amount
        total_licenses_change += change

        adjustments.append({
            "date": event_date,
            "change": change,
            "remaining_days": remaining_days,
            "prorated_amount": round(prorated_amount, 2)
        })

    renewal_licenses = existing_licenses + total_licenses_change
    renewal_amount = renewal_licenses * price_per_license
    next_bill_total = renewal_amount + round(total_adjustment, 2)

    return {
        "base_paid": base_price,
        "adjustments": adjustments,
        "total_adjustment": round(total_adjustment, 2),
        "renewal_licenses": renewal_licenses,
        "renewal_amount": renewal_amount,
        "next_bill_total": round(next_bill_total, 2)
    }

def convert_currency(amount_usd, currency, exchange_rates, conversion_fee_percent=5.2):
    rate = exchange_rates.get(currency, 1.0)
    converted = amount_usd * rate
    if currency != "USD":
        converted += converted * (conversion_fee_percent / 100)
    return round(converted, 2)

# ---------- App ----------
st.set_page_config(layout="wide")
st.title("💰 Prorate Billing System")

# ---------- Pricing ----------
st.subheader("📊 Pricing")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pro Monthly", f"${PRICING['Pro_Monthly']}/mo")
c2.metric("Pro Annual", f"${PRICING['Pro_Annual']}/mo")
c3.metric("Premium Monthly", f"${PRICING['Premium_Monthly']}/mo")
c4.metric("Premium Annual", f"${PRICING['Premium_Annual']}/mo")

# ---------- Sidebar ----------
menu = st.sidebar.radio(
    "Select Module",
    [
        "Prorate Billing Calculator",
        "Plan Change",
        "License Addition / Reduction",
        "Multi-Currency Prorate Calculator"
    ]
)

# =========================================================
# 1. PRORATE CALCULATOR
# =========================================================
if menu == "Prorate Billing Calculator":
    st.header("🧮 Prorate Billing Calculator")

    col_main, col_preview = st.columns([2, 1])

    with col_main:
        plan = st.selectbox("Plan", PRICING.keys())
        licenses = st.number_input("Licenses", min_value=1, value=1)

        mode = st.radio("Select Period", ["This Cycle", "Custom Period"])
        today = datetime.today()

        if mode == "This Cycle":
            start = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end = add_period(start, plan) - timedelta(days=1)
        else:
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input("Start Date", value=today)
            with col2:
                end = st.date_input("End Date", value=today + timedelta(days=30))
            start = datetime.combine(start, datetime.min.time())
            end = datetime.combine(end, datetime.min.time())

    with col_preview:
        st.subheader("📅 Billing Summary")

        if start <= end:
            total_days = (end - start).days + 1

            if is_annual(plan):
                cost = round(PRICING[plan] * licenses * 12, 2)
                st.info("Cycle: 365 days (12 months)")
                st.info(f"Formula: {PRICING[plan]} × {licenses} licenses × 12 months")
            else:
                cost = round(PRICING[plan] * licenses, 2)
                st.info("Cycle: 1 Month")
                st.info(f"Formula: {PRICING[plan]} × {licenses} licenses × 1 month")

            st.info(f"Start: {start.date()}")
            st.info(f"End:   {end.date()}")
            st.info(f"Days:  {total_days}")
            st.success(f"💰 Amount: ${cost}")
        else:
            st.warning("Select valid dates")

    if st.button("💾 Save as Invoice"):
        if start <= end:
            if is_annual(plan):
                cost = round(PRICING[plan] * licenses * 12, 2)
            else:
                cost = round(PRICING[plan] * licenses, 2)

            df = pd.DataFrame({
                "Plan": [plan],
                "Licenses": [licenses],
                "Start Date": [start.date()],
                "End Date": [end.date()],
                "Days": [(end - start).days + 1],
                "Billing Cycle": ["Annual (12 months)" if is_annual(plan) else "Monthly"],
                "Amount": [cost]
            })
            csv = StringIO()
            df.to_csv(csv, index=False)
            st.download_button("📥 Download Invoice", csv.getvalue(), "invoice.csv", "text/csv")

# =========================================================
# 2. PLAN CHANGE
# =========================================================
elif menu == "Plan Change":
    st.header("🔄 Plan Change (Carry Forward Billing)")

    old_plan = st.selectbox("Current Plan", list(PRICING.keys()), key="old_plan")
    new_plan = st.selectbox("New Plan", list(PRICING.keys()), key="new_plan")
    licenses = st.number_input("Licenses", min_value=1, value=1)

    start = st.date_input("Billing Start Date")
    change = st.date_input("Plan Change Date")

    start  = datetime.combine(start, datetime.min.time())
    change = datetime.combine(change, datetime.min.time())

    end        = add_period(start, old_plan)
    total_days = cycle_days(old_plan)

    st.info(f"Current billing cycle: {start.date()} → {end.date()} ({total_days} days)")

    if st.button("Calculate Plan Change"):

        if change < start:
            st.error("Change date cannot be before billing start.")

        elif change >= end:
            st.error("Change date cannot be on or after the billing cycle end.")

        else:
            used_days      = (change - start).days
            remaining_days = (end - change).days

            # ── OLD PLAN ──────────────────────────────────────────
            old_total     = PRICING[old_plan] * licenses
            old_per_day   = old_total / total_days
            used_amount   = round(old_per_day * used_days, 2)
            unused_credit = round(old_total - used_amount, 2)

            # ── NEW PLAN ──────────────────────────────────────────
            if is_annual(new_plan):
                new_total = round(PRICING[new_plan] * licenses * 12, 2)
                new_label = f"{PRICING[new_plan]} × {licenses} licenses × 12 months"
            else:
                new_total = round(PRICING[new_plan] * licenses, 2)
                new_label = f"{PRICING[new_plan]} × {licenses} licenses × 1 month"

            final_invoice = round(new_total - unused_credit, 2)

            st.subheader("📊 Breakdown")

            col1, col2 = st.columns(2)

            with col1:
                st.write("### Old Plan")
                st.write(f"Cycle: {total_days} days")
                st.write(f"Full Cycle Cost: ${round(old_total, 2)}")
                st.write(f"Used ({used_days} days): ${used_amount}")
                st.warning(f"Unused Credit: -${unused_credit}")

            with col2:
                st.write("### New Plan")
                st.write(f"Formula: {new_label}")
                st.write(f"New Plan Total: ${new_total}")

            st.divider()

            st.success(f"New Plan Total: ${new_total}")
            st.success(f"Unused Credit Deducted: -${unused_credit}")
            st.success(f"💰 Final Invoice: ${final_invoice}")

# =========================================================
# 3. LICENSE ADD / REDUCE
# =========================================================
elif menu == "License Addition / Reduction":
    st.header("➕➖ License Change")

    col_main, col_preview = st.columns([2, 1])

    with col_main:
        plan    = st.selectbox("Plan", PRICING.keys())
        current = st.number_input("Current Licenses", min_value=1, value=1)
        new     = st.number_input("Add or Reduce Licenses (Add are reduce from current Licenses)", min_value=1, value=1)

        start  = st.date_input("Billing Start Date")
        change = st.date_input("Change Date")

        start  = datetime.combine(start,  datetime.min.time())
        change = datetime.combine(change, datetime.min.time())

        end            = add_period(start, plan)
        remaining_days = (end - change).days
        days           = cycle_days(plan)

    with col_preview:
        st.subheader("📊 Live Calculation")

        if new > current:
            extra          = new - current
            prorate_charge = round(per_day(plan) * extra * remaining_days, 2)

            if is_annual(new_plan := plan):
                next_charge = round(PRICING[plan] * new * 12, 2)
                next_label  = f"{new} licenses × 12 months"
            else:
                next_charge = round(PRICING[plan] * new, 2)
                next_label  = f"{new} licenses × 1 month"

            final = round(prorate_charge + next_charge, 2)

            st.success("📈 License Increase")
            st.write(f"Added: {extra} license(s)")
            st.write(f"Remaining days this cycle: {remaining_days}")
            st.write(f"Prorated charge ({extra} lic × {remaining_days} days): **${prorate_charge}**")
            st.write(f"Next cycle ({next_label}): **${next_charge}**")
            st.success(f"💰 Final Invoice: ${final}")

        elif new < current:
            diff           = current - new
            prorate_credit = round(per_day(plan) * diff * remaining_days, 2)

            if is_annual(plan):
                next_charge = round(PRICING[plan] * new * 12, 2)
                next_label  = f"{new} licenses × 12 months"
            else:
                next_charge = round(PRICING[plan] * new, 2)
                next_label  = f"{new} licenses × 1 month"

            final = round(next_charge - prorate_credit, 2)

            st.warning("📉 License Reduction")
            st.write(f"Reduced: {diff} license(s)")
            st.write(f"Remaining days this cycle: {remaining_days}")
            st.write(f"Credit ({diff} lic × {remaining_days} days): **-${prorate_credit}**")
            st.write(f"Next cycle ({next_label}): **${next_charge}**")
            st.warning(f"💰 Final Invoice (after credit): ${final}")

        else:
            st.info("No Change")

    if st.button("Finalize Change"):
        if new > current:
            extra          = new - current
            prorate_charge = round(per_day(plan) * extra * remaining_days, 2)
            next_charge    = round(PRICING[plan] * new * 12, 2) if is_annual(plan) else round(PRICING[plan] * new, 2)
            final          = round(prorate_charge + next_charge, 2)

            st.subheader("📋 Invoice Breakdown")
            st.write(f"Prorated charge — {extra} added license(s), {remaining_days} days: **${prorate_charge}**")
            st.write(f"Next cycle full charge: **${next_charge}**")
            st.success(f"💰 Total Invoice: ${final}")

        elif new < current:
            diff           = current - new
            prorate_credit = round(per_day(plan) * diff * remaining_days, 2)
            next_charge    = round(PRICING[plan] * new * 12, 2) if is_annual(plan) else round(PRICING[plan] * new, 2)
            final          = round(next_charge - prorate_credit, 2)

            st.subheader("📋 Invoice Breakdown")
            st.write(f"Credit — {diff} removed license(s), {remaining_days} days: **-${prorate_credit}**")
            st.write(f"Next cycle full charge: **${next_charge}**")
            st.success(f"💰 Total Invoice (after credit): ${final}")

        else:
            st.info("No billing change")

# =========================================================
# 4. MULTI-CURRENCY PRORATE CALCULATOR (Prorate2)
# =========================================================
elif menu == "Multi-Currency Prorate Calculator":
    st.title("📅 Prorate Billing Calculator (Multi-Currency)")

    # Fix 3: Custom round — decimals > .5 round up to next integer, else round normally
    def smart_round(value):
        import math
        floor_val = math.floor(value)
        decimal   = value - floor_val
        return floor_val + 1 if decimal > 0.5 else floor_val

    # Sidebar setup
    st.sidebar.header("Billing Setup")

    # Fix 1: Default start date = today
    today_mc   = date.today()

    # Fix 2: When start changes, end = same day next month
    def next_month_date(d):
        month = d.month + 1
        year  = d.year
        if month > 12:
            month = 1
            year += 1
        # Cap day to last valid day of next month (e.g. Jan 31 → Feb 28)
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(d.day, last_day))

    start_date = st.sidebar.date_input("Billing Start Date", value=today_mc)
    end_date   = st.sidebar.date_input("Billing End Date",   value=next_month_date(start_date))

    existing_licenses = st.sidebar.number_input("Initial Licenses", 1, 1000, 5)
    price_per_license = st.sidebar.number_input("Price per License (USD)", 0.1, 1000.0, 2.99)
    base_price = existing_licenses * price_per_license

    st.sidebar.markdown("---")
    st.sidebar.subheader("Currency Options")

    currency = st.sidebar.selectbox(
        "Select Currency",
        ["USD", "INR", "JPY", "CAD"]
    )

    exchange_rates = {
        "USD": 1.0,
        "INR": 83.1535,
        "JPY": 156.28,
        "CAD": 1.37
    }

    conversion_fee_percent = st.sidebar.number_input(
        "Conversion Fee (%)", min_value=0.0, max_value=100.0, value=5.2, step=0.1
    )

    if currency == "USD":
        st.sidebar.info("💵 Conversion fee applicable except USD")

    # License change events
    st.header("Add or Reduce License Change Events")
    num_events = st.number_input("Number of Events", 0, 10, 3)

    events = []
    for i in range(num_events):
        st.subheader(f"Event {i+1}")
        event_date = st.date_input(f"Date of Event {i+1}", value=start_date, key=f"mc_date_{i}")
        change = st.number_input(f"License Change (e.g., +10 or -5)", value=0, key=f"mc_change_{i}")
        events.append((event_date, change))

    if st.button("💰 Calculate Billing"):
        result = prorate_adjustments(start_date, end_date, base_price, events, existing_licenses, price_per_license)

        symbol = {"USD": "$", "INR": "₹", "JPY": "¥", "CAD": "C$"}.get(currency, "")
        rate   = exchange_rates[currency]
        fee    = conversion_fee_percent / 100

        def to_currency(usd_amount):
            """Convert a single USD amount → apply exchange rate + fee → smart_round"""
            converted = usd_amount * rate
            if currency != "USD":
                converted += converted * fee
            return smart_round(converted)

        # ── USD Summary ───────────────────────────────────────
        st.markdown("## 🧾 Billing Summary (Base USD)")
        st.write(f"**Base Paid:** ${result['base_paid']}")
        st.write(f"**Renewal Licenses:** {result['renewal_licenses']} → ${result['renewal_amount']}")
        st.write(f"**Total Adjustments:** ${result['total_adjustment']}")
        st.success(f"💵 **Next Bill (USD): ${result['next_bill_total']}**")

        # ── Currency Conversion ───────────────────────────────
        # Step 1: Convert & round per-license price first, then multiply by renewal licenses
        # e.g. 2.99 USD → 261.55 INR → smart_round → 262, then 262 × 8 = 2096
        per_license_converted = to_currency(price_per_license)
        renewal_converted     = per_license_converted * result['renewal_licenses']

        # Step 2: Convert & round each prorated adjustment individually
        adj_converted_list = []
        for adj in result["adjustments"]:
            converted_adj = to_currency(adj['prorated_amount'])
            adj_converted_list.append({
                **adj,
                "converted_amount": converted_adj
            })

        # Step 3: Final total = sum of individually rounded amounts
        total_converted = renewal_converted + sum(a["converted_amount"] for a in adj_converted_list)

        st.markdown(f"### 🌍 Converted to {currency}")
        st.info(f"**Exchange Rate:** 1 USD = {rate} {currency}")
        if currency != "USD":
            st.info(f"**Conversion Fee:** {conversion_fee_percent}%")

        st.markdown(f"**Renewal ({result['renewal_licenses']} licenses):** "
                    f"{symbol}{renewal_converted}")

        st.markdown("### 📋 Adjustment Details")
        for adj in adj_converted_list:
            change_type = "Added" if adj["change"] > 0 else "Reduced"
            usd_val     = adj['prorated_amount']
            conv_val    = adj['converted_amount']
            st.write(
                f"- **{adj['date']}** → {change_type} {abs(adj['change'])} license(s) "
                f"→ ${usd_val} USD = {symbol}{conv_val} "
                f"({adj['remaining_days']} days remaining)"
            )

        st.divider()

        if currency == "USD":
            st.success(f"**Next Bill ({currency}): {symbol}{total_converted} (No Fee Applied)**")
        else:
            st.success(
                f"**Next Bill ({currency}): {symbol}{total_converted} "
                f"(Includes {conversion_fee_percent}% Conversion Fee | "
                f"Renewal {symbol}{renewal_converted} + "
                f"Adjustments {symbol}{sum(a['converted_amount'] for a in adj_converted_list)})**"
            )
