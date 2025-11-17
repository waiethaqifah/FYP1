import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
import os
import altair as alt
import plotly.express as px
import base64
import requests
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from github import Github
from twilio.rest import Client
from streamlit_js_eval import streamlit_js_eval

# -------------------- LOAD DATA FUNCTIONS --------------------
@st.cache_data
def load_employee_data():
    return pd.read_csv("employee_data.csv")

def load_data():
    if os.path.exists("requests.csv"):
        return pd.read_csv("requests.csv")
    else:
        return pd.DataFrame(columns=[
            'Timestamp', 'Employee ID', 'Name', 'Department', 'Phone Number', 'Email',
            'Location', 'Status', 'Supplies Needed', 'Additional Notes', 'Request Status'
        ])

def load_users():
    if os.path.exists("users.csv"):
        return pd.read_csv("users.csv")
    else:
        return pd.DataFrame(columns=['Username', 'Password', 'Role'])

# -------------------- AUTHENTICATION --------------------
def authenticate(username, password, users_df):
    user = users_df[(users_df['Username'] == username) & (users_df['Password'] == password)]
    if not user.empty:
        return user.iloc[0]['Role']
    return None

# -------------------- NOTIFICATION SOUND --------------------
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

# -------------------- INITIAL SETUP --------------------
data = load_data()
employee_df = load_employee_data()
users_df = load_users()

st.set_page_config(page_title="Tetron Disaster Support App", layout="wide")
st.title("🖘 Tetron Disaster Emergency Support System")

# -------------------- LOGIN SESSION --------------------
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
            st.success(f"✅ Welcome, {username} ({role})")
            st.rerun()
        else:
            st.error("❌ Invalid username or password.")
    st.stop()

# -------------------- SIDEBAR MENU --------------------
with st.sidebar:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
        }
        .sidebar-bottom {
            margin-top: auto;
            padding-bottom: 30px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.header("📋 Navigation")

    role = st.session_state.role
    username = st.session_state.username

    menu = st.selectbox(
        "Select Menu",
        ["Employee"] if role == "Employee" else ["Employee", "Admin"]
    )

    st.markdown("---")
    st.markdown(f"👤 **Logged in as:** `{username}`  \n🧩 **Role:** `{role}`")

    st.markdown('<div class="sidebar-bottom"></div>', unsafe_allow_html=True)
    logout_clicked = st.button("🚪 Logout", use_container_width=True)
    if logout_clicked:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.toast("👋 Logged out successfully.", icon="✅")
        st.rerun()

# -------------------- EMPLOYEE INTERFACE --------------------
# -------------------- EMPLOYEE INTERFACE --------------------
if menu == "Employee":
    st.header("📋 Submit Your Emergency Request")

    emp_id = st.text_input("Enter Your Employee ID")

    if emp_id.strip() != "":
        emp_info = employee_df[employee_df['Employee ID'] == emp_id]

        if not emp_info.empty:
            emp_info_row = emp_info.iloc[0]
            name = emp_info_row['Name']
            dept = emp_info_row['Department']
            phone = emp_info_row['Phone Number']
            email = emp_info_row['Email']

            st.success(f"✅ Employee verified: {name} ({dept})")
            st.write("### 👤 Employee Information")
            st.dataframe(emp_info)

            # ---------------- LOCATION AUTO-DETECTION + LEAFLET MAP ----------------
            # ---------------- LOCATION AUTO-DETECTION + LEAFLET MAP ----------------
            st.subheader("📍 Auto Detect Location")
            
            js_code = """
            new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(
                    async (pos) => {
                        let lat = pos.coords.latitude;
                        let lon = pos.coords.longitude;
                        let acc = pos.coords.accuracy;
            
                        // Reverse geocode using OpenStreetMap Nominatim
                        try {
                            let url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`;
                            let response = await fetch(url, {
                                headers: { "Accept": "application/json" }
                            });
                            let data = await response.json();
            
                            resolve({
                                lat: lat,
                                lon: lon,
                                acc: acc,
                                address: data.display_name || "Address not found"
                            });
                        } catch (e) {
                            resolve({
                                lat: lat,
                                lon: lon,
                                acc: acc,
                                address: "Reverse geocoding failed"
                            });
                        }
                    },
                    (err) => resolve(null),
                    { enableHighAccuracy: true }
                );
            });
            """
            
            location = streamlit_js_eval(js_expressions=js_code, key="gps_with_address")
            
            if location:
                st.success("Location Retrieved Successfully!")
                st.write(f"**Latitude:** {location['lat']}")
                st.write(f"**Longitude:** {location['lon']}")
                st.write(f"**Accuracy:** ±{round(location['acc'],1)} m")
                st.write(f"**Address:** {location['address']}")
            
                st.map({"lat": [location['lat']], "lon": [location['lon']]})
            
            else:
                st.info("Please allow location permission on your device.")


            # ---------------- GITHUB CONNECTION ----------------
            GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
            REPO = st.secrets["GITHUB_REPO"]
            FILE_PATH = "requests.csv"

            def get_github_file():
                url = f"https://raw.githubusercontent.com/{REPO}/main/{FILE_PATH}"
                return pd.read_csv(url)

            def push_to_github(updated_df):
                from base64 import b64encode
                api_url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
                headers = {"Authorization": f"token {GITHUB_TOKEN}"}

                current = requests.get(api_url, headers=headers)
                sha = current.json().get("sha")

                content = b64encode(updated_df.to_csv(index=False).encode()).decode()
                data = {"message": "Update requests.csv", "content": content, "sha": sha}

                r = requests.put(api_url, json=data, headers=headers)
                return r.status_code in [200, 201]

            # ---------------- WHATSAPP ALERT ----------------
            def send_whatsapp_alert(emp_name, dept, status, supplies, location, notes):
                try:
                    account_sid = st.secrets["TWILIO_SID"]
                    auth_token = st.secrets["TWILIO_AUTH"]
                    from_whatsapp = st.secrets["TWILIO_WHATSAPP_FROM"]
                    admins = [num.strip() for num in st.secrets["ADMIN_GROUP_NUMBERS"].split(",")]

                    client = Client(account_sid, auth_token)

                    body = (
                        f"🚨 *New Emergency Request Submitted!*\n\n"
                        f"👤 Name: {emp_name}\n"
                        f"🏢 Department: {dept}\n"
                        f"📍 Location: {location}\n"
                        f"📊 Status: {status}\n"
                        f"📦 Supplies: {supplies}\n"
                        f"📝 Notes: {notes}\n"
                    )

                    for admin in admins:
                        client.messages.create(from_=from_whatsapp, to=admin, body=body)

                except Exception as e:
                    st.warning(f"⚠️ WhatsApp error: {e}")

            # ---------------- FORM SUBMISSION ----------------
            with st.form("emergency_form"):
                status = st.selectbox("Your Situation", ["Safe", "Evacuated", "In Need of Help"])
                supplies = st.multiselect(
                    "Supplies Needed",
                    ["Food", "Water", "Baby Supplies", "Hygiene Kit", "Medical Kit", "Blanket"]
                )
                notes = st.text_area("Additional Notes")

                submit = st.form_submit_button("Submit Request")

                if submit:
                    if location  == "":
                        st.error("❌ Please detect your location first.")
                        st.stop()

                    try:
                        df = get_github_file()
                    except:
                        df = pd.DataFrame(columns=[
                            'Timestamp', 'Employee ID', 'Name', 'Department', 'Phone Number', 'Email',
                            'Location', 'Status', 'Supplies Needed', 'Additional Notes', 'Request Status'
                        ])

                    new_row = pd.DataFrame({
                        'Timestamp': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                        'Employee ID': [emp_id],
                        'Name': [name],
                        'Department': [dept],
                        'Phone Number': [phone],
                        'Email': [email],
                        'Location': [final_address],   # only address saved
                        'Status': [status],
                        'Supplies Needed': [", ".join(supplies)],
                        'Additional Notes': [notes],
                        'Request Status': ["Pending"]
                    })

                    updated = pd.concat([df, new_row], ignore_index=True)

                    if push_to_github(updated):
                        st.success("✅ Request submitted successfully!")
                        st.balloons()
                        send_whatsapp_alert(name, dept, status, ", ".join(supplies), final_address, notes)
                    else:
                        st.error("❌ Failed to update GitHub.")

        else:
            st.warning("❌ Employee ID not found.")


# -------------------- ADMIN INTERFACE --------------------
if menu == "Admin":
    st.header("🚰 Admin Dashboard - Manage Requests")
    data = load_data()

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
        new_status = st.selectbox(
            "Update Status",
            ["Pending", "Approved", "Delivered", "Rejected"],
            index=["Pending", "Approved", "Delivered", "Rejected"].index(current_status)
        )

        if st.button("Update Status"):
            data.at[selected_index, 'Request Status'] = new_status
            GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
            REPO_NAME = "waiethaqifah/fyp1"
            FILE_PATH = "requests.csv"
            try:
                g = Github(GITHUB_TOKEN)
                repo = g.get_repo(REPO_NAME)
                contents = repo.get_contents(FILE_PATH)
                updated_csv = data.to_csv(index=False)
                repo.update_file(
                    path=FILE_PATH,
                    message=f"Admin updated request status at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    content=updated_csv,
                    sha=contents.sha
                )
                st.success("✅ Request status updated and synced to GitHub.")
            except Exception as e:
                st.error(f"❌ Failed to update GitHub file: {e}")

    st.markdown("---")
    st.subheader("📊 Summary Report")
    st.write(data['Request Status'].value_counts())

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
    ).properties(width=600, height=400)
    st.altair_chart(delivery_chart)

    st.subheader("📅 Requests Over Time")
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    daily_requests = data.dropna(subset=['Timestamp']).groupby(
        data['Timestamp'].dt.date
    ).size().reset_index(name='Request Count')
    daily_requests = daily_requests.rename(columns={daily_requests.columns[0]: 'Date'})
    if not daily_requests.empty:
        st.line_chart(daily_requests.set_index('Date'))
    else:
        st.info("No valid timestamp entries available for request trend analysis.")

   
