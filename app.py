import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime

st.set_page_config(page_title="All-in-One Property Calculator (SG)", layout="wide")

# ------------------------------
# Helper functions
# ------------------------------
def amort_payment(principal, annual_rate, years):
    if principal <= 0 or years <= 0:
        return 0.0
    r = annual_rate / 12 / 100
    n = int(years * 12)
    if r == 0:
        return principal / n
    return principal * r * (1 + r)**n / ((1 + r)**n - 1)

def loan_balance(principal, annual_rate, years, months_elapsed):
    pmt = amort_payment(principal, annual_rate, years)
    r = annual_rate / 12 / 100
    bal = principal
    for _ in range(months_elapsed):
        interest = bal * r
        principal_pay = pmt - interest
        bal = max(0, bal - principal_pay)
    return bal

def irr(cashflows, guess=0.08, tol=1e-6, max_iter=100):
    r = guess
    for _ in range(max_iter):
        npv = 0
        d_npv = 0
        for t, cf in enumerate(cashflows):
            denom = (1 + r) ** t
            npv += cf / denom
            if t > 0:
                d_npv -= t * cf / ((1 + r) ** (t + 1))
        if abs(d_npv) < 1e-12:
            break
        new_r = r - npv / d_npv
        if abs(new_r - r) < tol:
            return new_r
        r = new_r
    return r

# ------------------------------
# Duty tables
# ------------------------------
BSD_TIERS = [
    (180000, 0.01),
    (180000, 0.02),
    (640000, 0.03),
    (500000, 0.04),
    (1500000, 0.05),
    (float("inf"), 0.06),
]

ABSD_TABLE = {
    "SC": [0.00, 0.20, 0.30],
    "PR": [0.05, 0.30, 0.35],
    "Foreigner": [0.60, 0.60, 0.60],
    "Entity": [0.65, 0.65, 0.65],
    "Trust": [0.65, 0.65, 0.65],
}

# ------------------------------
# Core functions
# ------------------------------
def calc_bsd(amount):
    bsd = 0
    remaining = amount
    for tier_amt, rate in BSD_TIERS:
        take = min(remaining, tier_amt)
        bsd += take * rate
        remaining -= take
        if remaining <= 0:
            break
    return bsd

def calc_absd(amount, profile, count):
    if profile not in ABSD_TABLE:
        return 0
    idx = 0 if count == 0 else (1 if count == 1 else 2)
    return amount * ABSD_TABLE[profile][idx]

def calc_max_loan(income, debts, age, tenure, rate, property_type, loan_type):
    tdsr_cap = 0.55
    msr_cap = 0.30 if property_type in ("HDB", "EC") else 1.0
    stress_rate = rate + 3.0
    avail_tdsr = max(0, income * tdsr_cap - debts)
    avail_msr = income * msr_cap
    monthly_cap = min(avail_tdsr, avail_msr)
    r = stress_rate / 12 / 100
    n = int(tenure * 12)
    if r == 0:
        loan = monthly_cap * n
    else:
        loan = monthly_cap * ((1 + r) ** n - 1) / (r * (1 + r) ** n)
    return loan

# ------------------------------
# UI Sidebar
# ------------------------------
st.sidebar.header("Profile & Inputs")
profile = st.sidebar.selectbox("Buyer Profile", ["SC", "PR", "Foreigner", "Entity", "Trust"], 0)
property_type = st.sidebar.selectbox("Property Type", ["HDB", "EC", "Private"], 2)
loan_type = st.sidebar.selectbox("Loan Type", ["Bank", "HDB"], 0)
income = st.sidebar.number_input("Gross Monthly Income (SGD)", 0.0, 1_000_000.0, 12_000.0, 500.0)
debts = st.sidebar.number_input("Monthly Debt Obligations", 0.0, 1_000_000.0, 0.0, 100.0)
age = st.sidebar.number_input("Borrower Age", 18, 75, 35)
tenure = st.sidebar.number_input("Tenure (Years)", 1, 35, 30)
rate = st.sidebar.number_input("Interest Rate (% p.a.)", 0.0, 15.0, 3.5, 0.1)
price = st.sidebar.number_input("Purchase Price (SGD)", 0.0, 100_000_000.0, 1_800_000.0, 10_000.0)
valuation = st.sidebar.number_input("Market Valuation (SGD)", 0.0, 100_000_000.0, 1_800_000.0, 10_000.0)
use_higher = st.sidebar.checkbox("Use whichever higher (Price vs Valuation)", True)
count = st.sidebar.number_input("Existing Properties", 0, 10, 0)

base = max(price, valuation) if use_higher else price

# ------------------------------
# Tabs
# ------------------------------
tab1, tab2, tab3 = st.tabs(["Eligibility & Loan", "Stamp Duties", "Buy vs Rent"])

with tab1:
    st.subheader("Loan Eligibility & Refinance Scenario")
    max_loan = calc_max_loan(income, debts, age, tenure, rate, property_type, loan_type)
    monthly = amort_payment(max_loan, rate, tenure)
    st.metric("Max Loan Amount", f"${max_loan:,.0f}")
    st.metric("Estimated Monthly Instalment", f"${monthly:,.0f}")
    refi_years = max(0, 75 - age)
    st.caption(f"Refinance-to-75 possible tenure: {refi_years} years.")

with tab2:
    st.subheader("Buyer’s & Additional Buyer’s Stamp Duty")
    bsd = calc_bsd(base)
    absd = calc_absd(base, profile, count)
    st.metric("BSD", f"${bsd:,.0f}")
    st.metric("ABSD", f"${absd:,.0f}")
    st.metric("Total Duties", f"${bsd + absd:,.0f}")

with tab3:
    st.subheader("Buy vs Rent (Quick View)")
    rent = st.number_input("Monthly Rent (SGD)", 0.0, 100_000.0, 4500.0, 100.0)
    years = st.number_input("Holding Period (Years)", 1, 40, 10)
    price_growth = st.number_input("Price Growth (% p.a.)", -10.0, 20.0, 2.0, 0.1)
    agent_fee = st.number_input("Agent Fee on Sale (%)", 0.0, 5.0, 2.0, 0.1)

    sale_price = price * ((1 + price_growth / 100) ** years)
    sale_cost = sale_price * agent_fee / 100
    downpayment = price - max_loan
    annual_instal = monthly * 12
    buy_cfs = [-downpayment - bsd - absd]
    for _ in range(years - 1):
        buy_cfs.append(-annual_instal)
    buy_cfs.append(-annual_instal + (sale_price - sale_cost))
    rent_cfs = [-(rent * 12) for _ in range(years)]
    irr_buy = irr(buy_cfs)
    st.metric("Buy IRR (est.)", f"{irr_buy*100:.2f}%")
    st.metric("Annual Rent Cost", f"${rent*12:,.0f}")

st.caption("Built by MiraclesGroup • For educational and professional use only.")
