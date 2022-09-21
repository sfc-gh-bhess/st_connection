from distutils.dep_util import newer_pairwise
import streamlit as st
import snowflake.connector
from snowflake.connector import SnowflakeConnection
from snowflake.snowpark import ( Session )
from snowflake.snowpark.session import _add_session
from snowflake.snowpark._internal.utils import ( get_application_name, get_version )
from snowflake.snowpark._internal.server_connection import ( 
    ServerConnection, 
    PARAM_APPLICATION, 
    PARAM_INTERNAL_APPLICATION_NAME, 
    PARAM_INTERNAL_APPLICATION_VERSION 
)
from typing import Optional, List, Any
import json
import datetime


STSTATE_SNOWFLAKE_SESSION="STSNOW_SESSION"
STSTATE_SNOWFLAKE_CONNECTION="STSNOW_CONNECTION"
STSTATE_SNOWFLAKE_RESULTS="STSNOW_RESULTS"

###
# Snowflake Connections and Cursors
#
# We will create a new Snowflake session for each web session so that they don't collide
###

# Snowflake DictCursor that will cache its results in Streamlit session_state
#   You can control the TTL of the cache by setting `cachettl` when calling execute().
#     The TTL is defined in number of seconds to cache. The default is 3600 seconds.
class SnowCacheCursor(snowflake.connector.cursor.DictCursor):
    def __init__(self, connection: snowflake.connector.SnowflakeConnection):
        super().__init__(connection)
        self.snowconn_session_id = connection.session_id
        self.cachekey = None

    CACHEKEY_TTL = "ttl"
    CACHEDEFAULT_TTL = 3600

    def set_default_ttl(self, ttl: int):
        self.CACHEDEFAULT_TTL = ttl
        return self
    
    def get_default_ttl(self):
        return self.CACHEDEFAULT_TTL

    def cacheLookup(self, keys: List[str]):
        c = st.session_state
        for idx in range(len(keys)):
            if keys[idx] in c:
                c = c[keys[idx]]
            else:
                return None
        if datetime.datetime.now() > c["expires"]:
            self.cacheClear(keys)
            return None
        return c["cursor"]

    def cacheClear(self, keys: List[str]):
        lastc = None
        lastk = None
        c = st.session_state
        for idx in range(len(keys)):
            if keys[idx] in c:
                lastc = c
                lastk = keys[idx]
                c = c[keys[idx]]
            else:
                return False
        del lastc[lastk]
        return True

    def clearCacheTtls(self):
        now = datetime.datetime.now()
        if STSTATE_SNOWFLAKE_RESULTS not in st.session_state:
            return
        if self.snowconn_session_id not in st.session_state[STSTATE_SNOWFLAKE_RESULTS]:
            return
        stale = []
        for k in st.session_state[STSTATE_SNOWFLAKE_RESULTS][self.snowconn_session_id].keys():
            v = st.session_state[STSTATE_SNOWFLAKE_RESULTS][self.snowconn_session_id][k]
            if "expires" in v:
                if v["expires"] < now:
                    stale.append(k)
        for k in stale:
            del st.session_state[STSTATE_SNOWFLAKE_RESULTS][self.snowconn_session_id][k]

    def cache(self, keys: List[str], res: Any, ttl: int):
        self.clearCacheTtls()
        if (ttl < 1):
            return
        c = st.session_state
        for idx in range(len(keys)):
            if keys[idx] not in c:
                c[keys[idx]] = {}
            c = c[keys[idx]]
        c["cursor"] = res
        c["expires"] = datetime.datetime.now() + datetime.timedelta(seconds=ttl)

    def execute(self, *args, **kwargs):
        tcachekey = hash(json.dumps(args) + "||" + json.dumps(kwargs))
        keys = [STSTATE_SNOWFLAKE_RESULTS, self.snowconn_session_id, tcachekey]
        # check cache and return
        res = self.cacheLookup(keys)
        if res is not None:
            res._results = None
            return res
        ttl = self.get_default_ttl()
        if self.CACHEKEY_TTL in kwargs:
            ttl = int(kwargs[self.CACHEKEY_TTL])
            del kwargs[self.CACHEKEY_TTL]
        # If this cursor was cached for some other query, create a new cursor and return the results from that
        if self.cachekey is not None:
            res = self.connection.cursor().execute(*args, **kwargs)
        else:
            self.cachekey = tcachekey
            res = super().execute(*args, **kwargs)
        self.cache(keys, res, ttl)
        return res
    
# Snowflake Connection that will cache itself in Streamlit session_state on connect
#   On close, will clear cached cursor results
class SnowCacheConnection(snowflake.connector.connection.SnowflakeConnection):
    CACHEKEY_TTL = "ttl"
    CACHEDEFAULT_TTL = 0
    default_ttl = CACHEDEFAULT_TTL

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    # def cache(self):
    #     st.session_state[STSTATE_SNOWFLAKE_CONNECTION] = self

    def clearCache(self):
        sid = self.session_id
        # if STSTATE_SNOWFLAKE_CONNECTION in st.session_state:
        #     del st.session_state[STSTATE_SNOWFLAKE_CONNECTION]
        if STSTATE_SNOWFLAKE_RESULTS in st.session_state:
            if sid in st.session_state[STSTATE_SNOWFLAKE_RESULTS]:
                del st.session_state[STSTATE_SNOWFLAKE_RESULTS][sid]

    def connect(self, *args, **kwargs):
        if self.CACHEKEY_TTL in kwargs:
            self.default_ttl = kwargs[self.CACHEKEY_TTL]
            del kwargs[self.CACHEKEY_TTL]
        super().connect(*args, **kwargs)
        # self.cache()

    def close(self, *args, **kwargs):
        self.clearCache()
        super().close(*args, **kwargs)

    # Always return a SnowCacheCursor
    def cursor(self, *args, **kwargs):
        if self.default_ttl < 1:
            return super().cursor(snowflake.connector.cursor.DictCursor)
        return super().cursor(SnowCacheCursor).set_default_ttl(self.default_ttl)

from typing import Dict, Union, Set
from snowflake.snowpark._internal.telemetry import TelemetryClient
from snowflake.snowpark.query_history import QueryHistory

# Snowpark Python Session Builder
class SnowCacheServerConnection(ServerConnection):
    def __init__(
        self,
        options: Dict[str, Union[int, str]],
        conn: Optional[SnowflakeConnection] = None,
    ) -> None:
        self._lower_case_parameters = {k.lower(): v for k, v in options.items()}
        self._add_application_name()
        self._conn = conn if conn else SnowCacheConnection(**self._lower_case_parameters)
        if "password" in self._lower_case_parameters:
            self._lower_case_parameters["password"] = None
        self._cursor = self._conn.cursor()
        self._telemetry_client = TelemetryClient(self._conn)
        self._query_listener: Set[QueryHistory] = set()
        # The session in this case refers to a Snowflake session, not a
        # Snowpark session
        self._telemetry_client.send_session_created_telemetry(not bool(conn))

class SnowCacheSessionBuilder(Session.SessionBuilder):
    def _create_internal(self, conn: Optional[SnowflakeConnection] = None) -> "Session":
        new_session = Session(
            SnowCacheServerConnection({}, conn) if conn else SnowCacheServerConnection(self._options)
        )
        if "password" in self._options:
            self._options["password"] = None
        _add_session(new_session)
        return new_session
session_builder = SnowCacheSessionBuilder()




