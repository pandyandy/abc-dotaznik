# ...existing code...
import streamlit as st
from keboola_streamlit import KeboolaStreamlit
import pandas as pd

URL = st.secrets.get("KEBOOLA_URL")
TOKEN = st.secrets.get("STORAGE_API_TOKEN")

st.set_page_config(layout="wide")
st.title('Test Keboola Snowflake - Zapis a čítanie')

def get_keboola_client():
    URL = st.secrets["KEBOOLA_URL"]
    TOKEN = st.secrets["STORAGE_API_TOKEN"]
    return KeboolaStreamlit(root_url=URL, token=TOKEN)

def get_snowflake_connection():
    if 'snowflake_session' not in st.session_state:
        st.session_state['snowflake_session'] = get_keboola_client().snowflake_create_session_object()
    return st.session_state['snowflake_session']    

def write_and_read_data() -> pd.DataFrame:
    try:
        # Zapis nového riadku
        write_query = """
        INSERT INTO KEBOOLA_47."out.c-ABC".ABC_VERSION (VERSION_ID, VERSION)
        VALUES (3, 'Test_v1')
        """
        get_keboola_client().snowflake_execute_query(
            session=get_snowflake_connection(),
            query=write_query
        )
        st.success("Dáta boli zapísané!")
        
        # Načítaj všetky dáta
        read_query = "SELECT * FROM KEBOOLA_47.\"out.c-ABC\".ABC_VERSION"
        data = get_keboola_client().snowflake_execute_query(
            session=get_snowflake_connection(),
            query=read_query
        )
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Chyba: {e}")
        return pd.DataFrame()

# Načítaj a zobraz dáta
df = write_and_read_data()
st.dataframe(df)
# ...existing code...