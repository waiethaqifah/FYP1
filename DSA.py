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

            # ---------------- LOCATION SELECTION ----------------
            st.subheader("📍 Select and Confirm Your Location")

            country = st.selectbox("Select Your Country", ["Malaysia", "Singapore", "Thailand", "Indonesia"])

            district_options = {
                "Malaysia": [
                    "Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang", "Penang",
                    "Perak", "Perlis", "Sabah", "Sarawak", "Selangor", "Terengganu",
                    "Kuala Lumpur", "Putrajaya", "Labuan"
                ],
                "Singapore": ["Central Region", "East Region", "North Region", "North-East Region", "West Region"],
                "Thailand": ["Bangkok", "Chiang Mai", "Phuket", "Pattaya", "Khon Kaen", "Songkhla"],
                "Indonesia": ["Jakarta", "Bandung", "Bali", "Surabaya", "Medan", "Makassar"]
            }

            district = st.selectbox("Select Your State / District", district_options[country])
            specific_area = st.text_input("Add Specific Area or Landmark (optional)", placeholder="e.g., near Hospital Sungai Buloh")

            st.markdown("#### 🗺️ Adjust Your Exact Location on the Map")

            # Approximate coordinates for selected region (for map center)
            region_coords = {
                "Malaysia": [4.2105, 101.9758],
                "Singapore": [1.3521, 103.8198],
                "Thailand": [13.7563, 100.5018],
                "Indonesia": [-0.7893, 113.9213]
            }

            lat, lon, address = None, None, None
            start_coords = region_coords.get(country, [3.139, 101.6869])

            # Folium map
            m = folium.Map(location=start_coords, zoom_start=6)
            folium.LatLngPopup().add_to(m)
            output = st_folium(m, width=700, height=400)

            if output and output.get("last_clicked"):
                lat = output["last_clicked"]["lat"]
                lon = output["last_clicked"]["lng"]
                st.info(f"📍 Selected coordinates: {lat:.4f}, {lon:.4f}")

                try:
                    geolocator = Nominatim(user_agent="tetron_disaster_app")
                    location = geolocator.reverse((lat, lon), language="en")
                    if location:
                        address = location.address
                        st.success(f"✅ Confirmed detailed location: {address}")
                except Exception:
                    st.warning("⚠️ Could not retrieve address from coordinates.")
                    address = f"{lat:.4f}, {lon:.4f}"

            if not address:
                # fallback address if no map click
                address = f"{specific_area}, {district}, {country}" if specific_area.strip() else f"{district}, {country}"

            st.success(f"📍 Final Location: {address}")

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
                r = requests.get(api_url, headers=headers)
                sha = r.json().get("sha")
                content = b64encode(updated_df.to_csv(index=False).encode()).decode()
                data = {"message": "Update requests.csv via Streamlit", "content": content, "sha": sha}
                result = requests.put(api_url, json=data, headers=headers)
                return result.status_code in [200, 201]

            # ---------------- WHATSAPP ALERT ----------------
            def send_whatsapp_alert(emp_name, dept, status, supplies, location, notes):
                try:
                    account_sid = st.secrets["TWILIO_SID"]
                    auth_token = st.secrets["TWILIO_AUTH"]
                    from_whatsapp = st.secrets["TWILIO_WHATSAPP_FROM"]
                    admin_group_numbers = [num.strip() for num in st.secrets["ADMIN_GROUP_NUMBERS"].split(",")]
                    client = Client(account_sid, auth_token)
                    message_body = (
                        f"🚨 *New Emergency Request Submitted!*\n\n"
                        f"👤 Name: {emp_name}\n"
                        f"🏢 Department: {dept}\n"
                        f"📍 Location: {location}\n"
                        f"📊 Status: {status}\n"
                        f"📦 Supplies Needed: {supplies}\n"
                        f"📝 Notes: {notes}\n\n"
                        f"Please check the admin dashboard for details."
                    )
                    for admin in admin_group_numbers:
                        client.messages.create(from_=from_whatsapp, to=admin, body=message_body)
                    st.info("📲 WhatsApp alert sent to admin group.")
                except Exception as e:
                    st.warning(f"⚠️ Failed to send WhatsApp alert: {e}")

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
                    try:
                        data = get_github_file()
                    except Exception:
                        data = pd.DataFrame(columns=[
                            'Timestamp', 'Employee ID', 'Name', 'Department', 'Phone Number', 'Email',
                            'Location', 'Status', 'Supplies Needed', 'Additional Notes', 'Request Status'
                        ])

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

                    if push_to_github(updated_data):
                        st.success("✅ Your emergency request has been submitted and synced to GitHub.")
                        st.balloons()
                        send_whatsapp_alert(name, dept, status, ", ".join(supplies), address, notes)
                    else:
                        st.error("❌ Failed to update GitHub file. Please check your token permissions.")
        else:
            st.warning("❌ Employee ID not found. Please check again.")
    # ---------------- MOCK REQUEST GENERATOR ----------------
    st.markdown("---")
    st.subheader("🧪 Mock Data Generation (Testing Only)")

    def generate_mock_requests(n=40):
        import random, time
        from datetime import datetime

        try:
            data = get_github_file()
        except Exception:
            data = pd.DataFrame(columns=[
                'Timestamp', 'Employee ID', 'Name', 'Department', 'Phone Number', 'Email',
                'Location', 'Status', 'Supplies Needed', 'Additional Notes', 'Request Status'
            ])

        departments = ["HR", "IT", "Logistics", "Operations", "Finance"]
        statuses = ["Safe", "Evacuated", "In Need of Help"]
        supplies_list = [
            ["Food", "Water"],
            ["Medical Kit", "Blanket"],
            ["Hygiene Kit", "Baby Supplies"],
            ["Water", "Blanket"]
        ]
        locations = [
            "Kuala Lumpur, Malaysia",
            "Selangor, Malaysia",
            "Johor Bahru, Malaysia",
            "Penang, Malaysia",
            "Sabah, Malaysia"
        ]

        new_entries = []
        for i in range(n):
            emp_id = f"EMP{1000 + i}"
            name = f"Employee {i+1}"
            dept = random.choice(departments)
            phone = f"+6011{random.randint(10000000, 99999999)}"
            email = f"employee{i+1}@example.com"
            location = random.choice(locations)
            status = random.choice(statuses)
            supplies = random.choice(supplies_list)
            notes = random.choice([
                "Need urgent assistance",
                "Safe but need food supplies",
                "Evacuated to safe zone",
                "Family stranded nearby"
            ])

            new_entry = {
                'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Employee ID': emp_id,
                'Name': name,
                'Department': dept,
                'Phone Number': phone,
                'Email': email,
                'Location': location,
                'Status': status,
                'Supplies Needed': ", ".join(supplies),
                'Additional Notes': notes,
                'Request Status': "Pending"
            }
            new_entries.append(new_entry)

            # 🔔 Send WhatsApp alert
            send_whatsapp_alert(name, dept, status, ", ".join(supplies), location, notes)
            time.sleep(1.5)  # to prevent Twilio spam limit

        mock_df = pd.DataFrame(new_entries)
        updated_data = pd.concat([data, mock_df], ignore_index=True)

        if push_to_github(updated_data):
            st.success(f"✅ Successfully added {n} mock requests and sent WhatsApp alerts.")
        else:
            st.error("❌ Failed to update GitHub file.")

    if st.button("Generate 40 Mock Requests"):
        with st.spinner("Generating 40 mock requests and sending WhatsApp alerts..."):
            generate_mock_requests(40)

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

    st.subheader("🧊 3D Interactive Chart: Supplies vs Status")
    if not data.empty:
        plot_data = data.copy()
        plot_data['Supplies Needed'] = plot_data['Supplies Needed'].fillna('None')
        fig = px.scatter_3d(plot_data, x='Status', y='Supplies Needed', z='Request Status',
                            color='Status', symbol='Request Status')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough data to display 3D chart.")
