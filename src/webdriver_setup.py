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

# Load .env file
load_dotenv()

def setup_webdriver():
    """
    Configura y devuelve una instancia del WebDriver de Chrome.
    Lee el modo headless desde la variable de entorno HEADLESS_MODE.

    Returns:
        webdriver.Chrome: Instancia configurada del WebDriver.
    """
    # Configurar opciones de Chrome
    chrome_options = Options()

    # Leer HEADLESS_MODE desde .env
    headless_env = os.getenv("HEADLESS_MODE", "False").lower() == "true"

    if headless_env:
        chrome_options.add_argument("--headless=new")
        print("INFO: Configurando Chrome en modo headless (desde .env).")
    else:
        print("INFO: Configurando Chrome en modo normal (no headless, desde .env).")
    
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    try:
        print("INFO: Obteniendo/Instalando ChromeDriver...")
        # 1. Obtener la ruta inicial devuelta por el manager
        initial_driver_path = ChromeDriverManager().install()
        print(f"INFO: Ruta inicial devuelta por manager: {initial_driver_path}")
        
        # 2. Determinar la ruta correcta al ejecutable
        driver_executable_path = None
        if os.path.isfile(initial_driver_path) and 'chromedriver' in os.path.basename(initial_driver_path) and 'THIRD_PARTY_NOTICES' not in initial_driver_path:
            # Parece que devolvió directamente el ejecutable
            driver_executable_path = initial_driver_path
            print(f"INFO: Usando la ruta devuelta directamente como ejecutable: {driver_executable_path}")
        elif 'THIRD_PARTY_NOTICES' in os.path.basename(initial_driver_path):
            # Devolvió notices, construir ruta al binario
            driver_dir_path = os.path.dirname(initial_driver_path)
            potential_executable = os.path.join(driver_dir_path, "chromedriver")
            if os.path.isfile(potential_executable):
                print(f"WARN: ChromeDriverManager devolvió notices, usando path construido: {potential_executable}")
                driver_executable_path = potential_executable
            else:
                raise FileNotFoundError(f"Manager devolvió notices, y no se encontró chromedriver en {potential_executable}")
        else:
            # Caso inesperado
             raise FileNotFoundError(f"La ruta devuelta por ChromeDriverManager no parece ser válida: {initial_driver_path}")

        # 3. Ahora que TENEMOS la ruta correcta, aplicar permisos
        print(f"INFO: Asegurando permisos para: {driver_executable_path}")
        try:
            subprocess.run(['xattr', '-d', 'com.apple.quarantine', driver_executable_path], check=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            # print(f"INFO: Intento de quitar cuarentena de {driver_executable_path}")
        except FileNotFoundError:
            pass # xattr no existe, no es macOS
            # print(f"INFO: Comando xattr no encontrado, omitiendo cuarentena.")
        except Exception as e:
            print(f"WARN: No se pudo quitar cuarentena: {e}")
        try:
            st = os.stat(driver_executable_path)
            if not (st.st_mode & stat.S_IEXEC):
                print(f"INFO: Añadiendo permiso ejecución a {driver_executable_path}")
                os.chmod(driver_executable_path, st.st_mode | stat.S_IEXEC)
            # else:
            #     print(f"INFO: Permiso ejecución OK en {driver_executable_path}")
        except Exception as e:
            print(f"WARN: No se pudo asegurar permiso ejecución: {e}")

    except Exception as e_manager:
        print(f"ERROR CRÍTICO: Falló la obtención/preparación de ChromeDriver: {e_manager}")
        raise

    # 4. Crear el Service con la ruta ASEGURADA
    print(f"INFO: Pasando ruta explícita al Service: {driver_executable_path}")
    service = Service(executable_path=driver_executable_path)
    
    try:
        print("INFO: Creando instancia de WebDriver...")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("INFO: WebDriver creado exitosamente.")
    except Exception as e_create:
        print(f"ERROR CRÍTICO: Falló la creación de webdriver.Chrome: {e_create}")
        print(f"  Service path: {driver_executable_path}")
        print(f"  Options: {chrome_options.arguments}")
        raise
    
    driver.implicitly_wait(IMPLICIT_WAIT)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    
    return driver
