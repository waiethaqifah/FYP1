import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import altair as alt
import plotly.express as px
import base64
import requests
from geopy.geocoders import Nominatim
import folium                          
from streamlit_folium import st_folium

# Load employee data
@st.cache_data
def load_employee_data():
    return pd.read_csv("employee_data.csv")

# Load request data from CSV (no caching to reflect live updates)
def load_data():
    if os.path.exists("requests.csv"):
        return pd.read_csv("requests.csv")
    else:
        return pd.DataFrame(columns=[
            'Timestamp', 'Employee ID', 'Name', 'Department', 'Phone Number', 'Email',
            'Location', 'Status', 'Supplies Needed', 'Additional Notes', 'Request Status'
        ])

# Load user credentials
def load_users():
    if os.path.exists("users.csv"):
        return pd.read_csv("users.csv")
    else:
        return pd.DataFrame(columns=['Username', 'Password', 'Role'])

# Authentication system
def authenticate(username, password, users_df):
    user = users_df[(users_df['Username'] == username) & (users_df['Password'] == password)]
    if not user.empty:
        return user.iloc[0]['Role']
    return None

# Notification sound on pending requests
def play_notification_sound():
    file_path = "chime-alert-demo-309545.mp3"
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            sound_html = f"""
                <audio autoplay>
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mpeg">
                </audio>
            """
            st.markdown(sound_html, unsafe_allow_html=True)

# Load data
data = load_data()
employee_df = load_employee_data()
users_df = load_users()

st.set_page_config(page_title="Tetron Disaster Support App", layout="wide")
st.title("🖘 Tetron Disaster Emergency Support System")

# Session state login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

if not st.session_state.logged_in:
    st.sidebar.header("🔐 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        role = authenticate(username, password, users_df)
        if role:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = role
            st.success(f"Welcome, {username} ({role})")
        else:
            st.error("Invalid username or password.")
    st.stop()

# Menu based on role
role = st.session_state.role
menu = st.sidebar.selectbox("Select Menu", ["Employee"] if role == "Employee" else ["Employee", "Admin"])

# ------------------- EMPLOYEE INTERFACE -------------------
if menu == "Employee":
    st.header("📋 Submit Your Emergency Request")
    emp_id = username

    emp_info = employee_df[employee_df['Employee ID'] == emp_id]
    if not emp_info.empty:
        emp_info_row = emp_info.iloc[0]
        name = emp_info_row['Name']
        dept = emp_info_row['Department']
        phone = emp_info_row['Phone Number']
        email = emp_info_row['Email']

        st.write("### 👤 Employee Information")
        st.write(emp_info)

        st.subheader("📍 Location Detection")

        # --- IP-based detection ---
        lat, lon, address = None, None, None
        try:
            resp = requests.get("http://ip-api.com/json/").json()
            lat, lon = resp.get("lat"), resp.get("lon")
            if lat and lon:
                address = f"{resp.get('city','Unknown')}, {resp.get('regionName','')}, {resp.get('country','')}"
                st.success(f"✅ Approximate location detected via IP: {address}")
            else:
                st.warning("⚠️ Could not detect your location automatically.")
        except Exception:
            st.warning("⚠️ Network or IP detection failed. You can select location manually below.")

        # --- Interactive map selection ---
        st.markdown("#### 🗺️ Confirm or Adjust Your Location on the Map")
        start_coords = [lat, lon] if lat and lon else [3.139, 101.6869]
        m = folium.Map(location=start_coords, zoom_start=6)
        folium.LatLngPopup().add_to(m)
        output = st_folium(m, width=700, height=400)

        if output and output.get("last_clicked"):
            lat = output["last_clicked"]["lat"]
            lon = output["last_clicked"]["lng"]
            st.info(f"📍 Selected coordinates: {lat:.4f}, {lon:.4f}")

        # --- Reverse geocode ---
        try:
            if lat and lon:
                geolocator = Nominatim(user_agent="tetron_disaster_app")
                location_obj = geolocator.reverse((lat, lon), language="en")
                if location_obj:
                    address = location_obj.address
                    st.success(f"✅ Confirmed location: {address}")
        except Exception:
            st.warning("⚠️ Could not retrieve address from coordinates.")

        if not address:
            address = st.text_input("Enter your current location manually (e.g., City or Area)")

        # --- Emergency Request Form ---
        with st.form("emergency_form"):
            status = st.selectbox("Your Situation", ["Safe", "Evacuated", "In Need of Help"])
            supplies = st.multiselect(
                "Supplies Needed",
                ["Food","Water","Baby Supplies","Hygiene Kit","Medical Kit","Blanket"]
            )
            notes = st.text_area("Additional Notes")
            submit = st.form_submit_button("Submit Request")

            if submit:
                new_data = pd.DataFrame({
                    'Timestamp': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                    'Employee ID': [emp_id],
                    'Name': [name],
                    'Department': [dept],
                    'Phone Number': [phone],
                    'Email': [email],
                    'Location': [address],
                    'Status': [status],
                    'Supplies Needed': [", ".join(supplies)],
                    'Additional Notes': [notes],
                    'Request Status': ["Pending"]
                })

                updated_data = pd.concat([data, new_data], ignore_index=True)
                updated_data.to_csv("requests.csv", index=False)
                st.success("✅ Your emergency request has been submitted successfully.")
                st.balloons()

        # --- Previous requests ---
        st.markdown("---")
        st.subheader("🗂️ Your Previous Requests")
        emp_reqs = data[data['Employee ID'] == emp_id]
        if not emp_reqs.empty:
            st.dataframe(emp_reqs)
        else:
            st.info("You have not submitted any requests yet.")
    else:
        st.warning("Employee ID not found. Please check again.")

# ------------------- ADMIN INTERFACE -------------------
if menu == "Admin":
    st.header("🚰 Admin Dashboard - Manage Requests")

    # Reload fresh data without cache
    data = load_data()

    # 🔔 Alert for new pending requests
    pending_count = data[data['Request Status'] == "Pending"].shape[0]
    if pending_count > 0:
        st.warning(f"🚨 There are {pending_count} new pending request(s) that need attention!")
        play_notification_sound()

    if data.empty:
        st.warning("No requests submitted yet.")
    else:
        st.dataframe(data)

        selected_index = st.selectbox("Select request to update:", data.index)
        current_status = data.loc[selected_index, 'Request Status']

        new_status = st.selectbox("Update Status", ["Pending", "Approved", "Delivered", "Rejected"], index=["Pending", "Approved", "Delivered", "Rejected"].index(current_status))
        if st.button("Update Status"):
            data.at[selected_index, 'Request Status'] = new_status
            data.to_csv("requests.csv", index=False)
            st.success("Request status updated.")

    st.markdown("---")
    st.subheader("📊 Summary Report")
    st.write(data['Request Status'].value_counts())

    # Additional Reporting
    st.markdown("---")
    st.subheader("📦 Stock Request Overview")
    supply_counts = data['Supplies Needed'].str.get_dummies(sep=", ").sum().sort_values(ascending=False)
    st.bar_chart(supply_counts)

    st.subheader("💰 Budget Estimation")
    unit_cost = {
        "Food": 10,
        "Water": 5,
        "Baby Supplies": 15,
        "Hygiene Kit": 12,
        "Medical Kit": 20,
        "Blanket": 8
    }

    total_cost = 0
    supply_cost_data = []

    for item, count in supply_counts.items():
        cost = count * unit_cost.get(item, 0)
        total_cost += cost
        supply_cost_data.append({"Item": item, "Quantity": count, "Total Cost (MYR)": cost})

    cost_df = pd.DataFrame(supply_cost_data)
    st.dataframe(cost_df)

    st.metric("Estimated Total Budget Needed (MYR)", f"RM {total_cost:.2f}")

    st.subheader("📈 Delivery Status Report")
    delivery_chart = alt.Chart(data).mark_bar().encode(
        x=alt.X('Request Status:N', title='Request Status'),
        y=alt.Y('count():Q', title='Number of Requests'),
        color='Request Status:N'
    ).properties(
        width=600,
        height=400
    )
    st.altair_chart(delivery_chart)

    st.subheader("📅 Requests Over Time")
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    daily_requests = data.dropna(subset=['Timestamp']).groupby(data['Timestamp'].dt.date).size().reset_index(name='Request Count')
    daily_requests = daily_requests.rename(columns={daily_requests.columns[0]: 'Date'})
    if not daily_requests.empty:
        st.line_chart(daily_requests.set_index('Date'))
    else:
        st.info("No valid timestamp entries available for request trend analysis.")

    st.subheader("🧊 3D Interactive Chart: Supplies vs Status")
    if not data.empty:
        plot_data = data.copy()
        plot_data['Supplies Needed'] = plot_data['Supplies Needed'].fillna('None')
        fig = px.scatter_3d(plot_data, x='Status', y='Supplies Needed', z='Request Status',
                            color='Status', symbol='Request Status')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough data to display 3D chart.")
