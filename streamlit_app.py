import streamlit as st
import pandas as pd
import numpy as np
import re
import os
from collections import defaultdict
from datetime import datetime
#from keboola_streamlit import KeboolaStreamlit
from kbcstorage.client import Client

st.set_page_config(layout="wide")

# ==================== KEBOOLA CONFIGURATION ====================
KEBOOLA_URL = os.environ.get("KEBOOLA_URL") or st.secrets.get("KEBOOLA_URL")
STORAGE_TOKEN = os.environ.get("STORAGE_API_TOKEN") or st.secrets.get("STORAGE_API_TOKEN")

# Keboola Table IDs (mapping)
TABLES = {
    'trans_data': 'out.c-ABC.ABC_FORM_VALIDATION_DATA',
    'fte_data': 'out.c-ABC.ABC_FORM_FTE',
    'cc_user': 'out.c-ABC.ABC_FORM_CC_USER',
    'saved_forms': 'out.c-ABC.ABC_FORM_ABC',
    'saved_bs': 'out.c-ABC.ABC_FORM_BS',
    'bl_order': 'out.c-ABC.ABC_FORM_BL_MAP',
    'gpm_order': 'out.c-ABC.ABC_FORM_GPM_MAP',
    'prod_mask_order': 'out.c-ABC.ABC_FORM_PROD_MAP',
    'channel_mask_order': 'out.c-ABC.ABC_FORM_CHANNEL_MAP',
    'version': 'out.c-ABC.ABC_VERSION',
    'cc_desc': 'out.c-ABC.ABC_FORM_CC_DESC',
    'trx_count': 'out.c-ABC.ABC_CALC_TRANSACTIONS'
}

# CSV Settings - UTF-8 s čiarkou a bodkočiarkou
CSV_ENCODING = 'utf-8'
CSV_SEPARATOR = ';'
CSV_DECIMAL = ','

# ==================== KEBOOLA CLIENT INITIALIZATION ====================
@st.cache_resource
def init_keboola_client():
    """Inicializácia a cachovanie Keboola Storage klienta"""
    try:
        client = Client(KEBOOLA_URL, STORAGE_TOKEN)
        return client
    except Exception as e:
        st.error(f"❌ Chyba pri inicializácii Keboola klienta: {e}")
        return None

client = init_keboola_client()

# ==================== KEBOOLA DATA LOADING ====================
def load_table_from_keboola(table_id):
    """Načítanie tabuľky z Keboola Storage"""
    if client is None:
        st.error("❌ Keboola klient nie je inicializovaný")
        return None
    
    try:
        # Export table to CSV
        client.tables.export_to_file(table_id, '.')
        
        # The file is saved with the table name
        table_name = table_id.split('.')[-1]
        file_path = f"{table_name}"
        
        # Read the CSV file - nechajme na nativne spravanie (Keboola má svoje nativne nastavenie)
        df = pd.read_csv(file_path)
        
        # Konvertuj všetky numerické stĺpce - nahradí čiarky bodkami
        df = convert_numeric_columns(df)
        
        # Clean up the file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None
      
@st.cache_data(ttl=300)
def load_data():
    """Načítanie všetkých potrebných dát s optimalizáciou verzií"""
    try:
        # trans_data - filtruj iba aktuálnu verziu
        trans_data = load_table_from_keboola(TABLES['trans_data'])
        if trans_data is not None and 'version' in trans_data.columns:
            trans_data = trans_data[trans_data['version'] == 'act'].copy()
        
        fte_data = load_table_from_keboola(TABLES['fte_data'])
        cc_user = load_table_from_keboola(TABLES['cc_user'])
        
        # saved_forms - filtruj verzie act a prev
        saved_forms = load_table_from_keboola(TABLES['saved_forms'])
        if saved_forms is not None and 'version' in saved_forms.columns:
            saved_forms = saved_forms[saved_forms['version'].isin(['act', 'prev'])].copy()
        
        # saved_bs - filtruj verzie act a prev
        saved_bs = load_table_from_keboola(TABLES['saved_bs'])
        if saved_bs is not None and 'version' in saved_bs.columns:
            saved_bs = saved_bs[saved_bs['version'].isin(['act', 'prev'])].copy()
        else:
            saved_bs = pd.DataFrame()
        
        bl_order = load_table_from_keboola(TABLES['bl_order'])
        gpm_order = load_table_from_keboola(TABLES['gpm_order'])
        prod_mask_order = load_table_from_keboola(TABLES['prod_mask_order'])
        channel_mask_order = load_table_from_keboola(TABLES['channel_mask_order'])
        version = load_table_from_keboola(TABLES['version'])
        cc_desc = load_table_from_keboola(TABLES['cc_desc'])
        
        # trx_count - filtruj iba aktuálnu verziu
        trx_count = load_table_from_keboola(TABLES['trx_count'])
        if trx_count is not None and 'version' in trx_count.columns:
            trx_count = trx_count[trx_count['version'] == 'act'].copy()
        
        return trans_data, fte_data, cc_user, saved_forms, saved_bs, bl_order, gpm_order, prod_mask_order, channel_mask_order, version, cc_desc, trx_count
    
    except Exception as e:
        st.error(f"❌ Chyba pri načítaní dát: {e}")
        return None, None, None, None, None, None, None, None, None, None, None, None

def load_dynamic_data():
    """Načítanie dynamických dát bez cache s filtráciou verzií"""
    try:
        cc_user = load_table_from_keboola(TABLES['cc_user'])
        
        # saved_forms - filtruj verzie act a prev
        saved_forms = load_table_from_keboola(TABLES['saved_forms'])
        if saved_forms is not None and 'version' in saved_forms.columns:
            saved_forms = saved_forms[saved_forms['version'].isin(['act', 'prev'])].copy()
        
        # saved_bs - filtruj verzie act a prev
        saved_bs = load_table_from_keboola(TABLES['saved_bs'])
        if saved_bs is not None and 'version' in saved_bs.columns:
            saved_bs = saved_bs[saved_bs['version'].isin(['act', 'prev'])].copy()
        else:
            saved_bs = pd.DataFrame()
        
        return cc_user, saved_forms, saved_bs
    
    except Exception as e:
        st.error(f"❌ Chyba pri načítaní dynamických dát: {e}")
        return None, None, None

# ==================== KEBOOLA DATA SAVING ====================
def save_data_to_keboola(df, table_id, is_incremental=True):
    """Uloženie dát do Keboola Storage - konvertuje čiarky na bodky"""
    if client is None:
        st.error("❌ Keboola klient nie je inicializovaný")
        return False
    
    try:
        temp_file = f"temp_upload_{table_id.split('.')[-1]}.csv"
        
        # Vytvor kopiu pre zápis
        df_to_save = df.copy()
        
        # Konvertuj čiarky na bodky v stĺpcoch s číslami
        # (používateľ videl čiarku, ale teraz konvertujeme na bodku pre Keboolu)
        numeric_columns = ['RAT_BL', 'RAT_PROD', 'RAT_ACTIVITY', 'RAT_CHANNEL', 'RAT_TOTAL']
        for col in numeric_columns:
            if col in df_to_save.columns:
                # Stringy s čiarkami konvertuj na bodky
                df_to_save[col] = df_to_save[col].astype(str).str.replace(',', '.')
        
        # Ulož do CSV - stringy sú už prekonvertované na bodky
        # Nechajme na nativne spravanie (Keboola má svoje nativne nastavenie)
        df_to_save.to_csv(
            temp_file
        )
        
        # Nahraj do Keboola Storage (append mode)
        client.tables.load(
            table_id=table_id,
            file_path=temp_file,
            is_incremental=is_incremental
        )
        
        # Vyčisti dočasný súbor
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return True
    
    except Exception as e:
        st.error(f"❌ Chyba pri ukladaní dát do {table_id}: {e}")
        return False

# ==================== HELPER FUNCTIONS ====================

def format_number(value, decimals=2):
    """Formátuj číslo s čiarkou ako desatinným oddeľovačom"""
    if decimals == 0:
        return f"{value:.0f}"
    elif decimals == 1:
        return f"{value:.1f}".replace('.', ',')
    else:  # decimals == 2
        return f"{value:.2f}".replace('.', ',')

def parse_decimal_value(value):
    """Bezpečne konvertuj hodnotu na float, pričom nahradí čiarku bodkou"""
    if pd.isna(value) or value == '':
        return 0.0
    try:
        # Konvertuj na string a nahraď čiarku bodkou
        str_value = str(value).strip().replace(',', '.')
        return float(str_value)
    except (ValueError, TypeError):
        return 0.0

def convert_numeric_columns(df):
    """Konvertuj všetky stĺpce s čiarkami na float - len bezpečne bez zmeny textových stĺpcov"""
    df_converted = df.copy()
    
    for col in df_converted.columns:
        try:
            # Skontroluj, či stĺpec obsahuje čiarky (indikátor desatinného oddeľovača)
            if df_converted[col].dtype == 'object':
                # Skus konvertovať všetky hodnoty
                test_converted = df_converted[col].astype(str).str.contains(',', na=False)
                
                # Ak je tam nejaká čiarka, skús konvertovať celý stĺpec
                if test_converted.any():
                    try:
                        converted_series = df_converted[col].apply(lambda x: parse_decimal_value(x) if pd.notna(x) else np.nan)
                        # Skontroluj či konverzia bola úspešná (väčšina hodnôt sú čísla)
                        non_nan_count = converted_series.notna().sum()
                        if non_nan_count > 0:
                            df_converted[col] = converted_series
                    except Exception:
                        pass
        except Exception:
            pass
    
    return df_converted

def get_slovak_datetime():
    """Vráti aktuálny dátum a čas vo formáte pre Slovensko"""
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")

# Pridaj JavaScript na konverziu čiarky na bodku pri vstupe
st.markdown(
    """
    <script>
        document.addEventListener('change', function(e) {
            if (e.target.type === 'number') {
                let value = e.target.value;
                if (value.includes(',')) {
                    e.target.value = value.split(',').join('.');  // Nahrad VŠETKY čiarky bodkami
                }
            }
        });
        
        document.addEventListener('input', function(e) {
            if (e.target.type === 'number') {
                let value = e.target.value;
                if (value.includes(',')) {
                    e.target.value = value.split(',').join('.');  // Nahrad VŠETKY čiarky bodkami
                }
            }
        });
    </script>
    """,
    unsafe_allow_html=True
)

def kontrola_id():
    """Kontrola a validácia User ID"""
    USER_ID = st.text_input("Zadajte svoje User ID")
    if not USER_ID:
        st.warning("Zadajte User ID pre pokračovanie")
        return None
    elif not re.fullmatch(r"^4\d{5}$", USER_ID):
        st.warning("User ID musí začínať číslom 4 a byť presne 6 miestne.")
        return None
    else:
        return str(USER_ID).strip()

@st.cache_data
def create_hierarchy(trans_data):
    """Vytvorenie hierarchie dát"""
    hierarchy = {
        'bl_to_products': defaultdict(set),
        'product_to_trans_types': defaultdict(set),
        'trans_type_to_channels': defaultdict(set)
    }
    
    for _, row in trans_data.iterrows():
        bl = str(row['BL']).strip() if pd.notna(row['BL']) else ''
        product = str(row['PRODUCT']).strip() if pd.notna(row['PRODUCT']) else ''
        trans_type = str(row['TRANS_TYPE']).strip() if pd.notna(row['TRANS_TYPE']) else ''
        channel = str(row['CHANNEL']).strip() if pd.notna(row['CHANNEL']) else ''
        
        if bl and product and trans_type and channel:
            hierarchy['bl_to_products'][bl].add(product)
            hierarchy['product_to_trans_types'][(bl, product)].add(trans_type)
            hierarchy['trans_type_to_channels'][(bl, product, trans_type)].add(channel)
    
    return hierarchy

def get_sorted_bls(bl_order, trans_data):
    """Získanie zoradeného zoznamu BL"""
    bl_unique = pd.DataFrame({'BL': trans_data['BL'].dropna().astype(str).str.strip().unique()})
    bl_unique = bl_unique.drop_duplicates(subset=['BL'])
    
    bl_unique = bl_unique.merge(bl_order, on='BL', how='left')
    
    def make_label(row):
        bl = row['BL']
        group = str(row.get('TXT_BUS_LINE', ''))
        if str(bl).strip() == str(group).strip():
            return bl
        return f"{group} - {bl}"
    
    bl_unique['BL_LABEL'] = bl_unique.apply(make_label, axis=1)
    bl_unique['BL_ORDER'] = bl_unique.get('BL_ORDER', pd.NA)
    bl_unique = bl_unique.sort_values('BL_ORDER').reset_index(drop=True)
    
    return bl_unique

def get_sorted_gpm(gpm_order, hierarchy, bl, product):
    """Získanie zoradeného zoznamu GPM_HIER (Trans_type)"""
    trans_types = sorted(hierarchy['product_to_trans_types'].get((bl, product), set()))
    
    if gpm_order is None or gpm_order.empty:
        return trans_types
    
    gpm_order_dict = {}
    for _, row in gpm_order.iterrows():
        gpm_hier = row['GPM_HIER']
        order = row.get('GPM_ORDER', 999)
        gpm_order_dict[gpm_hier] = order
    
    trans_types = sorted(trans_types, key=lambda x: gpm_order_dict.get(x, 999))
    
    return trans_types

def get_sorted_products(prod_mask_order, hierarchy, bl):
    """Získanie zoraďaného zoznamu produktov s maskou"""
    products = sorted(hierarchy['bl_to_products'].get(bl, set()))
    
    if prod_mask_order is None or prod_mask_order.empty:
        return products
    
    prod_df = pd.DataFrame({'DOM_ABC_PRD_MASK': products})
    prod_df = prod_df.merge(prod_mask_order, on='DOM_ABC_PRD_MASK', how='left')
    prod_df['PROD_ORDER'] = pd.to_numeric(prod_df.get('PROD_ORDER', pd.NA), errors='coerce')
    prod_df = prod_df.sort_values('PROD_ORDER', na_position='last').reset_index(drop=True)
    
    return prod_df['DOM_ABC_PRD_MASK'].tolist()

def get_sorted_channels(channel_mask_order, hierarchy, bl, product, trans_type):
    """Získanie zoradeného zoznamu kanálov s maskou"""
    channels = sorted(hierarchy['trans_type_to_channels'].get((bl, product, trans_type), set()))
    
    if channel_mask_order is None or channel_mask_order.empty:
        return channels
    
    chan_df = pd.DataFrame({'CHANNEL_ABC_MASK': channels})
    chan_df = chan_df.merge(channel_mask_order, on='CHANNEL_ABC_MASK', how='left')
    chan_df['CHANNEL_ORDER'] = pd.to_numeric(chan_df.get('CHANNEL_ORDER', pd.NA), errors='coerce')
    chan_df = chan_df.sort_values('CHANNEL_ORDER', na_position='last').reset_index(drop=True)
    
    return chan_df['CHANNEL_ABC_MASK'].tolist()

def apply_product_mask(product_name, prod_mask_order):
    """Konvertuj názov produktu na masku"""
    if prod_mask_order is None or prod_mask_order.empty:
        return product_name
    mask_row = prod_mask_order[prod_mask_order['DOM_ABC_PRD_MASK'] == product_name]
    if not mask_row.empty and 'DOM_ABC_PRD' in mask_row.columns:
        return str(mask_row.iloc[0]['DOM_ABC_PRD'])
    return product_name

def remove_product_mask(masked_name, prod_mask_order):
    """Konvertuj masku späť na názov"""
    if prod_mask_order is None or prod_mask_order.empty:
        return masked_name
    mask_row = prod_mask_order[prod_mask_order['DOM_ABC_PRD'] == masked_name]
    if not mask_row.empty and 'DOM_ABC_PRD_MASK' in mask_row.columns:
        return str(mask_row.iloc[0]['DOM_ABC_PRD_MASK'])
    return masked_name

def apply_channel_mask(channel_name, channel_mask_order):
    """Konvertuj názov kanála na masku"""
    if channel_mask_order is None or channel_mask_order.empty:
        return channel_name
    mask_row = channel_mask_order[channel_mask_order['CHANNEL_ABC_MASK'] == channel_name]
    if not mask_row.empty and 'CHANNEL_ABC' in mask_row.columns:
        return str(mask_row.iloc[0]['CHANNEL_ABC'])
    return channel_name

def remove_channel_mask(masked_name, channel_mask_order):
    """Konvertuj masku kanála späť na názov"""
    if channel_mask_order is None or channel_mask_order.empty:
        return masked_name
    mask_row = channel_mask_order[channel_mask_order['CHANNEL_ABC'] == masked_name]
    if not mask_row.empty and 'CHANNEL_ABC_MASK' in mask_row.columns:
        return str(mask_row.iloc[0]['CHANNEL_ABC_MASK'])
    return masked_name

def get_form_status(CC, VERSION, saved_forms):
    """Získanie statusu formulára"""
    mask = (
        (saved_forms['CC'].astype(str).str.strip() == str(CC).strip()) &
        (saved_forms['VERSION'].astype(str).str.strip() == str(VERSION))
    )
    
    if not saved_forms[mask].empty:
        return saved_forms[mask].iloc[0].get('STATUS', '')
    return ''

def get_existing_forms_by_status(CC, VERSION, saved_forms, status_filter):
    """Získanie formulárov s určitým statusom"""
    mask = (
        (saved_forms['CC'].astype(str).str.strip() == str(CC).strip()) &
        (saved_forms['VERSION'].astype(str).str.strip() == str(VERSION)) &
        (saved_forms['STATUS'].astype(str).str.strip() == status_filter)
    )
    
    result = saved_forms[mask] if not saved_forms[mask].empty else pd.DataFrame()
    
    # Nativny format z Kebooly: čísla sú s bodkami (alebo numeric), žiadna konverzia nie je potrebná
    for col in ['RAT_BL', 'RAT_PROD', 'RAT_ACTIVITY', 'RAT_CHANNEL', 'RAT_TOTAL']:
        if col in result.columns and result[col].dtype == 'object':
            result[col] = pd.to_numeric(result[col], errors='coerce')
    
    return result

def get_existing_from_prev_version(CC, prev_version, saved_forms):
    """Získanie formulárov z predoslej verzie"""
    if not prev_version or saved_forms.empty:
        return pd.DataFrame()
    
    mask = (
        (saved_forms['CC'].astype(str).str.strip() == str(CC).strip()) &
        (saved_forms['VERSION'].astype(str).str.strip() == prev_version)
    )
    
    result = saved_forms[mask] if not saved_forms[mask].empty else pd.DataFrame()
    
    # Nativny format z Kebooly: čísla sú s bodkami (alebo numeric), žiadna konverzia nie je potrebná
    for col in ['RAT_BL', 'RAT_PROD', 'RAT_ACTIVITY', 'RAT_CHANNEL', 'RAT_TOTAL']:
        if col in result.columns and result[col].dtype == 'object':
            result[col] = pd.to_numeric(result[col], errors='coerce')
    
    return result

def get_status_hierarchy(status):
    """Vrátí numerickú hodnotu pre porovnanie statusov"""
    status_order = {'Step1': 1, 'Step2': 2, 'Step3': 3, 'Submitted': 4}
    return status_order.get(status, 0)

def get_current_status(CC, VERSION, saved_forms):
    """Zistí aktuálny najvyšší STATUS"""
    mask = (
        (saved_forms['CC'].astype(str).str.strip() == str(CC).strip()) &
        (saved_forms['VERSION'].astype(str).str.strip() == str(VERSION))
    )
    if not saved_forms[mask].empty:
        statuses = saved_forms[mask]['STATUS'].unique()
        return max(statuses, key=lambda x: get_status_hierarchy(x)) if statuses.size > 0 else ''
    return ''

def save_form_step(USER_ID, CC, VERSION, form_data, saved_forms, bl_order, status, is_first_in_step=False):
    """Uloženie jednotlivého kroku formulára do Kebooly"""
    if saved_forms is None or saved_forms.empty:
        df_saved = pd.DataFrame()
    else:
        df_saved = saved_forms.copy()
    
    # Vymaž staré riadky
    if is_first_in_step:
        mask_old = (
            (df_saved['CC'].astype(str).str.strip() == str(CC).strip()) &
            (df_saved['VERSION'].astype(str).str.strip() == str(VERSION))
        )
        df_saved = df_saved[~mask_old]
    else:
        mask_old = (
            (df_saved['CC'].astype(str).str.strip() == str(CC).strip()) &
            (df_saved['VERSION'].astype(str).str.strip() == str(VERSION)) &
            (df_saved['BL'] == form_data.get('BL', '')) &
            (df_saved['DOM_ABC_PROD'] == form_data.get('DOM_ABC_PROD', '')) &
            (df_saved['GPM_HIER'] == form_data.get('GPM_HIER', '')) &
            (df_saved['TXT_CHANNEL'] == form_data.get('TXT_CHANNEL', ''))
        )
        df_saved = df_saved[~mask_old]
    
    def convert_to_comma_decimal(val):
        """Konvertuj na čiarku pre UI formulára (používateľ vidí čiarku)"""
        if val is None or val == 0 or val == '':
            return '0'
        # val je Python float s bodkou, konvertuj na string s čiarkou pre UI
        return str(float(val)).replace('.', ',')
    
    bl = form_data.get('BL', '')
    product = form_data.get('DOM_ABC_PROD', '')
    trans_type = form_data.get('GPM_HIER', '')
    channel = form_data.get('TXT_CHANNEL', '')
    
    bl_match = bl_order[bl_order['BL'] == bl] if bl else pd.DataFrame()
    txt_bus_line = bl_match.iloc[0]['TXT_BUS_LINE'] if not bl_match.empty else ''
    subsegment = bl_match.iloc[0].get('SUBSEGMENT', '') if not bl_match.empty else ''
    
    new_row = pd.DataFrame([{
        'USER_ID': str(USER_ID).strip(),
        'CC': str(CC).strip(),
        'BL': bl,
        'TXT_BUS_LINE': txt_bus_line,
        'RAT_BL': convert_to_comma_decimal(form_data.get('RAT_BL', 0)),
        'DOM_ABC_PROD': product,
        'RAT_PROD': convert_to_comma_decimal(form_data.get('RAT_PROD', 0)),
        'GPM_HIER': trans_type,
        'RAT_ACTIVITY': convert_to_comma_decimal(form_data.get('RAT_ACTIVITY', 0)),
        'TXT_CHANNEL': channel,
        'RAT_CHANNEL': convert_to_comma_decimal(form_data.get('RAT_CHANNEL', 0)),
        'SUBSEGMENT': subsegment,
        'RAT_TOTAL': convert_to_comma_decimal(form_data.get('RAT_TOTAL', 0)),
        'VERSION': str(VERSION),
        'STATUS': status,
        'FILL_DATE': get_slovak_datetime()
    }])
    
    df_saved = pd.concat([df_saved, new_row], ignore_index=True)
    save_data_to_keboola(df_saved, TABLES['saved_forms'], is_incremental=False)

def get_form_status_bs(CC, VERSION, saved_bs):
    """Získanie statusu BS formulára"""
    if saved_bs.empty:
        return ''
    mask = (
        (saved_bs['COST_CENTER'].astype(str).str.strip() == str(CC).strip()) &
        (saved_bs['VERSION'].astype(str).str.strip() == str(VERSION))
    )
    if not saved_bs[mask].empty:
        return saved_bs[mask].iloc[0].get('STATUS', '')
    return ''

def get_existing_forms_by_status_bs(CC, VERSION, saved_bs):
    """Získanie BS formulárov"""
    if saved_bs.empty:
        return pd.DataFrame()
    mask = (
        (saved_bs['COST_CENTER'].astype(str).str.strip() == str(CC).strip()) &
        (saved_bs['VERSION'].astype(str).str.strip() == str(VERSION))
    )
    result = saved_bs[mask] if not saved_bs[mask].empty else pd.DataFrame()
    
    # Nativny format z Kebooly: čísla sú s bodkami (alebo numeric)
    if 'RAT_TOTAL' in result.columns and result['RAT_TOTAL'].dtype == 'object':
        result['RAT_TOTAL'] = pd.to_numeric(result['RAT_TOTAL'], errors='coerce')
    
    return result

def get_existing_bs_from_prev_version(CC, prev_version, saved_bs):
    """Získanie BS formulárov z predoslej verzie"""
    if saved_bs.empty or not prev_version:
        return pd.DataFrame()
    
    mask = (
        (saved_bs['COST_CENTER'].astype(str).str.strip() == str(CC).strip()) &
        (saved_bs['VERSION'].astype(str).str.strip() == prev_version)
    )
    
    result = saved_bs[mask] if not saved_bs[mask].empty else pd.DataFrame()
    
    # Nativny format z Kebooly: čísla sú s bodkami (alebo numeric)
    if 'RAT_TOTAL' in result.columns and result['RAT_TOTAL'].dtype == 'object':
        result['RAT_TOTAL'] = pd.to_numeric(result['RAT_TOTAL'], errors='coerce')
    
    return result

def save_form_bs(USER_ID, CC, VERSION, form_data, saved_bs, bl_order):
    """Uloženie BS formulára do Kebooly"""
    if saved_bs is None or saved_bs.empty:
        df_saved = pd.DataFrame()
    else:
        df_saved = saved_bs.copy()
    
    # Vymaž staré riadky
    mask_old = (
        (df_saved['COST_CENTER'].astype(str).str.strip() == str(CC).strip()) &
        (df_saved['VERSION'].astype(str).str.strip() == str(VERSION))
    )
    df_saved = df_saved[~mask_old]
    
    def convert_to_comma_decimal(val):
        """Konvertuj na čiarku pre UI formulára (používateľ vidí čiarku)"""
        if val is None or val == 0 or val == '':
            return '0'
        # val je Python float s bodkou, konvertuj na string s čiarkou pre UI
        return str(float(val)).replace('.', ',')
    
    rows_to_insert = []
    for bl, rat_total in form_data.items():
        bl_match = bl_order[bl_order['BL'] == bl] if bl else pd.DataFrame()
        txt_bus_line = bl_match.iloc[0]['TXT_BUS_LINE'] if not bl_match.empty else ''
        subsegment = bl_match.iloc[0].get('SUBSEGMENT', '') if not bl_match.empty else ''
        
        new_row = pd.DataFrame([{
            'USER_ID': str(USER_ID).strip(),
            'BL': bl,
            'TXT_BUS_LINE': txt_bus_line,
            'SUBSEGMENT': subsegment,
            'COST_CENTER': str(CC).strip(),
            'RAT_TOTAL': convert_to_comma_decimal(rat_total),
            'VERSION': str(VERSION),
            'STATUS': 'Submitted',
            'FILL_DATE': get_slovak_datetime()
        }])
        
        rows_to_insert.append(new_row)
    
    if rows_to_insert:
        df_to_insert = pd.concat(rows_to_insert, ignore_index=True)
        df_saved = pd.concat([df_saved, df_to_insert], ignore_index=True)
    
    save_data_to_keboola(df_saved, TABLES['saved_bs'], is_incremental=False)

def main():
    # Inicializuj Keboola klienta
    if client is None:
        st.error("❌ Nie je možné sa pripojiť ku Keboole. Skontrolujte secrets.")
        st.stop()
    
    # Načítaj dáta
    trans_data, fte_data, _, _, _, bl_order, gpm_order, prod_mask_order, channel_mask_order, version, cc_desc, trx_count = load_data()
    cc_user, saved_forms, saved_bs = load_dynamic_data()
    
    if trans_data is None:
        st.stop()
    
    # Dynamicky nastavuj title
    if st.session_state.get('cc') and cc_desc is not None and not cc_desc.empty and 'ID' in cc_desc.columns:
        try:
            cc_row = cc_desc[cc_desc['ID'].astype(str) == str(st.session_state.cc)]
            if not cc_row.empty:
                txt_desc = cc_row.iloc[0].get('TXT_DESCRIPTION', '')
                st.title(f"📊 ABC dotazník - {txt_desc}")
            else:
                st.title("📊 ABC dotazník")
        except Exception:
            st.title("📊 ABC dotazník")
    else:
        st.title("📊 ABC dotazník")
    
    st.markdown("---")
    
    # Inicializuj session state
    if 'step' not in st.session_state:
        st.session_state.step = 'user_input'
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'cc' not in st.session_state:
        st.session_state.cc = None
    if 'form_type' not in st.session_state:
        st.session_state.form_type = None
    if 'selected_bls' not in st.session_state:
        st.session_state.selected_bls = {}
    if 'selected_products' not in st.session_state:
        st.session_state.selected_products = {}
    if 'selected_trans_types' not in st.session_state:
        st.session_state.selected_trans_types = {}
    if 'selected_channels' not in st.session_state:
        st.session_state.selected_channels = {}
    if 'fte_data_dict' not in st.session_state:
        st.session_state.fte_data_dict = {}
    if 'current_status_snapshot' not in st.session_state:
        st.session_state.current_status_snapshot = None

    # Verzia
    max_id = version['VERSION_ID'].max()
    act_version = version.loc[version['VERSION_ID'] == max_id, 'VERSION'].iloc[0]
    prev_version = None
    if max_id > 1:
        prev_version = version.loc[version['VERSION_ID'] == max_id - 1, 'VERSION'].iloc[0]
    
    # Filtruj trans_data na aktuálnu VERSION
    trans_data = trans_data[trans_data['VERSION'].astype(str).str.strip() == str(act_version).strip()]
    
    # ==================== ETAPA 1: USER INPUT ====================
    if st.session_state.step == 'user_input':
        st.header("Zadajte vaše údaje")
        st.markdown("Pred začatím vyplnenia formulára zadajte svoje osobné číslo a nákladové stredisko.")
        
        USER_ID = kontrola_id()
        
        if USER_ID:
            st.success(f"User ID {USER_ID} je platné.")
            
            allowed_CC = cc_user.loc[cc_user['USER_ID'].astype(str) == str(USER_ID), 'CC'].unique()
            
            if len(allowed_CC) == 0:
                st.error("User ID nie je v zozname editorov ABC klúčov")
                st.stop()
            else:
                cc_options = []
                cc_display_map = {}
                
                for cc in sorted(allowed_CC):
                    cc_str = str(cc).strip()
                    txt_desc = ""
                    
                    if cc_desc is not None and not cc_desc.empty and 'ID' in cc_desc.columns:
                        try:
                            cc_row = cc_desc[cc_desc['ID'].astype(str).str.strip() == cc_str]
                            if not cc_row.empty and 'TXT_DESCRIPTION' in cc_row.columns:
                                txt_desc = str(cc_row.iloc[0]['TXT_DESCRIPTION']).strip()
                        except Exception:
                            pass
                    
                    if txt_desc:
                        display_text = f"{cc_str} - {txt_desc}"
                    else:
                        display_text = cc_str
                    
                    cc_options.append(display_text)
                    cc_display_map[display_text] = cc_str
                
                cc_selected = st.selectbox("Vyberte nákladové stredisko", cc_options)
                CC = cc_display_map.get(cc_selected, cc_selected.split(' - ')[0])
                
                if st.button("Pokračovať →", type="primary"):
                    st.session_state.user_id = USER_ID
                    st.session_state.cc = CC
                    st.session_state.current_status_snapshot = get_current_status(CC, act_version, saved_forms)
                    
                    status = get_form_status(CC, act_version, saved_forms)
                    
                    if status == '':
                        existing = get_existing_from_prev_version(CC, prev_version, saved_forms)
                    else:
                        existing = get_existing_forms_by_status(CC, act_version, saved_forms, status)
                    
                    if not existing.empty:
                        for _, row in existing.iterrows():
                            bl = row['BL'] if pd.notna(row['BL']) and row['BL'] != '' else None
                            product = row['DOM_ABC_PROD'] if pd.notna(row['DOM_ABC_PROD']) and row['DOM_ABC_PROD'] != '' else None
                            trans_type = row['GPM_HIER'] if pd.notna(row['GPM_HIER']) and row['GPM_HIER'] != '' else None
                            channel = row['TXT_CHANNEL'] if pd.notna(row['TXT_CHANNEL']) and row['TXT_CHANNEL'] != '' else None
                            
                            # Bezpečne parsuj čísla s potenciálnymi čiarkami
                            rat_bl = parse_decimal_value(row['RAT_BL'])
                            rat_prod = parse_decimal_value(row['RAT_PROD'])
                            rat_act = parse_decimal_value(row['RAT_ACTIVITY'])
                            rat_chan = parse_decimal_value(row['RAT_CHANNEL'])
                            
                            # Debug: skontroluj či sú hodnoty načítané
                            st.write(f"DEBUG: BL={bl}, RAT_BL={rat_bl}, type={type(rat_bl)}")
                            
                            if bl and rat_bl > 0:
                                st.session_state.selected_bls[bl] = rat_bl
                            
                            if bl and product and rat_prod > 0:
                                unmasked_product = remove_product_mask(product, prod_mask_order)
                                st.session_state.selected_products[(bl, unmasked_product)] = rat_prod
                            
                            if bl and product and trans_type and rat_act > 0:
                                unmasked_product = remove_product_mask(product, prod_mask_order)
                                st.session_state.selected_trans_types[(bl, unmasked_product, trans_type)] = rat_act
                            
                            if bl and product and trans_type and channel and rat_chan > 0:
                                unmasked_product = remove_product_mask(product, prod_mask_order)
                                unmasked_channel = remove_channel_mask(channel, channel_mask_order)
                                st.session_state.selected_channels[(bl, unmasked_product, trans_type, unmasked_channel)] = rat_chan
                    
                    form_type_row = cc_user[cc_user['CC'].astype(str) == str(CC)]
                    if not form_type_row.empty:
                        form_type_value = form_type_row.iloc[0].get('FORM_TYPE', 'ABC')
                        form_type = str(form_type_value).strip() if pd.notna(form_type_value) else 'ABC'
                    else:
                        form_type = 'ABC'
                    st.session_state.form_type = form_type
                    
                    if form_type == 'BS':
                        st.session_state.step = 'bs_step1'
                    else:
                        st.session_state.step = 'step1'
                    st.rerun()
        
        return
    
    # Načítaj hierarchiu a BL
    hierarchy = create_hierarchy(trans_data)
    bl_unique = get_sorted_bls(bl_order, trans_data)
    
    # ==================== ETAPA 2: STEP 1 ====================
    if st.session_state.step == 'step1':
        st.header("Krok 1: Výber Biznis línií a segmentov")
        st.markdown("Vyberte všetky biznis línie a segmenty, v ktorých je vaše oddelenie aktívne, a rozdeľte medzi nimi alokáciu (celkom 100%).")
        
        col1, col2, *_ = st.columns(10)
        with col1:
            if st.button("🔄 Zmeniť údaje", key="btn_step1_change_data", use_container_width=True):
                st.session_state.step = 'user_input'
                st.session_state.user_id = None
                st.session_state.cc = None
                st.session_state.selected_bls = {}
                st.session_state.selected_products = {}
                st.session_state.selected_trans_types = {}
                st.session_state.selected_channels = {}
                st.session_state.fte_data_dict = {}
                st.session_state.current_status_snapshot = None
                st.rerun()
        with col2:
            btn_next_placeholder = col2.empty()
        
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = parse_decimal_value(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        bl_tooltips = {}
        for _, bl_row_data in bl_order.iterrows():
            bl_code = bl_row_data.get('BL', '')
            tooltip = bl_row_data.get('TOOLTIP', '')
            if bl_code and pd.notna(tooltip) and str(tooltip).strip():
                bl_tooltips[bl_code] = str(tooltip).strip()
        
        st.markdown("#### Business Lines")
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown("**Názov**")
        with col2:
            st.markdown("**Alokácia (%)**")
        with col3:
            st.markdown("**FTEs**")
        
        selected_bls_list = []
        allocations = {}
        
        for idx, bl_row in bl_unique.iterrows():
            bl = bl_row['BL']
            label = bl_row['BL_LABEL']
            tooltip_text = bl_tooltips.get(bl, '')
            
            checkbox_key = f"bl_check_{bl}_{idx}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = bl in st.session_state.selected_bls
            
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                if tooltip_text:
                    checkbox_value = st.checkbox(label, key=checkbox_key, help=tooltip_text)
                else:
                    checkbox_value = st.checkbox(label, key=checkbox_key)
                if checkbox_value:
                    selected_bls_list.append(bl)
            
            with col2:
                if checkbox_value:
                    allocation = st.number_input(
                        f"",
                        min_value=0.0,
                        max_value=100.0,
                        value=st.session_state.selected_bls.get(bl, 0.0),
                        step=0.1,
                        key=f"bl_alloc_{bl}_{idx}",
                        label_visibility="collapsed"
                    )
                    allocations[bl] = allocation
            
            with col3:
                if checkbox_value and num_fte_total:
                    allocation_val = allocations.get(bl, 0.0)
                    weighted_fte = (allocation_val / 100) * num_fte_total
                    st.write(format_number(weighted_fte, 2))
        
        total_allocation = sum(allocations.values())
        st.markdown("---")
        st.metric("Celková alokácia", f"{format_number(total_allocation, 1)}%")
        
        if abs(total_allocation - 100.0) > 0.01:
            st.error(f"⚠️ Celková alokácia musí byť presne 100%. Aktuálne: {format_number(total_allocation, 1)}%")
        
        with btn_next_placeholder.container():
            if st.button("Ďalej →", type="primary", key="btn_step1_next", disabled=len(selected_bls_list) == 0 or abs(total_allocation - 100.0) > 0.01, use_container_width=True):
                st.session_state.selected_bls = allocations.copy()
                
                if st.session_state.selected_bls:
                    idx = 0
                    for bl in st.session_state.selected_bls.keys():
                        form_data = {
                            'BL': bl,
                            'RAT_BL': st.session_state.selected_bls.get(bl, 0),
                            'DOM_ABC_PROD': '',
                            'RAT_PROD': 0,
                            'GPM_HIER': '',
                            'RAT_ACTIVITY': 0,
                            'TXT_CHANNEL': '',
                            'RAT_CHANNEL': 0,
                            'RAT_TOTAL': 0
                        }
                        save_form_step(st.session_state.user_id, st.session_state.cc, act_version, form_data, saved_forms, bl_order, 'Step1', is_first_in_step=(idx == 0))
                        idx += 1
                
                st.session_state.step = 'step2'
                st.rerun()
    
    # ==================== ETAPA 3: STEP 2 ====================
    elif st.session_state.step == 'step2':
        st.header("Krok 2: Výber produktov")
        st.markdown("Pre každú vybranú biznis líniu a segment vyberte všetky produkty a rozdeľte alokáciu (celkom 100% pre každú BL).")
        
        all_valid = True
        
        col1, col2, *_ = st.columns(10)
        with col1:
            if st.button("← Späť", key="btn_step2_back", use_container_width=True):
                st.session_state.step = 'step1'
                st.rerun()
        with col2:
            btn_next_placeholder = col2.empty()
        
        selected_bls_set = set(st.session_state.selected_bls.keys())
        st.session_state.selected_products = {
            (bl, prod): alloc for (bl, prod), alloc in st.session_state.selected_products.items() 
            if bl in selected_bls_set
        }
        st.session_state.selected_trans_types = {
            (bl, prod, trans): alloc for (bl, prod, trans), alloc in st.session_state.selected_trans_types.items() 
            if bl in selected_bls_set
        }
        st.session_state.selected_channels = {
            (bl, prod, trans, chan): alloc for (bl, prod, trans, chan), alloc in st.session_state.selected_channels.items() 
            if bl in selected_bls_set
        }
        
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = parse_decimal_value(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        current_status = st.session_state.current_status_snapshot
        use_current_version = get_status_hierarchy(current_status) >= get_status_hierarchy('Step2')
        
        prev_forms = get_existing_from_prev_version(st.session_state.cc, prev_version, saved_forms) if prev_version else pd.DataFrame()
        
        order_col = None
        for col in bl_order.columns:
            if col != 'BL' and pd.api.types.is_numeric_dtype(bl_order[col]):
                order_col = col
                break
        
        bl_order_dict = {}
        if order_col:
            bl_order_dict = dict(zip(bl_order['BL'], bl_order[order_col]))
        else:
            bl_order_dict = {bl: idx for idx, bl in enumerate(bl_order['BL'])}
        
        sorted_bls = sorted(st.session_state.selected_bls.items(), key=lambda x: bl_order_dict.get(x[0], 999))
        
        product_tooltips = {}
        if prod_mask_order is not None and not prod_mask_order.empty:
            for _, prod_row_data in prod_mask_order.iterrows():
                prod_code = prod_row_data.get('DOM_ABC_PRD_MASK', '')
                tooltip = prod_row_data.get('TOOLTIP', '')
                if prod_code and pd.notna(tooltip) and str(tooltip).strip():
                    product_tooltips[prod_code] = str(tooltip).strip()
        
        for bl, bl_alloc in sorted_bls:
            weighted_fte = (bl_alloc / 100) * num_fte_total
            st.markdown(f"### {bl} ({format_number(bl_alloc, 0)}%) - {format_number(weighted_fte, 2)} FTEs")
            
            products = get_sorted_products(prod_mask_order, hierarchy, bl)
            selected_products_list = []
            allocations = {}
            
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown("**Produkt**")
            with col2:
                st.markdown("**Alokácia (%)**")
            with col3:
                st.markdown("**FTEs**")
            
            for idx, product in enumerate(products):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    key = f"product_check_{bl}_{product}_{idx}"
                    tooltip_text = product_tooltips.get(product, '')
                    
                    should_auto_check = False
                    masked_product = apply_product_mask(product, prod_mask_order)
                    
                    if use_current_version:
                        if not saved_forms[
                            (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                            (saved_forms['VERSION'].astype(str) == str(act_version)) &
                            (saved_forms['BL'] == bl) &
                            (saved_forms['DOM_ABC_PROD'] == masked_product) &
                            (pd.to_numeric(saved_forms['RAT_PROD'], errors='coerce') > 0)
                        ].empty:
                            should_auto_check = True
                    else:
                        if not prev_forms.empty and not prev_forms[
                            (prev_forms['BL'] == bl) & 
                            (prev_forms['DOM_ABC_PROD'] == masked_product) &
                            (pd.to_numeric(prev_forms['RAT_PROD'], errors='coerce') > 0)
                        ].empty:
                            should_auto_check = True
                    
                    if key not in st.session_state:
                        st.session_state[key] = (bl, product) in st.session_state.selected_products or should_auto_check
                    
                    if tooltip_text:
                        checkbox_value = st.checkbox(product, key=key, help=tooltip_text)
                    else:
                        checkbox_value = st.checkbox(product, key=key)
                    if checkbox_value:
                        selected_products_list.append(product)
                
                with col2:
                    if checkbox_value:
                        default_value = 0.0
                        masked_product = apply_product_mask(product, prod_mask_order)
                        
                        if (bl, product) in st.session_state.selected_products:
                            default_value = st.session_state.selected_products[(bl, product)]
                        elif use_current_version:
                            current_row = saved_forms[
                                (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                                (saved_forms['VERSION'].astype(str) == str(act_version)) &
                                (saved_forms['BL'] == bl) &
                                (saved_forms['DOM_ABC_PROD'] == masked_product)
                            ]
                            if not current_row.empty:
                                default_value = parse_decimal_value(current_row.iloc[0]['RAT_PROD'])
                        else:
                            if not prev_forms.empty:
                                prev_row = prev_forms[
                                    (prev_forms['BL'] == bl) & 
                                    (prev_forms['DOM_ABC_PROD'] == masked_product)
                                ]
                                if not prev_row.empty:
                                    default_value = parse_decimal_value(prev_row.iloc[0]['RAT_PROD'])
                        
                        allocation = st.number_input(
                            f"",
                            min_value=0.0,
                            max_value=100.0,
                            value=st.session_state.selected_products.get((bl, product), default_value),
                            step=0.1,
                            key=f"product_alloc_{bl}_{product}_{idx}",
                            label_visibility="collapsed"
                        )
                        allocations[product] = allocation
                
                with col3:
                    if checkbox_value and num_fte_total:
                        allocation_val = allocations.get(product, 0.0)
                        weighted_fte = (bl_alloc / 100) * (allocation_val / 100) * num_fte_total
                        st.write(format_number(weighted_fte, 2))
            
            total_allocation = sum(allocations.values())
            st.metric(f"Celková alokácia pre {bl}", f"{format_number(total_allocation, 1)}%")
            
            if len(selected_products_list) == 0:
                st.warning(f"⚠️ Musíte vybrať aspoň jeden produkt pre {bl}")
                all_valid = False
            elif abs(total_allocation - 100.0) > 0.01:
                st.error(f"⚠️ Alokácia pre {bl} musí byť presne 100%. Aktuálne: {format_number(total_allocation, 1)}%")
                all_valid = False
            
            st.session_state.selected_products = {
                (b, p): alloc for (b, p), alloc in st.session_state.selected_products.items() 
                if b != bl
            }
            for product in selected_products_list:
                st.session_state.selected_products[(bl, product)] = allocations.get(product, 0.0)
            
            st.markdown("---")
        
        with btn_next_placeholder.container():
            if st.button("Ďalej →", type="primary", key="btn_step2_next", disabled=not all_valid, use_container_width=True):
                if st.session_state.selected_products:
                    idx = 0
                    for (bl, product), allocation in st.session_state.selected_products.items():
                        if bl in st.session_state.selected_bls and allocation > 0:
                            masked_product = apply_product_mask(product, prod_mask_order)
                            form_data = {
                                'BL': bl,
                                'RAT_BL': st.session_state.selected_bls.get(bl, 0),
                                'DOM_ABC_PROD': masked_product,
                                'RAT_PROD': allocation,
                                'GPM_HIER': '',
                                'RAT_ACTIVITY': 0,
                                'TXT_CHANNEL': '',
                                'RAT_CHANNEL': 0,
                                'RAT_TOTAL': 0
                            }
                            save_form_step(st.session_state.user_id, st.session_state.cc, act_version, form_data, saved_forms, bl_order, 'Step2', is_first_in_step=(idx == 0))
                            idx += 1
                
                st.session_state.step = 'step3'
                st.rerun()
    
    # ==================== ETAPA 4: STEP 3 ====================
    elif st.session_state.step == 'step3':
        st.header("Krok 3: Výber aktivity")
        st.markdown("Pre každý vybraný produkt vyberte všetky aktivity a rozdeľte alokáciu (celkom 100% pre každý produkt).")
        
        all_valid = True
        
        col1, col2, *_ = st.columns(10)
        with col1:
            if st.button("← Späť", key="btn_step3_back", use_container_width=True):
                st.session_state.step = 'step2'
                st.rerun()
        with col2:
            btn_next_placeholder = col2.empty()
        
        selected_products_set = set(st.session_state.selected_products.keys())
        st.session_state.selected_trans_types = {
            (bl, prod, trans): alloc for (bl, prod, trans), alloc in st.session_state.selected_trans_types.items() 
            if (bl, prod) in selected_products_set
        }
        st.session_state.selected_channels = {
            (bl, prod, trans, chan): alloc for (bl, prod, trans, chan), alloc in st.session_state.selected_channels.items() 
            if (bl, prod) in selected_products_set
        }
        
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = parse_decimal_value(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        current_status = st.session_state.current_status_snapshot
        use_current_version = get_status_hierarchy(current_status) >= get_status_hierarchy('Step3')
        
        prev_forms = get_existing_from_prev_version(st.session_state.cc, prev_version, saved_forms) if prev_version else pd.DataFrame()
        
        order_col = None
        for col in bl_order.columns:
            if col != 'BL' and pd.api.types.is_numeric_dtype(bl_order[col]):
                order_col = col
                break
        
        bl_order_dict = {}
        if order_col:
            bl_order_dict = dict(zip(bl_order['BL'], bl_order[order_col]))
        else:
            bl_order_dict = {bl: idx for idx, bl in enumerate(bl_order['BL'])}
        
        prod_order_dict = {}
        if prod_mask_order is not None and not prod_mask_order.empty:
            for _, row in prod_mask_order.iterrows():
                prod = row['DOM_ABC_PRD_MASK']
                order = row.get('PROD_ORDER', 999)
                prod_order_dict[prod] = order
        
        sorted_products = sorted(
            st.session_state.selected_products.items(),
            key=lambda x: (bl_order_dict.get(x[0][0], 999), prod_order_dict.get(x[0][1], 999))
        )
        
        gpm_tooltips = {}
        if gpm_order is not None and not gpm_order.empty:
            for _, gpm_row_data in gpm_order.iterrows():
                gpm_code = gpm_row_data.get('GPM_HIER', '')
                tooltip = gpm_row_data.get('TOOLTIP', '')
                if gpm_code and pd.notna(tooltip) and str(tooltip).strip():
                    gpm_tooltips[gpm_code] = str(tooltip).strip()
        
        def get_extended_tooltip(trans_type, bl, product, bl_order_data, prod_mask_data, trx_count_data, act_version_str):
            """Vytvorí rozšírený tooltip s TOOLTIP textom a tabuľkou"""
            tooltip_parts = []
            
            gpm_tooltip = gpm_tooltips.get(trans_type, '')
            if gpm_tooltip:
                tooltip_parts.append(gpm_tooltip)
            
            if trx_count_data is not None and not trx_count_data.empty:
                bl_row = bl_order_data[bl_order_data['BL'] == bl]
                if not bl_row.empty:
                    txt_bus_line = bl_row.iloc[0].get('TXT_BUS_LINE', '')
                    subsegment = bl_row.iloc[0].get('SUBSEGMENT', '')
                else:
                    txt_bus_line = ''
                    subsegment = ''
                
                prod_row = prod_mask_data[prod_mask_data['DOM_ABC_PRD_MASK'] == product]
                if not prod_row.empty:
                    dom_abc_prod = prod_row.iloc[0].get('DOM_ABC_PRD', '')
                    if not dom_abc_prod:
                        dom_abc_prod = prod_row.iloc[0].get('DOM_ABC_PROD', '')
                else:
                    dom_abc_prod = product
                
                filtered_trx = trx_count_data[
                    (trx_count_data['VERSION'].astype(str) == act_version_str) &
                    (trx_count_data['TXT_BUS_LINE'].astype(str).str.strip() == txt_bus_line.strip()) &
                    (trx_count_data['SUBSEGMENT'].astype(str).str.strip() == subsegment.strip()) &
                    (trx_count_data['DOM_ABC_PROD'].astype(str).str.strip() == dom_abc_prod.strip()) &
                    (trx_count_data['GPM_HIER'].astype(str).str.strip() == trans_type.strip())
                ]
                
                if not filtered_trx.empty:
                    if tooltip_parts:
                        tooltip_parts.append("")
                    
                    tooltip_parts.append("| Transakcia | Počet |")
                    tooltip_parts.append("|---|---|")
                    
                    if 'TXT_TRANS_DESC' in filtered_trx.columns and 'FC' in filtered_trx.columns:
                        trx_grouped = filtered_trx.groupby('TXT_TRANS_DESC')['FC'].sum().reset_index()
                        trx_grouped.columns = ['TXT_TRANS_DESC', 'FC']
                        
                        for _, row in trx_grouped.iterrows():
                            desc = str(row['TXT_TRANS_DESC'])
                            if len(desc) > 6:
                                desc = desc[6:]
                            
                            try:
                                fc_value = parse_decimal_value(row['FC'])
                                if fc_value >= 1000:
                                    fc_formatted = f"{int(fc_value):,}".replace(',', ' ')
                                else:
                                    fc_formatted = str(int(fc_value))
                            except:
                                fc_formatted = str(row['FC'])
                            
                            tooltip_parts.append(f"| {desc} | {fc_formatted} |")
            
            return "\n".join(tooltip_parts) if tooltip_parts else ""
        
        for (bl, product), product_alloc in sorted_products:
            bl_alloc = st.session_state.selected_bls.get(bl, 0.0)
            weighted_fte = (bl_alloc / 100) * (product_alloc / 100) * num_fte_total
            st.markdown(f"### {bl} ({format_number(bl_alloc, 0)}%) - {product} ({format_number(product_alloc, 0)}%) - {format_number(weighted_fte, 2)} FTEs")
            
            trans_types = get_sorted_gpm(gpm_order, hierarchy, bl, product)
            selected_trans_types_list = []
            allocations = {}
            
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown("**Aktivita**")
            with col2:
                st.markdown("**Alokácia (%)**")
            with col3:
                st.markdown("**FTEs**")
            
            for idx, trans_type in enumerate(trans_types):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    key = f"trans_check_{bl}_{product}_{trans_type}_{idx}"
                    extended_tooltip = get_extended_tooltip(trans_type, bl, product, bl_order, prod_mask_order, trx_count, str(act_version))
                    
                    should_auto_check = False
                    masked_product = apply_product_mask(product, prod_mask_order)
                    
                    if use_current_version:
                        if not saved_forms[
                            (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                            (saved_forms['VERSION'].astype(str) == str(act_version)) &
                            (saved_forms['BL'] == bl) &
                            (saved_forms['DOM_ABC_PROD'] == masked_product) &
                            (saved_forms['GPM_HIER'] == trans_type) &
                            (pd.to_numeric(saved_forms['RAT_ACTIVITY'], errors='coerce') > 0)
                        ].empty:
                            should_auto_check = True
                    else:
                        if not prev_forms.empty and not prev_forms[
                            (prev_forms['BL'] == bl) & 
                            (prev_forms['DOM_ABC_PROD'] == masked_product) & 
                            (prev_forms['GPM_HIER'] == trans_type) &
                            (pd.to_numeric(prev_forms['RAT_ACTIVITY'], errors='coerce') > 0)
                        ].empty:
                            should_auto_check = True
                    
                    if key not in st.session_state:
                        st.session_state[key] = (bl, product, trans_type) in st.session_state.selected_trans_types or should_auto_check
                    
                    if extended_tooltip:
                        checkbox_value = st.checkbox(trans_type, key=key, help=extended_tooltip)
                    else:
                        checkbox_value = st.checkbox(trans_type, key=key)
                    if checkbox_value:
                        selected_trans_types_list.append(trans_type)
                
                with col2:
                    if checkbox_value:
                        default_value = 0.0
                        masked_product = apply_product_mask(product, prod_mask_order)
                        
                        if (bl, product, trans_type) in st.session_state.selected_trans_types:
                            default_value = st.session_state.selected_trans_types[(bl, product, trans_type)]
                        elif use_current_version:
                            current_row = saved_forms[
                                (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                                (saved_forms['VERSION'].astype(str) == str(act_version)) &
                                (saved_forms['BL'] == bl) &
                                (saved_forms['DOM_ABC_PROD'] == masked_product) &
                                (saved_forms['GPM_HIER'] == trans_type)
                            ]
                            if not current_row.empty:
                                default_value = parse_decimal_value(current_row.iloc[0]['RAT_ACTIVITY'])
                        else:
                            if not prev_forms.empty:
                                prev_row = prev_forms[
                                    (prev_forms['BL'] == bl) & 
                                    (prev_forms['DOM_ABC_PROD'] == masked_product) & 
                                    (prev_forms['GPM_HIER'] == trans_type)
                                ]
                                if not prev_row.empty:
                                    default_value = parse_decimal_value(prev_row.iloc[0]['RAT_ACTIVITY'])
                        
                        allocation = st.number_input(
                            f"",
                            min_value=0.0,
                            max_value=100.0,
                            value=st.session_state.selected_trans_types.get((bl, product, trans_type), default_value),
                            step=0.1,
                            key=f"trans_alloc_{bl}_{product}_{trans_type}_{idx}",
                            label_visibility="collapsed"
                        )
                        allocations[trans_type] = allocation
                
                with col3:
                    if checkbox_value and num_fte_total:
                        bl_alloc = st.session_state.selected_bls.get(bl, 0.0)
                        allocation_val = allocations.get(trans_type, 0.0)
                        weighted_fte = (bl_alloc / 100) * (product_alloc / 100) * (allocation_val / 100) * num_fte_total
                        st.write(format_number(weighted_fte, 2))
            
            total_allocation = sum(allocations.values())
            st.metric(f"Celková alokácia pre {product}", f"{format_number(total_allocation, 1)}%")
            
            if len(selected_trans_types_list) == 0:
                st.warning(f"⚠️ Musíte vybrať aspoň jednu aktivitu pre {product}")
                all_valid = False
            elif abs(total_allocation - 100.0) > 0.01:
                st.error(f"⚠️ Alokácia pre {product} musí byť presne 100%. Aktuálne: {format_number(total_allocation, 1)}%")
                all_valid = False
            
            st.session_state.selected_trans_types = {
                (b, p, t): alloc for (b, p, t), alloc in st.session_state.selected_trans_types.items() 
                if not (b == bl and p == product)
            }
            for trans_type in selected_trans_types_list:
                st.session_state.selected_trans_types[(bl, product, trans_type)] = allocations.get(trans_type, 0.0)
            
            st.markdown("---")
        
        with btn_next_placeholder.container():
            if st.button("Ďalej →", type="primary", key="btn_step3_next", disabled=not all_valid, use_container_width=True):
                if st.session_state.selected_trans_types:
                    idx = 0
                    for (bl, product, trans_type), allocation in st.session_state.selected_trans_types.items():
                        if bl in st.session_state.selected_bls and (bl, product) in st.session_state.selected_products and allocation > 0:
                            masked_product = apply_product_mask(product, prod_mask_order)
                            form_data = {
                                'BL': bl,
                                'RAT_BL': st.session_state.selected_bls.get(bl, 0),
                                'DOM_ABC_PROD': masked_product,
                                'RAT_PROD': st.session_state.selected_products.get((bl, product), 0),
                                'GPM_HIER': trans_type,
                                'RAT_ACTIVITY': allocation,
                                'TXT_CHANNEL': '',
                                'RAT_CHANNEL': 0,
                                'RAT_TOTAL': 0
                            }
                            save_form_step(st.session_state.user_id, st.session_state.cc, act_version, form_data, saved_forms, bl_order, 'Step3', is_first_in_step=(idx == 0))
                            idx += 1
                
                st.session_state.step = 'step4'
                st.rerun()
    
    # ==================== ETAPA 5: STEP 4 ====================
    elif st.session_state.step == 'step4':
        st.header("Krok 4: Výber kanálov")
        st.markdown("Pre každú vybranú aktivitu vyberte klientsky kanál a rozdeľte alokáciu (celkom 100% pre každú aktivitu).")
        
        all_valid = True
        
        col1, col2, *_ = st.columns(10)
        with col1:
            if st.button("← Späť", key="btn_step4_back", use_container_width=True):
                st.session_state.step = 'step3'
                st.rerun()
        with col2:
            btn_done_placeholder = col2.empty()
        
        selected_trans_types_set = set(st.session_state.selected_trans_types.keys())
        st.session_state.selected_channels = {
            (bl, prod, trans, chan): alloc for (bl, prod, trans, chan), alloc in st.session_state.selected_channels.items() 
            if (bl, prod, trans) in selected_trans_types_set
        }
        
        if not st.session_state.selected_channels:
            current_forms = saved_forms[
                (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                (saved_forms['VERSION'].astype(str) == str(act_version))
            ]
            if not current_forms.empty:
                for _, row in current_forms.iterrows():
                    bl = row['BL']
                    product = remove_product_mask(row['DOM_ABC_PROD'], prod_mask_order)
                    trans_type = row['GPM_HIER']
                    channel = remove_channel_mask(row['TXT_CHANNEL'], channel_mask_order) if pd.notna(row['TXT_CHANNEL']) and str(row['TXT_CHANNEL']).strip() else ''
                    channel_alloc = parse_decimal_value(row['RAT_CHANNEL'])
                    
                    if channel and channel_alloc > 0 and (bl, product, trans_type) in st.session_state.selected_trans_types:
                        st.session_state.selected_channels[(bl, product, trans_type, channel)] = channel_alloc
        
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = parse_decimal_value(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        current_status = st.session_state.current_status_snapshot
        use_current_version = get_status_hierarchy(current_status) >= get_status_hierarchy('Submitted')
        
        prev_forms = get_existing_from_prev_version(st.session_state.cc, prev_version, saved_forms) if prev_version else pd.DataFrame()
        
        order_col = None
        for col in bl_order.columns:
            if col != 'BL' and pd.api.types.is_numeric_dtype(bl_order[col]):
                order_col = col
                break
        
        bl_order_dict = {}
        if order_col:
            bl_order_dict = dict(zip(bl_order['BL'], bl_order[order_col]))
        else:
            bl_order_dict = {bl: idx for idx, bl in enumerate(bl_order['BL'])}
        
        prod_order_dict = {}
        if prod_mask_order is not None and not prod_mask_order.empty:
            for _, row in prod_mask_order.iterrows():
                prod = row['DOM_ABC_PRD_MASK']
                order = row.get('PROD_ORDER', 0)
                prod_order_dict[prod] = order
        
        gpm_order_dict = {}
        if gpm_order is not None and not gpm_order.empty:
            for _, row in gpm_order.iterrows():
                gpm_hier = row['GPM_HIER']
                order = row.get('GPM_ORDER', 999)
                gpm_order_dict[gpm_hier] = order
        
        channel_order_dict = {}
        if channel_mask_order is not None and not channel_mask_order.empty:
            for _, row in channel_mask_order.iterrows():
                channel = row['CHANNEL_ABC_MASK']
                order = row.get('CHANNEL_ORDER', 0)
                channel_order_dict[channel] = order
        
        channel_tooltips = {}
        if channel_mask_order is not None and not channel_mask_order.empty:
            for _, channel_row_data in channel_mask_order.iterrows():
                channel_code = channel_row_data.get('CHANNEL_ABC_MASK', '')
                tooltip = channel_row_data.get('TOOLTIP', '')
                if channel_code and pd.notna(tooltip) and str(tooltip).strip():
                    channel_tooltips[channel_code] = str(tooltip).strip()
        
        sorted_trans_types = sorted(
            st.session_state.selected_trans_types.keys(),
            key=lambda x: (bl_order_dict.get(x[0], 999), prod_order_dict.get(x[1], 999), gpm_order_dict.get(x[2], 999))
        )
        
        for (bl, product, trans_type) in sorted_trans_types:
            bl_alloc = st.session_state.selected_bls.get(bl, 0.0)
            product_alloc = st.session_state.selected_products.get((bl, product), 0.0)
            trans_alloc = st.session_state.selected_trans_types.get((bl, product, trans_type), 0.0)
            weighted_fte = (bl_alloc / 100) * (product_alloc / 100) * (trans_alloc / 100) * num_fte_total
            
            st.markdown(f"### {bl} ({format_number(bl_alloc, 0)}%) - {product} ({format_number(product_alloc, 0)}%) - {trans_type} ({format_number(trans_alloc, 0)}%) - {format_number(weighted_fte, 2)} FTEs")
            
            channels = get_sorted_channels(channel_mask_order, hierarchy, bl, product, trans_type)
            channels = sorted(channels, key=lambda c: channel_order_dict.get(c, 999))
            
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown("**Kanál**")
            with col2:
                st.markdown("**Alokácia (%)**")
            with col3:
                st.markdown("**FTEs**")
            
            selected_channels_list = []
            allocations = {}
            
            for idx, channel in enumerate(channels):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    key = f"channel_check_{bl}_{product}_{trans_type}_{channel}_{idx}"
                    tooltip_text = channel_tooltips.get(channel, '')
                    
                    should_auto_check = False
                    masked_product = apply_product_mask(product, prod_mask_order)
                    masked_channel = apply_channel_mask(channel, channel_mask_order)
                    
                    if use_current_version:
                        if not saved_forms[
                            (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                            (saved_forms['VERSION'].astype(str) == str(act_version)) &
                            (saved_forms['BL'] == bl) & 
                            (saved_forms['DOM_ABC_PROD'] == masked_product) & 
                            (saved_forms['GPM_HIER'] == trans_type) &
                            (saved_forms['TXT_CHANNEL'] == masked_channel) &
                            (pd.to_numeric(saved_forms['RAT_CHANNEL'], errors='coerce') > 0)
                        ].empty:
                            should_auto_check = True
                    else:
                        if not prev_forms.empty and not prev_forms[
                            (prev_forms['BL'] == bl) & 
                            (prev_forms['DOM_ABC_PROD'] == masked_product) & 
                            (prev_forms['GPM_HIER'] == trans_type) &
                            (prev_forms['TXT_CHANNEL'] == masked_channel) &
                            (pd.to_numeric(prev_forms['RAT_CHANNEL'], errors='coerce') > 0)
                        ].empty:
                            should_auto_check = True
                    
                    if key not in st.session_state:
                        st.session_state[key] = (bl, product, trans_type, channel) in st.session_state.selected_channels or should_auto_check
                    
                    if tooltip_text:
                        checkbox_value = st.checkbox(channel, key=key, help=tooltip_text)
                    else:
                        checkbox_value = st.checkbox(channel, key=key)
                    if checkbox_value:
                        selected_channels_list.append(channel)
                
                with col2:
                    if checkbox_value:
                        default_value = 0.0
                        masked_product = apply_product_mask(product, prod_mask_order)
                        masked_channel = apply_channel_mask(channel, channel_mask_order)
                        
                        if (bl, product, trans_type, channel) in st.session_state.selected_channels:
                            default_value = st.session_state.selected_channels[(bl, product, trans_type, channel)]
                        elif use_current_version:
                            current_forms = saved_forms[
                                (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                                (saved_forms['VERSION'].astype(str) == str(act_version)) &
                                (saved_forms['BL'] == bl) & 
                                (saved_forms['DOM_ABC_PROD'] == masked_product) & 
                                (saved_forms['GPM_HIER'] == trans_type) &
                                (saved_forms['TXT_CHANNEL'] == masked_channel)
                            ]
                            if not current_forms.empty:
                                default_value = parse_decimal_value(current_forms.iloc[0]['RAT_CHANNEL'])
                        else:
                            if not prev_forms.empty:
                                prev_row = prev_forms[
                                    (prev_forms['BL'] == bl) & 
                                    (prev_forms['DOM_ABC_PROD'] == masked_product) & 
                                    (prev_forms['GPM_HIER'] == trans_type) &
                                    (prev_forms['TXT_CHANNEL'] == masked_channel)
                                ]
                                if not prev_row.empty:
                                    default_value = parse_decimal_value(prev_row.iloc[0]['RAT_CHANNEL'])
                        
                        allocation = st.number_input(
                            f"",
                            min_value=0.0,
                            max_value=100.0,
                            value=st.session_state.selected_channels.get((bl, product, trans_type, channel), default_value),
                            step=0.1,
                            key=f"channel_alloc_{bl}_{product}_{trans_type}_{channel}_{idx}",
                            label_visibility="collapsed"
                        )
                        allocations[channel] = allocation
                
                with col3:
                    if checkbox_value:
                        bl_alloc_val = st.session_state.selected_bls.get(bl, 0.0)
                        product_alloc_val = st.session_state.selected_products.get((bl, product), 0.0)
                        trans_alloc_val = st.session_state.selected_trans_types.get((bl, product, trans_type), 0.0)
                        channel_alloc_val = st.session_state.selected_channels.get((bl, product, trans_type, channel), 0.0)
                        weighted_fte = (bl_alloc_val / 100) * (product_alloc_val / 100) * (trans_alloc_val / 100) * (channel_alloc_val / 100) * num_fte_total
                        st.write(format_number(weighted_fte, 2))
            
            total_allocation = sum(allocations.values())
            if len(selected_channels_list) == 0:
                st.warning(f"⚠️ Musíte vybrať aspoň jeden kanál pre {trans_type}")
                all_valid = False
            elif abs(total_allocation - 100.0) > 0.01:
                st.error(f"⚠️ Alokácia pre {trans_type} musí byť presne 100%. Aktuálne: {format_number(total_allocation, 1)}%")
                all_valid = False
            
            st.session_state.selected_channels = {
                (b, p, t, c): alloc for (b, p, t, c), alloc in st.session_state.selected_channels.items() 
                if not (b == bl and p == product and t == trans_type)
            }
            for channel in selected_channels_list:
                st.session_state.selected_channels[(bl, product, trans_type, channel)] = allocations.get(channel, 0.0)
            
            st.markdown("---")
        
        with btn_done_placeholder.container():
            if st.button("Hotovo", type="primary", key="btn_step4_done", disabled=not all_valid, use_container_width=True):
                if st.session_state.selected_channels:
                    idx = 0
                    for (bl, product, trans_type, channel), allocation in st.session_state.selected_channels.items():
                        if (bl in st.session_state.selected_bls and 
                            (bl, product) in st.session_state.selected_products and 
                            (bl, product, trans_type) in st.session_state.selected_trans_types and
                            allocation > 0):
                            masked_product = apply_product_mask(product, prod_mask_order)
                            masked_channel = apply_channel_mask(channel, channel_mask_order)
                            rat_bl = st.session_state.selected_bls.get(bl, 0)
                            rat_prod = st.session_state.selected_products.get((bl, product), 0)
                            rat_activity = st.session_state.selected_trans_types.get((bl, product, trans_type), 0)
                            rat_channel = allocation
                            rat_total = (rat_bl * rat_prod * rat_activity * rat_channel) / 1000000
                            
                            form_data = {
                                'BL': bl,
                                'RAT_BL': rat_bl,
                                'DOM_ABC_PROD': masked_product,
                                'RAT_PROD': rat_prod,
                                'GPM_HIER': trans_type,
                                'RAT_ACTIVITY': rat_activity,
                                'TXT_CHANNEL': masked_channel,
                                'RAT_CHANNEL': rat_channel,
                                'RAT_TOTAL': rat_total
                            }
                            save_form_step(st.session_state.user_id, st.session_state.cc, act_version, form_data, saved_forms, bl_order, 'Submitted', is_first_in_step=(idx == 0))
                            idx += 1
                
                st.session_state.step = 'summary'
                st.rerun()
    
    # ==================== ETAPA BS: BS STEP 1 ====================
    elif st.session_state.step == 'bs_step1':
        st.header("Výber biznis línií a segmentov")
        st.markdown("Vyberte biznis línie a segmenty, ktorým venujete čas a rozdeľte medzi nimi alokáciu (celkom 100%).")
        
        col1, col2, *_ = st.columns(10)
        with col1:
            if st.button("🔄 Zmeniť údaje", key="btn_bs_step1_change_data", use_container_width=True):
                st.session_state.step = 'user_input'
                st.session_state.user_id = None
                st.session_state.cc = None
                st.session_state.selected_bls = {}
                st.session_state.form_type = None
                st.rerun()
        with col2:
            btn_done_placeholder = col2.empty()
        
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = parse_decimal_value(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        existing = get_existing_forms_by_status_bs(st.session_state.cc, act_version, saved_bs)
        if existing.empty and prev_version:
            existing = get_existing_bs_from_prev_version(st.session_state.cc, prev_version, saved_bs)
        
        if not existing.empty:
            for _, row in existing.iterrows():
                bl = row['BL'] if pd.notna(row['BL']) and row['BL'] != '' else None
                rat_total = parse_decimal_value(row['RAT_TOTAL'])
                if bl and rat_total > 0:
                    st.session_state.selected_bls[bl] = rat_total
        
        bl_tooltips = {}
        for _, bl_row_data in bl_order.iterrows():
            bl_code = bl_row_data.get('BL', '')
            tooltip = bl_row_data.get('TOOLTIP', '')
            if bl_code and pd.notna(tooltip) and str(tooltip).strip():
                bl_tooltips[bl_code] = str(tooltip).strip()
        
        st.markdown("#### Business Lines")
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown("**Názov**")
        with col2:
            st.markdown("**Alokácia (%)**")
        with col3:
            st.markdown("**FTEs**")
        
        selected_bls_list = []
        allocations = {}
        
        for idx, bl_row in bl_unique.iterrows():
            bl = bl_row['BL']
            label = bl_row['BL_LABEL']
            tooltip_text = bl_tooltips.get(bl, '')
            
            checkbox_key = f"bs_bl_check_{bl}_{idx}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = bl in st.session_state.selected_bls
            
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                if tooltip_text:
                    checkbox_value = st.checkbox(label, key=checkbox_key, help=tooltip_text)
                else:
                    checkbox_value = st.checkbox(label, key=checkbox_key)
                if checkbox_value:
                    selected_bls_list.append(bl)
            
            with col2:
                if checkbox_value:
                    allocation = st.number_input(
                        f"",
                        min_value=0.0,
                        max_value=100.0,
                        value=st.session_state.selected_bls.get(bl, 0.0),
                        step=0.1,
                        key=f"bs_bl_alloc_{bl}_{idx}",
                        label_visibility="collapsed"
                    )
                    allocations[bl] = allocation
            
            with col3:
                if checkbox_value and num_fte_total:
                    allocation_val = allocations.get(bl, 0.0)
                    weighted_fte = (allocation_val / 100) * num_fte_total
                    st.write(format_number(weighted_fte, 2))
        
        total_allocation = sum(allocations.values())
        st.markdown("---")
        st.metric("Celková alokácia", f"{format_number(total_allocation, 1)}%")
        
        if abs(total_allocation - 100.0) > 0.01:
            st.error(f"⚠️ Celková alokácia musí byť presne 100%. Aktuálne: {format_number(total_allocation, 1)}%")
        
        with btn_done_placeholder.container():
            if st.button("Hotovo", type="primary", key="btn_bs_step1_done", disabled=len(selected_bls_list) == 0 or abs(total_allocation - 100.0) > 0.01, use_container_width=True):
                st.session_state.selected_bls = allocations.copy()
                
                if st.session_state.selected_bls:
                    save_form_bs(st.session_state.user_id, st.session_state.cc, act_version, st.session_state.selected_bls, saved_bs, bl_order)
                
                st.session_state.step = 'bs_summary'
                st.rerun()
    
    # ==================== ETAPA BS SUMMARY ====================
    elif st.session_state.step == 'bs_summary':
        st.header("✅ Zhrnutie alokácie")
        st.success("Všetky alokácie boli úspešne zadané!")
        
        if st.button("← Späť", key="btn_bs_summary_back"):
            st.session_state.step = 'bs_step1'
            st.rerun()
        
        results = []
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = parse_decimal_value(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        for bl, rat_total in st.session_state.selected_bls.items():
            weighted_fte = (rat_total / 100) * num_fte_total
            results.append({
                'Business Line': bl,
                'Alokácia (%)': format_number(rat_total, 1),
                'FTE': format_number(weighted_fte, 2)
            })
        
        st.subheader("Výsledná alokácia")
        if results:
            results_df = pd.DataFrame(results)
            st.dataframe(results_df, use_container_width=True)
        
        col1, col2 = st.columns([1, 1])
        
        with col2:
            if results:
                csv_df = results_df.copy()
                numeric_cols = ['Alokácia (%)', 'FTE']
                for col in numeric_cols:
                    if col in csv_df.columns:
                        csv_df[col] = csv_df[col].str.replace('.', ',')
                
                csv_string = csv_df.to_csv(index=False, sep=';')
                csv_bytes = csv_string.encode('utf-8')
                
                filename = f"BS_dotaznik_{st.session_state.cc}"
                if cc_desc is not None and not cc_desc.empty and 'ID' in cc_desc.columns:
                    try:
                        cc_row = cc_desc[cc_desc['ID'].astype(str) == str(st.session_state.cc)]
                        if not cc_row.empty:
                            txt_desc = cc_row.iloc[0].get('TXT_DESCRIPTION', '')
                            filename = f"BS_dotaznik_{st.session_state.cc}_{txt_desc}"
                    except Exception:
                        pass
                filename = filename + ".csv"
                
                st.download_button(
                    label="📥 Stiahnuť výsledky CSV",
                    data=csv_bytes,
                    file_name=filename,
                    mime="text/csv;charset=utf-8"
                )
    
    # ==================== ETAPA SUMMARY ====================
    elif st.session_state.step == 'summary':
        st.header("✅ Zhrnutie alokácie")
        st.success("Všetky alokácie boli úspešne zadané!")
        
        if st.button("← Späť", key="btn_summary_back"):
            st.session_state.step = 'step4'
            st.rerun()
        
        results = []
        final_total = 0.0
        
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = float(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        for bl, bl_alloc in st.session_state.selected_bls.items():
            for (bl_key, product), product_alloc in st.session_state.selected_products.items():
                if bl_key != bl:
                    continue
                
                for (bl_t, product_t, trans_type), trans_alloc in st.session_state.selected_trans_types.items():
                    if bl_t != bl or product_t != product:
                        continue
                    
                    for (bl_c, product_c, trans_c, channel), channel_alloc in st.session_state.selected_channels.items():
                        if bl_c != bl or product_c != product or trans_c != trans_type:
                            continue
                        
                        final_alloc = bl_alloc * product_alloc * trans_alloc * channel_alloc / 1000000
                        final_total += final_alloc
                        
                        weighted_fte = (bl_alloc / 100) * (product_alloc / 100) * (trans_alloc / 100) * (channel_alloc / 100) * num_fte_total
                        
                        results.append({
                            'Business Line': bl,
                            'BL (%)': format_number(bl_alloc, 1),
                            'Product': product,
                            'Product (%)': format_number(product_alloc, 1),
                            'Aktivita': trans_type,
                            'Aktivita (%)': format_number(trans_alloc, 1),
                            'Kanál': channel,
                            'Kanál (%)': format_number(channel_alloc, 1),
                            'Alokácia (%)': format_number(final_alloc, 4),
                            'Weighted FTE': format_number(weighted_fte, 2)
                        })
        
        st.subheader("Výsledná alokácia")
        if results:
            results_df = pd.DataFrame(results)
            st.dataframe(results_df, use_container_width=True)
        
        st.metric("Celková finálna alokácia", f"{format_number(final_total, 4)}%")
        
        col1, col2 = st.columns([1, 1])
        
        with col2:
            if results:
                csv_df = results_df.copy()
                numeric_cols = ['BL (%)', 'Product (%)', 'Aktivita (%)', 'Kanál (%)', 'Alokácia (%)', 'Weighted FTE']
                for col in numeric_cols:
                    if col in csv_df.columns:
                        csv_df[col] = csv_df[col].str.replace('.', ',')
                
                csv_string = csv_df.to_csv(index=False, sep=';')
                csv_bytes = csv_string.encode('utf-8')
                
                filename = f"ABC_dotaznik_{st.session_state.cc}"
                if cc_desc is not None and not cc_desc.empty and 'ID' in cc_desc.columns:
                    try:
                        cc_row = cc_desc[cc_desc['ID'].astype(str) == str(st.session_state.cc)]
                        if not cc_row.empty:
                            txt_desc = cc_row.iloc[0].get('TXT_DESCRIPTION', '')
                            filename = f"ABC_dotaznik_{st.session_state.cc}_{txt_desc}"
                    except Exception:
                        pass
                filename = filename + ".csv"
                
                st.download_button(
                    label="📥 Stiahnuť výsledky CSV",
                    data=csv_bytes,
                    file_name=filename,
                    mime="text/csv;charset=utf-8"
                )

if __name__ == "__main__":
    main()