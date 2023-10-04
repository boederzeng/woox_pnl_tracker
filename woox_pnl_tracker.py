import streamlit as st
import requests
import hashlib
import hmac
import time
import pandas as pd

# Function to fetch orders with pagination
def fetch_all_orders(api_key, api_secret, start_t, end_t, pair):
    url = "https://api.woo.network/v1/orders"
    all_orders = []
    current_page = 1

    while True:
        params = {
            'realized_pnl': 'true',
            'status': 'COMPLETED',
            'start_t': str(start_t),
            'end_t': str(end_t),
            'page': str(current_page),
        }
        if pair and pair != "None":
            params['pair'] = pair
        sorted_params = sorted(params.items())
        normalized_params = '&'.join(f"{k}={v}" for k, v in sorted_params)
        timestamp = str(int(time.time() * 1000))
        normalized_string = f"{normalized_params}|{timestamp}"
        signature = hmac.new(api_secret.encode(), normalized_string.encode(), hashlib.sha256).hexdigest()
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'x-api-key': api_key,
            'x-api-signature': signature,
            'x-api-timestamp': timestamp,
        }
        response = requests.get(url, params=params, headers=headers)
        orders = response.json()

        if 'success' in orders and orders['success']:
            if 'rows' in orders:
                all_orders.extend(orders['rows'])

            # Pagination logic
            total = orders['meta']['total']
            records_per_page = orders['meta']['records_per_page']
            if total > current_page * records_per_page:
                current_page += 1
            else:
                break
        else:
            return None, orders.get('message', 'Unknown error')

    return all_orders, None


with open("woox_pairs.txt", "r") as f:
    woox_pairs = f.read().splitlines()

# Add a "None" option for deactivating pair filtering
woox_pairs = ["None"] + woox_pairs

# Sidebar for additional options
st.sidebar.title("Advanced Options")

# Add quick filter options
quick_filter = st.sidebar.radio("Time Filter", ["None", "Today", "Yesterday", "Current Week", "Current Month"])


if quick_filter == "None":
    start_date = st.sidebar.date_input("Start Date")
    end_date = st.sidebar.date_input("End Date")
elif quick_filter == "Today":
    end_date = pd.to_datetime("now", utc=True)  # Current date and time
    start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
elif quick_filter == "Yesterday":
    end_date = pd.to_datetime("now", utc=True)  # Current date and time
    start_date = end_date - pd.Timedelta(days=1)
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date.replace(hour=23, minute=59, second=59, microsecond=999999)
elif quick_filter == "Current Week":
    end_date = pd.to_datetime("now", utc=True)  # Current date and time
    start_date = end_date - pd.Timedelta(days=end_date.weekday())  # Start of the week
elif quick_filter == "Current Month":
    end_date = pd.to_datetime("now", utc=True)  # Current date and time
    start_date = end_date.replace(day=1)  # Start of the month

# Convert selected start and end dates to timestamps
start_t = int(pd.Timestamp(f"{start_date} 00:00:00").timestamp() * 1000)
end_t = int(pd.Timestamp(f"{end_date} 23:59:59").timestamp() * 1000)

# Auto-refresh settings
enable_auto_refresh = st.sidebar.checkbox("Enable Auto-Refresh", value=True)
refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 5, 300, 60)  # from 5 to 60 seconds, default 10 seconds



# Pair filter
selected_pair = st.sidebar.selectbox("Select Trading Pair", woox_pairs)  # or use multiselect for multiple selections


# Streamlit UI
st.title("WooX PnL Tracker")

# Inputs for API key, API secret, and date range
api_key = st.text_input("API Key", type="password")
api_secret = st.text_input("API Secret", type="password")

if 'fetch_orders' not in st.session_state:
    st.session_state.fetch_orders = True  # Set to True to fetch orders initially


# Button to fetch orders
if st.button("Fetch Orders"):
    st.session_state.fetch_orders = True
    if not api_key or not api_secret:
        st.warning("Please provide both API Key and API Secret.")
    else:
        all_orders, error_message = fetch_all_orders(api_key, api_secret, start_t, end_t, selected_pair)

        if all_orders:
            # Convert and display as before
            df = pd.DataFrame(all_orders)
            df['created_time'] = pd.to_datetime(df['created_time'].astype(float), unit='s')
            df['updated_time'] = pd.to_datetime(df['updated_time'].astype(float), unit='s')
            df['created_date'] = df['created_time'].dt.date  # Extract just the date part

            # Ensure 'realized_pnl' is float and check for missing values
            df['realized_pnl'] = df['realized_pnl'].astype(float)
            df['realized_pnl'].fillna(0, inplace=True)

            # Reverse the DataFrame
            df_reversed = df.iloc[::-1].copy()

            if selected_pair != "None":
                df = df[df['symbol'] == selected_pair]
                df_reversed = df_reversed[df_reversed['symbol'] == selected_pair]

            # Calculate the reverse cumulative sum of realized_pnl
            df_reversed['reverse_cumulative_pnl'] = df_reversed['realized_pnl'].cumsum()


            with st.expander("Click to view fetched orders"):
                st.write("Orders fetched successfully.")
                st.write(df)

            # Sum up the realized P&L for all fetched orders
            total_realized_pnl = df['realized_pnl'].sum()

            # Display the summed up realized P&L
            st.write(f"Total Realized P&L: {total_realized_pnl}")

            # Plot the daily P&L
            st.subheader("Reverse Cumulative Realized P&L Over Time")
            st.line_chart(df_reversed.set_index('created_time')['reverse_cumulative_pnl'])

            if enable_auto_refresh:
                st.write(f"Refreshing in {refresh_interval} seconds...")
                time.sleep(refresh_interval)
                st.session_state.fetch_orders = True  # Set it to True to simulate clicking "Fetch Orders"
                st.rerun()


        else:
            st.warning(f"Failed to fetch orders: {error_message}")



