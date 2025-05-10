"""
Configuración para el Revisor de Juntas de EVoting.
"""
import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno desde .env (si existe)
load_dotenv()

# --- Configuración de la Aplicación/EVoting ---
# Usar variable de entorno o un valor por defecto razonable
EVOTING_BASE_URL = os.getenv("EVOTING_BASE_URL", "https://eholders-mgnt.evoting.com") # Replace default with actual if known

# Credenciales (usar variables de entorno es lo más seguro)
EVOTING_USERNAME = os.getenv("EVOTING_USERNAME") # No default username
EVOTING_PASSWORD = os.getenv("EVOTING_PASSWORD") # No default password

# Advertir si las credenciales no están configuradas
if not EVOTING_USERNAME or not EVOTING_PASSWORD:
     logging.warning("EVOTING_USERNAME o EVOTING_PASSWORD no están configuradas en las variables de entorno. El login fallará.")

# Configuración de Selenium
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "False").lower() == "true"
IMPLICIT_WAIT = int(os.getenv("IMPLICIT_WAIT", "10"))
PAGE_LOAD_TIMEOUT = int(os.getenv("PAGE_LOAD_TIMEOUT", "30"))
POST_LOGIN_WAIT = int(os.getenv("POST_LOGIN_WAIT", "3")) # Reducido, waits explícitos son mejores

# Configuración de OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # No default key
if not OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY no está configurado. El procesamiento de documentos fallará.")

# Extensiones de archivo permitidas para carga
ALLOWED_EXTENSIONS = os.getenv("ALLOWED_EXTENSIONS", "pdf,png,jpg,jpeg,txt,json").split(',')
ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in ALLOWED_EXTENSIONS if ext.strip()} # Convert to set

# Directorios
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data") # General data
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads") # Specific for uploads
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates") # For HTML templates
REPORTS_DIR = os.path.join(ROOT_DIR, "reports") # For final JSON reports

# Asegurar que los directorios de datos y reportes existan
for directory in [UPLOAD_FOLDER, REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)
