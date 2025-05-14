import logging
import os
import time
# from dotenv import load_dotenv # ELIMINAR o comentar esta línea si existe

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Assuming these modules/classes exist and are correctly structured
from src.webdriver_setup import setup_webdriver # Assuming this function is available
from src.auth_manager import AuthManager
from src.config import EVOTING_USERNAME, EVOTING_PASSWORD, HEADLESS_MODE # Antes IS_HEADLESS_FROM_CONFIG
from src.google_sheets_client import read_sheet_data, update_cell_in_sheet # Import the new function

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load .env variables at the start of the script if they are needed here
# load_dotenv() # Uncomment if esocios_runner.py also directly accesses .env variables beyond what webdriver_setup does

ESOCIOS_BASE_URL = "https://esocios.evoting.com"
ESOCIOS_LOGIN_URL = f"{ESOCIOS_BASE_URL}/superadmin/login"
ESOCIOS_ORGANIZATIONS_URL = f"{ESOCIOS_BASE_URL}/superadmin/organizations" # Assuming this is the org page
ESOCIOS_ADD_ORGANIZATION_URL = f"{ESOCIOS_BASE_URL}/superadmin/organizations/add" # Assuming this is the add org page


def login_to_esocios(driver: WebDriver) -> bool:
    """Realiza el login en la plataforma E-Socios Superadmin.

    Args:
        driver: Instancia del WebDriver de Selenium.

    Returns:
        bool: True si el login fue exitoso, False en caso contrario.
    """
    logger.info(f"Intentando login en E-Socios: {ESOCIOS_LOGIN_URL}")
    auth_manager = AuthManager(driver, login_url=ESOCIOS_LOGIN_URL)
    
    try:
        if auth_manager.login(EVOTING_USERNAME, EVOTING_PASSWORD):
            logger.info("Login en E-Socios exitoso.")
            # Verificación adicional: después del login, la URL debería cambiar.
            # Podríamos esperar a que la URL sea diferente de la página de login
            # o que contenga una parte específica del dashboard/admin.
            # Por ejemplo, esperar a estar en ESOCIOS_ORGANIZATIONS_URL o similar.
            # Esto dependerá de la redirección exacta post-login.
            # Ejemplo simple:
            time.sleep(3) # Espera breve para redirección
            current_url = driver.current_url
            if ESOCIOS_LOGIN_URL in current_url:
                logger.warning(f"Login pareció exitoso, pero seguimos en la URL de login: {current_url}")
                # Se podría añadir una comprobación más robusta aquí basada en elementos de la página destino.
                # Por ahora, confiamos en la lógica interna de auth_manager.is_logged_in()
            
            # Re-verificar con is_logged_in, que ahora debería usar la URL base correcta.
            # Para esto, AuthManager.is_logged_in() necesitaría saber la URL base esperada
            # o tener una lógica más genérica para detectar si está logueado (ej. ausencia de forms de login)
            # La implementación actual de is_logged_in en AuthManager ya es bastante genérica.
            if auth_manager.is_logged_in():
                 logger.info("Confirmado: Sesión activa después del login en E-Socios.")
                 return True
            else:
                 logger.warning("auth_manager.is_logged_in() reporta que no hay sesión activa después del login.")
                 return False
        else:
            logger.error("Login en E-Socios falló según AuthManager.")
            return False
    except Exception as e:
        logger.error(f"Excepción durante el login en E-Socios: {e}", exc_info=True)
        return False

def navigate_to_create_organization_page(driver: WebDriver) -> bool:
    """Navega directamente a la página de creación de organizaciones después del login.

    Args:
        driver: Instancia del WebDriver de Selenium.

    Returns:
        bool: True si la navegación es exitosa, False en caso contrario.
    """
    # URL directa proporcionada por el usuario para la página de creación
    target_add_url = "https://esocios.evoting.com/admin/organizations/add" 
    # Nota: Esto es diferente del ESOCIOS_ADD_ORGANIZATION_URL global que era /superadmin/...
    
    try:
        logger.info(f"Navegando directamente a la página de creación de organización: {target_add_url}")
        driver.get(target_add_url)

        # Esperar a que la URL sea la correcta y que un elemento clave de la página esté presente.
        logger.info(f"Esperando que la URL sea: {target_add_url} (Timeout de 20s)")
        WebDriverWait(driver, 20).until(EC.url_to_be(target_add_url))
        
        logger.info(f"URL correcta ({driver.current_url}) alcanzada. Verificando título del encabezado...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h4[contains(text(),'Crear nueva organización')]"))
        )
        logger.info(f"Navegación directa a la página de creación de organización exitosa: {driver.current_url}")
        return True
    
    except TimeoutException:
        current_url_at_timeout = "N/A"
        try:
            current_url_at_timeout = driver.current_url
        except Exception as e_get_url:
            logger.error(f"Error al intentar obtener driver.current_url en el timeout: {e_get_url}")

        logger.error(
            f"Timeout esperando la página de creación en '{target_add_url}'. " \
            f"URL actual en el momento del timeout: '{current_url_at_timeout}'."
        )
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        screenshot_filename = f"error_direct_nav_create_org_{timestamp}.png"
        try:
            driver.save_screenshot(screenshot_filename)
            logger.info(f"Screenshot guardado como {screenshot_filename}")
        except Exception as e_screenshot:
            logger.error(f"Error al guardar screenshot '{screenshot_filename}': {e_screenshot}")
        return False
    
    except Exception as e:
        logger.error(f"Error inesperado al navegar directamente a la página de creación de organización: {e}", exc_info=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        screenshot_filename = f"error_direct_nav_unexpected_{timestamp}.png"
        try:
            driver.save_screenshot(screenshot_filename)
            logger.info(f"Screenshot guardado como {screenshot_filename}")
        except Exception as e_screenshot:
            logger.error(f"Error al guardar screenshot '{screenshot_filename}': {e_screenshot}")
        return False

def fill_organization_details(driver: WebDriver, org_name: str, parent_org_name: str = None) -> bool:
    """Rellena los detalles básicos de la organización en el formulario.

    Args:
        driver: Instancia del WebDriver de Selenium.
        org_name (str): Nombre de la nueva organización.
        parent_org_name (str, optional): Nombre de la organización padre (puede incluir ID, ej. "ANEF [9snl2kce]"). Defaults to None.

    Returns:
        bool: True si los detalles se rellenaron exitosamente, False en caso contrario.
    """
    try:
        logger.info(f"Rellenando Nombre de la organización: {org_name}")
        name_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "name"))
        )
        name_input.clear()
        name_input.send_keys(org_name)

        if parent_org_name:
            # Extraer solo el nombre base para la búsqueda si viene con ID
            search_term = parent_org_name.split('[')[0].strip()
            logger.info(f"Rellenando Organización padre: buscando '{search_term}' (original: '{parent_org_name}')")
            
            parent_org_section_xpath = "//label[contains(text(),'Organización padre')]/ancestor::div[contains(@class, 'MuiGrid2-grid-sm-6')]"
            parent_org_section = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, parent_org_section_xpath))
            )

            autocomplete_input_xpath = ".//div[contains(@class, 'MuiAutocomplete-root')]//input[@type='text']"
            autocomplete_input = parent_org_section.find_element(By.XPATH, autocomplete_input_xpath)
            
            first_option_xpath = "//ul[@role='listbox']/li[1]"
            max_retries = 3 # Podríamos aumentar esto si es necesario con la nueva técnica
            selected_parent = False

            for attempt in range(max_retries):
                logger.info(f"Intento {attempt + 1}/{max_retries} para seleccionar Organización Padre '{search_term}'...")
                autocomplete_input.clear()
                autocomplete_input.send_keys(search_term)
                time.sleep(1.0) # Pausa inicial después de escribir el término completo

                # Técnica de borrar y re-escribir último carácter (a partir del segundo intento)
                if attempt > 0 and len(search_term) > 0: # Solo si hay algo que borrar y no es el primer intento
                    logger.info(f"Aplicando técnica de re-escritura para '{search_term}' en intento {attempt + 1}.")
                    # Borrar el último carácter
                    autocomplete_input.send_keys(Keys.BACK_SPACE)
                    time.sleep(0.5) # Pausa breve
                    # Re-escribir el último carácter
                    autocomplete_input.send_keys(search_term[-1])
                    time.sleep(1.0) # Pausa después de re-escribir
                else:
                    # En el primer intento, ya se escribió y se hizo una pausa, ahora esperamos un poco más.
                    time.sleep(1.0) # Pausa adicional en el primer intento (total 2s después de send_keys inicial)

                try:
                    # Aumentamos la espera individual para la opción, ya que las pausas son más explícitas
                    parent_option = WebDriverWait(driver, 15).until( 
                        EC.element_to_be_clickable((By.XPATH, first_option_xpath))
                    )
                    option_text = parent_option.text
                    logger.info(f"Opción encontrada en desplegable: '{option_text}'. Haciendo clic...")
                    parent_option.click()
                    time.sleep(0.7)
                    selected_parent = True
                    logger.info(f"Organización padre '{search_term}' seleccionada exitosamente en intento {attempt + 1}.")
                    break
                except TimeoutException:
                    logger.warning(f"Intento {attempt + 1}: No se encontró opción para '{search_term}' después de las pausas y/o re-escritura.")
                    if attempt < max_retries - 1:
                        logger.info("Reintentando...")
                        # No es necesario un time.sleep(1) aquí ya que el bucle tiene pausas al inicio
                    else:
                        logger.error(f"No se pudo seleccionar la organización padre '{search_term}' después de {max_retries} intentos.")
                        driver.save_screenshot(f"error_fill_parent_org_no_options_{time.strftime('%Y%m%d-%H%M%S')}.png")
                        return False
            
            if not selected_parent:
                logger.error(f"Fallo final al seleccionar la organización padre '{search_term}'.")
                return False

        # --- Carga de Archivos ---
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
        logo_file_path = os.path.join(project_root, "logo-anef.png")
        login_image_path = os.path.join(project_root, "Iniciosesion_esocios.png")

        # Logo de la organización
        # El input real está oculto. El HTML muestra un label con id=":rg:" que es un botón.
        # El input es name="logo" y accept=".png"
        logger.info(f"Intentando cargar Logo de la organización: {logo_file_path}")
        if os.path.exists(logo_file_path):
            # Encontrar el input[type="file"] asociado. Suele estar cerca del botón visible.
            # XPath para el input oculto basado en el name="logo"
            logo_input_xpath = "//input[@type='file' and @name='logo']"
            logo_input_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, logo_input_xpath))
            )
            logo_input_element.send_keys(logo_file_path)
            logger.info("Logo de la organización cargado.")
            time.sleep(1) # Espera para que la UI procese la carga
        else:
            logger.warning(f"Archivo de logo no encontrado en {logo_file_path}. Saltando carga.")

        # Imagen para el inicio de sesión de usuario
        # Similar al logo, el input está oculto. name="loginImage"
        logger.info(f"Intentando cargar Imagen para el inicio de sesión: {login_image_path}")
        if os.path.exists(login_image_path):
            login_image_input_xpath = "//input[@type='file' and @name='loginImage']"
            login_image_input_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, login_image_input_xpath))
            )
            login_image_input_element.send_keys(login_image_path)
            logger.info("Imagen para el inicio de sesión cargada.")
            time.sleep(1) # Espera para que la UI procese la carga
        else:
            logger.warning(f"Archivo de imagen de login no encontrado en {login_image_path}. Saltando carga.")

        # TODO: Añadir lógica para Tipo de identificación (por ahora asume default 'RUN')

        logger.info("Detalles básicos de la organización (nombre, padre y logos) rellenados.")
        return True

    except TimeoutException as e:
        logger.error(f"Timeout rellenando detalles de la organización: {e}", exc_info=True)
        driver.save_screenshot(f"error_fill_details_timeout_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False
    except Exception as e:
        logger.error(f"Error inesperado rellenando detalles de la organización: {e}", exc_info=True)
        driver.save_screenshot(f"error_fill_details_unexpected_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False

def configure_payment_features(driver: WebDriver) -> bool:
    """Configura los switches de funcionalidades de pago.

    Args:
        driver: Instancia del WebDriver de Selenium.

    Returns:
        bool: True si los switches se configuraron correctamente, False en caso contrario.
    """
    try:
        logger.info("Configurando funcionalidades de pago...")

        # Helper function to toggle a switch if not already active
        def toggle_switch(switch_label_text: str):
            logger.info(f"Configurando switch: '{switch_label_text}'")
            # XPath para encontrar el label que contiene el texto del switch
            label_xpath = f"//label[.//span[contains(@class, 'MuiFormControlLabel-label') and contains(text(), '{switch_label_text}')]]"
            switch_label_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, label_xpath))
            )
            
            # Dentro de este label, encontrar el input checkbox
            checkbox_input = switch_label_element.find_element(By.XPATH, ".//input[@type='checkbox']")
            
            if not checkbox_input.is_selected():
                logger.info(f"Switch '{switch_label_text}' no está activo. Haciendo clic para activar...")
                # Es más robusto hacer clic en el elemento visible del switch (el span o el label mismo)
                # que en el input oculto, aunque a veces el input.click() funciona.
                # Vamos a intentar hacer clic en el switch_label_element, que es el <label>
                switch_label_element.click()
                time.sleep(0.5) # Pequeña pausa para que el estado se actualice
                if checkbox_input.is_selected():
                    logger.info(f"Switch '{switch_label_text}' activado exitosamente.")
                else:
                    logger.warning(f"Se hizo clic en el switch '{switch_label_text}', pero no parece estar seleccionado.")
                    # Podríamos intentar un segundo método de clic o lanzar un error aquí
            else:
                logger.info(f"Switch '{switch_label_text}' ya está activo.")

        toggle_switch("Descarga de usuarios")
        toggle_switch("Gráficos personalizados")
        # El switch "Envío de correos" está deshabilitado en el HTML de ejemplo (Mui-disabled)
        # Si necesitara activarse y estuviera habilitado, se añadiría aquí: 
        # toggle_switch("Envío de correos")

        logger.info("Funcionalidades de pago configuradas.")
        return True

    except TimeoutException as e:
        logger.error(f"Timeout configurando funcionalidades de pago: {e}", exc_info=True)
        driver.save_screenshot(f"error_payment_features_timeout_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False
    except Exception as e:
        logger.error(f"Error inesperado configurando funcionalidades de pago: {e}", exc_info=True)
        driver.save_screenshot(f"error_payment_features_unexpected_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False

def add_additional_user_field(driver: WebDriver, field_name: str, field_type: str) -> bool:
    """Añade un campo de datos adicional para los usuarios.

    Args:
        driver: Instancia del WebDriver de Selenium.
        field_name (str): Nombre del campo adicional (ej. "Apellido").
        field_type (str): Tipo de campo, "texto" o "numero".

    Returns:
        bool: True si el campo se añadió y configuró correctamente, False en caso contrario.
    """
    try:
        logger.info(f"Añadiendo campo adicional: '{field_name}' (Tipo: {field_type})")

        # 1. Scroll to the "Datos adicionales sobre los usuarios" header
        additional_data_header_xpath = "//span[contains(text(), 'Datos adicionales sobre los usuarios')]"
        try:
            logger.info(f"Intentando hacer scroll a la sección '{additional_data_header_xpath}'...")
            header_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, additional_data_header_xpath))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", header_element)
            logger.info("Scroll a la sección de datos adicionales completado.")
        except TimeoutException:
            logger.warning(f"No se encontró el encabezado de la sección '{additional_data_header_xpath}'. Continuando con scroll general...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);") # Fallback scroll
        
        time.sleep(0.5) # Pausa más larga para que cargue el contenido después del scroll

        # 2. Debug Screenshot
        timestamp_debug = time.strftime("%Y%m%d-%H%M%S")
        debug_screenshot_filename = f"debug_before_button_wait_{field_name.replace(' ','_')}_{timestamp_debug}.png"
        try:
            driver.save_screenshot(debug_screenshot_filename)
            logger.info(f"Debug screenshot guardado como: {debug_screenshot_filename}")
        except Exception as e_screenshot:
            logger.error(f"Error al guardar debug screenshot '{debug_screenshot_filename}': {e_screenshot}")

        button_xpath = ""
        if field_type == "texto":
            button_xpath = "//button[contains(normalize-space(), 'Tipo texto')]"
        elif field_type == "numero":
            button_xpath = "//button[contains(normalize-space(), 'Tipo número')]"
        else:
            logger.error(f"Tipo de campo no soportado: {field_type}")
            return False

        logger.info(f"Haciendo clic en el botón para añadir campo tipo '{field_type}' (XPath: {button_xpath})...")
        wait_time = 15 # Segundos

        # 3. Locate Button
        logger.info(f"Esperando que el botón '{field_type}' esté presente (Timeout: {wait_time}s)...")
        add_field_button_element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.XPATH, button_xpath))
        )
        
        # 4. If Found, Scroll to Button & JS Click
        logger.info(f"Botón '{field_type}' encontrado. Haciendo scroll al elemento y click con JavaScript...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", add_field_button_element)
        time.sleep(0.5) # Pequeña pausa después del scroll al botón
        driver.execute_script("arguments[0].click();", add_field_button_element)
        time.sleep(0.5) # Espera a que aparezca la nueva sección del formulario

        # La nueva sección aparece. Basado en tipotexto.html, esta sección es un Card.
        # Necesitamos encontrar el ÚLTIMO card de este tipo, ya que se añaden dinámicamente.
        # Asumimos que los campos adicionales se añaden dentro de un contenedor específico,
        # y que cada nuevo campo es un nuevo "MuiPaper-root MuiCard-root" dentro de ese contenedor.
        # El contenedor de "Datos adicionales sobre los usuarios" tiene un MuiCardHeader-content con ese texto.
        
        # XPath para la última sección de campo adicional añadida.
        # Esto busca el último Card que está dentro de un Card que tiene el header "Datos adicionales sobre los usuarios".
        # Y que además contiene un input para el nombre del dato (para distinguirlo de otros cards).
        new_field_section_xpath = "(//div[contains(@class, 'MuiCardContent-root') and .//input[contains(@id, ':') and @required]]//ancestor::div[contains(@class, 'MuiPaper-root') and contains(@class, 'MuiCard-root') and not(.//div[contains(@class, 'MuiCardHeader-root')])])[last()]"
        # Este XPath es complejo y frágil. Una mejor aproximación sería si cada nueva sección tuviera un ID único o un atributo distintivo.
        # Alternativa: buscar el último card que contenga un input cuyo id empieza con ":r" (o similar si es dinámico y predecible)
        # Y que también contenga un switch para "Mostrar al usuario"
        # Por ahora, nos basamos en la estructura de tipotexto.html donde el input tiene un ID dinámico y es required.
        # Y que no sea el card principal de "Datos adicionales sobre los usuarios" (que sí tiene un MuiCardHeader-root)

        # Simplificando: encontrar el último card que tiene un input para "Nombre del dato"
        # Asumiendo que los campos se apilan y el último es el recién añadido.
        # Buscamos un input con label "Nombre del dato" y que sea required.
        all_name_inputs_xpath = "//label[contains(text(),'Nombre del dato') and .//span[contains(@class, 'MuiFormLabel-asterisk')]]/following-sibling::div//input[@type='text']"
        
        # Esperar a que al menos un campo de nombre aparezca después de hacer clic en añadir
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, all_name_inputs_xpath)))
        
        name_input_elements = driver.find_elements(By.XPATH, all_name_inputs_xpath)
        if not name_input_elements:
            logger.error("No se encontró el campo 'Nombre del dato' después de añadir el campo.")
            return False
        
        # El último input de esta lista es el que acabamos de añadir
        name_input = name_input_elements[-1]
        logger.info(f"Campo 'Nombre del dato' encontrado. Ingresando: {field_name}")
        name_input.clear()
        name_input.send_keys(field_name)

        # Localizar el switch "Mostrar al usuario" DENTRO de la sección del campo recién añadido.
        # El switch está cerca del input que acabamos de rellenar.
        # Necesitamos un XPath relativo al contenedor del input `name_input`.
        # Suponiendo que `name_input` está dentro de un `div.MuiGrid2-root.MuiGrid2-grid-xs-6` y el switch en un `div.MuiGrid2-root.MuiGrid2-grid-xs-3` hermano o cercano.
        # Vamos a buscar el switch "Mostrar al usuario" que sea descendiente del mismo "abuelo" (el MuiGrid2-container) que el input.
        field_container_xpath = "./ancestor::div[contains(@class, 'MuiGrid2-container') and contains(@class, 'css-abli9d')]"
        # Este XPath asume la estructura de `tipotexto.html`.
        field_container = name_input.find_element(By.XPATH, field_container_xpath)
        
        show_user_switch_label_xpath = ".//label[.//span[contains(text(), 'Mostrar al usuario')]]"
        show_user_switch_label = WebDriverWait(field_container, 10).until(
            EC.presence_of_element_located((By.XPATH, show_user_switch_label_xpath))
        )
        show_user_checkbox = show_user_switch_label.find_element(By.XPATH, ".//input[@type='checkbox']")

        if not show_user_checkbox.is_selected():
            logger.info("Switch 'Mostrar al usuario' no está activo. Haciendo clic...")
            show_user_switch_label.click()
            time.sleep(0.5)
            if not show_user_checkbox.is_selected():
                 logger.warning("Se hizo clic en 'Mostrar al usuario', pero no parece estar seleccionado.")
            else:
                 logger.info("Switch 'Mostrar al usuario' activado.")
        else:
            logger.info("Switch 'Mostrar al usuario' ya está activo.")
        
        logger.info(f"Campo adicional '{field_name}' añadido y configurado.")
        return True

    except TimeoutException as e:
        logger.error(f"Timeout añadiendo campo adicional '{field_name}': {e}", exc_info=True)
        driver.save_screenshot(f"error_add_field_timeout_{field_name.replace(' ','_')}_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False
    except Exception as e:
        logger.error(f"Error inesperado añadiendo campo adicional '{field_name}': {e}", exc_info=True)
        driver.save_screenshot(f"error_add_field_unexpected_{field_name.replace(' ','_')}_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False

def submit_organization_form(driver: WebDriver, org_name: str) -> bool:
    """Hace clic en el botón final para agregar la organización y verifica el éxito.

    Args:
        driver: Instancia del WebDriver de Selenium.
        org_name (str): Nombre de la organización que se está creando (para logging).

    Returns:
        bool: True si el formulario se envió y se detectó una condición de éxito,
              False en caso contrario.
    """
    try:
        logger.info(f"Intentando enviar el formulario para la organización: {org_name}")
        submit_button_xpath = "//button[@type='submit' and contains(normalize-space(), 'Agregar')]"
        
        submit_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
        )
        # Scroll into view and click using JavaScript for potentially more reliability
        driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
        time.sleep(0.5) # Brief pause after scroll
        driver.execute_script("arguments[0].click();", submit_button)
        # submit_button.click() # Original click
        logger.info("Botón 'Agregar' clickeado.")

        # URL esperada después de una creación exitosa (asumiendo /admin/ path)
        # ESOCIOS_BASE_URL es "https://esocios.evoting.com"
        expected_admin_redirect_url = f"{ESOCIOS_BASE_URL}/admin" 
        # La URL original en la constante global era /superadmin

        # Espera combinada para redirección o mensaje de éxito.
        # Aumentamos el tiempo total de espera para la confirmación.
        confirmation_timeout = 30 # segundos

        try:
            # Prioridad 1: Verificar redirección a la lista de organizaciones (/admin/organizations)
            logger.info(f"Esperando redirección a una URL que contenga '/admin/organizations' (Timeout: {confirmation_timeout}s)")
            WebDriverWait(driver, confirmation_timeout).until(
                EC.url_contains("/admin/organizations")
            )
            # Adicionalmente, asegurarse de que no estamos en la página de 'add'
            current_url_after_redirect = driver.current_url
            if "/add" not in current_url_after_redirect:
                logger.info(f"Redirección a '{current_url_after_redirect}' detectada (contiene '/admin/organizations' y no '/add'). Asumiendo éxito para {org_name}.")
                return True
            else:
                logger.warning(f"Redirección a '{current_url_after_redirect}' pero aún contiene '/add'. Verificando mensaje de éxito.")

        except TimeoutException:
            current_url_at_timeout = driver.current_url
            logger.warning(
                f"No hubo redirección clara a '/admin/organizations' después de {confirmation_timeout}s. "
                f"URL actual: {current_url_at_timeout}. Intentando buscar mensaje de éxito."
            )

        # Prioridad 2: Si no hubo redirección clara, buscar un mensaje de éxito en la página actual.
        # Esto es útil si la creación es exitosa pero permanece en la misma página (quizás con formulario reseteado)
        # o si la redirección fue a otra página que no es la lista principal pero muestra un éxito.
        success_message_xpath = "//*[contains(@class, 'MuiAlert-filledSuccess') or @role='alert'][contains(normalize-space(), 'Organización creada') or contains(normalize-space(), 'éxito') or contains(normalize-space(), 'correctamente')]"
        try:
            # Usar un timeout más corto aquí, ya que la mayor parte del tiempo de confirmación ya pasó.
            success_element = WebDriverWait(driver, 10).until( 
                EC.visibility_of_element_located((By.XPATH, success_message_xpath))
            )
            logger.info(f"Mensaje de éxito encontrado en la página actual: '{success_element.text}'. Asumiendo éxito para {org_name}.")
            return True
        except TimeoutException:
            logger.error(
                f"No se detectó redirección a '/admin/organizations' ni un mensaje de éxito claro para {org_name} "
                f"después de {confirmation_timeout + 10}s totales de espera."
            )
            driver.save_screenshot(f"error_submit_no_confirmation_{org_name.replace(' ','_')}_{time.strftime('%Y%m%d-%H%M%S')}.png")
            return False

    except TimeoutException as e:
        logger.error(f"Timeout esperando el botón 'Agregar' o durante el proceso de envío para {org_name}: {e}", exc_info=True)
        driver.save_screenshot(f"error_submit_timeout_btn_{org_name.replace(' ','_')}_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al enviar el formulario para {org_name}: {e}", exc_info=True)
        driver.save_screenshot(f"error_submit_unexpected_{org_name.replace(' ','_')}_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False

def main_esocios_flow():
    """Función principal para el flujo de creación de organizaciones en E-Socios."""
    driver = None
    try:
        logger.info("Configurando WebDriver...")
        # Usar la variable HEADLESS_MODE importada de src.config
        logger.info(f"Valor de HEADLESS_MODE (importado de src.config) en runner: {HEADLESS_MODE} (Tipo: {type(HEADLESS_MODE)})")

        driver = setup_webdriver(headless_mode=HEADLESS_MODE) # Usar HEADLESS_MODE directamente
        
        if not driver:
            logger.error("No se pudo configurar el WebDriver. Abortando.")
            return

        if not login_to_esocios(driver):
            logger.error("Fallo en el login de E-Socios. Abortando.")
            return
        
        logger.info("Login exitoso. Procediendo...")

        spreadsheet_url_or_id = os.getenv("SPREADSHEET_URL_OR_ID")
        sheet_name = os.getenv("SHEET_NAME", "Slugs")
        
        # Definición de encabezados de columna
        slug_column_header = "Slug"
        org_name_column_header = "Nombre Organización"
        parent_org_column_header = "Organización padre"
        # Asume que la columna D (índice 4) se llamará "Estado Final" en el Sheet
        # y la columna E (índice 5) se llamará "Estado Procesamiento"
        final_status_column_header = "Estado Final" 
        processing_status_column_header = "Estado Procesamiento"

        # Índices de columna (1-indexed) para escribir en el Sheet
        status_column_index = 4  # Columna D para el estado final (sin cambios)
        processing_status_column_index = 5 # Columna E para el estado de "en proceso"
        
        logger.info(f"Leyendo datos desde Google Sheet ID: {spreadsheet_url_or_id}, Hoja: {sheet_name}")
        sheet_data = read_sheet_data(spreadsheet_url_or_id, sheet_name)
        
        if not sheet_data:
            logger.warning("No se encontraron datos en el Google Sheet o no se pudo acceder. Abortando.")
            return

        logger.info(f"Se encontraron {len(sheet_data)} filas de datos en el Google Sheet.")

        initial_navigation_successful = navigate_to_create_organization_page(driver)
        if not initial_navigation_successful:
            logger.error("Fallo inicial al navegar a la página de creación. Se intentará por organización.")

        for i, row_data in enumerate(sheet_data):
            current_row_in_sheet = i + 2 
            status_message = ""

            # Leer estados actuales de la fila desde los datos del sheet
            final_status_value = str(row_data.get(final_status_column_header, "")).strip()
            # processing_status_value = str(row_data.get(processing_status_column_header, "")).strip() # Opcional si queremos lógica más compleja con este estado

            # Condición 1: Saltar si la columna de estado final (D) ya tiene contenido
            if final_status_value:
                logger.info(f"Fila {current_row_in_sheet}: Ya tiene un estado final ('{final_status_value}'). Saltando.")
                continue
            
            # Marcar la fila como "Iniciado" en la columna de estado de procesamiento (E)
            update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, processing_status_column_index, "Iniciado")
            logger.info(f"Fila {current_row_in_sheet}: Marcada como 'Iniciado' en columna {processing_status_column_index}.")

            # Re-navegar si es necesario
            if not initial_navigation_successful or i > 0: 
                if not navigate_to_create_organization_page(driver):
                    status_message = "Error: Fallo al navegar a página de creación"
                    logger.error(f"{status_message} para fila {current_row_in_sheet}.")
                    update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message)
                    # Opcional: Limpiar marca "Iniciado" o poner "Error Navegación" en columna E
                    # update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, processing_status_column_index, "Error Navegación")
                    continue 
                else:
                    initial_navigation_successful = True

            slug = row_data.get(slug_column_header)
            org_name = row_data.get(org_name_column_header)
            parent_org_name = row_data.get(parent_org_column_header)
            
            logger.info(f"Procesando fila {current_row_in_sheet} del sheet: Slug='{slug}', Nombre='{org_name}', Padre='{parent_org_name}'")

            if not slug or not org_name:
                status_message = "Error: Datos faltantes (Slug o Nombre Organización)"
                logger.warning(f"{status_message} en fila {current_row_in_sheet}.")
                update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message)
                update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, processing_status_column_index, "Error Datos") # Actualizar estado en E
                continue
            
            all_steps_successful = False
            if fill_organization_details(driver, org_name, parent_org_name):
                if configure_payment_features(driver):
                    additional_fields = [
                        {"name": "Apellido", "type": "texto"},
                        {"name": "Sexo", "type": "texto"},
                        {"name": "Región", "type": "texto"},
                        {"name": "Provincia", "type": "texto"},
                        {"name": "Comuna", "type": "texto"},
                        {"name": "RSU/RAF", "type": "numero"}
                    ]
                    all_additional_fields_added = True
                    for field_idx, field in enumerate(additional_fields):
                        if not add_additional_user_field(driver, field["name"], field["type"]):
                            status_message = f"Error: Fallo al añadir campo '{field['name']}' para {org_name}"
                            all_additional_fields_added = False
                            break
                    if all_additional_fields_added:
                        if submit_organization_form(driver, org_name):
                            status_message = f"Éxito: Org '{org_name}' creada."
                            all_steps_successful = True
                        else:
                            status_message = f"Error: Fallo al enviar form para {org_name}"
                    # else: status_message ya está seteado por el fallo en add_additional_user_field
                else:
                    status_message = f"Error: Fallo al config. pago para {org_name}"
            else:
                status_message = f"Error: Fallo al rellenar detalles para {org_name}"

            logger.info(f"Fila {current_row_in_sheet}: Resultado final - {status_message}")
            update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message) # Columna D
            update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, processing_status_column_index, "Completado" if all_steps_successful else "Error Final") # Columna E
            
            initial_navigation_successful = False # Forzar re-navegación para la siguiente org
            
        logger.info("Flujo de E-Socios completado para todas las filas procesables del sheet.")

    except Exception as e:
        logger.error(f"Error crítico en el flujo principal de E-Socios: {e}", exc_info=True)
    finally:
        if driver:
            logger.info("Cerrando WebDriver de E-Socios.")
            driver.quit()

if __name__ == '__main__':
    main_esocios_flow() 