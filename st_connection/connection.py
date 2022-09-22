from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Type
import streamlit as st

# Abstract base class for connections
# You only need to override the is_open, connect, and close methods
# The ST_KEY is the key in st.session_state that a login connection is cached.
# The default_form_options() and default_options() are the defaults when those
#   are not supplied to the login form.
class AbstractConnection(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def is_open(self, conn) -> bool:
        pass

    @abstractmethod
    def connect(self, params):
        pass

    @abstractmethod
    def close(self, conn):
        pass

    def default_form_options(self):
        return {}

    def default_options(self):
        return {}

    def ST_KEY(self):
        return 'ST_CONN'

    ST_ERROR = 'ERR_ST_CONN'
    def connect_and_cache(self, params):
        try:
            if self.ST_ERROR in st.session_state:
                del st.session_state[self.ST_ERROR]
            st.session_state[self.ST_KEY()] = self.connect(params)
        except:
            st.session_state[self.ST_ERROR] = "Error connecting. Please try again."

    def close_and_clear(self, conn):
        self.close(conn)
        del st.session_state[self.ST_KEY()]

# Helper function that will call the callback, but will also clear the items from st.session_state (for safety)
def _callback_and_clear(callback, prefix, options):
    stcreds = {key:val for key,val in st.session_state.items() if key.startswith(prefix)}
    for k,v in stcreds.items():
        if v != "":
            options[k[len(prefix):]] = v
        del st.session_state[k]
    callback(options)

# Internal class that does all the work.
# The two main methods to know are singleton() and login()
T = TypeVar('T', bound=AbstractConnection)
class _connection:
    def __init__(self, impl: AbstractConnection):
        self._connection_impl = impl

    class ConnectionWrapper:
        def __init__(self, impl: AbstractConnection):
            self._connection = None
            self._connection_impl = impl
        
        def get_connection(self, params):
            if not self._validate_connection():
                self._connection = self._connection_impl.connect(params)
            return self._connection
        
        def _validate_connection(self) -> bool:
            if self._connection is None:
                return False
            return self._connection_impl.is_open(self._connection)

    def singleton(self, params):
        # Add the impl_hash to allow multiple types of connections in the same app
        @st.experimental_singleton
        def get_connection(params, impl_hash):
            return self.ConnectionWrapper(self._connection_impl)
        
        return get_connection(params, self._connection_impl.__hash__()).get_connection(params)

    def _login_form(self, form_options, options, form_title):
        if self._connection_impl.ST_ERROR in st.session_state:
            st.warning(st.session_state[self._connection_impl.ST_ERROR])
        ST_KEY = self._connection_impl.ST_KEY()
        if ST_KEY in st.session_state:
            if self._connection_impl.is_open(st.session_state[ST_KEY]):
                st.sidebar.button("Disconnect", on_click=self._connection_impl.close_and_clear, args=(st.session_state[ST_KEY],), key=f"Disconnect_{ST_KEY}")
                return st.session_state[ST_KEY]
            else:
                del st.session_state[ST_KEY]
        ST_FORM_KEY = f'{ST_KEY}_FORM'
        with st.form(form_title):
            for k,v in form_options.items():
                st.text_input(k.capitalize(), value="" if v is None else v, key=f"{ST_FORM_KEY}{k}", type="password" if v is None else "default")
            st.form_submit_button("Connect", on_click=_callback_and_clear, args=(self._connection_impl.connect_and_cache, ST_FORM_KEY, options))
        st.stop()

    def login(self, form_options = None, options = None, form_title = "Credentials"):
        if not form_options:
            form_options = self._connection_impl.default_form_options()
        if not options:
            options = self._connection_impl.default_options()
        return self._login_form(form_options, options, form_title)

class connection:
    AbstractConnection = AbstractConnection
    connection = _connection
