# Snowflake Connection Tools

This Python package helps users connect from Streamlit to data sources
that require connections. It provides a framework and abstract classes
to support a number of approaches for various use cases, and has some
best practices built in.

This package is intended to be extended by data source providers to 
simplify creation, caching, and management of persistent connections
necessary for various data sources, such as databases.

An implementation for Snowflake is included in tree.

## Installation 

You can install directly from github with this command:
```
pip install git+https://github.com/sfc-gh-bhess/st_connection.git
```
Note that python 3.8 is the only supported python version currently.

To install directly from github via pipenv, use:
```
pipenv install git+https://github.com/sfc-gh-bhess/st_connection.git#egg=st_connection
```


## Description

Streamlit is a powerful data and visualization tool, but to do data analysis
we need... DATA! Many data sources require making persistent connections, and
a best practice in Streamlit is to cache those connections.

There are a few different scenarios about how a Streamlit app will connect
to a data source (such as Snowflake):
1. A single, global connection to be used by all Streamlit users
2. Each Streamlit user provides their own data source credentials and the
connection is unique to them.

This package provides both ways to connect, with some specific nuances for 
each case.
1. For a global connection, the credentials will be static (e.g., in a credentials
file, or in the `st.secrets` construct). As such, we can automatically connect,
and if there's a need to reconnect, we have the credentials and can do that
automatically, as well. In this way, the user will never error by using a stale/closed
connection.
2. For the case where users provide their own credentials, we would want to 
present a login form to capture the necessary details to connect to the data source
(e.g., account, username, password, etc) and not present any more of the 
Streamlit app until those details were entered. Once the details are entered,
the connection to the data source should be made, and the credentials should be 
deleted (so as to minimize any security risk). While connected, there should 
be a logout button to end the session. However, it may come to pass that the 
connection may get closed (e.g., a failure, an idle timeout, etc). In that case,
we would want to act as if the user never logged in, namely we want to present
the login screen and gate the app until successfully logged in.

This package provides functions to support both scenarios.

In `st_connection.connection` we define an API that developers can use to 
create connections to other databases, and this package will handle the
singleton and login use cases.

## Extensible API

In the `connection.py` file we define an abstract class, `AbstractConnection`.
To create a connection for a data source, you just need to create a class
that derives from `AbstractConnection` and implement three methods:

```
class AbstractConnection(ABC):
    @abstractmethod
    def is_open(self, conn) -> bool:
        pass

    @abstractmethod
    def connect(self, params):
        pass

    @abstractmethod
    def close(self, conn):
        pass
```

* The `connect(params)` method takes a dictionary of parameters, connects to 
the data source, and returns the connection object.
* The `is_open(conn)` method will return a Boolean indicating if the 
connection is still open. The argument will be the connection object itself.
* The `close(conn)` method closes the connection.

There are other optional methods to override:
* An `ST_KEY()` method that returns a key to use when storing the connection
object in `st.session_state`.
* A `default_form_options()` method that returns a dictionary of default options
to use in the login form if none is supplied.
* A `default_options()` method that returns a dictionary of default options
that are not used in the login form but are used to connect if none is supplied.

### Making your connector available

Once you have created (and tested) your connector, place an instantiation
of that object in `st.connection.CONNECTORNAME`. For example:
```
st.connection.myconnector = st.connection.connection(MyConnectorImpl())
```

For example, the Snowflake connector created in this package is available
at `st.connection.snowflake` for a Snowpark Session (and 
`st.connection.snowflake_connection` for a Snowflake Connector connection).

## Singleton Connections
To support making a single global connection to the data source we can use the
`singleton()` method.

These connections will be shared across all Streamlit sessions. They will
test if the connection is closed (e.g., due to inactivity), and if so
they will automatically reconnect, so the users will never use a stale/closed
connection.

The pattern for all data sources would be (using CONNECTOR as a generic connector):
```
import json
import streamlit as st
import st_connection
import st_connection.CONNECTOR

creds = json.load(open("/path/to/json/credentials.json, "r"))
session = st.connection.CONNECTOR.singleton(creds)
```

At that point you can use the session just like you would otherwise. If
the connection gets severed, the session will automatically be recreated.

You can also pair this with `st.secrets`, of course:
```
import streamlit as st
import st_connection
import st_connection.CONNECTOR

session = st.connection.CONNECTOR.singleton(st.secrets[SECRETS_KEY])
```

### Snowpark Python
To connect to Snowflake using the Snowpark Python package, you would use
`st.connection.snowflake.singleton()`:

```
import json
import streamlit as st
import st_connection
import st_connection.snowflake

creds = json.load(open("/path/to/json/credentials.json, "r"))
session = st.connection.snowflake.singleton(creds)
```

You can pass any parameters to `st.connection.snowflake.singleton()` 
that you would normally pass to `snowflake.snowpark.Session.builder.configs()`.

At this point you will have a Snowpark `Session` object and can do normal Snowpark
operations with it:

```
session.table("mytable").select......
```

### Snowflake Python Connector
To connect to Snowflake using the Snowflake Python Connector package, you would use
`st.connection.snowflake_connection.singleton()`:

```
import json
import streamlit as st
import st_connection
import st_connection.snowflake_connection

creds = json.load(open("/path/to/json/credentials.json, "r"))
session = st.connection.snowflake_connection.singleton(creds)
```

You can pass any parameters to `st.connection.snowflake_connection.singleton()` 
that you would normally pass to `snowflake.connector.connect()`, but in 
a dictionary instead of in kwargs fashion.

At this point you will have a Snowflake Connector `SnowflakeConnection` object and can 
do normal Snowflake connector operations with it:

```
session.cursor().execute(......)
```

## Login Form
To support making a connection per user to a data source we can use the
`login()` method.

These connections will not be shared across Streamlit sessions, but will
be unique to each Streamlit user. They will present a login form, and 
once the details have been entered, a connection will be made. That connection
will be cached in the user's session state for efficient use.

These connections  will test if the connection is closed (e.g., due to inactivity), 
and if so they will revert to the login screen to get the credentials from the 
user and reconnect. As such,  the users will never use a stale/closed 
connection.

Once connected, a logout button is placed in the sidebar.

Anything below the call to `login()` will not be executed until the user logs in.
In the logic for `login()` if the user is not logged in, `st.stop()` is called.

The pattern for all data sources would be (using CONNECTOR as a generic connector):
```
import json
import streamlit as st
import st_connection
import st_connection.CONNECTOR

session = st.connection.CONNECTOR.login()
```

The login function takes 3 optional arguments:
* `form_options`: a dictionary. The keys of this dictionary will become input
fields for the user to fill in (e.g, `user`). The values of the keys will be
the default value (leave `""` for no default value, use `None` to indicate that
the input is in "password" mode).
* `options`: a dictionary. These options will be passed as-is to the connection.
For example, if you wanted to set a `timezone` and not allow a user to edit that,
you could put it in `options`. If you wanted them to edit it, you would put it
in `form_options`.
* `form_title`: a string to label the form for this login.

For example:

```
import st_connection
import st_connection.snowflake

## Things above here will be run before (and after) you log in.

session = st.connection.snowflake.login({'user': '', 'password': None, 'database': 'PROJECT_DB'}, {'account': 'XXX', 'warehouse': 'PROJECT_WH'}, 'Snowflake Login')

## Nothing below here will be run until you log in.
```

This would create a form to collect the `user`, `password` (which will not echo the input), 
and `database` (with a default value of `PROJECT_DB` filled in) . When the connection is made
the `account` will be hard-coded as `XXX` and the `warehouse` will be hard-coded as
`PROJECT_WH`. The form will have the name `Snowflake Login'.

### Snowpark Python
To connect to Snowflake using the Snowpark Python with a login form,
you would use `st.connection.snowflake.login()`:

```
import st_connection
import st_connection.snowflake

## Things above here will be run before (and after) you log in.

session = st.connection.snowflake.login({'user': '', 'password': None, 'database': 'PROJECT_DB'}, {'account': 'XXX', 'warehouse': 'PROJECT_WH'}, 'Snowflake Login')

## Nothing below here will be run until you log in.
```

At this point you will have a Snowpark `Session` object and can do normal Snowpark
operations with it:

```
session.table("mytable").select......
```

### Snowflake Python Connector
To connect to Snowflake using the Snowflake Python Connector with a login form,
you would use `st.connection.snowflake_connection.login()`:

```
import st_connection
import st_connection.snowflake

## Things above here will be run before (and after) you log in.

session = st.connection.snowflake_connection.login({'user': '', 'password': None, 'database': 'PROJECT_DB'}, {'account': 'XXX', 'warehouse': 'PROJECT_WH'}, 'Snowflake Login')

## Nothing below here will be run until you log in.
```

At this point you will have a Snowflake Connector `SnowflakeConnection` object and can 
do normal Snowflake connector operations with it:

```
session.cursor().execute(......)
```

## *Experimental Feature for Snowflake (Automatic Caching of Result Sets)*
It is a best practice in Streamlit to cache data that is retrieved
from a data store so as to have a more responsive application. To support
this in Snowflake, this package has a sub-package to support automatically
caching result sets without having to declare `@st.cache` or `@st.experimental_memo`.

This package provides for a new type of `SnowflakeCursor` that will automatically
cache itself based on the SQL that was executed (if it is the same SQL (and it is
in the cache) then the cached result will be returned instead of retrieving it from
Snowflake). The SQL must be identical - including parameters, etc.

All results are cached in the user's `st.session_state`. That is, there is no sharing of 
results across sessions (in global state). Even in the singleton pattern the 
results are stored in the user session. So, the Streamlit users will share connection
to the databsae, but will have their one result set cache.

To simplify the experience, this package provides a new class that derives from
`snowflake.connector.SnowflakeConnection` and `snowflake.snowpark.Session` and 
fully encapsulates the caching from the developer. A new implementation of 
a connector using these objects is included in `st.connection.session.cached`
and `st.connection.session_connection.cached`.

Not all results can (or should) be cached, and some should have a timeout after
which we will refresh the cache on next invocation. To support this, this library
does 2 things:
1. The default is not to cache at all, and, in fact, will use normal Snowflake
connections and Snowpark Sessions. 
2. You can set a time-to-live when creating the Snowflake connection or Snowpark
Session by adding an additional option, the `ttl` option. This is specified in 
number of seconds to keep the result set in cache. Once that time expires, the
result set is removed from the cache, and the next invocation of that SQL will
result in the query being processed again, with the result set then cached for
a new `ttl` seconds.

### Singleton Connections
The API is the same as above:

```
import json
import streamlit as st
import st_connection
import st_connection.snowflake

creds = json.load(open("/path/to/json/credentials.json, "r"))
session = st.connection.snowflake.cached.singleton(creds)
```

And

```
import json
import streamlit as st
import st_connection
import st_connection.snowflake_connection

creds = json.load(open("/path/to/json/credentials.json, "r"))
session = st.connection.snowflake_connection.cached.singleton(creds)
```

To add a TTL (of, say 120 seconds for example), the above code can be changed as 
follows:

```
import json
import streamlit as st
import st_connection
import st_connection.snowflake

creds = json.load(open("/path/to/json/credentials.json, "r"))
creds['ttl'] = 120
session = st.connection.snowflake.cached.singleton(creds)
```

And

```
import json
import streamlit as st
import st_connection
import st_connection.snowflake_connection

creds = json.load(open("/path/to/json/credentials.json, "r"))
creds['ttl'] = 120
session = st.connection.snowflake_connection.cached.singleton(creds)
```

### Login Form
The API is the same as above:

```
import st_connection
import st_connection.snowflake

## Things above here will be run before (and after) you log in.

session = st.connection.snowflake.login({'user': '', 'password': None, 'database': 'PROJECT_DB'}, {'account': 'XXX', 'warehouse': 'PROJECT_WH'}, 'Snowflake Login')

## Nothing below here will be run until you log in.
```

And

```
import st_connection
import st_connection.snowflake_connection

## Things above here will be run before (and after) you log in.

session = st.connection.snowflake_connection.login({'user': '', 'password': None, 'database': 'PROJECT_DB'}, {'account': 'XXX', 'warehouse': 'PROJECT_WH'}, 'Snowflake Login')

## Nothing below here will be run until you log in.
```

To add a TTL (of, say 120 seconds for example), the above code can be changed as 
follows, by adding it to the `options` dictionary:

```
import st_connection
import st_connection.snowflake

## Things above here will be run before (and after) you log in.

session = st.connection.snowflake.login({'user': '', 'password': None, 'database': 'PROJECT_DB'}, {'account': 'XXX', 'warehouse': 'PROJECT_WH', 'ttl': 120}, 'Snowflake Login')

## Nothing below here will be run until you log in.
```

And

```
import st_connection
import st_connection.snowflake_connection

## Things above here will be run before (and after) you log in.

session = st.connection.snowflake_connection.login({'user': '', 'password': None, 'database': 'PROJECT_DB'}, {'account': 'XXX', 'warehouse': 'PROJECT_WH', 'ttl': 120}, 'Snowflake Login')

## Nothing below here will be run until you log in.
```
