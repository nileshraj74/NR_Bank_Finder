import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="NR Bank Finder",
    page_icon="logo.png",
    layout="wide"
)

# ---------------- LOGIN ----------------
APP_PASSWORD = "Banthia@123"   # <-- Change this to your password

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ----- LOGIN PAGE -----
if not st.session_state.logged_in:
    st.image("logo.png", width=180)
    st.title("🔐 Login Required")

    password = st.text_input("Enter Password", type="password")

    if st.button("Login"):
        if password == APP_PASSWORD:
            st.session_state.logged_in = True
            st.success("Login successful ✅")
            st.rerun()
        else:
            st.error("Wrong password ❌")

    st.stop()

# ----- MAIN APP (After Login) -----
st.image("logo.png", width=180)

# ---------------- CONFIG ----------------
EXCEL_PATH = "Bank_Calc.xlsx"

st.set_page_config(page_title="Loan Proposal Eligibility Engine", layout="wide")
st.title("🏦 Bank Eligibility Analyzer (Auto Recommendation Engine)")

# ---------------- LOAD BANK RULES ----------------
@st.cache_data
def load_bank_rules():
    df = pd.read_excel(EXCEL_PATH)
    df.columns = df.columns.astype(str).str.strip()
    criteria_col = df.columns[0]
    df.set_index(criteria_col, inplace=True)
    df.index = df.index.astype(str).str.strip()

    def normalize(val):
        if isinstance(val, str) and "%" in val:
            return float(val.replace("%", "").strip()) / 100
        return val

    return df.applymap(normalize)

rules_df = load_bank_rules()
banks = rules_df.columns.tolist()

# ---------------- USER INPUTS ----------------
st.header("📥 Enter Proposal Details")
col1, col2, col3, col4 = st.columns(4)

with col1:
    primary_security = st.selectbox("Primary Security", ["Yes", "No"])
    land_cost = st.number_input("Land Cost (₹)", min_value=0.0)
    land_loan = st.number_input("Loan for Land Purchase (₹)", min_value=0.0)
    construction_cost = st.number_input("Construction Cost (₹)", min_value=0.0)
    construction_loan = st.number_input("Loan for Construction (₹)", min_value=0.0)

with col2:
    machinery_cost = st.number_input("Machinery Cost (₹)", min_value=0.0)
    machinery_loan = st.number_input("Loan for Machinery (₹)", min_value=0.0)
    utility_cost = st.number_input("Utility Cost (₹)", min_value=0.0)
    utility_loan = st.number_input("Loan for Utilities (₹)", min_value=0.0)
    contingencies = st.number_input("Contingencies (₹)", min_value=0.0)
    other_loan = st.number_input("Loan for Other Expenses (₹)", min_value=0.0)

with col3:
    cc_requirement = st.number_input("CC Requirement (₹)", min_value=0.0)
    other_sec_value = st.number_input("Market Value of Other Security (₹)", min_value=0.0)
    expected_roi = st.number_input("Expected ROI (%)", min_value=0.0)
    expected_pf = st.number_input("Expected Processing Fees (%)", min_value=0.0)
    margin_value = st.number_input("Promoter Own Fund + USL (₹)", min_value=0.0)

with col4:
    dscr1 = st.number_input("DSCR FY1", min_value=0.0)

# ---------------- AUTO CALCULATIONS ----------------
project_cost = land_cost + construction_cost + machinery_cost + utility_cost + contingencies
required_total_loan = land_loan + construction_loan + machinery_loan + utility_loan + other_loan + cc_requirement

st.subheader("📊 Calculated Values")
st.metric("Project Cost", f"₹{project_cost:,.0f}")
st.metric("Required Total Loan", f"₹{required_total_loan:,.0f}")

# ---------------- ELIGIBILITY ENGINE ----------------
if st.button("🚀 ShowMeTheBanks"):

    eligible_rows = []
    rejected_rows = []
    param_results = []
    recommendations = []

    for bank in banks:
        # ---- Bank Rules ----
        MinSec = rules_df.at["MinSec", bank]
        HighROI = rules_df.at["HighROI", bank]
        LowROI = rules_df.at["LowROI", bank]
        Min_PF = rules_df.at["Min_PF", bank]
        Max_PF = rules_df.at["Max_PF", bank]
        DSCR = rules_df.at["Ideal_DSCR", bank]

        Margin4Land = rules_df.at["Margin4LandPurchaseTL", bank]
        Margin4Cons = rules_df.at["Margin4ConstructionTL", bank]
        Margin4MTL = rules_df.at["Margin4MTL", bank]
        Margin4Util = rules_df.at["Margin4UtilitiesTL", bank]
        Margin4OTL = rules_df.at["Margin4OTL", bank]

        # ---- Security ----
        security_value = land_cost + construction_cost + other_sec_value if primary_security == "No" else other_sec_value
        security_coverage = security_value / required_total_loan if required_total_loan else 0

        security_required = MinSec * required_total_loan
        security_gap = security_required - security_value
        security_gap_pct = (security_gap / security_required) * 100 if security_required > 0 else 0

        # ---- Margin ----
        margin_required = (
                Margin4Land * land_loan +
                Margin4Cons * construction_loan +
                Margin4MTL * machinery_loan +
                Margin4Util * utility_loan +
                Margin4OTL * other_loan
        )

        gap = margin_required - margin_value
        gap_pct = (gap / margin_required) * 100 if margin_required > 0 else 0

        expected_roi_decimal = expected_roi / 100
        expected_pf_decimal = expected_pf / 100
        expected_dscr = dscr1

        # ---- Parameter Checks ----
        checks = {
            "Security_OK": security_coverage >= MinSec,
            "Margin_OK": margin_value >= margin_required,
            "ROI_OK": LowROI <= expected_roi_decimal <= HighROI,
            "PF_OK": Min_PF <= expected_pf_decimal <= Max_PF,
            "DSCR_OK": expected_dscr >= DSCR
        }

        temp = {"Bank": bank}
        temp.update(checks)
        param_results.append(temp)

        # ---- Approval Score ----
        score = 100
        score -= max(0, gap_pct)
        score -= max(0, security_gap_pct)
        score -= max(0, (LowROI - expected_roi_decimal) * 100)
        score -= max(0, (expected_roi_decimal - HighROI) * 100)
        score -= max(0, (expected_pf_decimal - Max_PF) * 100)
        score -= max(0, (Min_PF - expected_pf_decimal) * 100)
        score -= max(0, (DSCR - expected_dscr) * 10)
        score = max(0, min(100, score))

        # ---- Auto Recommendations ----
        rec_list = []
        if not checks["Security_OK"]:
            rec_list.append(f"Add security of ₹{security_gap:,.0f}")
        if not checks["Margin_OK"]:
            rec_list.append(f"Add promoter margin of ₹{gap:,.0f}")
        if not checks["ROI_OK"]:
            rec_list.append(f"Adjust ROI to {LowROI*100:.2f}% - {HighROI*100:.2f}%")
        if not checks["PF_OK"]:
            rec_list.append(f"Adjust PF to {Min_PF*100:.2f}% - {Max_PF*100:.2f}%")
        if not checks["DSCR_OK"]:
            rec_list.append(f"Improve DSCR to {DSCR:.2f}")

        recommendations.append({
            "Bank": bank,
            "Recommendations": "; ".join(rec_list) if rec_list else "Eligible - No Action Required"
        })

        # ---- Final Decision ----
        if not all(checks.values()):
            rejected_rows.append([
                bank, ",".join([k for k, v in checks.items() if not v]),
                margin_required, margin_value, gap, gap_pct,
                security_required, security_value, security_gap, security_gap_pct,
                score
            ])
            continue

        eligible_rows.append([
            bank,
            margin_required, margin_value, gap, gap_pct,
            security_required, security_value, security_gap, security_gap_pct,
            score
        ])

    # ---------------- DATAFRAMES ----------------
    eligible_df = pd.DataFrame(eligible_rows, columns=[
        "Bank",
        "Required Margin", "Available Margin", "Margin Gap", "Margin Gap %",
        "Required Security", "Available Security", "Security Gap", "Security Gap %",
        "Approval Score"
    ])

    rejected_df = pd.DataFrame(rejected_rows, columns=[
        "Bank", "Reject Reason",
        "Required Margin", "Available Margin", "Margin Gap", "Margin Gap %",
        "Required Security", "Available Security", "Security Gap", "Security Gap %",
        "Approval Score"
    ])

    param_df = pd.DataFrame(param_results)
    rec_df = pd.DataFrame(recommendations)

    if not eligible_df.empty:
        eligible_df = eligible_df.sort_values(by="Margin Gap")
    if not rejected_df.empty:
        rejected_df = rejected_df.sort_values(by="Margin Gap")

    # ---------------- TRAFFIC LIGHT MATRIX ----------------
    def traffic_light(val):
        return "🟢" if val else "🔴"

    circle_df = param_df.copy()
    for col in circle_df.columns[1:]:
        circle_df[col] = circle_df[col].apply(traffic_light)

    st.header("🚦 Parameter Eligibility Matrix")
    st.dataframe(circle_df)

    # ---------------- RESULTS ----------------
    st.header("✅ Eligible Banks (Ranked)")
    st.dataframe(eligible_df)

    st.header("❌ Rejected Banks")
    st.dataframe(rejected_df)

    # ---------------- RECOMMENDATIONS ----------------
    st.header("💡 Auto Recommendations")
    st.dataframe(rec_df)

    # ---------------- CHART ----------------
    st.header("📊 Bank Approval Score Ranking")
    if not eligible_df.empty:
        fig, ax = plt.subplots()
        ax.barh(eligible_df["Bank"], eligible_df["Approval Score"])
        ax.set_xlabel("Approval Score")
        ax.set_title("Eligible Bank Ranking")
        st.pyplot(fig)

    # ---------------- EXPORT TO EXCEL ----------------
    st.header("📥 Export Results")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        eligible_df.to_excel(writer, sheet_name="Eligible", index=False)
        rejected_df.to_excel(writer, sheet_name="Rejected", index=False)
        circle_df.to_excel(writer, sheet_name="Parameter_Checks", index=False)
        rec_df.to_excel(writer, sheet_name="Recommendations", index=False)

    st.download_button(
        label="📤 Download Excel Report",
        data=buffer.getvalue(),
        file_name="Loan_Bank_Eligibility_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

    )



