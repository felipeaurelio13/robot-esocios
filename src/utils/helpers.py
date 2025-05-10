import re
import logging
from datetime import datetime
from src.globals import ALLOWED_EXTENSIONS # Import constant

def allowed_file(filename):
    """
    Verifica si el archivo tiene una extensión permitida.

    Args:
        filename (str): Nombre del archivo.

    Returns:
        bool: True si la extensión está permitida, False en caso contrario.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _parse_datetime(date_string):
    """Intenta parsear una cadena de fecha/hora en varios formatos comunes."""
    if not date_string or not isinstance(date_string, str):
        return None
    formats = [
        "%Y-%m-%dT%H:%M:%S",  # Formato ISO común (Esperado)
        "%d/%m/%Y a las %H:%M:%S", # Formato visto en Selenium (Actual)
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    logging.warning(f"No se pudo parsear la fecha: {date_string} con los formatos conocidos.")
    return None # Retorna None si ningún formato coincide

def _normalize_text(text):
    """Normaliza texto a minúsculas, sin espacios extra y elimina numeración inicial (ej: '1. ')."""
    if not isinstance(text, str):
        return ""
    # Eliminar posible numeración inicial (números, punto, espacio)
    text_without_prefix = re.sub(r"^\s*\d+\.\s*", "", text).strip()
    # Convertir a minúsculas y normalizar espacios internos
    return ' '.join(text_without_prefix.lower().split())

def _compare_list(section_name, list_expected, list_actual, differences_list):
    """Compara dos listas simples (accionistas, usuarios). Añade una diferencia si no son idénticas.

    Args:
        section_name (str): Nombre de la sección ('accionistas', 'usuarios').
        list_expected (list): Lista esperada.
        list_actual (list): Lista actual.
        differences_list (list): Lista donde añadir las diferencias encontradas.
    """
    # Asegurarse que trabajamos con listas, incluso si vienen None
    expected = list_expected if isinstance(list_expected, list) else []
    actual = list_actual if isinstance(list_actual, list) else []

    if not actual and not expected: # Ambas vacías o None, no hay diferencia
        return

    # Comparación simple: ¿son idénticas las listas?
    # NOTA: Esto es sensible al orden y asume que los objetos internos son comparables.
    # Para una comparación más robusta (ignorando orden, comparando por ID), se necesitaría más lógica.
    if expected != actual:
        diff_type = 'lista_distinta'
        severity = 'warning'
        if not actual and expected:
            diff_type = 'lista_faltante_en_actual'
            severity = 'danger' # Considerar faltante como más grave
        elif actual and not expected:
            diff_type = 'lista_sobrante_en_actual'
            # severity sigue siendo 'warning' para sobrantes

        differences_list.append({
            "section": section_name,
            "field": "lista", # Indicador genérico de que es la lista completa
            "type": diff_type,
            "expected": expected, # Devolver las listas completas para la UI
            "actual": actual,
            "severity": severity
        }) 