import os
import json
import logging
import uuid
import shutil
import threading
import requests # Import requests
from datetime import datetime
from pathlib import Path # Use pathlib for easier path manipulation
from typing import Optional
import traceback
import time

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    send_file,
    current_app, # Use current_app to access app config in blueprints
)
from werkzeug.utils import secure_filename

# Import shared state and constants
from src.globals import combined_revision_status, combined_status_lock

# Import helper/utility functions
from src.utils.helpers import allowed_file
from src.utils.validation import _validate_questions, _validate_revisa_js_slug
from src.reporting import get_available_reports
from src.zoom_utils import get_zoom_meeting_details

# Import background tasks
from src.tasks.background import (
    run_verification_async_combined,
    process_documents_async_combined,
    _update_combined_status, # Note: Usually internal functions aren't imported directly
                               # but needed here to update status on thread start error.
                               # Consider refactoring background.py later if needed.
    _check_and_cleanup_task # Also needed for cleanup on initial error
)

# Import specific data/constants from other modules
from src.shareholder_manager import (
    CUSTODIAN_KEYWORDS,
    KNOWN_CUSTODIAN_RUTS,
    KNOWN_CUSTODIAN_NAMES_LOWER,
    KNOWN_AFP_DATA,
)

# Import the report generation function and target emails
# NOTE: Consider moving TARGET_EMAILS definition to a central config if used elsewhere
from report_upcoming_meetings import generate_meeting_report, TARGET_EMAILS

from src.webdriver_setup import setup_webdriver # Import the function
from src.auth_manager import AuthManager # Import AuthManager

# Importar load_dotenv y os para leer .env (aunque load_dotenv() se debe llamar en app.py)
from dotenv import load_dotenv

# Import WebDriver type hint if possible (adjust based on actual imports)
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)

# Define the blueprint
main_bp = Blueprint('main', __name__, template_folder='../templates', static_folder='../static')

# --- Constantes y Configuración --- 
# Inspector Standard
SLUG_CONFIG_DIR = Path('data/slug_configs')
BASE_API_URL = "https://eholders-mgnt-api-v3.evoting.com/admin/meetings"
BASE_LOGIN_URL = "https://eholders-mgnt.evoting.com/" # Assuming this is the standard login

# Inspector DCV
DCV_CONFIG_DIR = Path('data/dcv_configs')
DCV_API_URL = "https://eholders-mgnt-api.dcv.evoting.com/admin/meetings" # Solo config
DCV_LOGIN_URL = "https://eholders-mgnt.dcv.evoting.com/" 
DCV_INITIAL_SLUGS = [
    'OAqun6jD',
    'cHk0HPbx',
    'wb3BhtNd',
    '0PEKCvLE',
    'TaTKBzAO',
    'CJHZSHQk',
    'TcX7ycLs',
    'kfvZZKY8',
    'qZDVV0JS',
    'qh65dLqo',
    'Utaj5Kkb',
    'yKJirvFl',
    'MbWik5LO',
    'CkcPY4jC',
    'SmQE69ag',
    'Vw7XIS20',
    '7EiMumPD',
    'ugSwUoAJ',
    '8Ppb3wQ6',
    'Is1zW7dX',
    '1M1aCucq',
    '3lfPn6en',
    '9f98oXZt',
    'rWODLmko',
    'rutsy7ET',
    '7Xpnum2q',
    'XIdWj3wm',
    'NdMhZWP8',
    'oQPoLnhv',
    '357XAxJE',
    'q3uP9XzQ',
    '9Rwiv3yn',
    'F8AhJ1Mb',
    'u89nYpnP',
    'LcNNo6Xd',
    'Tzjffbk8',
    'iYqpTnD9',
    'XfsojAs6',
    '0PEKCvLE',
    'KDE8SNA5',
    'KxawXBXC',
    'AaBW7tEJ',
    'Oj4BqyQE',
    'GjxxDNO3',
    'TuXIZMW4',
    'aK11f1Wz',
    'ADNLX2wY',
    'p66nC5bV',
    'dnQXpWM5',
    '9Tol7Hqw',
    'Nqg0pEw1',
    'zAijh3WY',
    'UFZZKGsl',
    'LXN8tmhJ',
    'ZlFDOqJX',
    'GbU8I1rW',
    '0P8XB3wJ',
    'lpqF71fF',
    'xgYdhZRu',
    'eFefcwSx',
    'CV7fqHbE',
    'ACneDZNQ',
    '5qzI9rjd',
    'NHkn0fDq',
    'gROOkTTM',
    'wXelQRE5',
    'xCBXZyQi',
]

# === Main Routes ===

@main_bp.route('/')
def index():
    """Redirects root URL to the dashboard."""
    return redirect(url_for('main.dashboard')) # Use blueprint name in url_for

@main_bp.route('/dashboard')
def dashboard():
    """Displays the main dashboard with available reports."""
    try:
        # Use the imported reporting function
        reports = get_available_reports()
        total_reports = len(reports)
        successful_matches = sum(1 for r in reports if r.get('match') is True)
        mismatches = sum(1 for r in reports if r.get('match') is False)

        return render_template(
            'dashboard.html',
            reports=reports,
            total_reports=total_reports,
            successful_matches=successful_matches,
            mismatches=mismatches
        )
    except Exception as e:
        flash(f'Error al cargar el dashboard: {str(e)}', 'danger')
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        return render_template(
            'dashboard.html',
            reports=[],
            total_reports=0,
            successful_matches=0,
            mismatches=0
        )

@main_bp.route('/nueva-revision', methods=['GET', 'POST'])
def nueva_revision():
    """Handles the form for starting a new revision and initiates the background tasks."""
    if request.method == 'POST':
        slug = request.form.get('slug')
        username = request.form.get('username')
        password = request.form.get('password')
        uploaded_files = request.files.getlist('document_files')

        if not slug:
            flash('El SLUG de la junta es obligatorio.', 'danger')
            return redirect(url_for('main.nueva_revision'))

        if not uploaded_files or all(f.filename == '' for f in uploaded_files):
             flash('Debes subir al menos un documento fuente.', 'danger')
             return redirect(url_for('main.nueva_revision'))

        task_id = str(uuid.uuid4())
        # Use current_app.config here
        temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], task_id)
        saved_files_data = []
        initiation_error = None

        try:
            logger.info(f"[Nueva Revision] Task {task_id}: Creating temporary directory: {temp_dir}")
            os.makedirs(temp_dir, exist_ok=True)
            valid_files_found = False
            for file in uploaded_files:
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(temp_dir, filename)
                    logger.info(f"[Nueva Revision] Task {task_id}: Saving uploaded file {filename} to {filepath}")
                    file.save(filepath)
                    saved_files_data.append({'path': filepath, 'type': file.mimetype})
                    valid_files_found = True
                elif file and file.filename != '':
                     logger.warning(f"[Nueva Revision] Task {task_id}: File type not allowed: {file.filename}")
                     flash(f'Tipo de archivo no permitido: {file.filename}', 'warning')

            if not valid_files_found:
                 initiation_error = 'No se subieron archivos válidos o permitidos.'
                 flash(initiation_error, 'danger')
                 raise ValueError(initiation_error) # Raise exception to trigger cleanup

            logger.info(f"[Nueva Revision] Task {task_id}: Initializing combined status.")
            with combined_status_lock:
                combined_revision_status[task_id] = {
                    "status": "running",
                    "selenium": {"status": "pending", "message": "Esperando inicio...", "result_path": None, "error": None},
                    "docs": {"status": "pending", "message": "Esperando inicio...", "result_path": None, "error": None},
                    "comparison": {"status": "pending", "message": "Esperando resultados previos...", "result": None, "error": None},
                    "final_report": None,
                    "error": None,
                    "timestamp_start": datetime.now().isoformat(),
                    "_cleanup_started": False
                }

            logger.info(f"[Nueva Revision] Task {task_id}: Starting background threads.")
            # Pass necessary config values to the background tasks
            reports_dir_path = current_app.config['REPORTS_DIR']
            upload_folder_path_for_task = temp_dir # The specific task's temp dir

            selenium_thread = threading.Thread(
                target=run_verification_async_combined,
                args=(task_id, slug, username, password, reports_dir_path, upload_folder_path_for_task),
                daemon=True
            )
            docs_thread = threading.Thread(
                target=process_documents_async_combined,
                args=(task_id, saved_files_data),
                daemon=True
            )
            selenium_thread.start()
            docs_thread.start()

            logger.info(f"[Nueva Revision] Task {task_id}: Redirecting to progress page.")
            return redirect(url_for('main.combined_revision_progress', task_id=task_id))

        except Exception as e:
             logger.error(f"[Nueva Revision] Task {task_id}: Error during setup or thread start: {e}", exc_info=True)
             flash(initiation_error or f'Error al iniciar la revisión: {str(e)}', 'danger')
             if os.path.exists(temp_dir):
                 try:
                     logger.info(f"[Nueva Revision] Task {task_id}: Cleaning up temp dir {temp_dir} due to initiation error.")
                     shutil.rmtree(temp_dir)
                 except OSError as cleanup_error:
                      logger.error(f"[Nueva Revision] Task {task_id}: Error cleaning up temp dir {temp_dir}: {cleanup_error}")

             # Update status to error if task was added
             with combined_status_lock:
                 if task_id in combined_revision_status:
                     if combined_revision_status[task_id]['status'] != 'error':
                         combined_revision_status[task_id]['status'] = 'error'
                         combined_revision_status[task_id]['error'] = f'Error inicial: {str(e)}'
                         # Trigger cleanup directly if setup failed
                         logger.info(f"[Nueva Revision] Task {task_id}: Triggering cleanup immediately due to error.")
                         # Pass the temp_dir as upload_folder_path
                         cleanup_thread = threading.Thread(target=_check_and_cleanup_task, args=(task_id, temp_dir), daemon=True)
                         cleanup_thread.start()

             return redirect(url_for('main.nueva_revision'))

    # --- GET Request --- 
    return render_template('nueva_revision.html')

# === Combined Progress Routes ===

@main_bp.route('/combined-revision-progress/<task_id>')
def combined_revision_progress(task_id):
    """Displays the progress page for a combined revision task."""
    with combined_status_lock:
        if task_id not in combined_revision_status:
             logger.warning(f"Attempted to access progress page for non-existent task: {task_id}")
             flash(f"No se encontró la tarea de revisión con ID: {task_id}", "danger")
             return redirect(url_for('main.dashboard'))
    return render_template('combined_progress.html', task_id=task_id)

@main_bp.route('/combined-status/<task_id>')
def combined_status(task_id):
    """API endpoint to get the status of a combined revision task."""
    with combined_status_lock:
        status_data = combined_revision_status.get(task_id)
        if not status_data:
            return jsonify({'status': 'not_found', 'message': 'No se encontró el estado para esta tarea.'}), 404
        response_data = status_data.copy() # Return a copy

    # Add report URL if completed (outside the lock)
    if response_data.get('status') == 'completed' and response_data.get('final_report'):
        try:
            # Use blueprint name in url_for
            response_data['report_url'] = url_for('main.ver_informe', filename=response_data['final_report'])
        except Exception as url_err:
             logger.error(f"Task {task_id}: Error generating report URL: {url_err}")

    return jsonify(response_data)

# === Report Viewing and Downloading ===

@main_bp.route('/ver-informe/<filename>')
def ver_informe(filename):
    """Displays the detailed report view."""
    if '..' in filename or filename.startswith('/'):
        flash("Nombre de archivo inválido.", "danger")
        return redirect(url_for('main.dashboard'))

    # Use current_app.config here
    report_path = os.path.join(current_app.config['REPORTS_DIR'], secure_filename(filename))

    if not os.path.exists(report_path):
        flash(f"Informe '{filename}' no encontrado.", "danger")
        return redirect(url_for('main.dashboard'))

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)

        # --- Get expected slug directly from the report data --- 
        expected_slug = report_data.get('slug')
        if not expected_slug:
             logger.warning(f"Slug not found within the report data for filename: {filename}. Revisa.js validation might fail.")
             # Handle the case where slug is missing in older reports if needed
             # For now, we'll proceed, but the validation function handles None slug.

        # --- Get Zoom Details --- 
        zoom_details = None
        config_actual_data = report_data.get('configuracion_actual', {})
        zoom_info_data = config_actual_data.get('configuracion_general', {}).get('zoom', {})
        meeting_id = zoom_info_data.get('id')

        if meeting_id:
             try:
                 logger.info(f"Intentando obtener detalles de Zoom para meeting ID: {meeting_id}")
                 zoom_details = get_zoom_meeting_details(meeting_id)
                 if zoom_details:
                     logger.info(f"Detalles de Zoom obtenidos para ID: {meeting_id}")
                 else:
                     logger.warning(f"get_zoom_meeting_details devolvió None para ID: {meeting_id}.")
             except Exception as e_zoom:
                 logger.error(f"Error al llamar a get_zoom_meeting_details para {meeting_id}: {e_zoom}", exc_info=True)
                 # flash(f"Error al consultar API de Zoom: {e_zoom}", "warning") # Optional
        else:
            logger.info("No se encontró ID de reunión de Zoom en el informe.")
        # --- End Zoom Details --- 

        # --- Process Report Data for Display --- 
        config_actual = report_data.get('configuracion_actual', {})
        # Ensure config_actual is a dict before using .get(), handle inconsistent data
        shareholders_data = {} 
        if isinstance(config_actual, dict):
            shareholders_data = config_actual.get('accionistas', {})
        else:
            logger.warning(f"configuracion_actual in report '{filename}' is a {type(config_actual)}, expected dict. Skipping accionistas extraction.")
            config_actual = {} # Reset to empty dict to avoid further errors
        
        # Ensure shareholders_data is a dict before using .get()
        shareholders_list = []
        if isinstance(shareholders_data, dict):
            shareholders_list = shareholders_data.get('lista', [])
        else:
            logger.warning(f"accionistas field in report '{filename}' is a {type(shareholders_data)}, expected dict. Defaulting shareholder list to empty.")

        # Check Custodian Inconsistencies
        custodian_keywords_lower = {kw.lower() for kw in CUSTODIAN_KEYWORDS} # Set for efficiency
        for accionista in shareholders_list:
            if isinstance(accionista, dict):
                rut = accionista.get('identificador', '')
                nombre = accionista.get('nombre', '')
                nombre_lower_cleaned = nombre.strip().lower()
                estados = accionista.get('estados', [])
                if not isinstance(estados, list):
                    estados = [str(estados)]
                is_marked_as_custodian = any(st.strip().lower() == 'custodio' for st in estados if isinstance(st, str))

                contains_keyword = any(keyword in nombre_lower_cleaned for keyword in custodian_keywords_lower)
                rut_is_known = rut in KNOWN_CUSTODIAN_RUTS
                name_is_known_exact = nombre_lower_cleaned in KNOWN_CUSTODIAN_NAMES_LOWER
                should_be_custodian = contains_keyword or rut_is_known or name_is_known_exact
                is_known_afp = rut in KNOWN_AFP_DATA

                accionista['_custodian_warning'] = None
                if should_be_custodian and not is_marked_as_custodian:
                    accionista['_custodian_warning'] = 'missing'
                elif not should_be_custodian and is_marked_as_custodian and not is_known_afp:
                    accionista['_custodian_warning'] = 'incorrect'

        # Check Undistributed Directorio Questions
        preguntas = config_actual.get('preguntas', [])
        undistributed_directorio_questions = []
        if isinstance(preguntas, list):
            for q in preguntas:
                if isinstance(q, dict):
                    q_name = q.get('name', '').lower()
                    is_distributed = q.get('config', {}).get('distributed', False)
                    if (('elección' in q_name or 'eleccion' in q_name or 'designación' in q_name or 'designacion' in q_name)
                        and ('director' in q_name or 'directorio' in q_name)):
                        if not is_distributed:
                            undistributed_directorio_questions.append(q.get('name', '[Pregunta sin nombre]'))

        # --- Verify AFP Groups (Simplified Logic + Inference for Display) --- 
        afp_group_warnings = []
        afp_summary_status = 'OK'
        afp_summary_message = ''
        any_afp_detected = False
        groups_found_per_known_rut_lower = {rut: set() for rut in KNOWN_AFP_DATA.keys()}
        first_valid_group_by_rut = {}
        afps_detected_temp = []

        if isinstance(shareholders_list, list):
            for sh in shareholders_list:
                if isinstance(sh, dict):
                    rut_sh = sh.get('identificador')
                    if rut_sh in KNOWN_AFP_DATA:
                        grupo_actual = sh.get('grupo')
                        is_valid_group_str = grupo_actual and isinstance(grupo_actual, str) and grupo_actual.strip()
                        grupo_actual_norm = grupo_actual.strip().lower() if is_valid_group_str else "[GRUPO_VACIO/INVALIDO]"
                        groups_found_per_known_rut_lower[rut_sh].add(grupo_actual_norm)
                        if is_valid_group_str and rut_sh not in first_valid_group_by_rut:
                            first_valid_group_by_rut[rut_sh] = grupo_actual.strip()
                        afps_detected_temp.append({
                            'rut': rut_sh,
                            'nombre_accionista': sh.get('nombre', '[Sin Nombre]'),
                            'grupo_esperado': KNOWN_AFP_DATA[rut_sh].get('group', '[?]'),
                            'grupo_crudo': grupo_actual
                        })

        final_afp_list_for_template = []
        for afp_data in afps_detected_temp:
            rut_known = afp_data['rut']
            grupo_crudo = afp_data['grupo_crudo']
            grupo_a_mostrar = "[GRUPO_VACIO/INVALIDO]"
            is_crudo_valid = grupo_crudo and isinstance(grupo_crudo, str) and grupo_crudo.strip()
            if is_crudo_valid:
                grupo_a_mostrar = grupo_crudo
            else:
                inferred_group = first_valid_group_by_rut.get(rut_known)
                if inferred_group:
                    grupo_a_mostrar = f"{inferred_group} [Inferido]"
            final_afp_list_for_template.append({
                'rut': rut_known,
                'nombre_accionista': afp_data['nombre_accionista'],
                'grupo_esperado': afp_data['grupo_esperado'],
                'grupo_actual': grupo_a_mostrar
            })

        for rut_known, grupos_encontrados_lower in groups_found_per_known_rut_lower.items():
            was_detected = any(afp['rut'] == rut_known for afp in final_afp_list_for_template)
            if was_detected:
                any_afp_detected = True
                # Treat "[GRUPO_VACIO/INVALIDO]" and "sin grupo" as invalid for status check
                valid_groups_lower = {g for g in grupos_encontrados_lower if g != "[GRUPO_VACIO/INVALIDO]" and g != "sin grupo"}
                has_empty_invalid = "[GRUPO_VACIO/INVALIDO]" in grupos_encontrados_lower or "sin grupo" in grupos_encontrados_lower
                afp_name_known = KNOWN_AFP_DATA[rut_known].get('name', rut_known)
                warning_added = False
                if len(valid_groups_lower) > 1:
                    afp_group_warnings.append(f"Inconsistencia: AFP '{afp_name_known}' ({rut_known}) tiene múltiples grupos válidos: {list(valid_groups_lower)}.")
                    warning_added = True
                elif len(valid_groups_lower) == 1 and has_empty_invalid:
                    display_group_name = first_valid_group_by_rut.get(rut_known, list(valid_groups_lower)[0])
                    afp_group_warnings.append(f"Advertencia: AFP '{afp_name_known}' ({rut_known}) tiene grupo '{display_group_name}', pero algunas entradas no tienen grupo o es inválido.")
                    warning_added = True
                elif len(valid_groups_lower) == 0 and has_empty_invalid:
                    afp_group_warnings.append(f"Advertencia: Grupo para AFP '{afp_name_known}' ({rut_known}) está vacío/inválido en todas sus entradas.")
                    warning_added = True
                if warning_added:
                    afp_summary_status = 'INCONSISTENT'

        if not any_afp_detected:
            afp_summary_status = 'NOT_DETECTED'
            afp_summary_message = "No se detectaron AFPs conocidas en la lista de accionistas."
            afp_group_warnings = []
        elif afp_summary_status == 'OK':
            afp_summary_message = "Todas las AFPs detectadas tienen asignación de grupo consistente."
        elif afp_summary_status == 'INCONSISTENT':
            afp_summary_message = "Se encontraron inconsistencias o datos faltantes en los grupos de AFP. Revise detalles:"
        # --- End AFP Verification --- 

        # Prepare Question Comparison Details for JS
        question_details_json = None
        comp_selenium_docs = report_data.get('comparacion_selenium_vs_documentos', {})
        if comp_selenium_docs and 'differences' in comp_selenium_docs:
            question_comp_diff = next((diff for diff in comp_selenium_docs['differences'] if diff.get('type') == 'lista_preguntas_comparadas'), None)
            if question_comp_diff and 'details' in question_comp_diff:
                question_details_json = json.dumps(question_comp_diff['details'])
                logger.info(f"Preparando {len(question_comp_diff['details'])} detalles de preguntas para JS.")
            else:
                 logger.info("No se encontraron detalles de comparación de preguntas en el informe.")

        # Create Inconsistency Summary
        inconsistency_summary = {
            'custodians_missing': sum(1 for sh in shareholders_list if isinstance(sh, dict) and sh.get('_custodian_warning') == 'missing'),
            'custodians_incorrect': sum(1 for sh in shareholders_list if isinstance(sh, dict) and sh.get('_custodian_warning') == 'incorrect'),
            'undistributed_questions': len(undistributed_directorio_questions),
            'afp_group_warnings': len(afp_group_warnings),
            'afp_summary_status': afp_summary_status,
            'afp_summary_message': afp_summary_message
        }

        # --- Validate Questions --- 
        questions_status, invalid_questions_list = _validate_questions(preguntas)
        # --- End Validation --- 

        # --- NEW: Validate revisa.js slug --- 
        revisa_js_validation_result = None
        if config_actual and expected_slug: # Only run if we have config and slug
            revisa_js_validation_result = _validate_revisa_js_slug(config_actual, expected_slug)
        else:
             logger.warning(f"Skipping revisa.js validation for {filename}. Missing config_actual or expected_slug.")
             # Optionally create a default error result here
             revisa_js_validation_result = {
                'status': 'skipped', 
                'message': 'Validación omitida: falta configuración o slug esperado.', 
                'js_url': None, 
                'found_id': None,
                'expected_slug': expected_slug
             }
        # --- END NEW --- 

        return render_template(
            'ver_informe.html',
            filename=filename,
            report=report_data,
            config_actual=config_actual,
            questions_status=questions_status,
            invalid_questions=invalid_questions_list,
            accionistas=shareholders_list,
            preguntas_directorio_no_distribuidas=undistributed_directorio_questions,
            afp_group_warnings=afp_group_warnings,
            afp_status_summary=afp_summary_status,
            afp_status_message=afp_summary_message,
            afp_list=final_afp_list_for_template,
            zoom_details=zoom_details,
            inconsistency_summary=inconsistency_summary,
            question_details_json=question_details_json,
            revisa_js_validation=revisa_js_validation_result
        )

    except FileNotFoundError:
        flash(f"Informe '{filename}' no encontrado.", "danger")
        return redirect(url_for('main.dashboard'))
    except json.JSONDecodeError:
        flash(f"Error al leer el formato JSON del informe '{filename}'.", "danger")
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        logger.error(f"Error inesperado al procesar el informe '{filename}': {e}", exc_info=True)
        flash(f"Error inesperado al procesar el informe: {e}", "danger")
        return redirect(url_for('main.dashboard'))

@main_bp.route('/descargar-informe/<filename>')
def descargar_informe(filename):
    """Handles downloading of a report file."""
    if '..' in filename or filename.startswith('/'):
        flash('Nombre de archivo inválido.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Use current_app.config here
    report_path = os.path.join(current_app.config['REPORTS_DIR'], secure_filename(filename))

    if not os.path.exists(report_path):
        flash('El informe solicitado no existe', 'error')
        return redirect(url_for('main.dashboard'))
    try:
        return send_file(report_path, as_attachment=True)
    except Exception as e:
         flash(f'Error al intentar descargar el informe: {e}', 'danger')
         logger.error(f"Error sending report file {filename}: {e}")
         return redirect(url_for('main.ver_informe', filename=filename)) # Redirect back to view 

# === New Route for Upcoming Meetings Report ===

@main_bp.route('/reporte-reuniones')
def meeting_report_view():
    """Generates and displays the upcoming Zoom meetings report."""
    try:
        logger.info("Generating upcoming meetings report...")
        if not TARGET_EMAILS:
            logger.warning("TARGET_EMAILS list is empty. Cannot generate meeting report.")
            flash("No hay emails configurados para generar el reporte de reuniones.", "warning")
            # Return empty data to the template
            headers, report_data = [], []
        else:
            headers, report_data = generate_meeting_report(TARGET_EMAILS)

        return render_template('reporte_reuniones.html',
                               headers=headers,
                               report_data=report_data)
    except Exception as e:
        logger.error(f"Error generating upcoming meetings report: {e}", exc_info=True)
        flash(f'Error al generar el reporte de reuniones: {str(e)}', 'danger')
        # Render the template even on error, possibly showing an error message there
        return render_template('reporte_reuniones.html',
                               headers=[],
                               report_data=[],
                               error=f'Error al generar el reporte: {str(e)}')

# === Configuration Viewing ===

@main_bp.route('/ver-configuracion')
def ver_configuracion():
    """Displays current configuration values."""
    # This route is empty as per the new code block
    pass

    return render_template('ver_configuracion.html')

# === New Route for Slug Inspector ===

def get_authenticated_evoting_cookies(login_url: str = BASE_LOGIN_URL) -> Optional[dict]: # Quitar default de headless
    """Uses Selenium to log in and returns authentication cookies for requests.

    Args:
        login_url: The base URL for the management login page.

    Returns:
        A dictionary of cookies suitable for requests, or None if login fails.
    """
    driver = None
    cookies = None
    # Leer headless desde el entorno
    # Asegúrate de que load_dotenv() se llame al inicio de la app (ej. app.py)
    headless_str = os.getenv('SELENIUM_HEADLESS', 'True') # Default a 'True' si no está en .env
    headless_mode = headless_str.lower() in ('true', '1', 't')
    
    try:
        logger.info(f"Attempting to get authenticated cookies for {login_url} (headless={headless_mode})...")
        # Pasar el modo headless leído a setup_webdriver
        driver = setup_webdriver(headless=headless_mode) 
        auth = AuthManager(driver, login_url) # Pass login_url

        if auth.login(): # Use configured username/password
            logger.info(f"Login successful via Selenium for {login_url}, extracting cookies immediately...")
            # --- Extract Cookies Immediately --- 
            cookies = None
            try:
                # Try extracting cookies without navigating away first
                cookies = auth.get_requests_cookies()
                logger.info(f"Successfully extracted {len(cookies) if cookies else 0} cookies immediately after login.")
                
                # Optional: Add a small delay ONLY IF immediate extraction fails, then try again?
                # if not cookies:
                #     logger.warning("Immediate cookie extraction failed. Waiting 2s and trying again...")
                #     time.sleep(2)
                #     cookies = auth.get_requests_cookies()
                #     logger.info(f"Successfully extracted {len(cookies) if cookies else 0} cookies after delay.")

            except Exception as cookie_err:
                logger.error(f"Error during immediate cookie extraction for {login_url}: {cookie_err}", exc_info=True)
                cookies = None # Ensure cookies are None on error
            # --- End Cookie Extraction ---
            
            # --- Always quit driver now --- 
            try:
                driver.quit()
                logger.info(f"Selenium driver quit after successful login and cookie extraction attempt for {login_url}.") # Updated log
            except Exception as q_err:
                logger.error(f"Error quitting driver after successful login: {q_err}")
            # --- End Quit --- 
            
            return cookies # Return the extracted cookies
        else:
            logger.error(f"Selenium login failed for {login_url}. Cannot retrieve authenticated cookies.")
    except Exception as e:
        logger.error(f"Error during authenticated cookie retrieval for {login_url}: {e}", exc_info=True)
    finally:
        if driver:
            try:
                driver.quit()
                logger.info(f"Selenium driver quit successfully for {login_url} attempt.")
            except Exception as q_err:
                logger.error(f"Error quitting Selenium driver: {q_err}")

    if cookies:
         logger.info(f"Retrieved {len(cookies)} cookies for {login_url}.")
    else:
         logger.warning(f"Failed to retrieve cookies for {login_url}.")
    return cookies

def _fetch_and_save_json(api_url: str, output_path: Path, data_type: str, slug: str, cookies: Optional[dict] = None):
    """Fetches JSON from a URL using provided cookies and saves it.

    Args:
        api_url: The URL to fetch from.
        output_path: Path object to save the JSON.
        data_type: String identifier for logging ('config', 'users', 'holders').
        slug: The meeting slug (for logging).
        cookies: Optional dictionary of cookies to use for authentication.

    Returns:
        Tuple[bool, Optional[str]]: (Success status, Error message or None)
    """
    try:
        headers = {
            # Add any other necessary headers here (e.g., User-Agent)
            'Accept': 'application/json'
        }
        logger.debug(f"Fetching {data_type} for '{slug}' from {api_url} with cookies: {cookies is not None}")
        response = requests.get(api_url, timeout=45, cookies=cookies, headers=headers)
        response.raise_for_status()
        json_data = response.json()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        # logger.info(f"Successfully fetched and saved {data_type} for slug '{slug}' to {output_path}") # Logged in calling function now
        return True, None # Success, No Error Message
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error fetching {data_type} for slug '{slug}' from {api_url}")
        return False, "Timeout"
    except requests.exceptions.HTTPError as e:
        # Log the status code specifically for 401/403
        status_code = e.response.status_code
        log_msg = f"HTTP error {status_code} fetching {data_type} for slug '{slug}' from {api_url}"
        if status_code in [401, 403]:
            log_msg += " (Unauthorized/Forbidden - Check cookies/authentication)"
        logger.error(log_msg)
        return False, f"HTTP {status_code}"
    # (Rest of the exception handling remains the same...)
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching {data_type} for slug '{slug}' from {api_url}: {e}")
        return False, "Request Error"
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response for {data_type} for slug '{slug}': {e}")
        # (Saving raw response...)
        try:
            error_file_path = output_path.with_suffix('.error.txt')
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(error_file_path, 'w', encoding='utf-8') as f:
                 f.write(response.text)
            logger.info(f"Saved raw non-JSON response for {data_type} slug '{slug}' to {error_file_path}")
        except Exception as save_err:
            logger.error(f"Additionally failed to save raw error response for {data_type} slug '{slug}': {save_err}")
        return False, "JSON Decode Error"
    except OSError as e:
        logger.error(f"OS error saving {data_type} JSON for slug '{slug}' to {output_path}: {e}")
        return False, "Save Error"
    except Exception as e:
        logger.error(f"Unexpected error processing {data_type} for slug '{slug}': {traceback.format_exc()}")
        return False, "Unexpected Error"

def fetch_and_save_slug_data(slug: str, target_dir: Path, cookies: Optional[dict]) -> dict:
    """Fetches config, users, and holders data for a slug using provided cookies.

     Args:
        slug: The meeting slug.
        target_dir: The directory Path object to save the JSON.
        cookies: The dictionary of authentication cookies.

    Returns:
        dict: Results dictionary with success/error status for each data type.
    """
    results = {
        'config': {'success': None, 'error': None, 'path': target_dir / f"{slug}_config.json"},
        'users': {'success': None, 'error': None, 'path': target_dir / f"{slug}_users.json"},
        'holders': {'success': None, 'error': None, 'path': target_dir / f"{slug}_holders.json"}
    }

    logger.info(f"--- Fetching data for slug: {slug} ---")
    # Fetch Config
    config_url = f"{BASE_API_URL}/{slug}"
    results['config']['success'], results['config']['error'] = _fetch_and_save_json(
        config_url, results['config']['path'], 'config', slug, cookies
    )
    if results['config']['success']:
        logger.info(f" Success fetching config for '{slug}'")

    # Fetch Users
    users_url = f"{BASE_API_URL}/{slug}/users"
    results['users']['success'], results['users']['error'] = _fetch_and_save_json(
        users_url, results['users']['path'], 'users', slug, cookies
    )
    if results['users']['success']:
         logger.info(f" Success fetching users for '{slug}'")

    # Fetch Holders
    holders_url = f"{BASE_API_URL}/{slug}/holders"
    results['holders']['success'], results['holders']['error'] = _fetch_and_save_json(
        holders_url, results['holders']['path'], 'holders', slug, cookies
    )
    if results['holders']['success']:
         logger.info(f" Success fetching holders for '{slug}'")

    return results

@main_bp.route('/inspector-slugs')
def slug_inspector_view():
    """Displays configurations fetched for a list of slugs.
       Loads existing data by default, refetches on reload=true.
    """
    # TODO: Get this list dynamically
    slugs_to_process = [
         "N7YzFYWg", "oAPyi9lO", "zxfWl89p", "i5cQV2zD", "ZfbBDy6g", "uEsUYqQ7", "csXHOQ0S", "1XotJlyn", "0Na1oneZ", "TwEQ8pgQ", "PuKEES1l", "cphe3iLg", "GEM3pGNa", "q0Af1F4P", "P6JVntPJ", "ktYSs14N", "FHOhBAhh", "k3MwUW6v", "ybLhNGkr", "buwDjSyc", "c1hZQZ9O", "P3IMWKrx", "QIhCE1Do", "ulvDSUW1", "C0mN8WLt", "BvIquovD", "82nFWeZC", "V1sLFdWF", "ZvNiDggV", "ZG7Y2VZd", "RxALuuMR", "aeSJhvdV", "UaJmY6nC", "0KFo65JQ", "79agnLsY", "1Ysags9E", "B9AEhRvA", "MeXWaqPX", "zFp7RZXT", "q0hZWwTn", "vDy4RKUw", "7zONlD9f", "5lcZGKNa", "YZfsAYvm", "GF9Mpg0k", "77Z1eOQv", "JcHcruIb", "0iJ4LICH", "3vB3tscf", 
         #"invalid-slug-test"
    ]

    logger.info("--- Slug Inspector View --- ")
    auth_error = None
    auth_cookies = None
    fetch_statuses = {} # Store fetch results if reload is triggered

    # --- Step 1: Check if Reload is Requested --- 
    force_reload = request.args.get('reload') == 'true'

    if force_reload:
        logger.info("Reload requested. Attempting authentication and data fetching...")
        # --- Step 1a: Get Authentication Cookies via Selenium --- 
        auth_cookies = get_authenticated_evoting_cookies()

        if not auth_cookies:
            auth_error = "Fallo en la autenticación inicial vía Selenium."
            flash(f"Error crítico: {auth_error}", "danger")
            logger.critical(f"{auth_error} Cannot proceed with data fetch.")
            # Set force_reload back to False so it proceeds to load existing data
            force_reload = False 
        else:
            logger.info(f"Successfully obtained {len(auth_cookies)} authentication cookies for reload.")
            # --- Step 1b: Fetching Data using Cookies ---
            logger.info(f"Starting data fetch for slugs: {slugs_to_process}")
            for slug in slugs_to_process:
                fetch_statuses[slug] = fetch_and_save_slug_data(slug, SLUG_CONFIG_DIR, auth_cookies)
    else:
        logger.info("Loading existing data (no reload requested).")

    # --- Step 2: Data Preparation for Table (Always reads existing files) ---
    all_config_keys = set()
    table_data = []
    SLUG_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Read existing files regardless of reload status
    slug_files_in_dir = list(SLUG_CONFIG_DIR.glob('*_config.json'))
    logger.info(f"Found {len(slug_files_in_dir)} config files in {SLUG_CONFIG_DIR}.")

    for config_file in slug_files_in_dir:
        slug = config_file.stem.replace('_config', '')
        # Only display slugs that are currently requested OR were previously fetched
        # This logic might need refinement depending on desired behavior for removed slugs
        # if slug not in slugs_to_process: continue 

        users_file = SLUG_CONFIG_DIR / f"{slug}_users.json"
        holders_file = SLUG_CONFIG_DIR / f"{slug}_holders.json"
        
        # Get fetch status ONLY if a reload happened during this request
        current_fetch_status = fetch_statuses.get(slug, {}) 

        row_base = {
            '_slug': slug,
            # Show fetch status only if reload occurred
            '_config_status': current_fetch_status.get('config') if force_reload else None, 
            '_users_status': current_fetch_status.get('users') if force_reload else None,
            '_holders_status': current_fetch_status.get('holders') if force_reload else None,
            '_config_error': None, # Reset potential read error
            # File existence check is always relevant for links
            '_users_exist': users_file.exists(), 
            '_holders_exist': holders_file.exists()
        }

        # (Reading the config file and processing keys remains the same...)
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                if isinstance(config_data, dict):
                    current_keys = set(config_data.keys())
                    all_config_keys.update(current_keys)
                    row_base.update(config_data)
                else:
                    logger.warning(f"Config file {config_file} content is not a JSON object.")
                    row_base['_config_error'] = 'Invalid Format' # Shorten error
        except json.JSONDecodeError:
            logger.error(f"Could not decode JSON from config file: {config_file}")
            row_base['_config_error'] = 'Decode Error'
        except FileNotFoundError:
             logger.warning(f"Config file not found during table preparation: {config_file}")
             row_base['_config_error'] = 'Not Found' 
        except Exception as e:
            logger.error(f"Error reading config file {config_file}: {e}", exc_info=True)
            row_base['_config_error'] = 'Read Error'

        table_data.append(row_base)

    # Add rows for slugs requested in THIS load that failed fetch (only if reload was true)
    if force_reload:
        processed_slugs = {row['_slug'] for row in table_data}
        for slug, status_dict in fetch_statuses.items():
            if slug not in processed_slugs:
                 # Check if config fetch failed specifically
                 if not status_dict.get('config',{}).get('success'):
                     table_data.append({
                         '_slug': slug,
                         '_config_status': status_dict.get('config'),
                         '_users_status': status_dict.get('users'),
                         '_holders_status': status_dict.get('holders'),
                         '_config_error': status_dict.get('config', {}).get('error', 'Fetch Failed'),
                         '_users_exist': status_dict.get('users',{}).get('success'),
                         '_holders_exist': status_dict.get('holders',{}).get('success')
                     })

    # (Sorting keys and preparing final data remains the same...)
    sorted_config_keys = sorted(list(all_config_keys))
    final_table_data = []
    for row in table_data:
        # Keep metadata: slug, config_error (read error), existence flags
        complete_row = {
            k:v for k,v in row.items() 
            if k == '_slug' or k == '_config_error' or k.endswith('_exist')
        } 
        # Add fetch status *only if* reload occurred in this request
        if force_reload:
             complete_row['_config_status'] = row.get('_config_status')
             complete_row['_users_status'] = row.get('_users_status')
             complete_row['_holders_status'] = row.get('_holders_status')
             
        for key in sorted_config_keys:
            value = row.get(key)
            if isinstance(value, (dict, list)):
                try: display_value = f"[{type(value).__name__} ({len(value)})]"
                except: display_value = f"[{type(value).__name__}]"
            elif value is None: display_value = "None"
            elif value is True: display_value = "True"
            elif value is False: display_value = "False"
            else: display_value = str(value)
            complete_row[key] = display_value
        final_table_data.append(complete_row)

    default_visible_keys = ['name', 'company', 'status', 'start_date']
    default_visible_keys = [k for k in default_visible_keys if k in all_config_keys]

    # Add sorting to the final table data by slug for consistency
    final_table_data.sort(key=lambda x: x.get('_slug', ''))

    logger.info(f"--- Slug Inspector View Rendering (Reload={force_reload}) --- ")
    return render_template('inspector_slugs.html',
                           # Pass the list of slugs we *intended* to process
                           slugs_being_processed=slugs_to_process, 
                           columns=sorted_config_keys,
                           data=final_table_data,
                           default_visible_columns=default_visible_keys,
                           auth_error=auth_error, # Pass potential auth error
                           reload_occurred=force_reload) # Flag for template

# --- Detail Routes Helper (Modificado) ---

def _read_and_render_detail(slug: str, data_type: str, template_name: str):
    """Helper to read JSON and render detail template, attempting table format."""
    json_path = SLUG_CONFIG_DIR / f"{slug}_{data_type}.json"
    data = None
    headers = None # Initialize headers as None
    error = None
    is_list_of_dicts = False

    if not json_path.exists():
        error = f"Archivo {json_path.name} no encontrado. Posiblemente el fetch falló o fue omitido."
        logger.warning(f"Detail view requested but file not found: {json_path}")
    else:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data_raw = json.load(f)
                
                # Check if data is a list of dictionaries for table view
                if isinstance(data_raw, list) and data_raw and all(isinstance(item, dict) for item in data_raw):
                    is_list_of_dicts = True
                    data = data_raw # Use the raw list
                    # Extract headers from the keys of the first item
                    headers = list(data[0].keys()) 
                    logger.info(f"Rendering {data_type} for {slug} as a table with headers: {headers}")
                else:
                    # Otherwise, prepare for raw JSON display
                    data = json.dumps(data_raw, indent=4, ensure_ascii=False)
                    logger.info(f"Rendering {data_type} for {slug} as raw JSON.")

        except json.JSONDecodeError as e:
            error = f"Error al decodificar el archivo JSON ({json_path.name}): {e}"
            logger.error(f"Failed to decode {json_path}: {e}")
            data = None # Ensure data is None on error
        except Exception as e:
            error = f"Error inesperado al leer el archivo {json_path.name}: {e}"
            logger.error(f"Failed to read {json_path}: {e}", exc_info=True)
            data = None

    return render_template(template_name,
                           slug=slug,
                           data=data,
                           headers=headers, # Pass headers (will be None if not table)
                           is_table=is_list_of_dicts,
                           error=error)

# (view_slug_users y view_slug_holders sin cambios, usan el helper modificado) 

# --- NUEVA FUNCIÓN HELPER PARA DCV --- 
def _fetch_and_save_dcv_json(slug: str, cookies: Optional[dict]): # Expect cookies
    """
    Fetches DCV config JSON using requests with provided cookies.

    Args:
        slug (str): The meeting slug.
        cookies (Optional[dict]): The authentication cookies obtained after login.

    Returns:
        dict: Status dictionary ('success': bool, 'error': Optional[str]).
    """
    output_path = DCV_CONFIG_DIR / f"{slug}_config.json"
    api_url = f"{DCV_API_URL}/{slug}" # Corrected URL: Removed /config
    status = {'success': False, 'error': None}
    headers = {'Accept': 'application/json'}
    response = None
    
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use requests, mirroring _fetch_and_save_json logic
    try:
        logger.info(f"[DCV Fetch REQ] Fetching config for slug '{slug}' from {api_url} using requests...")
        if not cookies:
             logger.error(f"[DCV Fetch REQ] No cookies provided for slug '{slug}'. Cannot authenticate.")
             status['error'] = "Auth Error (No Cookies)"
             # We cannot proceed without cookies, so return the error status
             return status 

        response = requests.get(api_url, cookies=cookies, headers=headers, timeout=45)
        response.raise_for_status() 
        
        data = response.json() 
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        status['success'] = True
        logger.info(f"[DCV Fetch REQ] Successfully fetched and saved config for slug '{slug}' to {output_path}")

    # Exception Handling (copied & adapted from _fetch_and_save_json)
    except requests.exceptions.Timeout as e:
        error_msg = f"[DCV Fetch REQ] Timeout fetching config for {slug}: {e}"
        logger.error(error_msg)
        status['error'] = f'Timeout ({e})'
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_msg = f"[DCV Fetch REQ] HTTP error fetching config for {slug}: {status_code} {e.response.reason}"
        logger.error(error_msg)
        status['error'] = f'HTTP {status_code}'
        if status_code in [401, 403]:
            logger.warning(f"[DCV Fetch REQ] Received {status_code} for {slug} - Authentication failed or cookies expired?")
            status['error'] += " (Auth Failed?)"
        elif status_code == 404:
            logger.warning(f"[DCV Fetch REQ] Received 404 Not Found for {slug} at {api_url}")
            status['error'] += " (Not Found)"
    except requests.exceptions.RequestException as e:
        error_msg = f"[DCV Fetch REQ] Request error fetching config for {slug}: {e}"
        logger.error(error_msg)
        status['error'] = f'Request Error ({e})'
    except json.JSONDecodeError as e:
        response_text = response.text if response is not None else "(No response object)"
        error_msg = f"[DCV Fetch REQ] JSON decode error fetching config for {slug}: {e}. Response text: {response_text[:200]}..."
        logger.error(error_msg)
        status['error'] = f'Invalid JSON ({e})'
        invalid_path = output_path.with_suffix('.invalid.txt')
        try:
            if response is not None:
                with open(invalid_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                logger.info(f"[DCV Fetch REQ] Saved invalid response text to {invalid_path}")
            else:
                 logger.warning(f"[DCV Fetch REQ] Cannot save invalid response text, response object is None.")
        except Exception as save_err:
            logger.error(f"[DCV Fetch REQ] Could not save invalid response text: {save_err}")
    except OSError as e:
        logger.error(f"[DCV Fetch REQ] OS error saving config JSON for slug '{slug}' to {output_path}: {e}")
        status['error'] = "Save Error"
    except Exception as e:
        error_msg = f"[DCV Fetch REQ] Unexpected error processing config for {slug}: {e}"
        logger.error(error_msg, exc_info=True)
        status['error'] = f'Unexpected Error ({type(e).__name__})'
             
    return status

# Updated DCV Inspector View
@main_bp.route('/inspector-dcv')
def dcv_inspector_view():
    """Displays DCV slug configurations using requests with extracted cookies.""" # Corrected docstring
    reload_data = request.args.get('reload', 'false').lower() == 'true'
    auth_error = None
    fetch_results = {} 
    # driver = None # Not using driver here
    dcv_cookies = None # Expecting cookies

    if reload_data:
        logger.info("--- DCV Inspector View Reload Requested ---")
        DCV_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # --- Get DCV Cookies --- 
        try:
            logger.info(f"Attempting to get authenticated cookies for DCV: {DCV_LOGIN_URL}")
            # Calls the function which returns cookies (after logging debug info)
            dcv_cookies = init_selenium_session_and_login(DCV_LOGIN_URL) 

            if dcv_cookies:
                logger.info(f"DCV authentication successful, obtained {len(dcv_cookies)} cookie(s). Proceeding to fetch data via requests...")
                # Fetch data for each slug using the cookies
                for slug in DCV_INITIAL_SLUGS:
                    # Pass the cookies instance to the requests-based fetch function
                    status = _fetch_and_save_dcv_json(slug, dcv_cookies) # Pass cookies 
                    fetch_results[slug] = status
                logger.info("Finished fetching DCV data for all slugs using cookies.")
            else:
                # Authentication failed, cookies are None
                auth_error = "Fallo en la autenticación DCV vía Selenium (no se obtuvieron cookies post-navegación). Cannot proceed with DCV data fetch."
                logger.critical(auth_error)
                flash(auth_error, 'danger')

        except Exception as e:
             error_msg = f"Unexpected error during DCV cookie retrieval or data fetch process: {e}"
             logger.error(error_msg, exc_info=True)
             auth_error = error_msg 
             flash(f"Error inesperado durante la recarga: {e}", 'danger')
             
        # No finally block needed here as driver is handled within init_selenium_session_and_login
                     
    # --- Load and process data (regardless of reload) ---
    logger.info(f"--- DCV Inspector View Rendering (Reload={reload_data}) --- ")
    all_data = []
    all_columns = set()
    
    DCV_CONFIG_DIR.mkdir(parents=True, exist_ok=True) # Ensure dir exists
    config_files = list(DCV_CONFIG_DIR.glob('*_config.json'))
    logger.info(f"Found {len(config_files)} config files in {DCV_CONFIG_DIR}.")

    slugs_processed = set()

    for filepath in config_files:
        try:
            slug = filepath.stem.split('_config')[0]
            if slug in slugs_processed: continue # Skip if already processed (e.g., from fetch_results)
                
            with open(filepath, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # row = {'_slug': slug, 'config': config_data} # Old nested structure
            # --- Flatten the structure ---
            row = {'_slug': slug}
            row.update(config_data) # Merge config keys directly into the row
            # --- End Flatten ---
            
            all_columns.update(config_data.keys())
            
            # Add fetch status if reload happened and we have results for this slug
            if reload_data and slug in fetch_results:
                row['_config_status'] = fetch_results[slug]
                slugs_processed.add(slug) # Mark as processed

            all_data.append(row)

        except Exception as e:
            logger.error(f"Error reading or processing DCV config file {filepath}: {e}")
            # Add a row indicating the error for this file
            slug_from_filename = filepath.stem.split('_config')[0]
            if slug_from_filename not in slugs_processed:
                 all_data.append({'_slug': slug_from_filename, '_config_error': f'Error al leer/procesar archivo: {e}'})
                 if reload_data and slug_from_filename in fetch_results:
                     all_data[-1]['_config_status'] = fetch_results[slug_from_filename] # Add status if available
                 slugs_processed.add(slug_from_filename)


    # If reload happened, add rows for slugs that might have failed fetch entirely
    # and didn't even create a file
    if reload_data:
        for slug in DCV_INITIAL_SLUGS:
            if slug not in slugs_processed:
                 status = fetch_results.get(slug, {'success': False, 'error': 'Fetch no iniciado?'})
                 all_data.append({'_slug': slug, '_config_status': status})
                 slugs_processed.add(slug) # Mark as processed

    # Sort columns alphabetically for consistent display order in selector
    sorted_columns = sorted(list(all_columns))
    # Define default visible columns (adjust as needed for DCV)
    default_visible = {'landing_url', 'name', 'description', 'state', 'start_date', 'meeting_type'} 
    
    # Ensure default visible columns actually exist in the data
    # Also add 'landing_url' explicitly if it wasn't found dynamically
    if 'landing_url' not in sorted_columns:
        sorted_columns.insert(0, 'landing_url') # Add it if missing
    
    final_default_visible = [col for col in default_visible if col in all_columns or col == 'landing_url']
    # Make sure 'landing_url' is visible by default if present
    if 'landing_url' in sorted_columns and 'landing_url' not in final_default_visible:
        final_default_visible.append('landing_url')


    return render_template(
        'inspector_dcv.html',
        data=all_data,
        columns=sorted_columns,
        default_visible_columns=final_default_visible, 
        reload_occurred=reload_data,
        auth_error=auth_error
    )

# ... rest of the file ...

# Helper function to read details (adjust paths if needed) - No changes needed for DCV logic change
def _read_and_render_detail(slug: str, data_type: str, template_name: str):
    # ... (Función existente sin cambios) ...
    pass # Adding pass to fix indentation block error

# (view_slug_users y view_slug_holders no aplican a DCV por ahora) 

# --- Helper Functions for Slug Inspectors ---

# Renamed and refactored function
def init_selenium_session_and_login(login_url: str) -> Optional[dict]:
    """
    Logs in, gets cookies from BOTH login and API domains, merges them, and quits.
    Returns a combined cookie dictionary suitable for requests.

    Args:
        login_url (str): The base URL for the login page.

    Returns:
        Optional[dict]: The potentially formatted cookies dictionary.
    """
    driver = None # Initialize driver to None
    try:
        # --- Log the raw environment variable value --- 
        raw_headless_setting = os.getenv('SELENIUM_HEADLESS', 'true')
        logger.info(f"[Headless Check] Raw value from os.getenv('SELENIUM_HEADLESS'): '{raw_headless_setting}'")
        # --- End Log ---
        headless_mode = raw_headless_setting.lower() == 'true'
        logger.info(f"Attempting to setup WebDriver (Headless: {headless_mode}) for login at: {login_url}")
        driver = setup_webdriver(headless=headless_mode) # Pass headless status
        
        if not driver:
             logger.error(f"WebDriver setup failed for {login_url}. Cannot proceed with login.")
             return None # Return None if driver setup failed

        logger.info(f"WebDriver setup successful. Initializing AuthManager for {login_url}.")
        auth = AuthManager(driver, login_url=login_url)

        logger.info(f"Attempting login via Selenium for {login_url}...")
        login_successful = auth.login() # Use configured credentials

        if login_successful:
            logger.info(f"Login successful via Selenium for {login_url}. Attempting combined cookie extraction...")
            # --- Combined Cookie Extraction --- 
            final_cookies_for_requests = {}
            try:
                # 1. Get cookies immediately after login (from login domain)
                cookies_login_domain = driver.get_cookies()
                logger.info(f"[DEBUG COOKIES] Found {len(cookies_login_domain)} raw cookies from LOGIN domain ({login_url}):")
                for cookie in cookies_login_domain:
                    logger.info(f"  - {cookie}")
                    # Add to our final dict (simple name:value)
                    final_cookies_for_requests[cookie['name']] = cookie['value']
                
                # 2. Navigate to API base URL
                api_base_url = DCV_API_URL.split('/admin')[0] 
                if api_base_url:
                    logger.info(f"Navigating driver to API base URL: {api_base_url}...")
                    driver.get(api_base_url)
                    time.sleep(2) 
                    logger.info(f"Current URL after navigating to API base: {driver.current_url}")
                    
                    # 3. Get cookies again (from API domain)
                    cookies_api_domain = driver.get_cookies()
                    logger.info(f"[DEBUG COOKIES] Found {len(cookies_api_domain)} raw cookies from API domain ({api_base_url}):")
                    for cookie in cookies_api_domain:
                        logger.info(f"  - {cookie}")
                        # Add/overwrite in our final dict (API domain cookies might be more specific/important)
                        final_cookies_for_requests[cookie['name']] = cookie['value']
                else:
                    logger.warning("Could not determine API base URL from DCV_API_URL, skipping API domain cookie check.")

                logger.info(f"Combined and formatted {len(final_cookies_for_requests)} cookies for requests.")

            except Exception as cookie_err:
                logger.error(f"Error during combined cookie extraction for {login_url}: {cookie_err}", exc_info=True)
                final_cookies_for_requests = None # Indicate failure 
            # --- End Cookie Extraction ---
            
            # --- Always quit driver --- 
            try:
                driver.quit()
                logger.info(f"Selenium driver quit after successful login and cookie extraction attempt for {login_url}.")
            except Exception as q_err:
                logger.error(f"Error quitting driver after successful login: {q_err}")
            # --- End Quit --- 
            
            return final_cookies_for_requests # Return the combined, formatted cookies
        else:
            logger.error(f"Selenium login failed for {login_url}.")
    except Exception as e:
        logger.error(f"Exception during Selenium session initialization or login for {login_url}: {e}", exc_info=True)
        if driver: # Ensure driver is quit even if other exceptions occur
             try:
                 driver.quit()
                 # Corrected log message string below
                 logger.info(f"Selenium driver quit due to exception during setup/login for {login_url}.") 
             except Exception as quit_err:
                 logger.error(f"Error quitting driver during exception handling: {quit_err}")
        return None

    if final_cookies_for_requests:
         logger.info(f"Retrieved {len(final_cookies_for_requests)} cookies for {login_url}.")
    else:
         logger.warning(f"Failed to retrieve cookies for {login_url}.")
    return final_cookies_for_requests

# --- Standard Slug Inspector Functions (Using Requests) ---

def _fetch_and_save_json(api_url: str, output_path: Path, data_type: str, slug: str, cookies: Optional[dict] = None) -> dict:
    """Fetches JSON data from the API using requests and saves it locally.

    Args:
        api_url: The URL to fetch from.
        output_path: Path object to save the JSON.
        data_type: String identifier for logging ('config', 'users', 'holders').
        slug: The meeting slug (for logging).
        cookies: Optional dictionary of cookies to use for authentication.

    Returns:
        dict: Status dictionary ('success': bool, 'error': Optional[str]).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    status = {'success': False, 'error': None}
    headers = {'Accept': 'application/json'}
    response = None # Initialize response
    
    try:
        logger.info(f"Fetching {data_type} data for slug '{slug}' from {api_url} using requests...")
        response = requests.get(api_url, cookies=cookies, headers=headers, timeout=45)
        response.raise_for_status()
        
        data = response.json()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        status['success'] = True
        logger.info(f"Successfully fetched and saved {data_type} for slug '{slug}' to {output_path}")
        
    except requests.exceptions.Timeout as e:
        error_msg = f"Timeout fetching {data_type} for {slug}: {e}"
        logger.error(error_msg)
        status['error'] = f'Timeout ({e})'
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP error fetching {data_type} for {slug}: {e.response.status_code} {e.response.reason}"
        logger.error(error_msg)
        status['error'] = f'HTTP {e.response.status_code}'
        if e.response.status_code in [401, 403]:
            logger.warning(f"Received {e.response.status_code} - Authentication failed or cookies expired for {slug}.")
            status['error'] += " (Auth Failed?)"
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error fetching {data_type} for {slug}: {e}"
        logger.error(error_msg)
        status['error'] = f'Request Error ({e})'
    except json.JSONDecodeError as e:
        response_text = response.text if response is not None else "(No response object)"
        error_msg = f"JSON decode error fetching {data_type} for {slug}: {e}. Response text: {response_text[:200]}..."
        logger.error(error_msg)
        status['error'] = f'Invalid JSON ({e})'
        invalid_path = output_path.with_suffix('.invalid.txt')
        try:
            if response is not None:
                with open(invalid_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                logger.info(f"Saved invalid response text to {invalid_path}")
            else:
                 logger.warning(f"Cannot save invalid response text, response object is None.")
        except Exception as save_err:
            logger.error(f"Could not save invalid response text: {save_err}")
    except OSError as e:
        logger.error(f"OS error saving {data_type} JSON for slug '{slug}' to {output_path}: {e}")
        status['error'] = "Save Error"
    except Exception as e:
        error_msg = f"Unexpected error processing {data_type} for {slug}: {e}"
        logger.error(error_msg, exc_info=True)
        status['error'] = f'Unexpected Error ({type(e).__name__})'
        
    return status

def fetch_and_save_slug_data(slug: str, target_dir: Path, cookies: Optional[dict]) -> dict:
    """Fetches config, users, and holders JSON for a given slug and saves them.

    Args:
        slug: The meeting slug.
        target_dir: The directory Path object to save the JSON.
        cookies: The dictionary of authentication cookies.

    Returns:
        dict: Results dictionary with status objects for each data type.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    fetch_types = {
        'config': f"{BASE_API_URL}/{slug}/config",
        'users': f"{BASE_API_URL}/{slug}/users",
        'holders': f"{BASE_API_URL}/{slug}/holders"
    }
    
    logger.info(f"--- Fetching data for standard slug: {slug} ---")
    for data_type, api_url in fetch_types.items():
        output_path = target_dir / f"{slug}_{data_type}.json"
        status = _fetch_and_save_json(api_url, output_path, data_type, slug, cookies)
        results[f'_{data_type}_status'] = status # Store the whole status dict
        if status['success']:
            logger.info(f" Success fetching {data_type} for '{slug}'")
        else:
             logger.warning(f" Failed fetching {data_type} for '{slug}': {status['error']}")
            
    return results

# @main_bp.route('/inspector-slugs')
# def slug_inspector_view():
#     # ... existing logic for standard inspector using requests ...
#     # This function is now quite long and could be refactored later.
#     # For now, leaving it as is until we confirm the DCV approach works.
#     pass

# --- DCV Inspector Functions (Using Selenium) ---

# def _fetch_and_save_dcv_json(slug: str, driver: WebDriver) -> dict:
#     """
#     Fetches DCV config JSON using Selenium driver navigation and enhanced parsing.
# 
#     Args:
#         slug (str): The meeting slug.
#         driver (WebDriver): The authenticated Selenium WebDriver instance.
# 
#     Returns:
#         dict: Status dictionary ('success': bool, 'error': Optional[str]).
#     """
#     output_path = DCV_CONFIG_DIR / f"{slug}_config.json"
#     api_url = f"{DCV_API_URL}/{slug}"
#     status = {'success': False, 'error': None}
#     json_text = "(Not retrieved)" # Initialize for error logging
#     page_source = "(Not retrieved)"
#     
#     output_path.parent.mkdir(parents=True, exist_ok=True)
# 
#     try:
#         logger.info(f"[DCV Fetch] Navigating Selenium driver to config URL for slug '{slug}': {api_url}")
#         driver.get(api_url)
#         # Give the page a moment to potentially render JavaScript or finish loading
#         time.sleep(2) 
#         
#         page_source = driver.page_source
#         json_found = False
#         data = None
# 
#         # --- Enhanced JSON Extraction --- 
#         try:
#             # Primary target: Look for JSON within a <pre> tag
#             pre_element = driver.find_element(By.TAG_NAME, "pre")
#             json_text = pre_element.text
#             logger.info(f"[DCV Fetch] Found <pre> tag for slug '{slug}'. Attempting to parse content...")
#             data = json.loads(json_text)
#             json_found = True
#         except NoSuchElementException:
#             logger.warning(f"[DCV Fetch] No <pre> tag found for slug '{slug}'. Checking body...")
#             try:
#                 # Fallback: Check if the body text is JSON
#                 json_text = driver.find_element(By.TAG_NAME, "body").text
#                 # Basic check if it looks like JSON before attempting parse
#                 if json_text.strip().startswith('{') or json_text.strip().startswith('['):
#                     logger.info(f"[DCV Fetch] Body text for slug '{slug}' looks like JSON. Attempting parse...")
#                     data = json.loads(json_text)
#                     json_found = True
#                 else:
#                     logger.error(f"[DCV Fetch] Body text for slug '{slug}' does not start like JSON: {json_text[:100]}...")
#                     status['error'] = "Invalid Content (Not JSON in body)"
#             except Exception as body_err:
#                 logger.error(f"[DCV Fetch] Error getting/parsing body text for slug '{slug}': {body_err}", exc_info=True)
#                 status['error'] = "Error parsing body text"
#         except json.JSONDecodeError as json_e:
#             # This catches JSON errors specifically from the <pre> tag attempt
#             logger.error(f"[DCV Fetch] Failed to decode JSON from <pre> tag for slug '{slug}': {json_e}. Text: {json_text[:200]}...")
#             status['error'] = f'Invalid JSON in <pre> ({json_e})'
#             # Save the invalid text from <pre>
#             invalid_path = output_path.with_suffix('.invalid_pre.txt')
#             try: 
#                 with open(invalid_path, 'w', encoding='utf-8') as f:
#                     f.write(json_text)
#                 logger.info(f"[DCV Fetch] Saved invalid <pre> text to {invalid_path}")
#             except Exception as save_err:
#                 logger.error(f"[DCV Fetch] Could not save invalid <pre> text: {save_err}")
#         except Exception as e:
#             # Catch other unexpected errors during extraction (e.g., finding elements)
#              logger.error(f"[DCV Fetch] Unexpected error during JSON extraction attempt for slug '{slug}': {e}", exc_info=True)
#              status['error'] = f'Extraction Error ({type(e).__name__})'
#         # --- End Enhanced JSON Extraction ---
# 
#         if json_found and data is not None:
#              # Save the successfully parsed JSON data
#              with open(output_path, 'w', encoding='utf-8') as f:
#                  json.dump(data, f, ensure_ascii=False, indent=4)
#              status['success'] = True
#              logger.info(f"[DCV Fetch] Successfully parsed and saved config for slug '{slug}' to {output_path}")
#         elif not status['error']: # If no error was set during extraction but json wasn't found
#              error_msg = f"[DCV Fetch] Could not find valid JSON in <pre> or body for slug '{slug}'. Page source saved." 
#              logger.error(error_msg)
#              status['error'] = "JSON Not Found in Source"
#              # Save the full page source if JSON wasn't found
#              invalid_path = output_path.with_suffix('.source.html')
#              try:
#                  with open(invalid_path, 'w', encoding='utf-8') as f:
#                      f.write(page_source)
#                  logger.info(f"[DCV Fetch] Saved full page source to {invalid_path}")
#              except Exception as save_err:
#                  logger.error(f"[DCV Fetch] Could not save full page source: {save_err}")
# 
#     # --- Exception Handling for driver.get() or other major issues --- 
#     except Exception as e: 
#         error_msg = f"[DCV Fetch] Major error navigating or processing slug '{slug}' via Selenium: {e}"
#         logger.error(error_msg, exc_info=True)
#         status['error'] = f'Selenium Navigation Error ({type(e).__name__})'
#         # Attempt screenshot if a major error occurs
#         try:
#              ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#              screenshot_path = f"error_screenshot_dcv_fetch_{slug}_{ts}.png"
#              if driver: # Check if driver is still valid
#                  driver.save_screenshot(screenshot_path)
#                  logger.info(f"Saved screenshot on navigation error to: {screenshot_path}")
#              else:
#                   logger.warning(f"Could not save screenshot, driver object is invalid.")
#         except Exception as screen_err:
#              logger.error(f"Could not save screenshot on navigation error: {screen_err}")
#              
#     return status