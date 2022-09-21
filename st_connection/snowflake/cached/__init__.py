import streamlit as st
import st_connection.snowflake
from st_connection.snowflake.cached.snowflake_connection import cached

# Placing in st.connection for convenience
# Instantiate a connection with:
#    conn = st.connection.snowflake.cached.connection.login()
# or
#    conn = st.connection.snowflake.cached.connection.singleton()
# Instantiate a session with:
#    session = st.connection.snowflake.cached.session.login()
# or
#    session = st.connection.snowflake.cached.session.singleton()
st.connection.snowflake.cached = cached.session
st.connection.snowflake_connection.cached = cached.connection
