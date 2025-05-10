"""
Módulo para manejar la autenticación y sesiones en EVoting.
"""
import os
import json
import pickle
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
from urllib.parse import urlparse

from src.config import EVOTING_BASE_URL, EVOTING_USERNAME, EVOTING_PASSWORD

class AuthManager:
    """
    Clase para manejar la autenticación y sesiones en la plataforma EVoting.
    """
    
    def __init__(self, driver, login_url=None):
        """
        Inicializa el gestor de autenticación.
        
        Args:
            driver: Instancia del WebDriver de Selenium.
            login_url (str, optional): URL base para la página de login.
                                       Si es None, usa EVOTING_BASE_URL.
        """
        self.driver = driver
        self.cookies_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cookies.pkl")
        # Usar la URL proporcionada o la de configuración por defecto
        self.login_url = login_url if login_url else f"{EVOTING_BASE_URL}/"
        logging.info(f"AuthManager inicializado para URL de login: {self.login_url}")
        
    def login(self, username=None, password=None):
        """
        Realiza el inicio de sesión en la plataforma EVoting utilizando correo electrónico y contraseña.
        
        Args:
            username (str, optional): Correo electrónico. Si no se proporciona, se usa el valor de configuración.
            password (str, optional): Contraseña. Si no se proporciona, se usa el valor de configuración.
            
        Returns:
            bool: True si el inicio de sesión fue exitoso, False en caso contrario.
        """
        # Usar credenciales de configuración si no se proporcionan
        login_username = username or EVOTING_USERNAME
        login_password = password or EVOTING_PASSWORD
        
        if not login_username or not login_password:
            logging.error("Login credentials (username or password) are not configured or provided.")
            raise ValueError("Se requieren credenciales de inicio de sesión")
        
        logging.info(f"Iniciando proceso de login en {self.login_url} con usuario: {login_username}")
        
        # Intentar cargar cookies existentes
        # NOTA: La validez de las cookies depende del dominio. Si los dominios son diferentes
        # (ej. evoting.com vs dcv.evoting.com), las cookies de uno no servirán para el otro.
        # Se podría hacer el archivo de cookies dependiente de la URL, pero por ahora se omite.
        if os.path.exists(self.cookies_file):
            try:
                logging.info(f"Intentando usar cookies guardadas ({self.cookies_file})...")
                # Primero navegar a la página de login del dominio correcto para poder aplicar cookies
                self.driver.get(self.login_url) 
                logging.info(f"Navegado a URL de login: {self.driver.current_url}")
                
                # # Cargar cookies guardadas
                # with open(self.cookies_file, 'rb') as file:
                #     cookies = pickle.load(file)
                #     logging.info(f"Cargadas {len(cookies)} cookies")
                #     for cookie in cookies:
                #         # Intentar añadir cookie, podría fallar si el dominio no coincide
                #         try:
                #             # Quitar expiry si existe, causa problemas a veces
                #             if 'expiry' in cookie: del cookie['expiry'] 
                #             self.driver.add_cookie(cookie)
                #         except Exception as cookie_err:
                #             logging.warning(f"No se pudo añadir la cookie (dominio podría no coincidir?): {cookie}. Error: {cookie_err}")
                
                # Recargar la página para aplicar las cookies
                logging.info("Recargando página para aplicar cookies...")
                self.driver.refresh()
                time.sleep(1)  # Aumentar tiempo para procesamiento
                logging.info(f"URL después de recargar: {self.driver.current_url}")
                
                # Verificar si el login automático funcionó (usando is_logged_in)
                if self.is_logged_in():
                    logging.info(f"Login exitoso con cookies guardadas para {self.login_url}")
                    return True
                else:
                    logging.warning(f"Las cookies ({self.cookies_file}) han expirado o no funcionaron para {self.login_url}. Realizando login manual...")
            except Exception as e:
                logging.error(f"Error al cargar/aplicar cookies: {str(e)}. Realizando login manual...", exc_info=True)
        
        # Si las cookies fallaron o no existían, proceder con login manual
        try:
            # Navegar a la página de inicio de sesión (si no se hizo ya)
            if self.driver.current_url.rstrip('/') != self.login_url.rstrip('/'):
                logging.info(f"Navegando a página de login: {self.login_url}")
                self.driver.get(self.login_url)
                logging.info(f"URL actual: {self.driver.current_url}")
            else:
                logging.info(f"Ya estamos en la URL de login: {self.driver.current_url}")

            # --- Intento de clic en 'Ingresar' inicial (si aplica) ---
            # Esta lógica puede variar entre las UIs (evoting vs dcv)
            # Intentamos hacerlo más robusto: buscar el botón, si no, buscar el username directamente
            username_field_locator = (By.NAME, "username")
            try:
                # Verificar si el campo username ya está visible
                self.driver.find_element(*username_field_locator)
                logging.info("Campo username encontrado directamente. Procediendo a ingresar credenciales.")
            except NoSuchElementException:
                # Si no está visible, buscar el botón 'Ingresar'
                logging.info("Campo username no visible. Buscando botón 'Ingresar' inicial...")
                ingresar_button_locator = (By.XPATH, "//button[normalize-space()='Ingresar']")
                try:
                    ingresar_button = WebDriverWait(self.driver, 7).until(
                        EC.element_to_be_clickable(ingresar_button_locator)
                    )
                    ingresar_button.click()
                    logging.info("Clic en 'Ingresar' inicial realizado. Esperando formulario...")
                    # Esperar a que el campo username aparezca después del clic
                    WebDriverWait(self.driver, 5).until(
                        EC.visibility_of_element_located(username_field_locator)
                    )
                    logging.info("Campo username apareció después del clic.")
                except TimeoutException:
                    logging.error("No se pudo encontrar o hacer clic en 'Ingresar' Y el campo username no apareció/existió.")
                    # Capturar screenshot podría ser útil aquí para depurar la UI
                    return False
                except Exception as click_err:
                    logging.error(f"Error inesperado al hacer clic en 'Ingresar': {click_err}")
                    return False

            # --- Ingresar credenciales --- 
            logging.info("Ingresando credenciales...")
            email_input = self.driver.find_element(*username_field_locator)
            email_input.clear()
            email_input.send_keys(login_username)
            
            password_input_locator = (By.NAME, "password")
            password_input = WebDriverWait(self.driver, 5).until(
                EC.visibility_of_element_located(password_input_locator)
            )
            password_input.clear()
            password_input.send_keys(login_password)
            
            # --- Clic en botón de login --- 
            logging.info("Haciendo clic en botón de login...")
            # Usar un selector más genérico que podría funcionar en ambas UIs
            login_button_locator = (By.XPATH, "//button[@type='submit']") 
            try:
                login_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(login_button_locator)
                )
                login_button.click()
                logging.info(f"CLIC LOGIN HECHO. URL Inmediata: {self.driver.current_url}")
            except TimeoutException:
                 logging.error("No se encontró el botón de submit del login.")
                 # Intentar con el texto específico como fallback (puede variar)
                 try:
                     login_button_locator_text = (By.XPATH, "//button[@type='submit' and (contains(., 'Iniciar sesión') or contains(., 'Ingresar'))]")
                     login_button = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable(login_button_locator_text)
                     )
                     login_button.click()
                     logging.info(f"CLIC LOGIN (Fallback) HECHO. URL Inmediata: {self.driver.current_url}")
                 except TimeoutException:
                      logging.error("Tampoco se encontró el botón de login por texto.")
                      # Capturar estado antes de retornar False
                      try:
                          ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                          screenshot_path = f"error_screenshot_login_btn_{ts}.png"
                          self.driver.save_screenshot(screenshot_path)
                          logging.info(f"Screenshot guardado en: {screenshot_path}")
                      except Exception as screen_err:
                          logging.error(f"Error al guardar screenshot: {screen_err}")
                      return False
            
            # --- Esperar y verificar login --- 
            logging.info("Esperando completar login...")
            try:
                # --- Modificación para loggear durante la espera --- 
                max_wait = 35 # Segundos
                interval = 2  # Segundos entre chequeos
                elapsed_time = 0
                login_success = False
                # login_url_base = self.login_url.rstrip('/') # No longer primary check

                while elapsed_time < max_wait:
                    current_url = self.driver.current_url
                    # logging.info(f"[Esperando Login] URL: {current_url} | ...detailed conditions...") # Old logging

                    if self.is_logged_in(current_url_override=current_url):
                        logging.info(f"Login parece exitoso. URL actual: {current_url}")
                        login_success = True
                        break
                    
                    logging.info(f"[Esperando Login] URL: {current_url} | Tiempo: {elapsed_time}s")
                    time.sleep(interval)
                    elapsed_time += interval

                if login_success:
                    self._save_cookies()
                    logging.info(f"Login exitoso y cookies guardadas para {self.login_url}. URL final: {self.driver.current_url}")
                    return True
                else:
                    logging.error(f"Login falló después de esperar. URL final: {self.driver.current_url}")
                    # Consider saving screenshot here if not already done by specific error handlers
                    return False

            except TimeoutException: # This specific exception might be less likely if the loop uses is_logged_in
                logging.error("Timeout general esperando la finalización del login.", exc_info=True)
                return False
            
        except (TimeoutException, NoSuchElementException) as e:
            logging.error(f"Error (Timeout/No encontrado) durante el inicio de sesión manual: {str(e)}", exc_info=True)
            # Añadir screenshot
            return False
        except Exception as e:
            logging.error(f"Error inesperado durante el inicio de sesión manual: {str(e)}", exc_info=True)
            return False
    
    def _save_cookies(self):
        """
        Guarda las cookies de la sesión actual para reutilizarlas posteriormente.
        """
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.cookies_file), exist_ok=True)
            
            # Guardar cookies
            with open(self.cookies_file, 'wb') as file:
                pickle.dump(self.driver.get_cookies(), file)
            print("Cookies guardadas correctamente")
        except Exception as e:
            print(f"Error al guardar cookies: {str(e)}")
    
    def logout(self):
        """
        Cierra la sesión en la plataforma EVoting.
        
        Returns:
            bool: True si el cierre de sesión fue exitoso, False en caso contrario.
        """
        try:
            # Buscar y hacer clic en el botón o enlace de cierre de sesión
            logout_button = self.driver.find_element(By.XPATH, "//a[contains(@href, 'logout') or contains(text(), 'Cerrar sesión')]")
            logout_button.click()
            
            # Esperar a que se complete el cierre de sesión
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            
            # Eliminar el archivo de cookies si existe
            if os.path.exists(self.cookies_file):
                os.remove(self.cookies_file)
                print("Archivo de cookies eliminado")
            
            return True
            
        except (TimeoutException, NoSuchElementException) as e:
            print(f"Error durante el cierre de sesión: {str(e)}")
            return False
    
    def get_requests_cookies(self) -> dict:
        """Formatea las cookies de Selenium para ser usadas con requests."""
        selenium_cookies = self.driver.get_cookies()
        requests_cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
        logging.info(f"Formateadas {len(requests_cookies)} cookies para requests.")
        return requests_cookies
    
    def is_logged_in(self, current_url_override=None) -> bool:
        """
        Verifica si el usuario está actualmente logueado en la plataforma.
        Una sesión se considera activa si la URL actual está en el dominio base
        y no es una página de login/autenticación intermedia.

        Args:
            current_url_override (str, optional): Permite pasar una URL específica para testear,
                                                  en lugar de usar self.driver.current_url.

        Returns:
            bool: True si parece estar logueado, False en caso contrario.
        """
        try:
            current_url = current_url_override if current_url_override else self.driver.current_url
            if not current_url or not current_url.startswith("http"):
                logging.warning("URL actual no válida o no disponible para is_logged_in.")
                return False

            login_page_parsed = urlparse(self.login_url)
            current_page_parsed = urlparse(current_url)

            base_site_domain = login_page_parsed.netloc
            current_domain = current_page_parsed.netloc

            # Condición 1: El dominio actual debe coincidir con el dominio de la página de login.
            if current_domain != base_site_domain:
                logging.debug(f"[is_logged_in] Dominio actual ({current_domain}) no coincide con dominio base ({base_site_domain}).")
                return False

            # Condición 2: No debemos estar en la URL exacta de login (a menos que sea idéntica al dominio base, poco probable).
            if current_url.rstrip('/') == self.login_url.rstrip('/'):
                logging.debug(f"[is_logged_in] Aún en la página de login exacta: {current_url}")
                return False
            
            # Condición 3: La ruta actual no debe contener subcadenas típicas de páginas de autenticación.
            # Esto ayuda a filtrar redirecciones intermedias (ej. auth0, sso, etc.)
            auth_keywords = ["login", "signin", "auth", "sso", "callback", "logout", "error"]
            current_path_lower = current_page_parsed.path.lower()
            if any(keyword in current_path_lower for keyword in auth_keywords):
                # Excepción: si la URL base ya es algo como /admin/login, esto podría ser problemático.
                # Pero dado que estamos verificando no estar en la self.login_url exacta, esto debería ser seguro.
                # Si la URL base es 'esocios.evoting.com' y la URL de login es 'esocios.evoting.com/superadmin/login'
                # y estamos en 'esocios.evoting.com/superadmin/organisations', no debería haber problema.
                # Si estamos en 'esocios.evoting.com/callback?code=...' esto es un problema.
                logging.debug(f"[is_logged_in] URL path ({current_page_parsed.path}) contiene keyword de autenticación.")
                return False

            # Condición 4: Debería haber una ruta más allá del simple dominio base (ej. /admin, /dashboard)
            # Esto es una heurística, podría ser demasiado estricto si la página post-login es el root.
            # Pero para la mayoría de las apps de admin, hay una ruta.
            if not current_page_parsed.path or current_page_parsed.path == '/':
                 # A menos que la URL de login sea el dominio base (ej. "https://app.com/" y NO "https://app.com/login")
                 # Y la página post-login sea también el dominio base.
                 # En el caso de E-Socios, login_url tiene /superadmin/login, y post-login es /admin o similar, así que esto es útil.
                 if self.login_url.replace(login_page_parsed.scheme + "://", "").replace(base_site_domain, "").strip("/") : # si login_url tiene path
                    logging.debug(f"[is_logged_in] URL actual ({current_url}) es solo el dominio base, pero se esperaba una ruta.")
                    return False


            # Si pasamos todas las verificaciones, asumimos que estamos logueados.
            logging.debug(f"[is_logged_in] Sesión activa detectada en URL: {current_url}")
            return True
        
        except Exception as e:
            logging.error(f"Excepción en is_logged_in: {e}", exc_info=True)
            return False
