"""
Configuración del WebDriver para Selenium.
"""
import os
import stat
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv
from src.config import IMPLICIT_WAIT, PAGE_LOAD_TIMEOUT
import logging

# Configurar logger para este módulo
logger_setup = logging.getLogger(__name__)
if not logger_setup.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - WEBDRIVER_SETUP: %(message)s')
    handler.setFormatter(formatter)
    logger_setup.addHandler(handler)
    logger_setup.setLevel(logging.INFO)

# Load .env file
# load_dotenv() # Comentado o eliminado, se cargará en el runner principal

def setup_webdriver(headless_mode: bool):
    """
    Configura y devuelve una instancia del WebDriver de Chrome.
    Usa el modo headless provisto como argumento.

    Args:
        headless_mode (bool): True para ejecutar en modo headless, False para modo normal.

    Returns:
        webdriver.Chrome: Instancia configurada del WebDriver o None si falla.
    """
    logger_setup.info(f"Función setup_webdriver llamada con headless_mode: {headless_mode} (Tipo: {type(headless_mode)})")

    try:
        chrome_options = Options()
        if headless_mode:
            chrome_options.add_argument("--headless=new")
            logger_setup.info("Chrome configurado para ejecutarse en modo headless (nuevo).")
        else:
            logger_setup.info("Chrome configurado para ejecutarse en modo normal (con UI).")
        
        chrome_options.add_argument("--disable-gpu") # A menudo recomendado para headless
        chrome_options.add_argument("--window-size=1920,1080") # Puede ayudar en algunos casos
        chrome_options.add_argument("--no-sandbox") # Necesario en algunos entornos CI/Linux
        chrome_options.add_argument("--disable-dev-shm-usage") # Supera problemas de recursos limitados
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")

        logger_setup.info("Inicializando ChromeDriverManager...")
        base_driver_path_info = ChromeDriverManager().install()
        logger_setup.info(f"ChromeDriverManager().install() devolvió: {base_driver_path_info}")

        # --- Lógica para determinar la ruta correcta al ejecutable --- 
        # Esto es un workaround para el problema de que a veces se selecciona el archivo de notices.
        if "THIRD_PARTY_NOTICES" in base_driver_path_info:
            executable_path = os.path.join(os.path.dirname(base_driver_path_info), "chromedriver")
            logger_setup.warning(f"ChromeDriverManager devolvió ruta a notices. Intentando ruta construida: {executable_path}")
        elif os.path.isdir(base_driver_path_info) and not os.path.isfile(os.path.join(base_driver_path_info, "chromedriver")):
            # Si devuelve un directorio (inesperado aquí pero por si acaso) y no es el ejecutable directo
            # Esto necesitaría una lógica más compleja para encontrar el ejecutable dentro, pero es poco probable.
            # Por ahora, si es un directorio, asumimos que install() falló en devolver el ejecutable.
            # Intentamos adivinar basado en la estructura típica de caché de chromedriver-mac-arm64
            potential_exe_path = os.path.join(base_driver_path_info, "chromedriver-mac-arm64", "chromedriver")
            if os.path.exists(potential_exe_path):
                 executable_path = potential_exe_path
                 logger_setup.warning(f"ChromeDriverManager devolvió un directorio. Usando ruta construida: {executable_path}")
            else: # Fallback a la ruta original, puede que falle pero es lo que tenemos
                 executable_path = base_driver_path_info # O lanzar un error aquí
                 logger_setup.error(f"ChromeDriverManager devolvió un directorio y no se pudo construir una ruta válida. Usando: {executable_path}")
        else:
            # Si no es notices y no es un directorio problemático, asumimos que es el ejecutable correcto.
            executable_path = base_driver_path_info
            logger_setup.info(f"Usando ruta devuelta por ChromeDriverManager como ejecutable: {executable_path}")
        
        if not os.path.isfile(executable_path):
            logger_setup.error(f"La ruta al ejecutable determinada ({executable_path}) no es un archivo válido. WebDriver fallará.")
            raise FileNotFoundError(f"ChromeDriver ejecutable no encontrado en {executable_path}")

        # --- Añadir permisos de ejecución --- 
        try:
            logger_setup.info(f"Verificando/Estableciendo permisos de ejecución para: {executable_path}")
            st = os.stat(executable_path)
            if not (st.st_mode & stat.S_IEXEC):
                logger_setup.info(f"Añadiendo permiso de ejecución a {executable_path}")
                os.chmod(executable_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            else:
                logger_setup.info(f"Permiso de ejecución ya establecido para {executable_path}")
        except Exception as e_perm:
            logger_setup.error(f"Error al intentar establecer permisos de ejecución para {executable_path}: {e_perm}", exc_info=True)
            # Continuar de todas formas, puede que falle por otras razones o que los permisos ya estén bien
            # pero es una fuente común de problemas en macOS.

        logger_setup.info(f"Usando ruta explícita para el servicio de ChromeDriver: {executable_path}")
        service = Service(executable_path=executable_path)
        
        logger_setup.info("Creando instancia del WebDriver de Chrome...")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger_setup.info("WebDriver de Chrome creado exitosamente.")
        return driver

    except Exception as e:
        logger_setup.error(f"Error al configurar el WebDriver de Chrome: {e}", exc_info=True)
        return None
