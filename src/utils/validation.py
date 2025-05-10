import logging
import requests
import re

logger = logging.getLogger(__name__)

def _validate_questions(questions_list):
    """Valida las preguntas según las reglas especificadas.

    Args:
        questions_list (list): Lista de diccionarios de preguntas de config_actual.

    Returns:
        tuple: (str, list) - Estado general ('ok' o 'error') y lista de preguntas inválidas (dict con 'name', 'reason' y 'options_found').
    """
    invalid_questions = []
    required_options = {'apruebo', 'rechazo', 'abstención'}

    if not isinstance(questions_list, list):
        logger.warning("Se esperaba una lista para validar preguntas, se recibió: %s", type(questions_list))
        return 'error', [{'name': '[Estructura Inválida]', 'reason': 'Se esperaba una lista de preguntas.'}]

    for q in questions_list:
        if not isinstance(q, dict):
            logger.warning("Item inválido encontrado en lista de preguntas (no es dict): %s", q)
            # Opcional: añadir a invalid_questions si se quiere reportar
            invalid_questions.append({'name': '[Item Inválido]', 'reason': 'El item en la lista no es un diccionario.'})
            continue

        name = q.get('name', '[Pregunta sin nombre]')
        name_lower = name.lower()

        # Asunción: el flag 'secret' está en q['config']['secret']
        # Si es diferente, ajustar esta línea:
        is_secret = q.get('config', {}).get('secret', False)
        is_director_election = (
            ('elección' in name_lower or 'eleccion' in name_lower or 'designación' in name_lower or 'designacion' in name_lower)
            and ('director' in name_lower or 'directorio' in name_lower)
        )
        # Chequear si es informativa
        is_informative = '[informativa]' in name_lower

        # Saltar validación si es secreta, elección de directorio o informativa
        if is_secret or is_director_election or is_informative:
            logger.debug(f"Pregunta '{name}' omitida de validación (secreta/directorio/informativa)." )
            continue

        # Validar opciones para preguntas públicas no de directorio
        current_options = q.get('options', [])
        if not isinstance(current_options, list):
            logger.warning(f"Opciones inválidas para pregunta '{name}' (no es lista): {current_options}")
            invalid_questions.append({
                'name': name,
                'reason': f"Formato de opciones inválido (se esperaba una lista)."
            })
            continue # Pasar a la siguiente pregunta

        # Extraer nombres de opciones, asegurando que sean strings y en minúsculas
        current_options_set = set()
        for opt in current_options:
            if isinstance(opt, dict) and isinstance(opt.get('name'), str):
                opt_name_lower = opt['name'].lower().strip()
                if opt_name_lower: # Ignorar nombres vacíos
                    current_options_set.add(opt_name_lower)
            else:
                logger.warning(f"Opción inválida encontrada en pregunta '{name}': {opt}")
                # Opcional: añadir a invalid_questions si se quiere ser más estricto

        if current_options_set != required_options:
            options_found_list = sorted(list(current_options_set))
            reason = f"Opciones encontradas: {options_found_list if options_found_list else 'Ninguna'}. Se esperaban: {sorted(list(required_options))}."
            logger.warning(f"Validación fallida para pregunta '{name}': {reason}")
            invalid_questions.append({
                'name': name,
                'reason': reason,
                'options_found': options_found_list
            })

    status = 'ok' if not invalid_questions else 'error'
    logger.info(f"Validación de preguntas finalizada. Estado: {status}. Inválidas: {len(invalid_questions)}")
    return status, invalid_questions

def _validate_revisa_js_slug(config_actual: dict, expected_slug: str) -> dict:
    """Valida si el meeting_id en revisa.js coincide con el slug esperado.

    Args:
        config_actual (dict): Configuración actual extraída (contiene landing_url).
        expected_slug (str): El slug esperado para la junta.

    Returns:
        dict: Un diccionario con el resultado de la validación:
              {'status': 'ok'|'mismatch'|'error'|'not_found'|'skipped', 
               'message': str, 
               'js_url': str | None, 
               'found_id': str | None,
               'expected_slug': str}
    """
    logger.info(f"Iniciando validación de slug en revisa.js para slug esperado: {expected_slug}")
    
    # --- Get landing_url ---
    # Assuming path based on previous exploration of report structure
    config_general = config_actual.get('configuracion_general', {})
    # Correctly access nested landing_url
    landing_url = config_general.get('config', {}).get('landing_url') 

    result = {
        'status': 'skipped', 
        'message': 'No se inició la validación.', 
        'js_url': None, 
        'found_id': None,
        'expected_slug': expected_slug
    }

    if not landing_url:
        result['status'] = 'config_missing'
        result['message'] = "No se encontró 'landing_url' en la configuración actual para verificar revisa.js."
        logger.warning(result['message'])
        return result

    # --- Prepend protocol if missing ---
    if isinstance(landing_url, str) and not landing_url.startswith(('http://', 'https://')):
        logger.info(f"Prefijando 'https://' a la landing_url: {landing_url}")
        landing_url = f"https://{landing_url}"
        # Update the landing_url within config_actual as well for consistency downstream, if needed elsewhere?
        # Consider if this mutation is desired or if it should only affect the local variable.
        # For now, only updating local variable `landing_url` used for validation.
        # config_general.setdefault('config', {})['landing_url'] = landing_url # Optional: Update the source dict

    # --- Validate URL format ---
    if not isinstance(landing_url, str) or not landing_url.startswith(('http://', 'https://')):
        result['status'] = 'error'
        # The message now reflects the potentially corrected URL if prefix was added
        result['message'] = f"El 'landing_url' ({landing_url}) no es una URL válida incluso después de intentar corregirla."
        logger.warning(result['message'])
        return result
        
    # Ensure landing_url doesn't end with a slash before appending
    if landing_url.endswith('/'):
        landing_url = landing_url[:-1]
        
    js_url = f"{landing_url}/js/revisa.js"
    result['js_url'] = js_url
    logger.info(f"Intentando obtener JS desde: {js_url}")

    # --- Fetch JS Content ---
    try:
        response = requests.get(js_url, timeout=15) # 15 seconds timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        # Check content type - optional but good practice
        content_type = response.headers.get('content-type', '').lower()
        if 'javascript' not in content_type:
             logger.warning(f"URL {js_url} devolvió Content-Type inesperado: {content_type}")
             # Continue anyway, maybe it's still JS

        js_content = response.text
        logger.info(f"Contenido de {js_url} obtenido exitosamente.")

    except requests.exceptions.Timeout:
        result['status'] = 'error'
        result['message'] = f"Timeout al intentar obtener {js_url}."
        logger.error(result['message'])
        return result
    except requests.exceptions.RequestException as e:
        result['status'] = 'error'
        result['message'] = f"Error de red al obtener {js_url}: {e}"
        logger.error(result['message'])
        return result
    except Exception as e: # Catch potential decoding errors or others
        result['status'] = 'error'
        result['message'] = f"Error inesperado al procesar la respuesta de {js_url}: {e}"
        logger.error(result['message'], exc_info=True)
        return result

    # --- Extract meeting_id ---
    # Regex to find: const meeting_id = "..." or '...' ; might have spaces
    match = re.search(r"meeting_id\s*=\s*[\"']([^\"']+)[\"']", js_content)
    
    if not match:
        result['status'] = 'not_found'
        result['message'] = f"No se pudo encontrar la variable 'meeting_id' en {js_url}."
        logger.warning(result['message'])
        return result
        
    found_id = match.group(1)
    result['found_id'] = found_id
    logger.info(f"Meeting ID encontrado en {js_url}: '{found_id}'")

    # --- Compare ---
    if found_id == expected_slug:
        result['status'] = 'ok'
        result['message'] = f"Coincidencia: El 'meeting_id' ('{found_id}') en {js_url} coincide con el slug esperado."
        logger.info(result['message'])
    else:
        result['status'] = 'mismatch'
        result['message'] = f"Discrepancia: El 'meeting_id' ('{found_id}') en {js_url} NO coincide con el slug esperado ('{expected_slug}')."
        logger.warning(result['message'])
        
    return result 