import requests
import time
import pandas as pd
import streamlit as st

class APIClient:

    def __init__(self):
        self.api_base_url = 'https://app-2drive-dab2-100330.proudwave-fe47a2ed.westeurope.azurecontainerapps.io/api'
        self.auth_url = 'https://vinacles.eu.auth0.com/oauth/token'
        self.auth_credentials = {
            'client_id': 'NlZMoM5v9XBGMpXrRKzqgzzviSZUs9Dp',
            'client_secret': 's_qkClB-Ms8Kzzd17HftdZVHeR1lnp9QWFyroJ0PRNIkN0cxieJm9Mc8YeJ82YYZ',
            'audience': 'api:vinalces.dab.100330',
            'grant_type': 'client_credentials'
        }
        
        self.access_token = None
        self.token_expiry = None  


    def get_token(self):
        """Haalt een nieuw access token op bij Auth0 als het huidige token verlopen is."""

        if self.access_token and time.time() < self.token_expiry:
            
            return self.access_token  

        try:
            response = requests.post(
                self.auth_url,
                json=self.auth_credentials,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status() 

            token_data = response.json()
            self.access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 0)  
            self.token_expiry = time.time() + expires_in

            return self.access_token
        
        except requests.exceptions.RequestException as e:
            print(f'Fout bij ophalen token: {e}')
            
            return None



    def get_data(self, endpoint):
        """Maakt een GET-aanroep naar het opgegeven API-endpoint."""
        
        token = self.get_token()
        if not token:
            print('Geen geldig token beschikbaar. Kan de API niet aanroepen.')
            
            return None

        try:
            response = requests.get(
                f'{self.api_base_url}/{endpoint}',
                headers={'Authorization': f'Bearer {token}'}
            )

            response.raise_for_status()
            data = response.json() 
            
            return pd.DataFrame(data.get('value', [])) 
        
        except requests.exceptions.RequestException as e:
            print(f'Fout bij ophalen data van {endpoint}: {e}')
            
            return None
        


    def empty_df(self, columns):
        """Geeft een lege DataFrame met vaste kolommen terug."""
        
        return pd.DataFrame(columns=columns)



    def get_parts_for_affiliate(self, affiliate_id, label):

        wo = self.get_data(
            f'GetAftersalesForAffiliateExtended?AffiliateId={affiliate_id}'
        )

        if wo is None:
            st.warning(f"⚠️ Werkorders niet geladen ({label})")
            return pd.DataFrame()

        wo = wo[['WONUMMER', 'InvoicedDate']]

        time.sleep(0.4)

        onderdelen = self.get_data(
            f'GetAftersalesPartsForAffiliateExtended?AffiliateId={affiliate_id}'
        )

        if onderdelen is None:
            st.warning(f"⚠️ Onderdelen niet geladen ({label})")
            return pd.DataFrame()

        df = onderdelen.merge(wo, on='WONUMMER', how='left')

        df['AffiliateId'] = label
        df['InvoicedDate'] = pd.to_datetime(
            df['InvoicedDate'], errors='coerce'
        ).dt.strftime('%d-%m-%Y')

        
        df = df.rename(columns={
            'PartNumber': 'Onderdeelnummer',
            'Price': 'Verkoopprijs',
            'CompanyName': 'Relatie',
            'AffiliateId': 'Vestiging',
            'InvoicedDate': 'Factuurdatum'
        })

        return df



    def get_price_history(self, df, onderdeelnummer):
        """Geeft de prijs historie van een onderdeelnummer weer."""
        
        history = df[df['Onderdeelnummer'] == onderdeelnummer][['Onderdeelnummer', 'Verkoopprijs', 'Relatie', 'Vestiging', 'Factuurdatum']]
        
        if history.empty:
            return None
        
        history['Factuurdatum'] = pd.to_datetime(history['Factuurdatum'], dayfirst=True, errors='coerce')
        history = history.sort_values(by='Factuurdatum', ascending=False)
        history['Factuurdatum'] = history['Factuurdatum'].dt.strftime('%d-%m-%Y')

        return history

@st.cache_resource
def get_api_client():
    return APIClient()


@st.cache_data(ttl=3600)
def load_data_for_affiliate(affiliate_id, label):
    client = get_api_client()
    return client.get_parts_for_affiliate(affiliate_id, label)


def main():
    st.title('Prijshistorie van onderdelen')
    
    correct_password = st.secrets["auth"]["password"]

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:

        password_input = st.text_input("Voer het wachtwoord in:", type="password")

        if st.button("Inloggen"):
            if password_input == correct_password:
                st.session_state.authenticated = True
                # st.experimental_rerun()  
                st.rerun() 
            else:
                st.warning("Onjuist wachtwoord. Probeer opnieuw.")
                st.session_state.authenticated = False
        return  
    
    affiliate_map = {
        "Tilburg": 259,
        "Rotterdam": 261,
        "Heerhugowaard": 467
    }

    vestiging = st.selectbox(
        "Kies een vestiging",
        list(affiliate_map.keys())
    )

    affiliate_id = affiliate_map[vestiging]
    data = load_data_for_affiliate(affiliate_id, vestiging)

    if data.empty:
        st.warning("Geen data beschikbaar voor deze vestiging")
        st.stop()


    onderdeelnummer = st.text_input('Voer het onderdeelnummer in:')

    if onderdeelnummer:
        client = get_api_client()
        history = client.get_price_history(data, onderdeelnummer)

        if history is not None:
            st.write(f'Prijshistorie voor onderdeelnummer {onderdeelnummer}:')
            history.index = range(1, len(history) + 1)
            st.dataframe(history)

        else:
            st.write(f'Geen resultaten gevonden voor onderdeelnummer {onderdeelnummer}.')


if __name__ == '__main__':
    main()