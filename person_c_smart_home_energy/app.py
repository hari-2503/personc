"""Person C - Streamlit frontend for the Smart Home Energy Monitor API.

Run:  streamlit run app.py   (API_BASE_URL defaults to http://127.0.0.1:8003)
"""
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from ui_common import resolve_api_base_url, api_delete, api_get, api_post, api_put, money

st.set_page_config(page_title="Smart Home Energy Monitor (C)", layout="wide")


API_BASE_URL = resolve_api_base_url(st.secrets)

st.title("Smart Home Electricity Monitoring & Bill Estimation")
st.caption("Person C - Hariharan S (23MID0182) | CSI3007 Advanced Python Programming | "
           f"API: `{API_BASE_URL}`")

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Appliances", "Usage Readings", "Consumption", "Billing & Tariffs", "6-Month History"],
)


def current_month() -> str:
    return date.today().strftime("%Y-%m")


# ------------------------------------------------------------------ Dashboard
if page == "Dashboard":
    st.subheader("This month at a glance")
    ok, status = api_get(API_BASE_URL, "/integrations/status")
    if not ok:
        st.error(status)
    else:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Appliances", f"{status['active_appliances_count']} active")
        col2.metric("Readings logged", status["readings_count"])
        col3.metric("Months with data", len(status["months_with_data"]))
        summary = status["latest_month_summary"]
        col4.metric("Month-to-date kWh", f"{summary['estimated_kwh']:.1f}")

        ok, estimate = api_get(API_BASE_URL, "/bill/estimate", params={"month": current_month()})
        if ok:
            if estimate["status"] == "ok":
                if estimate["tariff_verified"] is False:
                    st.warning("Tariff rates are UNVERIFIED seed values - verify against the "
                               "official TNEB/TANGEDCO tariff order (GET /tariffs).")
                col1, col2, col3 = st.columns(3)
                col1.metric("Estimated kWh", f"{estimate['estimated_kwh']:.1f}")
                col2.metric("Energy charge", money(estimate["energy_charge"]))
                col3.metric("Estimated bill", money(estimate["estimated_amount"]))
            else:
                st.info(estimate.get("note") or f"Estimate status: {estimate['status']}")

        ok, compare = api_get(API_BASE_URL, "/bill/compare", params={"month": current_month()})
        if ok:
            if compare["status"] == "no_actual":
                st.info("No actual bill recorded for this month yet - record it under "
                        "Billing & Tariffs once the electricity board bill arrives.")
            elif compare.get("needs_investigation"):
                st.error(f"Deviation {compare['deviation_percent']}% exceeds the "
                         f"{compare['threshold_percent']}% threshold. {compare['suggested_action']}")
                st.caption(compare["disclaimer"])

# ------------------------------------------------------------------ Appliances
elif page == "Appliances":
    st.subheader("Appliances")
    ok, appliances = api_get(API_BASE_URL, "/appliances")
    if not ok:
        st.error(appliances)
    else:
        if appliances:
            df = pd.DataFrame(appliances)[
                ["id", "name", "room", "rated_power_kw", "quantity", "typical_hours_per_day", "active"]
            ]
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption("Energy per reading: E_kWh = rated_power_kw x quantity x hours_used")
        else:
            st.info("No appliances yet.")

        appliance_id = st.number_input("Appliance ID to delete", min_value=1, step=1)
        if st.button("Delete appliance (also deletes its readings)"):
            ok, result = api_delete(API_BASE_URL, f"/appliances/{int(appliance_id)}")
            if ok:
                st.success(f"Deleted #{int(appliance_id)}")
                st.rerun()
            else:
                st.error(result)

    st.markdown("#### Add an appliance")
    with st.form("add_appliance", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name *", placeholder="Air Conditioner 1.5T")
        room = c2.text_input("Room", placeholder="Bedroom")
        c3, c4 = st.columns(2)
        power = c3.number_input("Rated power (kW) *", min_value=0.01, value=1.5, step=0.05,
                                help="1.5 kW = 1500 W")
        quantity = c3.number_input("Quantity", min_value=1, value=1, step=1)
        hours = c4.number_input("Typical hours/day (per unit)", min_value=0.0, max_value=24.0, value=4.0, step=0.5)
        notes = st.text_input("Notes")
        if st.form_submit_button("Save appliance"):
            if not name:
                st.error("Name is required.")
            else:
                ok, result = api_post(API_BASE_URL, "/appliances", {
                    "name": name, "room": room, "rated_power_kw": power,
                    "quantity": int(quantity), "typical_hours_per_day": hours, "notes": notes,
                })
                if ok:
                    st.success(f"Saved appliance #{result['id']}")
                    st.rerun()
                else:
                    st.error(result)

# -------------------------------------------------------------- Usage Readings
elif page == "Usage Readings":
    st.subheader("Log daily operating hours")
    with st.form("add_reading"):
        ok, appliances = api_get(API_BASE_URL, "/appliances", params={"active": "true"})
        names = {f"{a['id']} - {a['name']}": a for a in appliances} if ok else {}
        chosen = st.selectbox("Appliance *", list(names) if names else ["(no appliances)"])
        reading_date = st.date_input("Date *", value=date.today() - timedelta(days=1))
        hours = st.number_input("Hours used *", min_value=0.0, max_value=24.0, value=4.0, step=0.5)
        if st.form_submit_button("Save reading (upsert)"):
            if not names:
                st.error("Add an appliance first.")
            else:
                appliance = names[chosen]
                ok, result = api_post(API_BASE_URL, "/readings", {
                    "appliance_id": appliance["id"],
                    "reading_date": reading_date.isoformat(),
                    "hours_used": hours,
                })
                if ok:
                    st.success(f"Logged {result['kwh']} kWh for {result['appliance_name']} "
                               f"on {result['reading_date']}")
                else:
                    st.error(result)

    st.markdown("#### Fill a whole day with typical hours")
    default_date = st.date_input("Date to fill", value=date.today() - timedelta(days=1), key="bulk_date")
    if st.button("Log typical hours for all active appliances"):
        ok, result = api_post(API_BASE_URL, "/readings/bulk-default",
                              {"reading_date": default_date.isoformat()})
        if ok:
            st.success(f"Created {result['created']} readings, skipped {result['skipped']}.")
        else:
            st.error(result)

    st.markdown("#### Recent readings")
    ok, data = api_get(API_BASE_URL, "/readings", params={"limit": 60})
    if ok:
        if data["readings"]:
            df = pd.DataFrame(data["readings"])[
                ["reading_date", "appliance_name", "hours_used", "kwh", "source"]
            ]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No readings yet.")
    else:
        st.error(data)

# ----------------------------------------------------------------- Consumption
elif page == "Consumption":
    st.subheader("Daily consumption")
    col1, col2 = st.columns(2)
    start = col1.date_input("Start date", value=date.today() - timedelta(days=13))
    end = col2.date_input("End date", value=date.today())
    ok, data = api_get(API_BASE_URL, "/consumption/daily", params={"start": start.isoformat(), "end": end.isoformat()})
    if not ok:
        st.error(data)
    elif data["days"]:
        df = pd.DataFrame(data["days"])
        fig = px.bar(df, x="date", y="total_kwh", title="kWh per day")
        st.plotly_chart(fig, use_container_width=True)
        latest = data["days"][-1]
        st.markdown(f"**Breakdown for {latest['date']}**")
        st.dataframe(pd.DataFrame(latest["by_appliance"]), use_container_width=True, hide_index=True)
    else:
        st.info("No readings in this range.")

    st.subheader("Monthly consumption")
    ok, data = api_get(API_BASE_URL, "/consumption/monthly", params={"months": 6})
    if ok:
        if data["months"]:
            df = pd.DataFrame(data["months"])
            fig = px.line(df, x="month", y="total_kwh", markers=True, title="kWh per month")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No monthly data yet.")
    else:
        st.error(data)

# ----------------------------------------------------------- Billing & Tariffs
elif page == "Billing & Tariffs":
    st.subheader("Bill estimate")
    month = st.text_input("Month (YYYY-MM)", value=current_month(), max_chars=7)
    ok, estimate = api_get(API_BASE_URL, "/bill/estimate", params={"month": month})
    if ok:
        if estimate["status"] == "ok":
            col1, col2, col3 = st.columns(3)
            col1.metric("Estimated kWh", f"{estimate['estimated_kwh']:.1f}")
            col2.metric("Energy charge", money(estimate["energy_charge"], estimate["currency"]))
            col3.metric("Estimated bill", money(estimate["estimated_amount"], estimate["currency"]))
            st.caption(f"Tariff: {estimate['tariff_name']} | verified={estimate['tariff_verified']}")
            if estimate["slab_breakdown"]:
                st.dataframe(pd.DataFrame(estimate["slab_breakdown"]), use_container_width=True, hide_index=True)
            if estimate["tariff_verified"] is False:
                st.warning(estimate.get("note") or "Tariff rates are unverified.")
        else:
            st.info(estimate.get("note") or f"Status: {estimate['status']}")
    else:
        st.error(estimate)

    st.subheader("Record the actual bill")
    with st.form("actual_bill"):
        actual_month = st.text_input("Month *", value=current_month(), key="actual_month", max_chars=7)
        c1, c2 = st.columns(2)
        kwh_actual = c1.number_input("Billed units (kWh) *", min_value=0.0, value=300.0, step=10.0)
        amount_actual = c2.number_input("Billed amount (INR) *", min_value=0.0, value=1200.0, step=50.0)
        notes = st.text_input("Notes")
        if st.form_submit_button("Save actual bill"):
            ok, result = api_post(API_BASE_URL, "/bill/actual", {
                "month": actual_month, "kwh_actual": kwh_actual, "amount_actual": amount_actual, "notes": notes,
            })
            if ok:
                st.success(f"Actual bill for {actual_month} saved.")
            else:
                st.error(result)

    st.subheader("Estimate vs actual (deviation analysis)")
    compare_month = st.text_input("Month to compare", value=current_month(), key="compare_month", max_chars=7)
    if st.button("Compare now"):
        ok, compare = api_get(API_BASE_URL, "/bill/compare", params={"month": compare_month})
        if not ok:
            st.error(compare)
        elif compare["status"] != "ok":
            st.info(f"Status: {compare['status']} - {compare.get('disclaimer', '')}")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("D (amount)", money(compare["D_amount"]))
            col2.metric("Deviation", f"{compare['deviation_percent']}%")
            col3.metric("Threshold", f"{compare['threshold_percent']}%")
            if compare["needs_investigation"]:
                st.error("Above threshold - investigate. " + (compare.get("suggested_action") or ""))
            else:
                st.success("Within threshold.")
            st.caption(compare["disclaimer"])

    st.subheader("Configured tariffs")
    ok, tariffs = api_get(API_BASE_URL, "/tariffs")
    if ok:
        st.caption(f"Default tariff: {tariffs['default_tariff']}")
        for tariff in tariffs["tariffs"]:
            badge = "VERIFIED" if tariff["verified"] else "UNVERIFIED SEED"
            with st.expander(f"{tariff['name']} ({tariff['billing_cycle']}) - {badge}"):
                st.write(tariff["notes"])
                st.dataframe(pd.DataFrame(tariff["slabs"]), use_container_width=True, hide_index=True)
    else:
        st.error(tariffs)

# ---------------------------------------------------------------- History
elif page == "6-Month History":
    st.subheader("Estimated vs actual - last months")
    months = st.slider("How many months", 1, 24, 6)
    ok, data = api_get(API_BASE_URL, "/history", params={"months": months})
    if not ok:
        st.error(data)
    else:
        df = pd.DataFrame(data["months"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        plot_df = df[["month", "estimated_amount", "actual_amount"]].melt(
            id_vars="month", var_name="series", value_name="amount"
        )
        fig = px.bar(plot_df, x="month", y="amount", color="series", barmode="group",
                     title="Estimated vs actual bill amount")
        st.plotly_chart(fig, use_container_width=True)
        flagged = df[df["needs_investigation"] == True]  # noqa: E712
        if not flagged.empty:
            st.error(f"Months flagged for investigation: {', '.join(flagged['month'])}")
        st.caption("Deviation is only an investigation signal - it cannot prove a meter fault.")
