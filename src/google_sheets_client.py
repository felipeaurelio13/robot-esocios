import gspread
from google.oauth2.service_account import Credentials
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the scope for Google Sheets API
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

# Path to the service account key file
# Ensure 'actualizacion-padron-b0c0035f9580.json' is in the project root or specify the correct path.
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'actualizacion-padron-b0c0035f9580.json')

def get_google_sheets_client():
    """Autentica con Google Sheets API y devuelve un cliente gspread.

    Returns:
        gspread.Client: Cliente gspread autenticado.
        None: Si la autenticación falla.
    """
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPE)
        client = gspread.authorize(creds)
        logger.info("Autenticación con Google Sheets exitosa.")
        return client
    except FileNotFoundError:
        logger.error(f"Archivo de credenciales no encontrado en: {SERVICE_ACCOUNT_FILE}")
        raise
    except Exception as e:
        logger.error(f"Error durante la autenticación con Google Sheets: {e}", exc_info=True)
        raise

def read_sheet_data(spreadsheet_name_or_url: str, sheet_name: str) -> list[dict]:
    """Lee datos de una hoja específica en un Google Sheet.

    Args:
        spreadsheet_name_or_url (str): Nombre o URL del Google Sheet.
        sheet_name (str): Nombre de la hoja dentro del spreadsheet.

    Returns:
        list[dict]: Una lista de diccionarios, donde cada diccionario representa una fila.
                    Las claves del diccionario son los encabezados de las columnas.
                    Devuelve una lista vacía si la hoja está vacía o ocurre un error.
    """
    client = get_google_sheets_client()
    if not client:
        return []

    try:
        if spreadsheet_name_or_url.startswith("https://"):
            spreadsheet = client.open_by_url(spreadsheet_name_or_url)
            logger.info(f"Abriendo spreadsheet por URL: {spreadsheet_name_or_url}")
        else:
            # Asumir que si no es una URL, es un ID/key para abrir con open_by_key
            # O podría ser un nombre, pero open_by_key fallará si no es un ID válido.
            # Dado que el runner pasa un ID, priorizamos open_by_key.
            logger.info(f"Intentando abrir spreadsheet por key/ID: {spreadsheet_name_or_url}")
            spreadsheet = client.open_by_key(spreadsheet_name_or_url) 
        
        worksheet = spreadsheet.worksheet(sheet_name)
        records = worksheet.get_all_records()
        logger.info(f"Datos leídos de la hoja '{sheet_name}' en el spreadsheet '{spreadsheet_name_or_url}'.")
        return records
    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(f"Spreadsheet no encontrado: '{spreadsheet_name_or_url}'. Verifica el nombre o URL.")
        raise
    except gspread.exceptions.WorksheetNotFound:
        logger.error(f"Hoja no encontrada: '{sheet_name}' en el spreadsheet '{spreadsheet_name_or_url}'.")
        raise
    except Exception as e:
        logger.error(f"Error al leer datos de Google Sheets: {e}", exc_info=True)
        # Podríamos querer devolver una lista vacía o propagar la excepción según el caso de uso.
        # Por ahora, propagamos para ser explícitos sobre el fallo.
        raise

def update_cell_in_sheet(spreadsheet_url_or_id: str, sheet_name: str, row_index: int, col_index: int, value: str) -> bool:
    """Actualiza una celda específica en una Google Sheet.

    Args:
        spreadsheet_url_or_id (str): La URL completa de la Google Sheet o su ID.
        sheet_name (str): El nombre de la pestaña (worksheet) a leer.
        row_index (int): El índice de la fila a actualizar (1-based).
        col_index (int): El índice de la columna a actualizar (1-based).
        value (str): El valor a escribir en la celda.

    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario.
    """
    try:
        client = get_google_sheets_client()
        if not client:
            logger.error("No se pudo obtener el cliente de Google Sheets para actualizar la celda.")
            return False

        logger.info(f"Intentando actualizar celda ({row_index}, {col_index}) en '{sheet_name}' con valor '{value}'")
        
        # Intentar abrir por URL o por ID
        try:
            if spreadsheet_url_or_id.startswith("https://"):
                spreadsheet = client.open_by_url(spreadsheet_url_or_id)
            else:
                spreadsheet = client.open_by_key(spreadsheet_url_or_id)
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"Spreadsheet no encontrado con URL/ID: {spreadsheet_url_or_id}")
            return False
        except Exception as e:
            logger.error(f"Error al abrir spreadsheet '{spreadsheet_url_or_id}': {e}", exc_info=True)
            return False

        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"Worksheet '{sheet_name}' no encontrado en el spreadsheet.")
            return False
        except Exception as e:
            logger.error(f"Error al abrir worksheet '{sheet_name}': {e}", exc_info=True)
            return False
            
        worksheet.update_cell(row_index, col_index, value)
        logger.info(f"Celda ({row_index}, {col_index}) en '{sheet_name}' actualizada exitosamente a '{value}'.")
        return True

    except gspread.exceptions.APIError as e:
        logger.error(f"Error de API de Google Sheets al actualizar celda ({row_index}, {col_index}) con valor '{value}': {e}", exc_info=True)
        # Podríamos querer verificar e.response.status_code aquí para más detalles
        if 'exceeded' in str(e).lower() and ('quota' in str(e).lower() or 'limit' in str(e).lower()):
            logger.warning("Se ha alcanzado un límite de cuota de la API de Google Sheets. Intentar más tarde.")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al actualizar celda ({row_index}, {col_index}) con valor '{value}': {e}", exc_info=True)
        return False

if __name__ == '__main__':
    # Ejemplo de uso (requiere configuración de credenciales y spreadsheet_details)
    # Descomentar y reemplazar con valores reales para probar.
    
    # TEST_SPREADSHEET_NAME = "Tu Nombre de Spreadsheet Aquí" 
    # TEST_SHEET_NAME = "Hoja1"
    
    # logger.info(f"Intentando leer: {TEST_SPREADSHEET_NAME} - Hoja: {TEST_SHEET_NAME}")
    # data = read_sheet_data(TEST_SPREADSHEET_NAME, TEST_SHEET_NAME)
    # if data:
    #     logger.info(f"Primeras 5 filas de datos: {data[:5]}")
    # else:
    #     logger.warning("No se pudieron obtener datos o la hoja está vacía.")
    pass 