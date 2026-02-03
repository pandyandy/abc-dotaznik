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

def save_data(changed_data):
    keboola = get_keboola_client()
    return keboola.write_table(
        table_id='out.c-ABC.ABC_VERSION',
        df=changed_data,
        is_incremental=True
    )

def delete_data(version_id_to_delete):
    keboola = get_keboola_client()
    
    # Priamy SQL DELETE na Snowflake
    delete_query = f"DELETE FROM KEBOOLA_47.\"out.c-ABC\".ABC_VERSION WHERE VERSION_ID = '{version_id_to_delete}'"
    
    st.write(f"SQL Query: {delete_query}")
    
    result = keboola.snowflake_execute_query(
        session=get_snowflake_connection(),
        query=delete_query
    )
    
    st.write(f"Výsledok DELETE: {result}")

def write_and_read_data() -> pd.DataFrame:
    try:
        # Vytvor DataFrame s novými dátami
        # new_data = pd.DataFrame({
        #     'VERSION_ID': [3],
        #     'VERSION': ['Test_v1']
        # })
        
        # Zapis dáta
        # save_data(new_data)
        # st.success("Dáta boli zapísané!")
        
        # Vymaž riadok kde VERSION_ID = 3
        delete_data(3)
        st.success("Riadok s VERSION_ID=3 bol vymazaný!")
        
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