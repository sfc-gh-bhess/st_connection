from st_connection.snowflake.cached.cached import SnowCacheConnection, session_builder
import streamlit as st
from st_connection.snowflake import snowflake_connection
import snowflake.connector
from snowflake.snowpark import Session

class SnowflakeCachedConnectionImpl(snowflake_connection.SnowflakeConnectionImpl):
    def connect(self, params) -> snowflake.connector.SnowflakeConnection:
        return SnowCacheConnection(**params)

class SnowflakeCachedSessionImpl(snowflake_connection.SnowflakeSessionImpl):
    def connect(self, params) -> Session:
        return session_builder.configs(params).create()


class cached:
    connection = st.connection.connection(SnowflakeCachedConnectionImpl())
    session = st.connection.connection(SnowflakeCachedSessionImpl())

