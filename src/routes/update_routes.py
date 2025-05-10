import os
import json
import logging
import uuid
import shutil
import time
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)
from werkzeug.utils import secure_filename

# Import helper functions
from src.utils.helpers import allowed_file
from src.utils.comparison import _compare_configurations # Needed for re-comparison

# Import Processors
from src.processors import OpenAIProcessor

logger = logging.getLogger(__name__)

# Define the blueprint
update_bp = Blueprint('update', __name__, template_folder='../templates')

# === Update Routes ===

@update_bp.route('/actualizar-documentos/<original_filename>')
def actualizar_documentos_form(original_filename):
    """Displays the form to upload new documents for an existing report."""
    filename_safe = secure_filename(original_filename)
    # Use current_app.config
    report_path = os.path.join(current_app.config['REPORTS_DIR'], filename_safe)

    if not os.path.exists(report_path):
        flash(f'El informe "{original_filename}" no existe.', 'danger')
        return redirect(url_for('main.dashboard')) # Redirect to main dashboard

    return render_template('actualizar_documentos.html', original_filename=filename_safe)

@update_bp.route('/actualizar-documentos-submit/<original_filename>', methods=['POST'])
def actualizar_documentos_submit(original_filename):
    """Processes the uploaded documents, re-runs comparison, and updates the report."""
    start_time = time.time()
    filename_safe = secure_filename(original_filename)
    # Use current_app.config
    reports_dir = current_app.config['REPORTS_DIR']
    upload_folder = current_app.config['UPLOAD_FOLDER']
    report_path = os.path.join(reports_dir, filename_safe)

    if not os.path.exists(report_path):
        flash(f'Error: El informe original "{original_filename}" no fue encontrado.', 'danger')
        return redirect(url_for('main.dashboard'))

    uploaded_files = request.files.getlist('document_files')
    if not uploaded_files or all(f.filename == '' for f in uploaded_files):
        flash('Debes subir al menos un nuevo documento fuente.', 'danger')
        # Redirect back to the form using blueprint notation
        return redirect(url_for('update.actualizar_documentos_form', original_filename=original_filename))

    # Load original report data
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            original_report_data = json.load(f)
        config_selenium_original = original_report_data.get('configuracion_actual')
        if not config_selenium_original:
            raise ValueError("No se encontró 'configuracion_actual' en el informe original.")
    except (json.JSONDecodeError, ValueError, FileNotFoundError) as e:
        flash(f'Error al cargar datos del informe original: {e}', 'danger')
        logger.error(f"[Update Docs] Error loading original report {report_path}: {e}")
        return redirect(url_for('main.dashboard'))

    # Create temporary directory for new documents
    update_task_id = str(uuid.uuid4())
    temp_dir = os.path.join(upload_folder, f"update_{update_task_id}")
    new_saved_files_data = []
    error_during_upload = False

    try:
        logger.info(f"[Update Docs] Update {update_task_id}: Creating temp dir {temp_dir} for report {original_filename}")
        os.makedirs(temp_dir, exist_ok=True)
        valid_files_found = False
        for file in uploaded_files:
            if file and file.filename != '' and allowed_file(file.filename):
                new_filename = secure_filename(file.filename)
                filepath = os.path.join(temp_dir, new_filename)
                logger.info(f"[Update Docs] Update {update_task_id}: Saving new file {new_filename} to {filepath}")
                file.save(filepath)
                new_saved_files_data.append({'path': filepath, 'type': file.mimetype})
                valid_files_found = True
            elif file and file.filename != '':
                 logger.warning(f"[Update Docs] Update {update_task_id}: File type not allowed: {file.filename}")
                 flash(f'Tipo de archivo no permitido: {file.filename}', 'warning')

        if not valid_files_found:
            flash('No se subieron archivos válidos o permitidos para la actualización.', 'danger')
            error_during_upload = True

    except Exception as e:
        flash(f'Error al guardar los nuevos documentos: {str(e)}', 'danger')
        logger.error(f"[Update Docs] Update {update_task_id}: Error saving uploaded files: {e}", exc_info=True)
        error_during_upload = True

    if error_during_upload:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        return redirect(url_for('update.actualizar_documentos_form', original_filename=original_filename))

    # Process new documents with OpenAI
    new_config_docs = None
    processing_error_msg = None
    try:
        logger.info(f"[Update Docs] Update {update_task_id}: Processing {len(new_saved_files_data)} new documents.")
        processor = OpenAIProcessor()
        file_paths_for_openai = [f['path'] for f in new_saved_files_data]
        extracted_data = processor.process_multiple_sources(file_paths_for_openai)

        if not extracted_data or not isinstance(extracted_data, dict):
            raise ValueError("OpenAI no devolvió datos válidos o el formato es incorrecto.")
        if 'error' in extracted_data:
            raise ValueError(f"Error de OpenAI: {extracted_data['error']}")

        new_config_docs = extracted_data
        logger.info(f"[Update Docs] Update {update_task_id}: OpenAI processing successful.")

    except Exception as e:
        processing_error_msg = f"Error al procesar nuevos documentos con OpenAI: {str(e)}"
        logger.error(f"[Update Docs] Update {update_task_id}: {processing_error_msg}", exc_info=True)
        flash(processing_error_msg, 'danger')
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        return redirect(url_for('update.actualizar_documentos_form', original_filename=original_filename))

    # Re-run comparison
    new_comparison_results = None
    comparison_error_msg = None
    try:
        logger.info(f"[Update Docs] Update {update_task_id}: Re-comparing with new documents data.")
        # Pass the module's logger to the comparison function
        new_diff_list = _compare_configurations(new_config_docs, config_selenium_original)
        new_comparison_results = {
             "match": not bool(new_diff_list),
             "differences": new_diff_list,
             "timestamp": datetime.now().isoformat()
        }
        logger.info(f"[Update Docs] Update {update_task_id}: Re-comparison successful. Match: {new_comparison_results.get('match')}")
    except Exception as e:
        comparison_error_msg = f"Error durante la re-comparación: {str(e)}"
        logger.error(f"[Update Docs] Update {update_task_id}: {comparison_error_msg}", exc_info=True)
        flash(f"Error en la comparación, el informe puede estar incompleto: {comparison_error_msg}", 'warning')

    # Update and overwrite the original report
    try:
        logger.info(f"[Update Docs] Update {update_task_id}: Updating report file {report_path}")
        original_report_data['configuracion_documentos'] = new_config_docs
        original_report_data['comparacion_selenium_vs_documentos'] = new_comparison_results
        original_report_data['timestamp_actualizacion'] = datetime.now().isoformat()
        if comparison_error_msg:
             original_report_data['error_actualizacion'] = comparison_error_msg

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(original_report_data, f, ensure_ascii=False, indent=2)
        logger.info(f"[Update Docs] Update {update_task_id}: Report {original_filename} updated.")
        flash(f'Informe "{original_filename}" actualizado exitosamente.', 'success')

    except Exception as e:
        save_error_msg = f"Error crítico al guardar el informe actualizado: {str(e)}"
        logger.error(f"[Update Docs] Update {update_task_id}: {save_error_msg}", exc_info=True)
        flash(save_error_msg, 'danger')
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        return redirect(url_for('main.dashboard')) # Redirect to dashboard on critical save error

    # Clean up temporary directory for the update
    finally:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"[Update Docs] Update {update_task_id}: Cleaned up temp directory {temp_dir}")
            except Exception as e:
                logger.error(f"[Update Docs] Update {update_task_id}: Error cleaning up temp dir {temp_dir}: {e}")

    end_time = time.time()
    logger.info(f"[Update Docs] Update {update_task_id}: Process finished in {end_time - start_time:.2f} seconds.")
    # Redirect to view the updated report using the main blueprint's endpoint
    return redirect(url_for('main.ver_informe', filename=filename_safe)) 