import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from io import StringIO

# ---------- Pricing ----------
PRICING = {
    "Pro_Monthly": 2.49,
    "Pro_Annual": 2.24,
    "Premium_Monthly": 3.99,
    "Premium_Annual": 3.59
}

# ---------- Functions ----------
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
    ["Prorate Billing Calculator", "Plan Change", "License Addition / Reduction"]
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

        mode = st.radio("Billing Mode", ["This Cycle", "Custom Period"])
        today = datetime.today()

        if mode == "This Cycle":
            start = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end = add_period(start, plan) - timedelta(days=1)
        else:
            col1, col2 = st.columns(2)
            with col1:
                start = st.date_input("Start Date", value=today)
            with col2:
                end = st.date_input("End Date", value=today + timedelta(days=7))
            start = datetime.combine(start, datetime.min.time())
            end = datetime.combine(end, datetime.min.time())

    with col_preview:
        st.subheader("📅 Billing Summary")

        if start <= end:
            total_days = (end - start).days + 1

            # ── Annual: total = price × licenses × 12 months ──
            if is_annual(plan):
                cost = round(PRICING[plan] * licenses * 12, 2)
                st.info("Cycle: 365 days (12 months)")
                st.info(f"Formula: {PRICING[plan]} × {licenses} licenses × 12 months")
            else:
                cost = round(PRICING[plan] * licenses, 2)
                st.info("Cycle: 30 days")
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

    # Billing cycle end is based on OLD plan
    end        = add_period(start, old_plan)
    total_days = cycle_days(old_plan)   # 30 or 365

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
            old_total      = PRICING[old_plan] * licenses          # full cycle cost
            old_per_day    = old_total / total_days
            used_amount    = round(old_per_day * used_days, 2)
            unused_credit  = round(old_total - used_amount, 2)

            # ── NEW PLAN ──────────────────────────────────────────
            if is_annual(new_plan):
                # Annual: charge full 12-month amount
                new_total = round(PRICING[new_plan] * licenses * 12, 2)
                new_label = f"{PRICING[new_plan]} × {licenses} licenses × 12 months"
            else:
                # Monthly: charge one full month
                new_total = round(PRICING[new_plan] * licenses, 2)
                new_label = f"{PRICING[new_plan]} × {licenses} licenses × 1 month"

            final_invoice = round(new_total - unused_credit, 2)

            # ── DISPLAY ───────────────────────────────────────────
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
        new     = st.number_input("New Licenses",     min_value=1, value=1)

        start  = st.date_input("Billing Start Date")
        change = st.date_input("Change Date")

        start  = datetime.combine(start,  datetime.min.time())
        change = datetime.combine(change, datetime.min.time())

        end            = add_period(start, plan)
        remaining_days = (end - change).days
        days           = cycle_days(plan)   # 30 or 365

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
            diff          = current - new
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