import logging
import re
import json
import difflib
import string
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Import data específico de AFPs (Necesario para la verificación de grupo AFP)
from src.shareholder_manager import KNOWN_AFP_DATA
from .validation import _validate_revisa_js_slug

# --- Definición de Anfitriones Alternativos Base --- 
# Mover aquí para que sea importable
BASE_EXPECTED_ALTERNATIVE_HOSTS: List[str] = [
    'nvenegas@evoting.cl', 'hgonzalez@evoting.cl', 'nmolina@evoting.cl',
    'aparra@evoting.cl', 'jantinao@evoting.cl', 'hola@evoting.cl',
    'mrojas@evoting.cl', 'fcavada@evoting.cl', 'florca@evoting.cl',
    'administrador2@evoting.cl'
]
# ---------------------------------------------------

logger = logging.getLogger(__name__) # Usar logger específico del módulo

def _validate_series_configuration(config_actual: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Valida que si hay múltiples series, todas tengan los checks activados.

    Args:
        config_actual (dict): Configuración actual obtenida de Selenium/API.

    Returns:
        list: Lista de alertas si la validación falla.
    """
    alerts = []
    shares_config = config_actual.get('configuracion_general', {}).get('shares', {})
    
    if not shares_config or not isinstance(shares_config, dict):
        logger.warning("No se encontró configuración de 'shares' válida para validar.")
        return alerts # No hay series para validar

    series_list = list(shares_config.values())
    
    if len(series_list) > 1:
        logger.info(f"Validando configuración de checks para {len(series_list)} series.")
        for serie in series_list:
            serie_name = serie.get('name', 'Desconocida')
            is_attendance = serie.get('attendance', False)
            is_show_on_header = serie.get('showOnHeader', False)
            is_show_on_attendance = serie.get('showOnAttendance', False)

            if not (is_attendance and is_show_on_header and is_show_on_attendance):
                # Guardar el estado de todos los checks relevantes
                check_status = {
                    "Suma a la asistencia": is_attendance,
                    "Se muestra en resumen de usuario": is_show_on_header,
                    "Se muestra en la asistencia": is_show_on_attendance
                }
                # Crear lista de nombres faltantes para el log y mensaje (opcional)
                missing_checks_names = [name for name, status in check_status.items() if not status]
                                
                alerts.append({
                    "section": "configuracion",
                    "field": "series",
                    "identifier": f"Serie '{serie_name}'",
                    "type": "validacion_checks_multiples_series",
                    "expected": "Todos los checks requeridos activos",
                    "actual": f"Checks desactivados: {len(missing_checks_names)}", # Opcional: mostrar conteo
                    "details": {"check_status": check_status}, # Guardar el estado de cada check
                    "severity": "warning",
                    "message": f"Alerta: La serie '{serie_name}' tiene checks desactivados, pero existen múltiples series."
                })
                logger.warning(f"Validación fallida para serie '{serie_name}': Estado checks: {check_status}")
            else:
                 logger.debug(f"Serie '{serie_name}' validada correctamente (múltiples series).")
                 
    else:
        logger.info("Validación de checks de múltiples series omitida (solo hay una serie o ninguna).")

    return alerts

def _compare_configurations(config_expected, config_actual):
    """Compara config_expected (de docs) con config_actual (estructura unificada de API/Selenium).

    Args:
        config_expected (dict): Configuración extraída de los documentos.
        config_actual (dict): Configuración obtenida de Selenium/API.

    Returns:
        list: Una lista de diccionarios, cada uno representando una diferencia encontrada.
              Devuelve una lista vacía si no hay diferencias.
    """
    differences = []
    logger.info("Iniciando comparación entre configuración de documentos y datos actuales...")

    fuente_actual = config_actual.get('fuente', 'Desconocida')
    logger.info(f"Fuente de datos actuales: {fuente_actual}")

    # --- Obtener datos de ambas fuentes --- 
    junta_expected = config_expected.get('configuracion', {}).get('junta', {})
    junta_actual = config_actual.get('junta', {}) # Contiene nombre, tipo, estado (copiados de API)
    config_general_api = config_actual.get('configuracion_general', {}) # Contiene company, start_date

    # --- Comparación Campos Generales --- 

    # 1. Comparar Nombre de la EMPRESA/ORGANIZACIÓN
    expected_org = junta_expected.get('organizacion')
    actual_org = config_general_api.get('company')
    if expected_org and actual_org and expected_org != actual_org:
        differences.append({
            "section": "junta",
            "field": "organizacion", # Campo específico para la empresa
            "type": "valor_distinto",
            "expected": expected_org,
            "actual": actual_org,
            "severity": "warning"
        })

    # 2. Comparar TÍTULO de la Junta
    expected_title = junta_expected.get('nombre') # Título junta desde Docs
    actual_title = junta_actual.get('nombre')    # Título junta desde API (ya estaba bien)
    if expected_title and actual_title and expected_title != actual_title:
         differences.append({
             "section": "junta",
             "field": "nombre", # Campo específico para el título
             "type": "valor_distinto",
             "expected": expected_title,
             "actual": actual_title,
             "severity": "warning"
         })

    # 3. Comparar TIPO de la Junta
    expected_type = junta_expected.get('tipo') # Tipo desde Docs (puede no venir)
    actual_type = junta_actual.get('tipo') # Usar 'tipo' copiado
    if expected_type and actual_type and expected_type != actual_type:
         differences.append({
             "section": "junta",
             "field": "tipo",
             "type": "valor_distinto",
             "expected": expected_type,
             "actual": actual_type,
             "severity": "warning"
         })
    # ... añadir otras comparaciones de junta si es necesario ...

    # --- Comparación Posicional de Preguntas --- 
    logger.info("Realizando comparación posicional de preguntas...")
    expected_preguntas_list = config_expected.get('configuracion', {}).get('preguntas', [])
    actual_preguntas_list_raw = config_actual.get('preguntas', [])

    # Ordenar lista ACTUAL (Selenium) por 'order' antes de extraer títulos
    def get_order(item):
        if isinstance(item, dict):
            order_val = item.get('order')
            if isinstance(order_val, (int, float)):
                return order_val
        return float('inf') # Poner items sin orden válido al final

    actual_preguntas_list = sorted(actual_preguntas_list_raw, key=get_order)
    logger.info(f"Ordenadas {len(actual_preguntas_list)} preguntas actuales por 'order' para comparación.")

    # Extraer títulos LITERALES manteniendo el orden (ahora ordenado por 'order')
    expected_literal_titles = [p.get('titulo', '') for p in expected_preguntas_list if isinstance(p, dict)] # Mantenemos orden original de docs
    actual_literal_titles = [p.get('name', '') for p in actual_preguntas_list if isinstance(p, dict)] # Ahora ordenado por 'order'

    # Helper de normalización (copiado para uso local en la comparación)
    def _normalize_for_check(text):
        if not isinstance(text, str):
            return ""
        
        # 1. Convertir a minúsculas
        text = text.lower()
        
        # 2. Quitar prefijos como "1.", "a)" etc. (mantener esta lógica)
        text = re.sub(r"^\s*[a-z0-9][\.\)]\s*", "", text).strip()
        
        # 3. Eliminar puntuación común (excepto quizás guiones si son significativos)
        # Creamos un string con la puntuación a eliminar
        # Podemos ajustar esto si algún signo SÍ es importante
        punctuation_to_remove = string.punctuation.replace('-', '') # Ejemplo: mantener guiones
        # Crear tabla de traducción para eficiencia
        translator = str.maketrans('', '', punctuation_to_remove)
        text = text.translate(translator)
        
        # 4. Reemplazar todos los caracteres de espacio (incluidos no estándar) por un solo espacio
        text = re.sub(r"\s+", " ", text)
        
        # 5. Eliminar espacios al inicio/final (redundante pero seguro)
        text = text.strip()
        
        return text

    comparison_details = []
    overall_match = True # Asumir éxito inicial
    max_len = max(len(expected_literal_titles), len(actual_literal_titles))

    for i in range(max_len):
        exp_title = expected_literal_titles[i] if i < len(expected_literal_titles) else None
        act_title = actual_literal_titles[i] if i < len(actual_literal_titles) else None

        # 1. Comparación NORMALIZADA (para determinar si conceptualmente son iguales)
        norm_exp = _normalize_for_check(exp_title) if exp_title else None
        norm_act = _normalize_for_check(act_title) if act_title else None
        match = (norm_exp is not None) and (norm_act is not None) and (norm_exp == norm_act)

        # 2. Comparación LITERAL (para detectar diferencias exactas)
        literal_match = (exp_title is not None) and (act_title is not None) and (exp_title == act_title)

        # 3. Generar detalles de la diferencia si no hay match literal
        diff_html = None
        diff_type = 'none' # none, sutil, major
        if not literal_match:
            if match: # Normalizado coincide -> diferencia sutil
                diff_type = 'sutil'
            else: # Ni literal ni normalizado -> diferencia mayor
                diff_type = 'major'
            
            # Generar diff HTML usando difflib para resaltar cambios
            # Usaremos Differ para un formato simple con marcadores +/-/?, aunque HtmlDiff es más visual.
            # HtmlDiff puede ser muy verboso para cambios pequeños, probemos con Differ.
            # Necesitamos asegurar que ambos inputs sean listas de strings (líneas)
            # Como son títulos cortos, trataremos cada título como una sola línea.
            expected_lines = [exp_title or ""] # Tratar None como vacío
            actual_lines = [act_title or ""]
            
            # Usar ndiff para obtener líneas con marcadores (+ - ?)
            diff_result = list(difflib.ndiff(expected_lines, actual_lines))
            
            # Convertir a un HTML simple para visualización
            diff_html_parts = []
            for line in diff_result:
                if line.startswith('+ '):
                    diff_html_parts.append(f'<ins style="background-color: #ccffcc; text-decoration: none;">{line[2:]}</ins>')
                elif line.startswith('- '):
                    diff_html_parts.append(f'<del style="background-color: #ffcccc; text-decoration: none;">{line[2:]}</del>')
                elif line.startswith('? '):
                    # Línea de información de difflib, la ignoramos o la mostramos de forma especial
                    pass # Opcional: diff_html_parts.append(f'<span style="color: blue;">{line[2:]}</span>')
                else: # Líneas sin cambios (no deberían ocurrir con ndiff en este caso simple)
                    diff_html_parts.append(line) # o line[2:] si tiene prefijo de espacio
            diff_html = ' '.join(diff_html_parts) # Unir en una sola línea para display simple

        comparison_details.append({
            "index": i + 1,
            "expected": exp_title,
            "actual": act_title,
            "match": match, # Coincidencia normalizada (conceptual)
            "literal_match": literal_match, # Coincidencia exacta
            "diff_type": diff_type, # 'none', 'sutil', 'major'
            "diff_html": diff_html # HTML con resaltado o None
        })

        # Si cualquier par no coincide (conceptual), el match general es falso
        if not match:
            overall_match = False

    # Añadir el resultado como un bloque informativo SOLO SI HAY DETALLES
    if comparison_details:
        differences.append({
            "section": "preguntas",
            "field": "comparacion_posicional",
            "type": "lista_preguntas_comparadas", 
            "details": comparison_details, # Lista de resultados por posición
            "overall_match": overall_match, # Booleano general
            "severity": "info" 
        })
        logger.info(f"Comparación posicional de preguntas: Coincidencia general={overall_match}")
    else:
        logger.info("No se encontraron preguntas en ninguna fuente para comparación posicional (bloque NO añadido).") # Mensaje actualizado

    # --- Comparación de Accionistas (DESACTIVADA) ---
    logger.info("Comparación de accionistas desactivada (ya no se extraen de documentos).")
    # [El código de comparación de accionistas original (custodios y listas) se omite]

    # --- Comparación de Usuarios (DESACTIVADA) ---
    logger.info("Comparación de usuarios desactivada (ya no se extraen de documentos).")
    # [El código de comparación de usuarios original se omite]

    # --- Validación de Configuración de Series (Nueva) ---
    logger.info("Iniciando validación de configuración de series...")
    series_alerts = _validate_series_configuration(config_actual)
    if series_alerts:
        differences.extend(series_alerts)
        logger.info(f"Se añadieron {len(series_alerts)} alertas de validación de series.")
    else:
        logger.info("Validación de configuración de series OK.")

    # --- Verificación de Grupo AFP --- 
    logger.info("Iniciando verificación de grupo AFP...")
    afp_list = config_actual.get('afp_list', []) # Obtener lista específica de AFPs

    if not afp_list:
        logger.info("No se encontró lista de AFPs (afp_list) o la llamada falló. Omitiendo verificación de grupo AFP.")
    else:
        grupos_afp = set()
        nombres_inconsistentes = []
        for afp in afp_list:
            # Verificar consistencia del nombre (opcional pero útil)
            nombre_afp = afp.get('name', '')
            if 'afp' not in nombre_afp.lower():
                nombres_inconsistentes.append(f"{nombre_afp} ({afp.get('identity', 'N/A')})")

            # Recopilar el grupo
            grupo = afp.get('group') # Obtener valor del campo group
            if grupo: # Ignorar grupos nulos o vacíos
                grupos_afp.add(grupo)
            else:
                 # Considerar si un grupo vacío/nulo es un problema en sí mismo
                 grupos_afp.add("[GRUPO VACÍO/NULO]") # Añadir marcador para detectarlo

        # Reportar nombres inconsistentes si los hay
        if nombres_inconsistentes:
            differences.append({
                "section": "afp", "identifier": "Consistencia Nombres",
                "field": "nombre", "type": "afp_nombre_inconsistente",
                "expected": "Contener 'AFP'", "actual": f"Nombres sin 'AFP': {', '.join(nombres_inconsistentes)}",
                "severity": "warning"
            })

        # Evaluar los grupos encontrados
        num_grupos_validos = len([g for g in grupos_afp if g != "[GRUPO VACÍO/NULO]"])

        if not grupos_afp:
            # Esto no debería pasar si afp_list no está vacía, pero por si acaso
             differences.append({
                "section": "afp", "identifier": "Agrupación",
                "field": "grupo", "type": "afp_sin_grupo_definido",
                "expected": "Un grupo único definido", "actual": "Ningún grupo encontrado",
                "severity": "danger"
            })
        elif "[GRUPO VACÍO/NULO]" in grupos_afp and num_grupos_validos == 0:
             # Todas las AFPs tienen grupo vacío/nulo
             differences.append({
                "section": "afp", "identifier": "Agrupación",
                "field": "grupo", "type": "afp_grupo_vacio_o_nulo",
                "expected": "Un grupo único definido", "actual": "Grupo vacío/nulo para todas",
                "severity": "danger"
            })
        elif len(grupos_afp) > 1:
            # Hay más de un grupo (incluyendo potencialmente el marcador de vacío)
            differences.append({
                "section": "afp", "identifier": "Agrupación",
                "field": "grupo", "type": "afp_multiples_grupos",
                "expected": "Un grupo único", "actual": f"Grupos encontrados: {list(grupos_afp)}",
                "severity": "danger"
            })
        else: # Solo un grupo y no es el marcador de vacío
             grupo_unico = list(grupos_afp)[0]
             logger.info(f"Verificación AFP OK: Todas las AFPs pertenecen al grupo único: '{grupo_unico}'")
    # --- FIN Verificación Grupo AFP ---

    # --- Verificación Anfitriones Alternativos Zoom ---
    logger.info("Iniciando verificación de anfitriones alternativos de Zoom...")
    zoom_config_actual = config_actual.get('configuracion_general', {}).get('zoom', {})

    if not zoom_config_actual or not isinstance(zoom_config_actual, dict):
        logger.warning("No se encontró configuración de Zoom ('configuracion_general.zoom') en los datos actuales o no es un diccionario. Omitiendo verificación.")
    else:
        actual_host_email = zoom_config_actual.get('host_email')
        alternative_hosts_list_actual = zoom_config_actual.get('alternative_hosts', []) # Lista de dicts

        if not actual_host_email:
             logger.warning("No se encontró 'host_email' en la configuración de Zoom. No se puede determinar la lista final esperada de alternativos.")
        else:
            # Crear la lista final esperada: todos los base excepto el host actual
            final_expected_alternative_hosts = set(h.lower() for h in BASE_EXPECTED_ALTERNATIVE_HOSTS if h.lower() != actual_host_email.lower())
            logger.debug(f"[Zoom Check] Host actual: {actual_host_email}") # DEBUG
            logger.debug(f"[Zoom Check] Hosts alternativos esperados (set): {final_expected_alternative_hosts}") # DEBUG
            
            # Extraer emails actuales de la lista de diccionarios
            actual_alternative_emails = set()
            if isinstance(alternative_hosts_list_actual, list):
                for host_dict in alternative_hosts_list_actual:
                    if isinstance(host_dict, dict) and 'email' in host_dict:
                        actual_alternative_emails.add(host_dict['email'].lower())
            logger.debug(f"[Zoom Check] Hosts alternativos actuales (set): {actual_alternative_emails}") # DEBUG
            
            # Encontrar los faltantes
            missing_hosts = final_expected_alternative_hosts - actual_alternative_emails
            logger.debug(f"[Zoom Check] Hosts alternativos faltantes calculados: {missing_hosts}") # DEBUG

            # Condición para añadir la diferencia
            if missing_hosts:
                logger.warning(f"Anfitriones alternativos faltantes en Zoom: {missing_hosts}") # Este log ya existía
                differences.append({
                    "section": "zoom",
                    "field": "alternative_hosts",
                    "type": "faltan_anfitriones_alternativos",
                    "expected": f"Esperados (excluyendo host {actual_host_email}): {sorted(list(final_expected_alternative_hosts))}",
                    "actual": f"Actuales: {sorted(list(actual_alternative_emails))}",
                    "details": {"faltantes": sorted(list(missing_hosts))},
                    "severity": "warning"
                })
            else:
                 logger.info("Verificación de anfitriones alternativos de Zoom OK. Todos los esperados (excluyendo host) están presentes.")

    # --- Verificación de Alertas de Plataforma (ELIMINADA DE COMPARACIÓN) --- 
    logger.info("Verificación de alertas de plataforma eliminada de la comparación.")
    # [El código de comparación de alertas se omite]

    logger.info(f"Comparación finalizada. Diferencias informativas generadas: {len(differences)}")
    return differences 


def generate_comparison_report_data(config_expected, config_actual):
    """Genera los datos estructurados para el reporte de comparación.

    Llama a _compare_configurations y luego procesa los resultados para
    incluir conteos totales y por sección.

    Args:
        config_expected (dict): Configuración extraída de los documentos.
        config_actual (dict): Configuración obtenida de Selenium/API.

    Returns:
        dict: Un diccionario listo para pasar a la plantilla HTML, con:
              - total_diff_count (int)
              - diff_counts_by_section (dict)
              - detailed_differences (list)
    """
    detailed_differences = _compare_configurations(config_expected, config_actual)
    
    total_diff_count = len(detailed_differences)
    diff_counts_by_section = {}

    # Extraer las secciones de preguntas para contar sus diferencias internas
    preguntas_comparison = next((item for item in detailed_differences if item.get("section") == "preguntas" and item.get("type") == "lista_preguntas_comparadas"), None)
    
    preguntas_diff_count = 0
    if preguntas_comparison and not preguntas_comparison.get('overall_match', True):
        # Contar cuántos items en 'details' tienen 'match': False
        preguntas_diff_count = sum(1 for detail in preguntas_comparison.get('details', []) if not detail.get('match'))
        
    if preguntas_diff_count > 0:
        diff_counts_by_section['preguntas'] = preguntas_diff_count
        # Asegurarse de que la sección 'preguntas' no se cuente dos veces en el bucle principal
        # (Asumimos que las diferencias de preguntas se manejan solo a través de 'overall_match')
    else:
        diff_counts_by_section['preguntas'] = 0 # Inicializar si no hay diferencias

    # Contar otras diferencias por sección
    for diff in detailed_differences:
        section = diff.get("section")
        # No contar la sección 'preguntas' aquí si ya la contamos arriba
        if section and section != 'preguntas': 
            diff_counts_by_section[section] = diff_counts_by_section.get(section, 0) + 1
        elif section == 'preguntas' and section not in diff_counts_by_section:
            # Asegurar que 'preguntas' exista si no se encontró en la lógica anterior
             diff_counts_by_section['preguntas'] = 0

    # Asegurar que secciones importantes siempre existan en el conteo, incluso con 0 diferencias
    for section_key in ['junta', 'afp']: # Añadir otras secciones si es necesario
        if section_key not in diff_counts_by_section:
            diff_counts_by_section[section_key] = 0
            
    logger.info(f"Datos de comparación generados. Total Diferencias: {total_diff_count}. Por sección: {diff_counts_by_section}")

    return {
        "total_diff_count": total_diff_count,
        "diff_counts_by_section": diff_counts_by_section,
        "detailed_differences": detailed_differences # Pasar la lista original para la plantilla
    } 