import streamlit as st
import st_connection.connection
from snowflake.connector import SnowflakeConnection, connect
from snowflake.snowpark import Session

# Implementation that creates Snowflake Connector connections
class SnowflakeConnectionImpl(st.connection.AbstractConnection):
    def __init__(self):
        pass

    def is_open(self, conn: SnowflakeConnection) -> bool:
        return not conn.is_closed()

    def connect(self, params) -> SnowflakeConnection:
        return connect(**params)
    
    def close(self, conn: SnowflakeConnection):
        conn.close()
    
    def ST_KEY(self):
        return 'ST_SNOW_CONN'
    
    def default_form_options(self):
        return {'account': '', 'user': '', 'password': None}

# Implementation that creates Snowflake Snowpark sessions
class SnowflakeSessionImpl(st.connection.AbstractConnection):
    def __init__(self):
        pass

    def is_open(self, conn: Session) -> bool:
        return not conn._conn._conn.is_closed()
    
    def connect(self, params) -> Session:
        return Session.builder.configs(params).create()
    
    def close(self, conn: Session):
        conn.close()

    def ST_KEY(self):
        return 'ST_SNOW_SESS'
    
    def default_form_options(self):
        return {'account': '', 'user': '', 'password': None}

class snowflake:
    connection = st.connection.connection(SnowflakeConnectionImpl())
    session = st.connection.connection(SnowflakeSessionImpl())
