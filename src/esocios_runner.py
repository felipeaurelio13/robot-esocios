import logging
import os
import time
from dotenv import load_dotenv # Ensure dotenv is loaded for this script too if .env is used directly here

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Assuming these modules/classes exist and are correctly structured
from src.webdriver_setup import setup_webdriver # Assuming this function is available
from src.auth_manager import AuthManager
from src.config import EVOTING_USERNAME, EVOTING_PASSWORD # Credentials from config
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
            
            logger.info(f"Escribiendo '{search_term}' en el campo de Organización padre...")
            autocomplete_input.clear()
            autocomplete_input.send_keys(search_term)
            time.sleep(1.5) # Aumentar ligeramente la pausa para que aparezcan las opciones

            # Esperar y hacer clic en la PRIMERA opción del desplegable.
            # Las opciones de Material UI suelen estar en un ul con role="listbox".
            # Queremos el primer 'li' dentro de ese 'ul'.
            first_option_xpath = "//ul[@role='listbox']/li[1]" 
            
            logger.info(f"Esperando la primera opción en el desplegable usando XPath: {first_option_xpath}...")
            try:
                parent_option = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, first_option_xpath))
                )
                logger.info(f"Primera opción encontrada: '{parent_option.text}'. Haciendo clic...")
                parent_option.click()
                time.sleep(0.5) # Pequeña pausa después del clic
            except TimeoutException:
                logger.error(f"No se encontró ninguna opción en el desplegable para '{search_term}' después de escribir.")
                driver.save_screenshot(f"error_fill_parent_org_no_options_{time.strftime('%Y%m%d-%H%M%S')}.png")
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
        # El ID :rl: es dinámico. Usar XPath basado en tipo y texto.
        submit_button_xpath = "//button[@type='submit' and contains(normalize-space(), 'Agregar')]"
        
        submit_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
        )
        submit_button.click()
        logger.info("Botón 'Agregar' clickeado.")

        # Esperar la confirmación. Esto es la parte más incierta y necesitará ajuste.
        # Opción 1: Redirección a la página de lista de organizaciones.
        # Opción 2: Aparición de un mensaje de éxito (snackbar/toast).
        # Opción 3: Desaparición de elementos clave del formulario (ej. el mismo botón de submit o el título de "Crear").

        # Por ahora, intentaremos detectar una redirección a la página de organizaciones
        # O, si nos quedamos en la misma URL (add), que aparezca un mensaje de éxito.
        # Esta URL es a la que esperamos ser redirigidos tras un éxito.
        expected_redirect_url = ESOCIOS_ORGANIZATIONS_URL 
        
        try:
            WebDriverWait(driver, 25).until(EC.url_to_be(expected_redirect_url))
            logger.info(f"Redirección a {expected_redirect_url} detectada. Asumiendo éxito para {org_name}.")
            # Adicionalmente, podríamos verificar si la nueva organización aparece en la lista,
            # pero eso añadiría complejidad ahora.
            return True
        except TimeoutException:
            # Si no hubo redirección, quizás hubo un error en la página o un mensaje de éxito.
            current_url_after_submit = driver.current_url
            logger.warning(f"No hubo redirección a {expected_redirect_url} después de 25s. URL actual: {current_url_after_submit}")
            
            # Intentar buscar un mensaje de éxito genérico (esto es muy especulativo)
            # Los snackbars de Material UI a menudo tienen role="alert" o clases específicas.
            success_message_xpath = "//*[contains(@class, 'MuiAlert-filledSuccess') or @role='alert'][contains(normalize-space(), 'Organización creada') or contains(normalize-space(), 'éxito') or contains(normalize-space(), 'correctamente')]"
            try:
                success_element = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, success_message_xpath))
                )
                logger.info(f"Mensaje de éxito encontrado: '{success_element.text}'. Asumiendo éxito para {org_name}.")
                return True
            except TimeoutException:
                logger.error(f"No se detectó redirección ni mensaje de éxito claro para {org_name}. El formulario podría haber fallado o la UI es diferente.")
                driver.save_screenshot(f"error_submit_no_confirmation_{org_name.replace(' ','_')}_{time.strftime('%Y%m%d-%H%M%S')}.png")
                return False

    except TimeoutException as e:
        logger.error(f"Timeout esperando el botón 'Agregar' para {org_name}: {e}", exc_info=True)
        driver.save_screenshot(f"error_submit_timeout_btn_{org_name.replace(' ','_')}_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al enviar el formulario para {org_name}: {e}", exc_info=True)
        driver.save_screenshot(f"error_submit_unexpected_{org_name.replace(' ','_')}_{time.strftime('%Y%m%d-%H%M%S')}.png")
        return False

def main_esocios_flow():
    """Función principal para el flujo de creación de organizaciones en E-Socios."""
    # Cargar variables de entorno para asegurar que HEADLESS_MODE esté disponible para setup_webdriver
    # Aunque setup_webdriver llama a load_dotenv(), llamarlo aquí también es seguro y explícito.
    load_dotenv() 

    driver = None
    try:
        logger.info("Configurando WebDriver...")
        # Llamada a setup_webdriver actualizada para no pasar el argumento 'headless'
        driver = setup_webdriver() 
        if not driver:
            logger.error("No se pudo configurar el WebDriver. Abortando.")
            return

        if not login_to_esocios(driver):
            logger.error("Fallo en el login de E-Socios. Abortando.")
            # No se puede escribir en la hoja si el login falla y no hemos leído la hoja aún.
            return
        
        logger.info("Login exitoso. Procediendo con los siguientes pasos...")

        # 1. Leer datos del Google Sheet
        # Estos podrían moverse a variables de entorno o a config.py
        spreadsheet_url_or_id = os.getenv("SPREADSHEET_URL_OR_ID")
        sheet_name = os.getenv("SHEET_NAME", "Slugs")
        slug_column_header = "Slug"
        org_name_column_header = "Nombre Organización"
        parent_org_column_header = "Organización padre"
        status_column_index = 4 # Columna D para el estado
        
        logger.info(f"Leyendo datos desde Google Sheet ID: {spreadsheet_url_or_id}, Hoja: {sheet_name}")
        sheet_data = read_sheet_data(spreadsheet_url_or_id, sheet_name)
        
        if not sheet_data:
            logger.warning("No se encontraron datos en el Google Sheet o no se pudo acceder. Abortando.")
            # No hay filas para actualizar aquí.
            return

        logger.info(f"Se encontraron {len(sheet_data)} filas de datos en el Google Sheet.")

        # La navegación a la página de creación se hace una vez si es posible,
        # y luego se reintenta por cada organización si falla o después de un éxito.
        initial_navigation_successful = navigate_to_create_organization_page(driver)
        if not initial_navigation_successful:
            logger.error("Fallo inicial al navegar a la página de creación de organizaciones. Se intentará por organización.")

        for i, row in enumerate(sheet_data):
            current_row_in_sheet = i + 2 # i es 0-indexed, sheets son 1-indexed, +1 por el header
            status_message = ""

            # Siempre intentar navegar a la página de creación al inicio de cada iteración
            # si la navegación inicial falló o después de procesar una organización.
            if not initial_navigation_successful or i > 0: # i > 0 para re-navegar después de la primera
                if not navigate_to_create_organization_page(driver):
                    status_message = "Error: Fallo al navegar a la página de creación"
                    logger.error(f"{status_message} para la fila {current_row_in_sheet}.")
                    update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message)
                    continue # Pasar a la siguiente fila
                else:
                    initial_navigation_successful = True # Se logró navegar para esta o una iteración futura

            slug = row.get(slug_column_header)
            org_name = row.get(org_name_column_header)
            parent_org_name = row.get(parent_org_column_header)
            
            logger.info(f"Procesando fila {current_row_in_sheet} del sheet: Slug='{slug}', Nombre='{org_name}', Padre='{parent_org_name}'")

            if not slug or not org_name:
                status_message = "Error: Datos faltantes (Slug o Nombre Organización)"
                logger.warning(f"{status_message} en fila {current_row_in_sheet}. Slug: '{slug}', Nombre: '{org_name}'")
                update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message)
                continue
            
            logger.info(f"Comenzando procesamiento en E-Socios para la organización: {org_name} (Slug: {slug})")
            
            if not fill_organization_details(driver, org_name, parent_org_name):
                status_message = f"Error: Fallo al rellenar detalles básicos para {org_name}"
                logger.error(f"{status_message}. Saltando esta organización.")
                update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message)
                initial_navigation_successful = False # Forzar re-navegación
                continue

            if not configure_payment_features(driver):
                status_message = f"Error: Fallo al configurar funcionalidades de pago para {org_name}"
                logger.error(f"{status_message}. Saltando esta organización.")
                update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message)
                initial_navigation_successful = False # Forzar re-navegación
                continue

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
                    status_message = f"Error: Fallo al añadir campo adicional '{field['name']}' para {org_name}"
                    logger.error(f"{status_message}. Se detiene la adición de más campos para esta organización.")
                    all_additional_fields_added = False
                    break
            
            if not all_additional_fields_added:
                # El status_message ya se estableció en el bucle anterior
                update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message)
                initial_navigation_successful = False # Forzar re-navegación
                continue

            if not submit_organization_form(driver, org_name):
                status_message = f"Error: Fallo al enviar formulario para {org_name}"
                logger.error(f"{status_message}. Saltando esta organización.")
                update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message)
                initial_navigation_successful = False # Forzar re-navegación
                continue
            else:
                status_message = f"Éxito: Organización '{org_name}' creada y formulario enviado."
                logger.info(status_message)
                update_cell_in_sheet(spreadsheet_url_or_id, sheet_name, current_row_in_sheet, status_column_index, status_message)
                initial_navigation_successful = False # Forzar re-navegación para la siguiente organización
            
        logger.info("Flujo de E-Socios completado para todas las filas del sheet.")

    except Exception as e:
        logger.error(f"Error crítico en el flujo principal de E-Socios: {e}", exc_info=True)
        # Aquí podría ser útil escribir un estado general de error si es posible, 
        # pero no tenemos una fila específica a menos que el error ocurra dentro del bucle.
    finally:
        if driver:
            logger.info("Cerrando WebDriver de E-Socios.")
            driver.quit()

if __name__ == '__main__':
    # Asegurarse de que .env se carga si se usa (generalmente en el entrypoint principal de la app)
    # from dotenv import load_dotenv
    # load_dotenv() 
    main_esocios_flow() 