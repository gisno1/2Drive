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
        

    def get_parts(self):
        """Haalt onderdelen op en voegt de InvoicedDate toe."""
        
        wo_259 = self.get_data('GetAftersalesForAffiliateExtended?AffiliateId=259')[['WONUMMER', 'InvoicedDate']]
        wo_261 = self.get_data('GetAftersalesForAffiliateExtended?AffiliateId=261')[['WONUMMER', 'InvoicedDate']]

        onderdelen_259 = self.get_data('GetAftersalesPartsForAffiliateExtended?AffiliateId=259').merge(wo_259, on='WONUMMER', how='left')
        onderdelen_261 = self.get_data('GetAftersalesPartsForAffiliateExtended?AffiliateId=261').merge(wo_261, on='WONUMMER', how='left')

        df = pd.concat([onderdelen_259, onderdelen_261], ignore_index=True)

        affiliate_mapping = {259: 'Tilburg', 261: 'Rotterdam'}
        df['AffiliateId'] = df['AffiliateId'].replace(affiliate_mapping)

        df['InvoicedDate'] = pd.to_datetime(df['InvoicedDate'], errors='coerce').dt.strftime('%d-%m-%Y')
        
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
        
        return history


@st.cache_data
def load_data():
    """Laadt de data eenmalig en cache deze."""
    client = APIClient()
    return client.get_parts()

def main():
    st.title("Prijshistorie van onderdelen")

    data = load_data()

    onderdeelnummer = st.text_input("Voer het onderdeelnummer in:")

    if onderdeelnummer:
        client = APIClient()
        history = client.get_price_history(data, onderdeelnummer)

        if history is not None:
            st.write(f"Prijshistorie voor onderdeelnummer {onderdeelnummer}:")
            st.write(history)
        else:
            st.write(f"Geen resultaten gevonden voor onderdeelnummer {onderdeelnummer}.")


if __name__ == '__main__':
    main()