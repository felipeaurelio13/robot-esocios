"""
Configuración para el Revisor de Juntas de EVoting.
"""
import os
import logging
from dotenv import load_dotenv

# --- Configuración del Logger para este módulo ---
logger_cfg = logging.getLogger(f"{__name__}.config_loader") 
if not logger_cfg.handlers and not logging.getLogger().handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - CFG: %(message)s')
    ch.setFormatter(formatter)
    logger_cfg.addHandler(ch)
    logger_cfg.setLevel(logging.INFO)
elif not logger_cfg.handlers: # Si el logger raíz tiene handlers, heredamos pero seteamos nivel.
    logger_cfg.setLevel(logging.INFO) 

# --- Carga de .env ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path_calculated = os.path.join(project_root, '.env')

logger_cfg.info(f"[CONFIG_LOAD] Directorio raíz del proyecto: {project_root}")
logger_cfg.info(f"[CONFIG_LOAD] Ruta absoluta esperada para .env: {dotenv_path_calculated}")

found_dotenv = os.path.exists(dotenv_path_calculated)
if found_dotenv:
    load_dotenv(dotenv_path=dotenv_path_calculated, override=True)
    logger_cfg.info(f"[CONFIG_LOAD] .env encontrado y cargado desde: {dotenv_path_calculated}")
else:
    logger_cfg.warning(f"[CONFIG_LOAD] Archivo .env NO encontrado en {dotenv_path_calculated}. Se usarán valores por defecto o del sistema.")

# --- Configuración de la Aplicación/EVoting ---
EVOTING_BASE_URL = os.getenv("EVOTING_BASE_URL", "https://eholders-mgnt.evoting.com")
EVOTING_USERNAME = os.getenv("EVOTING_USERNAME")
EVOTING_PASSWORD = os.getenv("EVOTING_PASSWORD")

if not EVOTING_USERNAME or not EVOTING_PASSWORD:
     logger_cfg.warning("CFG WARN: EVOTING_USERNAME o EVOTING_PASSWORD no están configurados.")

# --- Configuración de Selenium (HEADLESS_MODE) ---
raw_headless_mode = os.getenv("HEADLESS_MODE", "False") # Default es "False" (string)
HEADLESS_MODE = raw_headless_mode.lower() == "true"

logger_cfg.info(f"[CONFIG_LOAD] os.getenv('HEADLESS_MODE', 'False') devolvió: '{raw_headless_mode}'")
logger_cfg.info(f"[CONFIG_LOAD] HEADLESS_MODE procesado como: {HEADLESS_MODE} (Tipo: {type(HEADLESS_MODE)})")

IMPLICIT_WAIT = int(os.getenv("IMPLICIT_WAIT", "10"))
PAGE_LOAD_TIMEOUT = int(os.getenv("PAGE_LOAD_TIMEOUT", "30"))
POST_LOGIN_WAIT = int(os.getenv("POST_LOGIN_WAIT", "3"))

# --- Configuración de OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger_cfg.warning("CFG WARN: OPENAI_API_KEY no está configurado.")

# --- Rutas y Directorios (Asegúrate que ROOT_DIR y otros paths se definan correctamente si los usas) ---
ROOT_DIR = project_root # project_root ya es el directorio raíz
DATA_DIR = os.path.join(ROOT_DIR, "data")
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
REPORTS_DIR = os.path.join(ROOT_DIR, "reports")

for directory in [UPLOAD_FOLDER, REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)

# --- Google Sheets ---
SPREADSHEET_URL_OR_ID = os.getenv("SPREADSHEET_URL_OR_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "Slugs")
if not SPREADSHEET_URL_OR_ID:
    logger_cfg.warning("CFG WARN: SPREADSHEET_URL_OR_ID no está configurado.")

# Extensiones de archivo permitidas para carga
ALLOWED_EXTENSIONS = os.getenv("ALLOWED_EXTENSIONS", "pdf,png,jpg,jpeg,txt,json").split(',')
ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in ALLOWED_EXTENSIONS if ext.strip()} # Convert to set

# Directorios
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates") # For HTML templates
