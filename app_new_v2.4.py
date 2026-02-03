import streamlit as st
import pandas as pd
import re
import os
from collections import defaultdict
from datetime import datetime

st.set_page_config(layout="wide")

# Cesty k súborom
data_path = 'trans_data.csv'
fte_path = 'FTE.csv'
cc_user_path = 'CC_USER.csv'
forms_path = 'saved_forms.csv'
saved_bs_path = 'saved_bs.csv'
bl_order_path = 'bl_order.csv'
gpm_order_path = 'gpm_order.csv'
prod_mask_order_path = 'prod_mask_order.csv'
channel_mask_order_path = 'Channel_mask_order.csv'
version_path = 'version.csv'
cc_desc_path = 'CC_DESC.csv'
trx_count_path = 'TRX_COUNT.csv'

encoding_type = 'cp1250'
decimal_sep = ','

def format_number(value, decimals=2):
    """Formátuj číslo s čiarkou ako desatinným oddeľovačom"""
    if decimals == 0:
        return f"{value:.0f}"
    elif decimals == 1:
        return f"{value:.1f}".replace('.', ',')
    else:  # decimals == 2
        return f"{value:.2f}".replace('.', ',')


def get_slovak_datetime():
    """Vráti aktuálny dátum a čas vo formáte pre Slovensko (DD.MM.YYYY HH:MM:SS)"""
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


# Pridaj JavaScript na konverziu čiarky na bodku pri vstupe
st.markdown(
    """
    <script>
        document.addEventListener('change', function(e) {
            if (e.target.type === 'number') {
                let value = e.target.value;
                // Konvertuj čiarku na bodku
                if (value.includes(',')) {
                    e.target.value = value.replace(',', '.');
                }
            }
        });
        
        document.addEventListener('input', function(e) {
            if (e.target.type === 'number') {
                let value = e.target.value;
                // Umožni psanie čiarky - automaticky konvertuj na bodku
                if (value.includes(',')) {
                    e.target.value = value.replace(',', '.');
                }
            }
        });
    </script>
    """,
    unsafe_allow_html=True
)


@st.cache_data
def load_data():
    """Načítanie všetkých potrebných dát s optimalizáciou verzií"""
    try:
        # trans_data - filtruj iba aktuálnu verziu
        trans_data = pd.read_csv(data_path, encoding=encoding_type, sep=';')
        if 'version' in trans_data.columns:
            trans_data = trans_data[trans_data['version'] == 'act'].copy()
        
        fte_data = pd.read_csv(fte_path, encoding=encoding_type, sep=';', decimal=decimal_sep)
        cc_user = pd.read_csv(cc_user_path, encoding=encoding_type, sep=';')
        
        # saved_forms - filtruj verzie act a prev
        saved_forms = pd.read_csv(forms_path, encoding=encoding_type, sep=';', decimal=decimal_sep)
        if 'version' in saved_forms.columns:
            saved_forms = saved_forms[saved_forms['version'].isin(['act', 'prev'])].copy()
        
        # saved_bs - filtruj verzie act a prev
        if os.path.exists(saved_bs_path):
            saved_bs = pd.read_csv(saved_bs_path, encoding=encoding_type, sep=';', decimal=decimal_sep)
            if 'version' in saved_bs.columns:
                saved_bs = saved_bs[saved_bs['version'].isin(['act', 'prev'])].copy()
        else:
            saved_bs = pd.DataFrame()
        
        bl_order = pd.read_csv(bl_order_path, encoding=encoding_type, sep=';')
        gpm_order = pd.read_csv(gpm_order_path, encoding=encoding_type, sep=';') if os.path.exists(gpm_order_path) else None
        prod_mask_order = pd.read_csv(prod_mask_order_path, encoding=encoding_type, sep=';') if os.path.exists(prod_mask_order_path) else None
        channel_mask_order = pd.read_csv(channel_mask_order_path, encoding=encoding_type, sep=';') if os.path.exists(channel_mask_order_path) else None
        version = pd.read_csv(version_path, encoding=encoding_type, sep=';')
        cc_desc = pd.read_csv(cc_desc_path, encoding=encoding_type, sep=';') if os.path.exists(cc_desc_path) else None
        
        # trx_count - filtruj iba aktuálnu verziu
        if os.path.exists(trx_count_path):
            trx_count = pd.read_csv(trx_count_path, encoding=encoding_type, sep=';')
            if 'version' in trx_count.columns:
                trx_count = trx_count[trx_count['version'] == 'act'].copy()
        else:
            trx_count = None
        
        return trans_data, fte_data, cc_user, saved_forms, saved_bs, bl_order, gpm_order, prod_mask_order, channel_mask_order, version, cc_desc, trx_count
    except FileNotFoundError as e:
        st.error(f"Súbor bol neobjavený: {e}")
        return None, None, None, None, None, None, None, None, None, None, None, None

def load_dynamic_data():
    """Načítanie dynamických dát bez cache (saved_forms, saved_bs, cc_user) s filtráciou verzií"""
    try:
        cc_user = pd.read_csv(cc_user_path, encoding=encoding_type, sep=';')
        
        # saved_forms - filtruj verzie act a prev
        saved_forms = pd.read_csv(forms_path, encoding=encoding_type, sep=';', decimal=decimal_sep)
        if 'version' in saved_forms.columns:
            saved_forms = saved_forms[saved_forms['version'].isin(['act', 'prev'])].copy()
        
        # saved_bs - filtruj verzie act a prev
        if os.path.exists(saved_bs_path):
            saved_bs = pd.read_csv(saved_bs_path, encoding=encoding_type, sep=';', decimal=decimal_sep)
            if 'version' in saved_bs.columns:
                saved_bs = saved_bs[saved_bs['version'].isin(['act', 'prev'])].copy()
        else:
            saved_bs = pd.DataFrame()
        
        return cc_user, saved_forms, saved_bs
    except FileNotFoundError as e:
        st.error(f"Súbor bol neobjavený: {e}")
        return None, None, None

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
        product = str(row['Product']).strip() if pd.notna(row['Product']) else ''
        trans_type = str(row['Trans_type']).strip() if pd.notna(row['Trans_type']) else ''
        channel = str(row['Channel']).strip() if pd.notna(row['Channel']) else ''
        
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
    
    # Vytvor dict z gpm_order kde GPM_HIER -> GPM_ORDER
    gpm_order_dict = {}
    for _, row in gpm_order.iterrows():
        gpm_hier = row['GPM_HIER']
        order = row.get('GPM_ORDER', 999)
        gpm_order_dict[gpm_hier] = order
    
    # Sortuj trans_types podľa GPM_ORDER
    trans_types = sorted(trans_types, key=lambda x: gpm_order_dict.get(x, 999))
    
    return trans_types

def get_sorted_products(prod_mask_order, hierarchy, bl):
    """Získanie zoraďaného zoznamu produktov s maskou"""
    products = sorted(hierarchy['bl_to_products'].get(bl, set()))
    
    if prod_mask_order is None:
        return products
    
    # Mergiť podľa DOM_ABC_PRD_MASK (to sú pôvodné názvy z trans_data)
    prod_df = pd.DataFrame({'DOM_ABC_PRD_MASK': products})
    prod_df = prod_df.merge(prod_mask_order, on='DOM_ABC_PRD_MASK', how='left')
    prod_df['PROD_ORDER'] = pd.to_numeric(prod_df.get('PROD_ORDER', pd.NA), errors='coerce')
    prod_df = prod_df.sort_values('PROD_ORDER', na_position='last').reset_index(drop=True)
    
    # Vrať originálne názvy (DOM_ABC_PRD_MASK), nie masky
    return prod_df['DOM_ABC_PRD_MASK'].tolist()

def get_sorted_channels(channel_mask_order, hierarchy, bl, product, trans_type):
    """Získanie zoradeného zoznamu kanálov s maskou"""
    channels = sorted(hierarchy['trans_type_to_channels'].get((bl, product, trans_type), set()))
    
    if channel_mask_order is None:
        return channels
    
    # Mergiť podľa CHANNEL_ABC_MASK (to sú pôvodné názvy z trans_data)
    chan_df = pd.DataFrame({'CHANNEL_ABC_MASK': channels})
    chan_df = chan_df.merge(channel_mask_order, on='CHANNEL_ABC_MASK', how='left')
    chan_df['CHANNEL_ORDER'] = pd.to_numeric(chan_df.get('CHANNEL_ORDER', pd.NA), errors='coerce')
    chan_df = chan_df.sort_values('CHANNEL_ORDER', na_position='last').reset_index(drop=True)
    
    # Vrať originálne názvy (CHANNEL_ABC_MASK), nie masky
    return chan_df['CHANNEL_ABC_MASK'].tolist()

def apply_product_mask(product_name, prod_mask_order):
    """Konvertuj názov produktu na masku (napr. 'Business accounts' -> 'Current accounts')"""
    if prod_mask_order is None:
        return product_name
    # Hľadaj podľa DOM_ABC_PRD_MASK (názov v formulári) a vráti DOM_ABC_PRD (názov v saved_forms)
    mask_row = prod_mask_order[prod_mask_order['DOM_ABC_PRD_MASK'] == product_name]
    if not mask_row.empty and 'DOM_ABC_PRD' in mask_row.columns:
        return str(mask_row.iloc[0]['DOM_ABC_PRD'])
    return product_name

def remove_product_mask(masked_name, prod_mask_order):
    """Konvertuj masku späť na názov (napr. 'Current accounts' -> 'Business accounts')"""
    if prod_mask_order is None:
        return masked_name
    # Hľadaj podľa DOM_ABC_PRD (masky) a vráti DOM_ABC_PRD_MASK (pôvodnýNázov)
    mask_row = prod_mask_order[prod_mask_order['DOM_ABC_PRD'] == masked_name]
    if not mask_row.empty and 'DOM_ABC_PRD_MASK' in mask_row.columns:
        return str(mask_row.iloc[0]['DOM_ABC_PRD_MASK'])
    return masked_name

def apply_channel_mask(channel_name, channel_mask_order):
    """Konvertuj názov kanála na masku"""
    if channel_mask_order is None:
        return channel_name
    # Hľadaj podľa CHANNEL_ABC_MASK (názov v formulári) a vráti CHANNEL_ABC (názov v saved_forms)
    mask_row = channel_mask_order[channel_mask_order['CHANNEL_ABC_MASK'] == channel_name]
    if not mask_row.empty and 'CHANNEL_ABC' in mask_row.columns:
        return str(mask_row.iloc[0]['CHANNEL_ABC'])
    return channel_name

def remove_channel_mask(masked_name, channel_mask_order):
    """Konvertuj masku kanála späť na názov"""
    if channel_mask_order is None:
        return masked_name
    # Hľadaj podľa CHANNEL_ABC (masky) a vráti CHANNEL_ABC_MASK (pôvodnýNázov)
    mask_row = channel_mask_order[channel_mask_order['CHANNEL_ABC'] == masked_name]
    if not mask_row.empty and 'CHANNEL_ABC_MASK' in mask_row.columns:
        return str(mask_row.iloc[0]['CHANNEL_ABC_MASK'])
    return masked_name

def get_form_status(CC, VERSION, saved_forms):
    """Získanie statusu formulára pre danú VERSION a CC (bez USER_ID, lebo CC zodpovedný sa môže zmeniť)"""
    mask = (
        (saved_forms['CC'].astype(str).str.strip() == str(CC).strip()) &
        (saved_forms['VERSION'].astype(str).str.strip() == str(VERSION))
    )
    
    if not saved_forms[mask].empty:
        # Vráť prvý riadok, môže byť len jeden pre CC+VERSION na daný čas
        return saved_forms[mask].iloc[0].get('STATUS', '')
    return ''

def get_existing_forms_by_status(CC, VERSION, saved_forms, status_filter):
    """Získanie formulárov s určitým statusom (bez USER_ID, lebo CC zodpovedný sa môže zmeniť)"""
    mask = (
        (saved_forms['CC'].astype(str).str.strip() == str(CC).strip()) &
        (saved_forms['VERSION'].astype(str).str.strip() == str(VERSION)) &
        (saved_forms['STATUS'].astype(str).str.strip() == status_filter)
    )
    
    if not saved_forms[mask].empty:
        result = saved_forms[mask]
    else:
        return pd.DataFrame()
    
    # Konverzia čiarok na bodky pre numerické stĺpce
    for col in ['RAT_BL', 'RAT_PROD', 'RAT_ACTIVITY', 'RAT_CHANNEL', 'RAT_TOTAL']:
        if col in result.columns:
            result[col] = result[col].astype(str).str.replace(',', '.').astype(float)
    
    return result

def get_existing_from_prev_version(CC, prev_version, saved_forms):
    """Získanie existujúcich formulárov z predoslej verzie (bez USER_ID, lebo CC zodpovedný sa môže zmeniť)"""
    if not prev_version:
        return pd.DataFrame()
    
    mask = (
        (saved_forms['CC'].astype(str).str.strip() == str(CC).strip()) &
        (saved_forms['VERSION'].astype(str).str.strip() == prev_version)
    )
    
    if not saved_forms[mask].empty:
        result = saved_forms[mask]
    else:
        return pd.DataFrame()
    
    # Konverzia čiarok na bodky pre numerické stĺpce
    for col in ['RAT_BL', 'RAT_PROD', 'RAT_ACTIVITY', 'RAT_CHANNEL', 'RAT_TOTAL']:
        if col in result.columns:
            result[col] = result[col].astype(str).str.replace(',', '.').astype(float)
    
    return result

def get_status_hierarchy(status):
    """Vrátí numerickú hodnotu pre porovnanie statusov (vyššia hodnota = vyšší status)"""
    status_order = {'Step1': 1, 'Step2': 2, 'Step3': 3, 'Submitted': 4}
    return status_order.get(status, 0)

def get_current_status(CC, VERSION, saved_forms):
    """Zistí aktuálny najvyšší STATUS pre dané CC a VERSION (bez USER_ID, lebo CC zodpovedný sa môže zmeniť)"""
    mask = (
        (saved_forms['CC'].astype(str).str.strip() == str(CC).strip()) &
        (saved_forms['VERSION'].astype(str).str.strip() == str(VERSION))
    )
    if not saved_forms[mask].empty:
        statuses = saved_forms[mask]['STATUS'].unique()
        # Vráti najvyšší status
        return max(statuses, key=lambda x: get_status_hierarchy(x)) if statuses.size > 0 else ''
    return ''

def save_form_step(USER_ID, CC, VERSION, form_data, saved_forms, bl_order, status, is_first_in_step=False):
    """Uloženie jednotlivého kroku formulára - prepíše všetky riadky pre CC+VERSION na úrovni statusu (bez USER_ID v filtri)"""
    if os.path.exists(forms_path):
        df_saved = pd.read_csv(forms_path, encoding=encoding_type, sep=';')
    else:
        df_saved = pd.DataFrame()
    
    # Ak je to prvý raz v kroku, vymaž všetky staré riadky pre dané CC a VERSION (bez USER_ID)
    if is_first_in_step:
        mask_old = (
            (df_saved['CC'].astype(str).str.strip() == str(CC).strip()) &
            (df_saved['VERSION'].astype(str).str.strip() == str(VERSION))
        )
        df_saved = df_saved[~mask_old]
    else:
        # Ak nie je prvý, len vymaž riadky s rovnakým BL, produktom a ostatnými parametrami (aby sa predchádnuli duplikáty)
        mask_old = (
            (df_saved['CC'].astype(str).str.strip() == str(CC).strip()) &
            (df_saved['VERSION'].astype(str).str.strip() == str(VERSION)) &
            (df_saved['BL'] == form_data.get('BL', '')) &
            (df_saved['DOM_ABC_PROD'] == form_data.get('DOM_ABC_PROD', '')) &
            (df_saved['GPM_HIER'] == form_data.get('GPM_HIER', '')) &
            (df_saved['TXT_CHANNEL'] == form_data.get('TXT_CHANNEL', ''))
        )
        df_saved = df_saved[~mask_old]
    
    # Konvertuj percentá na čiarky
    def convert_to_comma_decimal(val):
        if val is None or val == 0 or val == '':
            return '0'
        return str(float(val)).replace('.', ',')
    
    # Vytvor nový riadok s formátovaním podľa obsahu
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
    df_saved.to_csv(forms_path, sep=';', encoding=encoding_type, index=False)

def get_form_status_bs(CC, VERSION, saved_bs):
    """Získanie statusu BS formulára pre danú VERSION a CC"""
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
    """Získanie BS formulárov s daným CC a VERSION"""
    if saved_bs.empty:
        return pd.DataFrame()
    mask = (
        (saved_bs['COST_CENTER'].astype(str).str.strip() == str(CC).strip()) &
        (saved_bs['VERSION'].astype(str).str.strip() == str(VERSION))
    )
    if not saved_bs[mask].empty:
        result = saved_bs[mask]
    else:
        return pd.DataFrame()
    
    # Konverzia čiarok na bodky pre numerické stĺpce
    if 'RAT_TOTAL' in result.columns:
        result['RAT_TOTAL'] = result['RAT_TOTAL'].astype(str).str.replace(',', '.').astype(float)
    
    return result

def get_existing_bs_from_prev_version(CC, prev_version, saved_bs):
    """Získanie existujúcich BS formulárov z predoslej verzie"""
    if saved_bs.empty or not prev_version:
        return pd.DataFrame()
    
    mask = (
        (saved_bs['COST_CENTER'].astype(str).str.strip() == str(CC).strip()) &
        (saved_bs['VERSION'].astype(str).str.strip() == prev_version)
    )
    
    if not saved_bs[mask].empty:
        result = saved_bs[mask]
    else:
        return pd.DataFrame()
    
    # Konverzia čiarok na bodky pre numerické stĺpce
    if 'RAT_TOTAL' in result.columns:
        result['RAT_TOTAL'] = result['RAT_TOTAL'].astype(str).str.replace(',', '.').astype(float)
    
    return result

def save_form_bs(USER_ID, CC, VERSION, form_data, saved_bs, bl_order):
    """Uloženie BS formulára"""
    if os.path.exists(saved_bs_path):
        df_saved = pd.read_csv(saved_bs_path, encoding=encoding_type, sep=';')
    else:
        df_saved = pd.DataFrame()
    
    # Vymaž všetky staré riadky pre dané CC a VERSION
    mask_old = (
        (df_saved['COST_CENTER'].astype(str).str.strip() == str(CC).strip()) &
        (df_saved['VERSION'].astype(str).str.strip() == str(VERSION))
    )
    df_saved = df_saved[~mask_old]
    
    # Konvertuj percentá na čiarky
    def convert_to_comma_decimal(val):
        if val is None or val == 0 or val == '':
            return '0'
        return str(float(val)).replace('.', ',')
    
    # Ulož všetky vybrané BL do saved_bs
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
        
        df_saved = pd.concat([df_saved, new_row], ignore_index=True)
    
    df_saved.to_csv(saved_bs_path, sep=';', encoding=encoding_type, index=False)

def main():
    # Načítaj statické dáta z cache a dynamické dáta bez cache
    trans_data, fte_data, _, _, _, bl_order, gpm_order, prod_mask_order, channel_mask_order, version, cc_desc, trx_count = load_data()
    cc_user, saved_forms, saved_bs = load_dynamic_data()
    
    if trans_data is None:
        st.stop()
    
    # Dynamicky nastavuj title podľa CC
    if st.session_state.get('cc') and cc_desc is not None and not cc_desc.empty and 'ID' in cc_desc.columns:
        try:
            cc_row = cc_desc[cc_desc['ID'].astype(str) == str(st.session_state.cc)]
            if not cc_row.empty:
                txt_desc = cc_row.iloc[0].get('TXT_DESCRIPTION', '')
                st.title(f"📊 ABC dotazník - {txt_desc}")
            else:
                st.title("📊 ABC dotazník")
        except Exception as e:
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
    
    # Filtruj trans_data len na aktuálnu VERSION
    trans_data = trans_data[trans_data['VERSION'].astype(str).str.strip() == str(act_version).strip()]
    
    # Etapa 1: User ID a CC
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
                # Vytvor dictionary s CC a TXT_DESC pre display v dropdowne
                cc_options = []
                cc_display_map = {}
                
                for cc in sorted(allowed_CC):
                    cc_str = str(cc).strip()
                    txt_desc = ""
                    
                    # Hľadaj TXT_DESC v CC_DESC
                    if cc_desc is not None and not cc_desc.empty and 'ID' in cc_desc.columns:
                        try:
                            cc_row = cc_desc[cc_desc['ID'].astype(str).str.strip() == cc_str]
                            if not cc_row.empty and 'TXT_DESCRIPTION' in cc_row.columns:
                                txt_desc = str(cc_row.iloc[0]['TXT_DESCRIPTION']).strip()
                        except Exception:
                            pass
                    
                    # Vytvor display text (CC - TXT_DESC ak existuje, inak iba CC)
                    if txt_desc:
                        display_text = f"{cc_str} - {txt_desc}"
                    else:
                        display_text = cc_str
                    
                    cc_options.append(display_text)
                    cc_display_map[display_text] = cc_str
                
                # Selectbox s display textom
                cc_selected = st.selectbox("Vyberte nákladové stredisko", cc_options)
                
                # Extrakt skutočné CC z display textu
                CC = cc_display_map.get(cc_selected, cc_selected.split(' - ')[0])
                
                if st.button("Pokračovať →", type="primary"):
                    st.session_state.user_id = USER_ID
                    st.session_state.cc = CC
                    
                    # Ulož snapshot aktuálneho statusu na začiatku session (nezmení sa počas vyplňovania)
                    st.session_state.current_status_snapshot = get_current_status(CC, act_version, saved_forms)
                    
                    # Zisti status pre CC+VERSION (bez USER_ID)
                    status = get_form_status(CC, act_version, saved_forms)
                    
                    if status == '':
                        # Žiadna hodnota v aktualnej verzii - načítaj z predoslej Version
                        existing = get_existing_from_prev_version(CC, prev_version, saved_forms)
                    else:
                        # Načítaj z aktualnej Version
                        existing = get_existing_forms_by_status(CC, act_version, saved_forms, status)
                    
                    # Naplň session state podľa toho, čo je uložené
                    if not existing.empty:
                        for _, row in existing.iterrows():
                            bl = row['BL'] if pd.notna(row['BL']) and row['BL'] != '' else None
                            product = row['DOM_ABC_PROD'] if pd.notna(row['DOM_ABC_PROD']) and row['DOM_ABC_PROD'] != '' else None
                            trans_type = row['GPM_HIER'] if pd.notna(row['GPM_HIER']) and row['GPM_HIER'] != '' else None
                            channel = row['TXT_CHANNEL'] if pd.notna(row['TXT_CHANNEL']) and row['TXT_CHANNEL'] != '' else None
                            
                            rat_bl = float(str(row['RAT_BL']).replace(',', '.')) if pd.notna(row['RAT_BL']) and float(str(row['RAT_BL']).replace(',', '.')) != 0 else 0
                            rat_prod = float(str(row['RAT_PROD']).replace(',', '.')) if pd.notna(row['RAT_PROD']) and float(str(row['RAT_PROD']).replace(',', '.')) != 0 else 0
                            rat_act = float(str(row['RAT_ACTIVITY']).replace(',', '.')) if pd.notna(row['RAT_ACTIVITY']) and float(str(row['RAT_ACTIVITY']).replace(',', '.')) != 0 else 0
                            rat_chan = float(str(row['RAT_CHANNEL']).replace(',', '.')) if pd.notna(row['RAT_CHANNEL']) and float(str(row['RAT_CHANNEL']).replace(',', '.')) != 0 else 0
                            
                            if bl and rat_bl > 0:
                                st.session_state.selected_bls[bl] = rat_bl
                            
                            if bl and product and rat_prod > 0:
                                # Demaskuj názov produktu aby sa zhodoval s hierarchiou
                                unmasked_product = remove_product_mask(product, prod_mask_order)
                                st.session_state.selected_products[(bl, unmasked_product)] = rat_prod
                            
                            if bl and product and trans_type and rat_act > 0:
                                # Demaskuj názov produktu aby sa zhodoval s hierarchiou
                                unmasked_product = remove_product_mask(product, prod_mask_order)
                                st.session_state.selected_trans_types[(bl, unmasked_product, trans_type)] = rat_act
                            
                            if bl and product and trans_type and channel and rat_chan > 0:
                                # Demaskuj názov produktu a kanála aby sa zhodovali s hierarchiou
                                unmasked_product = remove_product_mask(product, prod_mask_order)
                                unmasked_channel = remove_channel_mask(channel, channel_mask_order)
                                st.session_state.selected_channels[(bl, unmasked_product, trans_type, unmasked_channel)] = rat_chan
                    
                    # Zisti FORM_TYPE pre vybraný CC
                    form_type_row = cc_user[cc_user['CC'].astype(str) == str(CC)]
                    form_type = form_type_row.iloc[0].get('FORM_TYPE', 'ABC').strip() if not form_type_row.empty else 'ABC'
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
    
    # Etapa 2: Krok 1 - Výber BL
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
        
        # FTE data
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = float(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        # Vytvoríme slovník s tooltipmi pre BL
        bl_tooltips = {}
        for _, bl_row_data in bl_order.iterrows():
            bl_code = bl_row_data.get('BL', '')
            tooltip = bl_row_data.get('TOOLTIP', '')
            if bl_code and pd.notna(tooltip) and str(tooltip).strip():
                bl_tooltips[bl_code] = str(tooltip).strip()
        
        # Nadpisy stĺpcov
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
            
            # Kontrola, či má BL tooltip
            tooltip_text = bl_tooltips.get(bl, '')
            display_label = label
            
            checkbox_key = f"bl_check_{bl}_{idx}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = bl in st.session_state.selected_bls
            
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                if tooltip_text:
                    checkbox_value = st.checkbox(display_label, key=checkbox_key, help=tooltip_text)
                else:
                    checkbox_value = st.checkbox(display_label, key=checkbox_key)
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
        
        # Umiestni "Ďalej" button na vrch v placeholder
        with btn_next_placeholder.container():
            if st.button("Ďalej →", type="primary", key="btn_step1_next", disabled=len(selected_bls_list) == 0 or abs(total_allocation - 100.0) > 0.01, use_container_width=True):
                st.session_state.selected_bls = allocations.copy()
                
                # Uložiť Krok 1 s STATUS=Step1 - uložiť VŠETKY vybrané BL
                if st.session_state.selected_bls:
                    for idx, bl in enumerate(st.session_state.selected_bls.keys()):
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
                        # Vymaž staré riadky len pri prvom BL
                        save_form_step(st.session_state.user_id, st.session_state.cc, act_version, form_data, saved_forms, bl_order, 'Step1', is_first_in_step=(idx == 0))
                
                st.session_state.step = 'step2'
                st.rerun()
  
    # Etapa 3: Krok 2 - Výber produktov
    elif st.session_state.step == 'step2':
        
        st.header("Krok 2: Výber produktov")
        
        st.markdown("Pre každú vybranú biznis líniu a segment vyberte všetky produkty a rozdeľte alokáciu (celkom 100% pre každú BL).")
        
        # Inicializuj all_valid hneď na vrchu
        all_valid = True
        
        col1, col2, *_ = st.columns(10)
        with col1:
            if st.button("← Späť", key="btn_step2_back", use_container_width=True):
                st.session_state.step = 'step1'
                st.rerun()
        with col2:
            btn_next_placeholder = col2.empty()
        
        # Vyčisti selected_products, selected_trans_types a selected_channels aby ostali len z vybraných BL
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
        
        # FTE data
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = float(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        # Použij snapshot statusu z začiatku session (nie aktuálny, ktorý sa počas vyplňovania mení)
        current_status = st.session_state.current_status_snapshot
        use_current_version = get_status_hierarchy(current_status) >= get_status_hierarchy('Step2')
        
        # Načítaj existujúce hodnoty z predošlej verzie pre dopĺňanie v Kroku 2
        prev_forms = get_existing_from_prev_version(st.session_state.cc, prev_version, saved_forms) if prev_version else pd.DataFrame()
        
        # Sortuj selected_bls podľa poradia v BL_ORDER (použi prvý numerický stĺpec ako poradie)
        # Nájdi stĺpec s poradím - zvyčajne to je druhý stĺpec alebo s názvom obsahujúcim "ORDER"
        order_col = None
        for col in bl_order.columns:
            if col != 'BL' and pd.api.types.is_numeric_dtype(bl_order[col]):
                order_col = col
                break
        
        bl_order_dict = {}
        if order_col:
            bl_order_dict = dict(zip(bl_order['BL'], bl_order[order_col]))
        else:
            # Fallback: použij index ak nemá poradie
            bl_order_dict = {bl: idx for idx, bl in enumerate(bl_order['BL'])}
        
        sorted_bls = sorted(st.session_state.selected_bls.items(), key=lambda x: bl_order_dict.get(x[0], 999))
        
        # Vytvoríme slovník s tooltipmi pre produkty
        product_tooltips = {}
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
            
            # Nadpisy stĺpcov
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
                    # Kontrola, či má produkt tooltip
                    tooltip_text = product_tooltips.get(product, '')
                    
                    # Logika predvyplnenia - zaškrť checkbox len ak existuje v relevantnej verzii s hodnotou > 0
                    should_auto_check = False
                    masked_product = apply_product_mask(product, prod_mask_order)
                    
                    if use_current_version:
                        # STATUS >= Step2: zaškrť len ak existuje v aktualnej verzii s hodnotou > 0
                        # Hľadaj bez USER_ID, lebo CC zodpovedný sa môže zmeniť
                        if not saved_forms[
                            (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                            (saved_forms['VERSION'].astype(str) == str(act_version)) &
                            (saved_forms['BL'] == bl) &
                            (saved_forms['DOM_ABC_PROD'] == masked_product) &
                            (saved_forms['RAT_PROD'].astype(str).str.replace(',', '.').astype(float) > 0)
                        ].empty:
                            should_auto_check = True
                    else:
                        # STATUS < Step2: zaškrť len ak existuje v predošlej verzii s hodnotou > 0
                        if not prev_forms.empty and not prev_forms[
                            (prev_forms['BL'] == bl) & 
                            (prev_forms['DOM_ABC_PROD'] == masked_product) &
                            (prev_forms['RAT_PROD'].astype(str).str.replace(',', '.').astype(float) > 0)
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
                        # Predvyplnenie: session_state > aktualnaVerzia > predoslaVerzia
                        default_value = 0.0
                        masked_product = apply_product_mask(product, prod_mask_order)
                        
                        # Priorita 1: session_state
                        if (bl, product) in st.session_state.selected_products:
                            default_value = st.session_state.selected_products[(bl, product)]
                        # Priorita 2: aktualnaVerzia (ak je STATUS >= Step2)
                        elif use_current_version:
                            current_row = saved_forms[
                                (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                                (saved_forms['VERSION'].astype(str) == str(act_version)) &
                                (saved_forms['BL'] == bl) &
                                (saved_forms['DOM_ABC_PROD'] == masked_product)
                            ]
                            if not current_row.empty:
                                default_value = float(str(current_row.iloc[0]['RAT_PROD']).replace(',', '.')) if pd.notna(current_row.iloc[0]['RAT_PROD']) else 0.0
                        # Priorita 3: predoslaVerzia (fallback)
                        else:
                            if not prev_forms.empty:
                                prev_row = prev_forms[
                                    (prev_forms['BL'] == bl) & 
                                    (prev_forms['DOM_ABC_PROD'] == masked_product)
                                ]
                                if not prev_row.empty:
                                    default_value = float(str(prev_row.iloc[0]['RAT_PROD']).replace(',', '.')) if pd.notna(prev_row.iloc[0]['RAT_PROD']) else 0.0
                        
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
            
            # Vymaž všetky produkty pre tento BL a potom pridaj len vybrané
            st.session_state.selected_products = {
                (b, p): alloc for (b, p), alloc in st.session_state.selected_products.items() 
                if b != bl
            }
            for product in selected_products_list:
                st.session_state.selected_products[(bl, product)] = allocations.get(product, 0.0)
            
            st.markdown("---")
        
        # Umiestni "Ďalej" button na vrch v placeholder
        with btn_next_placeholder.container():
            if st.button("Ďalej →", type="primary", key="btn_step2_next", disabled=not all_valid, use_container_width=True):
                # Uložiť Krok 2 s STATUS=Step2 - uložiť IBA vybrané produkty z vybraných BL
                if st.session_state.selected_products:
                    idx = 0
                    for (bl, product), allocation in st.session_state.selected_products.items():
                        # Filtruj - ulož len produkty z vybraných BL
                        if bl in st.session_state.selected_bls and allocation > 0:
                            # Aplikuj masku na názov produktu pri ukladaní
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
                            # Vymaž staré riadky len pri prvom produkte
                            save_form_step(st.session_state.user_id, st.session_state.cc, act_version, form_data, saved_forms, bl_order, 'Step2', is_first_in_step=(idx == 0))
                            idx += 1
                
                st.session_state.step = 'step3'
                st.rerun()
    
    # Etapa 4: Krok 3 - Výber aktivít
    elif st.session_state.step == 'step3':
        st.header("Krok 3: Výber aktivity")
        st.markdown("Pre každý vybraný produkt vyberte všetky aktivity a rozdeľte alokáciu (celkom 100% pre každý produkt).")
        
        # Inicializuj all_valid hneď na vrchu
        all_valid = True
        
        col1, col2, *_ = st.columns(10)
        with col1:
            if st.button("← Späť", key="btn_step3_back", use_container_width=True):
                st.session_state.step = 'step2'
                st.rerun()
        with col2:
            btn_next_placeholder = col2.empty()
        
        # Vyčisti selected_trans_types a selected_channels aby ostali len z vybraných produktov
        selected_products_set = set(st.session_state.selected_products.keys())
        st.session_state.selected_trans_types = {
            (bl, prod, trans): alloc for (bl, prod, trans), alloc in st.session_state.selected_trans_types.items() 
            if (bl, prod) in selected_products_set
        }
        st.session_state.selected_channels = {
            (bl, prod, trans, chan): alloc for (bl, prod, trans, chan), alloc in st.session_state.selected_channels.items() 
            if (bl, prod) in selected_products_set
        }
        
        # FTE data
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = float(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        # Použij snapshot statusu z začiatku session (nie aktuálny, ktorý sa počas vyplňovania mení)
        current_status = st.session_state.current_status_snapshot
        use_current_version = get_status_hierarchy(current_status) >= get_status_hierarchy('Step3')
        
        # Načítaj existujúce hodnoty z predoslej Version pre dopĺňanie v Kroku 3
        prev_forms = get_existing_from_prev_version(st.session_state.cc, prev_version, saved_forms) if prev_version else pd.DataFrame()
        
        # Vytvorenie order dictionáries pre sortovanie
        # BL_ORDER - nájdi stĺpec s poradím
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
        for _, row in prod_mask_order.iterrows():
            prod = row['DOM_ABC_PRD_MASK']
            order = row.get('PROD_ORDER', 999)
            prod_order_dict[prod] = order
        
        # Sortuj selected_products podľa BL_ORDER a PROD_ORDER
        sorted_products = sorted(
            st.session_state.selected_products.items(),
            key=lambda x: (bl_order_dict.get(x[0][0], 999), prod_order_dict.get(x[0][1], 999))
        )
        
        # Vytvoríme slovník s tooltipmi pre aktivity
        gpm_tooltips = {}
        if gpm_order is not None and not gpm_order.empty:
            for _, gpm_row_data in gpm_order.iterrows():
                gpm_code = gpm_row_data.get('GPM_HIER', '')
                tooltip = gpm_row_data.get('TOOLTIP', '')
                if gpm_code and pd.notna(tooltip) and str(tooltip).strip():
                    gpm_tooltips[gpm_code] = str(tooltip).strip()
        
        # Funkcia na vytvorenie rozšíreného tooltipu s tabuľkou z TRX_COUNT
        def get_extended_tooltip(trans_type, bl, product, bl_order_data, prod_mask_data, trx_count_data, act_version_str):
            """Vytvorí rozšírený tooltip s TOOLTIP textom z gpm_order a tabuľkou z TRX_COUNT"""
            tooltip_parts = []
            
            # Najskôr pridaj TOOLTIP text z gpm_order ak existuje
            gpm_tooltip = gpm_tooltips.get(trans_type, '')
            if gpm_tooltip:
                tooltip_parts.append(gpm_tooltip)
            
            # Potom filtruj a pridaj tabuľku z TRX_COUNT ak existuje
            if trx_count_data is not None and not trx_count_data.empty:
                # Nájdi TXT_BUS_LINE z bl_order podľa bl
                bl_row = bl_order_data[bl_order_data['BL'] == bl]
                if not bl_row.empty:
                    txt_bus_line = bl_row.iloc[0].get('TXT_BUS_LINE', '')
                    subsegment = bl_row.iloc[0].get('SUBSEGMENT', '')
                else:
                    txt_bus_line = ''
                    subsegment = ''
                
                # Nájdi DOM_ABC_PROD z prod_mask_order podľa product
                # product je nemaskovaný názov (DOM_ABC_PRD_MASK), potrebujem DOM_ABC_PRD (skutočný názov v TRX_COUNT)
                prod_row = prod_mask_data[prod_mask_data['DOM_ABC_PRD_MASK'] == product]
                if not prod_row.empty:
                    # Skús najprv DOM_ABC_PRD, potom DOM_ABC_PROD
                    dom_abc_prod = prod_row.iloc[0].get('DOM_ABC_PRD', '')
                    if not dom_abc_prod:
                        dom_abc_prod = prod_row.iloc[0].get('DOM_ABC_PROD', '')
                else:
                    dom_abc_prod = product
                
                # Filtruj TRX_COUNT podľa všetkých kritérií
                filtered_trx = trx_count_data[
                    (trx_count_data['VERSION'].astype(str) == act_version_str) &
                    (trx_count_data['TXT_BUS_LINE'].astype(str).str.strip() == txt_bus_line.strip()) &
                    (trx_count_data['SUBSEGMENT'].astype(str).str.strip() == subsegment.strip()) &
                    (trx_count_data['DOM_ABC_PROD'].astype(str).str.strip() == dom_abc_prod.strip()) &
                    (trx_count_data['GPM_HIER'].astype(str).str.strip() == trans_type.strip())
                ]
                
                # Ak máme údaje, vytvor tabuľku
                if not filtered_trx.empty:
                    if tooltip_parts:  # Ak je už gpm_tooltip, pridaj separator
                        tooltip_parts.append("")
                    
                    # Pridaj hlavičky tabuľky
                    tooltip_parts.append("Transakcia                         Počet")
                    tooltip_parts.append("-" * 50)
                    
                    # Vytvor tabuľku s TXT_TRANS_DESC (bez prvých 6 znakov) a sumou FC
                    if 'TXT_TRANS_DESC' in filtered_trx.columns and 'FC' in filtered_trx.columns:
                        # Skupuj podľa TXT_TRANS_DESC a sumuj FC
                        trx_grouped = filtered_trx.groupby('TXT_TRANS_DESC')['FC'].sum().reset_index()
                        trx_grouped.columns = ['TXT_TRANS_DESC', 'FC']
                        
                        # Zisti max dĺžku popisov pre zarovnanie
                        max_desc_len = 0
                        for _, row in trx_grouped.iterrows():
                            desc = str(row['TXT_TRANS_DESC'])
                            if len(desc) > 6:
                                desc = desc[6:]
                            max_desc_len = max(max_desc_len, len(desc))
                        max_desc_len = min(max_desc_len, 40)  # Maximum 40 znakov
                        
                        # Vytvor čitateľnú tabuľku - znovu pridaj hlavičky s dynamickým zarovnaním
                        tooltip_parts = [part for part in tooltip_parts if not part.startswith("Transakcia")]  # Vymaž staré hlavičky
                        if tooltip_parts and tooltip_parts[-1].startswith("-"):  # Vymaž aj oddeľovač
                            tooltip_parts.pop()
                        
                        # Vytvor Markdown tabuľku
                        tooltip_parts.append("| Transakcia | Počet |")
                        tooltip_parts.append("|---|---|")
                        
                        # Pridaj dáta
                        for _, row in trx_grouped.iterrows():
                            desc = str(row['TXT_TRANS_DESC'])
                            # Odstráň prvých 6 znakov z TXT_TRANS_DESC
                            if len(desc) > 6:
                                desc = desc[6:]
                            
                            # Konvertuj FC na číslo
                            try:
                                fc_value = float(str(row['FC']).replace(',', '.'))
                                # Formátuj s medzerou ako tisícový oddeľovač
                                if fc_value >= 1000:
                                    fc_formatted = f"{int(fc_value):,}".replace(',', ' ')
                                else:
                                    fc_formatted = str(int(fc_value))
                            except:
                                fc_formatted = str(row['FC'])
                            
                            # Markdown tabuľka formát
                            tooltip_parts.append(f"| {desc} | {fc_formatted} |")
            
            return "\n".join(tooltip_parts) if tooltip_parts else ""
        
        for (bl, product), product_alloc in sorted_products:
            bl_alloc = st.session_state.selected_bls.get(bl, 0.0)
            weighted_fte = (bl_alloc / 100) * (product_alloc / 100) * num_fte_total
            st.markdown(f"### {bl} ({format_number(bl_alloc, 0)}%) - {product} ({format_number(product_alloc, 0)}%) - {format_number(weighted_fte, 2)} FTEs")
            
            trans_types = get_sorted_gpm(gpm_order, hierarchy, bl, product)
            selected_trans_types_list = []
            allocations = {}
            
            # Nadpisy stĺpcov
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
                    # Vytvor rozšírený tooltip s tabuľkou z TRX_COUNT
                    extended_tooltip = get_extended_tooltip(trans_type, bl, product, bl_order, prod_mask_order, trx_count, str(act_version))
                    if key not in st.session_state:
                        # Zaškrť checkbox len ak existuje v relevantnej verzii s hodnotou > 0
                        should_auto_check = False
                        masked_product = apply_product_mask(product, prod_mask_order)
                        
                        if use_current_version:
                            # STATUS >= Step3: zaškrť len ak existuje v aktualnej verzii s hodnotou > 0
                            # Hľadaj bez USER_ID, lebo CC zodpovedný sa môže zmeniť
                            if not saved_forms[
                                (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                                (saved_forms['VERSION'].astype(str) == str(act_version)) &
                                (saved_forms['BL'] == bl) &
                                (saved_forms['DOM_ABC_PROD'] == masked_product) &
                                (saved_forms['GPM_HIER'] == trans_type) &
                                (saved_forms['RAT_ACTIVITY'].astype(str).str.replace(',', '.').astype(float) > 0)
                            ].empty:
                                should_auto_check = True
                        else:
                            # STATUS < Step3: zaškrť len ak existuje v predoslej verzii s hodnotou > 0
                            if not prev_forms.empty and not prev_forms[
                                (prev_forms['BL'] == bl) & 
                                (prev_forms['DOM_ABC_PROD'] == masked_product) & 
                                (prev_forms['GPM_HIER'] == trans_type) &
                                (prev_forms['RAT_ACTIVITY'].astype(str).str.replace(',', '.').astype(float) > 0)
                            ].empty:
                                should_auto_check = True
                        
                        st.session_state[key] = (bl, product, trans_type) in st.session_state.selected_trans_types or should_auto_check
                    
                    if extended_tooltip:
                        checkbox_value = st.checkbox(trans_type, key=key, help=extended_tooltip)
                    else:
                        checkbox_value = st.checkbox(trans_type, key=key)
                    if checkbox_value:
                        selected_trans_types_list.append(trans_type)
                
                with col2:
                    if checkbox_value:
                        # Predvyplnenie: session_state > aktualnaVerzia > predoslaVerzia
                        default_value = 0.0
                        masked_product = apply_product_mask(product, prod_mask_order)
                        
                        # Priorita 1: session_state
                        if (bl, product, trans_type) in st.session_state.selected_trans_types:
                            default_value = st.session_state.selected_trans_types[(bl, product, trans_type)]
                        # Priorita 2: aktualnaVerzia (ak je STATUS >= Step3)
                        elif use_current_version:
                            current_row = saved_forms[
                                (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                                (saved_forms['VERSION'].astype(str) == str(act_version)) &
                                (saved_forms['BL'] == bl) &
                                (saved_forms['DOM_ABC_PROD'] == masked_product) &
                                (saved_forms['GPM_HIER'] == trans_type)
                            ]
                            if not current_row.empty:
                                default_value = float(str(current_row.iloc[0]['RAT_ACTIVITY']).replace(',', '.')) if pd.notna(current_row.iloc[0]['RAT_ACTIVITY']) else 0.0
                        # Priorita 3: predoslaVerzia (fallback)
                        else:
                            if not prev_forms.empty:
                                prev_row = prev_forms[
                                    (prev_forms['BL'] == bl) & 
                                    (prev_forms['DOM_ABC_PROD'] == masked_product) & 
                                    (prev_forms['GPM_HIER'] == trans_type)
                                ]
                                if not prev_row.empty:
                                    default_value = float(str(prev_row.iloc[0]['RAT_ACTIVITY']).replace(',', '.')) if pd.notna(prev_row.iloc[0]['RAT_ACTIVITY']) else 0.0
                        
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
            
            # Vymaž všetky aktivity pre tento BL/produkt a potom pridaj len vybrané
            st.session_state.selected_trans_types = {
                (b, p, t): alloc for (b, p, t), alloc in st.session_state.selected_trans_types.items() 
                if not (b == bl and p == product)
            }
            for trans_type in selected_trans_types_list:
                st.session_state.selected_trans_types[(bl, product, trans_type)] = allocations.get(trans_type, 0.0)
            
            st.markdown("---")
        
        # Umiestni "Ďalej" button na vrch v placeholder
        with btn_next_placeholder.container():
            if st.button("Ďalej →", type="primary", key="btn_step3_next", disabled=not all_valid, use_container_width=True):
                # Uložiť Krok 3 s STATUS=Step3 - uložiť IBA vybrané aktivity z vybraných BL/produktov
                if st.session_state.selected_trans_types:
                    idx = 0
                    for (bl, product, trans_type), allocation in st.session_state.selected_trans_types.items():
                        # Filtruj - ulož len aktivity z vybraných BL a produktov
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
                            # Vymaž staré riadky len pri prvej aktivite
                            save_form_step(st.session_state.user_id, st.session_state.cc, act_version, form_data, saved_forms, bl_order, 'Step3', is_first_in_step=(idx == 0))
                            idx += 1
                
                st.session_state.step = 'step4'
                st.rerun()
    
    # Etapa 5: Krok 4 - Výber kanálov
    elif st.session_state.step == 'step4':
        st.header("Krok 4: Výber kanálov")
        st.markdown("Pre každú vybranú aktivitu vyberte klientsky kanál a rozdeľte alokáciu (celkom 100% pre každú aktivitu).")
        
        # Inicializuj all_valid hneď na vrchu
        all_valid = True
        
        col1, col2, *_ = st.columns(10)
        with col1:
            if st.button("← Späť", key="btn_step4_back", use_container_width=True):
                st.session_state.step = 'step3'
                st.rerun()
        with col2:
            btn_done_placeholder = col2.empty()
        
        all_valid = True
        
        # Vyčisti selected_channels aby ostali len z vybraných aktivít
        selected_trans_types_set = set(st.session_state.selected_trans_types.keys())
        st.session_state.selected_channels = {
            (bl, prod, trans, chan): alloc for (bl, prod, trans, chan), alloc in st.session_state.selected_channels.items() 
            if (bl, prod, trans) in selected_trans_types_set
        }
        
        # Ak sú selected_channels prázdne, načítaj všetky kanály z aktualnej verzie (bez USER_ID)
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
                    channel_alloc = float(str(row['RAT_CHANNEL']).replace(',', '.')) if pd.notna(row['RAT_CHANNEL']) else 0.0
                    
                    # Načítaj len kanály, ktoré patria do vybraných aktivít
                    if channel and channel_alloc > 0 and (bl, product, trans_type) in st.session_state.selected_trans_types:
                        st.session_state.selected_channels[(bl, product, trans_type, channel)] = channel_alloc
        
        # FTE data
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = float(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        # Použij snapshot statusu z začiatku session (nie aktuálny, ktorý sa počas vyplňovania mení)
        current_status = st.session_state.current_status_snapshot
        use_current_version = get_status_hierarchy(current_status) >= get_status_hierarchy('Submitted')
        
        # Načítať formuláre z predošlej verzie na predvyplnenie
        prev_forms = get_existing_from_prev_version(st.session_state.cc, prev_version, saved_forms) if prev_version else pd.DataFrame()
        
        # Vytvorenie BL/Product/Trans_type order dictionáries pre sortovanie
        # BL_ORDER - nájdi stĺpec s poradím
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
        for _, row in prod_mask_order.iterrows():
            prod = row['DOM_ABC_PRD_MASK']
            order = row.get('PROD_ORDER', 0)
            prod_order_dict[prod] = order
        
        # GPM_ORDER dict
        gpm_order_dict = {}
        if gpm_order is not None and not gpm_order.empty:
            for _, row in gpm_order.iterrows():
                gpm_hier = row['GPM_HIER']
                order = row.get('GPM_ORDER', 999)
                gpm_order_dict[gpm_hier] = order
        
        channel_order_dict = {}
        for _, row in channel_mask_order.iterrows():
            channel = row['CHANNEL_ABC_MASK']
            order = row.get('CHANNEL_ORDER', 0)
            channel_order_dict[channel] = order
        
        # Vytvoríme slovník s tooltipmi pre kanály
        channel_tooltips = {}
        for _, channel_row_data in channel_mask_order.iterrows():
            channel_code = channel_row_data.get('CHANNEL_ABC_MASK', '')
            tooltip = channel_row_data.get('TOOLTIP', '')
            if channel_code and pd.notna(tooltip) and str(tooltip).strip():
                channel_tooltips[channel_code] = str(tooltip).strip()
        
        all_valid = True
        
        # Sortuj selected_trans_types podľa BL_ORDER, PROD_ORDER a GPM_ORDER
        sorted_trans_types = sorted(
            st.session_state.selected_trans_types.keys(),
            key=lambda x: (bl_order_dict.get(x[0], 999), prod_order_dict.get(x[1], 999), gpm_order_dict.get(x[2], 999))
        )
        
        # Iteruj podľa uložených/vybraných aktivít v správnom poradí
        for (bl, product, trans_type) in sorted_trans_types:
            # Zistí percentá pre tento blok
            bl_alloc = st.session_state.selected_bls.get(bl, 0.0)
            product_alloc = st.session_state.selected_products.get((bl, product), 0.0)
            trans_alloc = st.session_state.selected_trans_types.get((bl, product, trans_type), 0.0)
            weighted_fte = (bl_alloc / 100) * (product_alloc / 100) * (trans_alloc / 100) * num_fte_total
            
            st.markdown(f"### {bl} ({format_number(bl_alloc, 0)}%) - {product} ({format_number(product_alloc, 0)}%) - {trans_type} ({format_number(trans_alloc, 0)}%) - {format_number(weighted_fte, 2)} FTEs")
            
            # Načítaj dostupné kanály pre túto aktivitu
            channels = get_sorted_channels(channel_mask_order, hierarchy, bl, product, trans_type)
            # Sortuj kanály podľa CHANNEL_ORDER
            channels = sorted(channels, key=lambda c: channel_order_dict.get(c, 999))
            
            # Nadpisy stĺpcov
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
                    # Kontrola, či má kanál tooltip
                    tooltip_text = channel_tooltips.get(channel, '')
                    
                    # Zaškrť checkbox len ak existuje v relevantnej verzii s hodnotou > 0
                    should_auto_check = False
                    masked_product = apply_product_mask(product, prod_mask_order)
                    masked_channel = apply_channel_mask(channel, channel_mask_order)
                    
                    if use_current_version:
                        # STATUS >= Submitted: zaškrť len ak existuje v aktualnej verzii s hodnotou > 0
                        # Hľadaj bez USER_ID, lebo CC zodpovedný sa môže zmeniť (ako v get_current_status)
                        if not saved_forms[
                            (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                            (saved_forms['VERSION'].astype(str) == str(act_version)) &
                            (saved_forms['BL'] == bl) & 
                            (saved_forms['DOM_ABC_PROD'] == masked_product) & 
                            (saved_forms['GPM_HIER'] == trans_type) &
                            (saved_forms['TXT_CHANNEL'] == masked_channel) &
                            (saved_forms['RAT_CHANNEL'].astype(str).str.replace(',', '.').astype(float) > 0)
                        ].empty:
                            should_auto_check = True
                    else:
                        # STATUS < Submitted: zaškrť len ak existuje v predoslej verzii s hodnotou > 0
                        if not prev_forms.empty and not prev_forms[
                            (prev_forms['BL'] == bl) & 
                            (prev_forms['DOM_ABC_PROD'] == masked_product) & 
                            (prev_forms['GPM_HIER'] == trans_type) &
                            (prev_forms['TXT_CHANNEL'] == masked_channel) &
                            (prev_forms['RAT_CHANNEL'].astype(str).str.replace(',', '.').astype(float) > 0)
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
                        # Najprv skúsiť načítať z aktualnej verzie, potom z predošlej
                        default_value = 0.0
                        masked_product = apply_product_mask(product, prod_mask_order)
                        masked_channel = apply_channel_mask(channel, channel_mask_order)
                        
                        # Priorita 1: session_state
                        if (bl, product, trans_type, channel) in st.session_state.selected_channels:
                            default_value = st.session_state.selected_channels[(bl, product, trans_type, channel)]
                        # Priorita 2: aktualnaVerzia (ak je STATUS >= Submitted)
                        elif use_current_version:
                            # Hľadaj bez USER_ID, lebo CC zodpovedný sa môže zmeniť (ako v get_current_status)
                            current_forms = saved_forms[
                                (saved_forms['CC'].astype(str) == str(st.session_state.cc)) &
                                (saved_forms['VERSION'].astype(str) == str(act_version)) &
                                (saved_forms['BL'] == bl) & 
                                (saved_forms['DOM_ABC_PROD'] == masked_product) & 
                                (saved_forms['GPM_HIER'] == trans_type) &
                                (saved_forms['TXT_CHANNEL'] == masked_channel)
                            ]
                            if not current_forms.empty:
                                default_value = float(str(current_forms.iloc[0]['RAT_CHANNEL']).replace(',', '.')) if pd.notna(current_forms.iloc[0]['RAT_CHANNEL']) else 0.0
                        # Priorita 3: predoslaVerzia (fallback)
                        else:
                            if not prev_forms.empty:
                                prev_row = prev_forms[
                                    (prev_forms['BL'] == bl) & 
                                    (prev_forms['DOM_ABC_PROD'] == masked_product) & 
                                    (prev_forms['GPM_HIER'] == trans_type) &
                                    (prev_forms['TXT_CHANNEL'] == masked_channel)
                                ]
                                if not prev_row.empty:
                                    default_value = float(str(prev_row.iloc[0]['RAT_CHANNEL']).replace(',', '.')) if pd.notna(prev_row.iloc[0]['RAT_CHANNEL']) else 0.0
                        
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
            
            # Overenie posledného bloku
            total_allocation = sum(allocations.values())
            if len(selected_channels_list) == 0:
                st.warning(f"⚠️ Musíte vybrať aspoň jeden kanál pre {trans_type}")
                all_valid = False
            elif abs(total_allocation - 100.0) > 0.01:
                st.error(f"⚠️ Alokácia pre {trans_type} musí byť presne 100%. Aktuálne: {format_number(total_allocation, 1)}%")
                all_valid = False
            
            # Vymaž všetky kanály pre túto aktivitu a potom pridaj len vybrané
            st.session_state.selected_channels = {
                (b, p, t, c): alloc for (b, p, t, c), alloc in st.session_state.selected_channels.items() 
                if not (b == bl and p == product and t == trans_type)
            }
            for channel in selected_channels_list:
                st.session_state.selected_channels[(bl, product, trans_type, channel)] = allocations.get(channel, 0.0)
            
            st.markdown("---")
        
        # Umiestni "Hotovo" button na vrch v placeholder
        with btn_done_placeholder.container():
            if st.button("Hotovo", type="primary", key="btn_step4_done", disabled=not all_valid, use_container_width=True):
                # Uložiť Krok 4 s STATUS=Submitted - uložiť IBA kanály z vybraných BL/produktov/aktivít
                if st.session_state.selected_channels:
                    idx = 0
                    for (bl, product, trans_type, channel), allocation in st.session_state.selected_channels.items():
                        # Filtruj - ulož len kanály z vybraných BL, produktov a aktivít
                        if (bl in st.session_state.selected_bls and 
                            (bl, product) in st.session_state.selected_products and 
                            (bl, product, trans_type) in st.session_state.selected_trans_types and
                            allocation > 0):
                            # Aplikuj masku na názvy pri ukladaní
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
                            # Vymaž staré riadky len pri prvom kanále
                            save_form_step(st.session_state.user_id, st.session_state.cc, act_version, form_data, saved_forms, bl_order, 'Submitted', is_first_in_step=(idx == 0))
                            idx += 1
                
                st.session_state.step = 'summary'
                st.rerun()
    
    # Etapa BS: BS Step 1 - Výber BL a RAT_TOTAL
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
        
        # FTE data
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = float(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
        # Načítaj existujúce hodnoty z aktualnej alebo predoslej verzie
        existing = get_existing_forms_by_status_bs(st.session_state.cc, act_version, saved_bs)
        if existing.empty and prev_version:
            existing = get_existing_bs_from_prev_version(st.session_state.cc, prev_version, saved_bs)
        
        # Naplň session state podľa existujúcich dát
        if not existing.empty:
            for _, row in existing.iterrows():
                bl = row['BL'] if pd.notna(row['BL']) and row['BL'] != '' else None
                rat_total = float(str(row['RAT_TOTAL']).replace(',', '.')) if pd.notna(row['RAT_TOTAL']) else 0
                if bl and rat_total > 0:
                    st.session_state.selected_bls[bl] = rat_total
        
        # Vytvoríme slovník s tooltipmi pre BL
        bl_tooltips = {}
        for _, bl_row_data in bl_order.iterrows():
            bl_code = bl_row_data.get('BL', '')
            tooltip = bl_row_data.get('TOOLTIP', '')
            if bl_code and pd.notna(tooltip) and str(tooltip).strip():
                bl_tooltips[bl_code] = str(tooltip).strip()
        
        # Nadpisy stĺpcov
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
            
            # Kontrola, či má BL tooltip
            tooltip_text = bl_tooltips.get(bl, '')
            display_label = label
            
            checkbox_key = f"bs_bl_check_{bl}_{idx}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = bl in st.session_state.selected_bls
            
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                if tooltip_text:
                    checkbox_value = st.checkbox(display_label, key=checkbox_key, help=tooltip_text)
                else:
                    checkbox_value = st.checkbox(display_label, key=checkbox_key)
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
        
        # Umiestni "Hotovo" button na vrch v placeholder
        with btn_done_placeholder.container():
            if st.button("Hotovo", type="primary", key="btn_bs_step1_done", disabled=len(selected_bls_list) == 0 or abs(total_allocation - 100.0) > 0.01, use_container_width=True):
                st.session_state.selected_bls = allocations.copy()
                
                # Uložiť BS formulár
                if st.session_state.selected_bls:
                    save_form_bs(st.session_state.user_id, st.session_state.cc, act_version, st.session_state.selected_bls, saved_bs, bl_order)
                
                st.session_state.step = 'bs_summary'
                st.rerun()
    
    # Etapa BS Summary: Zhrnutie pre BS
    elif st.session_state.step == 'bs_summary':
        st.header("✅ Zhrnutie alokácie")
        st.success("Všetky alokácie boli úspešne zadané!")
        
        if st.button("← Späť", key="btn_bs_summary_back"):
            st.session_state.step = 'bs_step1'
            st.rerun()
        
        # Príprava dát pre zobrazenie
        results = []
        
        # FTE data
        fte_row = fte_data[fte_data['CC'].astype(str) == str(st.session_state.cc)]
        num_fte_total = float(fte_row['NUM_FTE'].values[0]) if not fte_row.empty else 0
        
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
                # Konvertuj dataframe na CSV s správnym kódovaním a desatinným oddeľovačom
                csv_df = results_df.copy()
                # Nahraď bodky čiarkami v numerických stĺpcoch
                numeric_cols = ['Alokácia (%)', 'FTE']
                for col in numeric_cols:
                    if col in csv_df.columns:
                        csv_df[col] = csv_df[col].str.replace('.', ',')
                
                # Export s cp1250 kódovaním a separátorom ;
                csv_string = csv_df.to_csv(index=False, sep=';')
                csv_bytes = csv_string.encode(encoding_type, errors='replace')
                
                # Vytvor filename
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
                    mime="text/csv;charset=cp1250"
                )
    
    # Etapa 6: Zhrnutie
    elif st.session_state.step == 'summary':
        st.header("✅ Zhrnutie alokácie")
        st.success("Všetky alokácie boli úspešne zadané!")
        
        if st.button("← Späť", key="btn_summary_back"):
            st.session_state.step = 'step4'
            st.rerun()
        
        # Príprava dát pre zobrazenie
        results = []
        final_total = 0.0
        
        # FTE data
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
                # Konvertuj dataframe na CSV s správnym kódovaním a desatinným oddeľovačom
                csv_df = results_df.copy()
                # Nahraď bodky čiarkami v numerických stĺpcoch
                numeric_cols = ['BL (%)', 'Product (%)', 'Aktivita (%)', 'Kanál (%)', 'Alokácia (%)', 'Weighted FTE']
                for col in numeric_cols:
                    if col in csv_df.columns:
                        csv_df[col] = csv_df[col].str.replace('.', ',')
                
                # Export s cp1250 kódovaním a separátorom ;
                # Najprv vytvor CSV ako string
                csv_string = csv_df.to_csv(index=False, sep=';')
                # Konvertuj na bytes s cp1250 kódovaním
                csv_bytes = csv_string.encode(encoding_type, errors='replace')
                
                # Vytvor filename
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
                    mime="text/csv;charset=cp1250"
                )

if __name__ == "__main__":
    main()
