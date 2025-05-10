import os
import json
import logging
import threading
import shutil
import uuid
from datetime import datetime

# Import shared state and constants
from src.globals import combined_revision_status, combined_status_lock, REPORTS_DIR

# Import functions/classes from other modules
from src.utils.comparison import _compare_configurations, generate_comparison_report_data
from src.main import RevisorJuntas
from src.processors import OpenAIProcessor
from src.reporting import generate_report_data
from src.config import REPORTS_DIR

logger = logging.getLogger(__name__)

# --- Background Task Helper Functions ---

def _update_combined_status(task_id, section, status, message, result_path=None, error_details=None, final_report_path=None):
    """Helper function to update the combined status dictionary safely."""
    with combined_status_lock:
        if task_id in combined_revision_status:
            task_status = combined_revision_status[task_id]
            
            if section == 'overall':
                task_status['status'] = status
                if error_details:
                    task_status['error'] = error_details
                if final_report_path: # Store the final report filename
                    task_status['final_report'] = final_report_path
                logger.info(f"[BG Task] Task {task_id}: Overall status updated to {status}. Final Report: {final_report_path}")
            elif section in task_status:
                task_status[section]['status'] = status
                task_status[section]['message'] = message
                if result_path:
                    task_status[section]['result_path'] = result_path
                if error_details:
                    task_status[section]['error'] = error_details
                    existing_error = task_status.get('error') or ''
                    task_status['error'] = existing_error + f"[{section} Error]: {error_details}\n"
                    task_status['status'] = 'error'
            else:
                logger.warning(f"[BG Task] Task {task_id}: Attempted to update non-existent section '{section}'.")
        else:
            logger.warning(f"[BG Task] Task {task_id}: Attempted to update status for non-existent task.")

def _check_and_trigger_comparison(task_id, upload_folder_path):
    """Checks if both Selenium and Docs processing are done and triggers comparison.
    
    Args:
        task_id (str): The ID of the task.
        upload_folder_path (str): The path to the temporary upload folder for this task, used for cleanup.
    """
    should_trigger = False
    should_cleanup = False
    selenium_path = None
    docs_path = None
    reports_dir = REPORTS_DIR # Use REPORTS_DIR from config

    with combined_status_lock:
        if task_id in combined_revision_status:
            status = combined_revision_status[task_id]
            selenium_done = status['selenium']['status'] in ['completed', 'error']
            docs_done = status['docs']['status'] in ['completed', 'error']
            comparison_pending = status['comparison']['status'] == 'pending'
            
            if selenium_done and docs_done and comparison_pending:
                should_trigger = True
                # Get paths needed for comparison
                selenium_path = status['selenium'].get('result_path')
                docs_path = status['docs'].get('result_path')
                # Mark comparison as running
                status['comparison']['status'] = 'running'
                status['comparison']['message'] = 'Iniciando comparación...'
                logger.info(f"[BG Task] Task {task_id}: Both Selenium and Docs finished. Triggering comparison.")
            elif status['status'] in ['completed', 'error']:
                # If overall is done but comparison didn't run (e.g., error before), trigger cleanup
                 if status['comparison']['status'] == 'pending':
                      logger.warning(f"[BG Task] Task {task_id}: Overall status is {status['status']} but comparison is still pending. Triggering cleanup.")
                      should_cleanup = True
            # else: Conditions not met, do nothing yet
        else:
            # Task doesn't exist, maybe already cleaned up?
            logger.warning(f"[BG Task] Task {task_id}: Status check called, but task not found.")
            return # Exit if task is gone

    # --- Perform Comparison (outside the lock) --- 
    comparison_error = None
    if should_trigger:
        try:
            # Check if prerequisite steps failed
            selenium_failed = combined_revision_status[task_id]['selenium']['status'] == 'error'
            docs_failed = combined_revision_status[task_id]['docs']['status'] == 'error'

            if selenium_failed or docs_failed:
                 reason = "falló la obtención de datos de Selenium/API" if selenium_failed else "" 
                 reason += " y " if selenium_failed and docs_failed else ""
                 reason += "falló el procesamiento de documentos" if docs_failed else ""
                 raise ValueError(f"No se puede comparar porque {reason}.")

            if not selenium_path or not docs_path:
                raise FileNotFoundError("No se encontraron las rutas a los archivos de resultados de Selenium o Documentos.")

            # --- Load data from both results --- 
            logger.info(f"[BG Task] Task {task_id}: Loading data from result files...")
            try:
                with open(selenium_path, 'r', encoding='utf-8') as f_sel:
                    selenium_results = json.load(f_sel)
                with open(docs_path, 'r', encoding='utf-8') as f_doc:
                    docs_results = json.load(f_doc)
                
                # --- Extract actual and expected config --- 
                # Assuming selenium report IS the structure containing 'configuracion_actual'
                config_actual = selenium_results.get('configuracion_actual') 
                if not config_actual:
                    raise ValueError("'configuracion_actual' no encontrada en los resultados de Selenium.")
                
                # Assuming docs result IS the expected config dictionary (configuracion_documentos)
                config_expected = docs_results 
                if not isinstance(config_actual, dict) or not isinstance(config_expected, dict):
                    raise TypeError("Expected config_actual and config_expected to be dictionaries.")

                # --- Perform Comparison using the updated function --- 
                logger.info(f"[BG Task] Task {task_id}: Performing comparison...")
                # LLAMAR A LA FUNCIÓN NUEVA QUE DEVUELVE EL DICCIONARIO COMPLETO
                comparison_summary_data = generate_comparison_report_data(config_expected, config_actual)
                
                # EXTRAER la lista de diferencias para compatibilidad con lógica existente (si es necesario)
                # diff_list = comparison_summary_data.get('detailed_differences', []) 

                # --- Assemble Final Report (using the new structure for comparison) --- 
                logger.info(f"[BG Task] Task {task_id}: Assembling final report...")
                # Start with the base data from the selenium report (contains config_actual)
                final_report_data = selenium_results.copy()
                # Add the document-based config
                final_report_data['configuracion_documentos'] = config_expected
                # ADD THE NEW COMPARISON SUMMARY STRUCTURE
                final_report_data['comparison_summary'] = comparison_summary_data 
                # Overwrite/set the final status based on comparison
                final_report_data['status'] = 'completed' # Mark as completed
                
                # --- Save Final Report --- 
                timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                slug = final_report_data.get('slug', 'unknown')
                final_report_filename = f"report_{slug}_{task_id}.json" # Use task_id for uniqueness
                final_report_path = os.path.join(reports_dir, final_report_filename)
                logger.info(f"[BG Task] Task {task_id}: Saving final report to: {final_report_path}")
                
                os.makedirs(reports_dir, exist_ok=True)
                with open(final_report_path, 'w', encoding='utf-8') as f_final:
                    json.dump(final_report_data, f_final, ensure_ascii=False, indent=2)
                logger.info(f"[BG Task] Task {task_id}: Final report saved successfully.")
                
                # Update status with comparison result and final path
                # Usar el conteo del nuevo summary
                diff_count = comparison_summary_data.get('total_diff_count', 0) 
                comp_status_message = f"Comparación completada. Diferencias: {diff_count}."
                _update_combined_status(task_id, 'comparison', 'completed', comp_status_message, result_path=final_report_path) 
                _update_combined_status(task_id, 'overall', 'completed', 'Revisión completada.', final_report_path=final_report_filename)
            
            except FileNotFoundError as fnf_err:
                 raise FileNotFoundError(f"Error cargando archivos de resultados: {fnf_err}") from fnf_err
            except (json.JSONDecodeError, TypeError, ValueError) as data_err:
                 raise ValueError(f"Error procesando datos para comparación: {data_err}") from data_err

        except Exception as e:
            comparison_error = f"Error durante la comparación: {str(e)}"
            logger.error(f"[BG Task] Task {task_id}: {comparison_error}", exc_info=True)
            # Update status if comparison fails
            _update_combined_status(task_id, 'comparison', 'error', comparison_error, error_details=str(e))
            _update_combined_status(task_id, 'overall', 'error', comparison_error)
        
        # Mark that cleanup should be triggered now comparison is done/failed
        should_cleanup = True

    # --- Trigger cleanup if needed --- 
    if should_cleanup:
         logger.info(f"[BG Task] Task {task_id}: Triggering cleanup check thread.")
         cleanup_thread = threading.Thread(target=_check_and_cleanup_task, args=(task_id, upload_folder_path), daemon=True)
         cleanup_thread.start()

# --- Main Background Task Runners ---

def run_verification_async_combined(task_id, slug, username, password, reports_dir, upload_folder_path):
    """Runs Selenium verification in a background thread."""
    logger.info(f"[BG Task] Task {task_id}: Starting Selenium verification for slug: {slug} (Upload folder: {upload_folder_path})")
    _update_combined_status(task_id, 'selenium', 'running', 'Iniciando Selenium...')
    revisor = None
    final_report_path = None
    error_message = None

    # Define the expected report path based on task_id and passed reports_dir
    # Note: REPORTS_DIR from globals might differ if app configured differently
    selenium_report_filename = f"report_{slug}_{task_id}.json"
    selenium_report_path = os.path.join(reports_dir, selenium_report_filename)

    try:
        def selenium_status_update(status, message, results_param=None):
            _update_combined_status(task_id, 'selenium', status, message)

        revisor = RevisorJuntas()
        # Assuming run_verification now returns a dict with 'status', 'report_path', 'error'
        results = revisor.run_verification(
            slug=slug,
            expected_config_path=None,
            username=username,
            password=password,
            status_update_callback=selenium_status_update
        )

        results_dict = results if isinstance(results, dict) else {}
        final_report_path = results_dict.get('report_path') # Should match selenium_report_path
        error_message = results_dict.get('error')
        final_status = results_dict.get('status', 'error')

        if final_status == 'completed' and final_report_path:
            logger.info(f"[BG Task] Task {task_id}: Selenium verification completed. Report: {final_report_path}")
            _update_combined_status(task_id, 'selenium', 'completed', 'Datos obtenidos vía Selenium/API.', result_path=final_report_path)
        else:
            effective_error_msg = error_message or "Error desconocido durante la verificación Selenium."
            logger.error(f"[BG Task] Task {task_id}: Selenium verification failed. Error: {effective_error_msg}")
            _update_combined_status(task_id, 'selenium', 'error', effective_error_msg, error_details=effective_error_msg)

    except Exception as e:
        error_message = f"Error crítico durante la ejecución de Selenium: {str(e)}"
        logger.error(f"[BG Task] Task {task_id}: {error_message}", exc_info=True)
        _update_combined_status(task_id, 'selenium', 'error', error_message, error_details=str(e))
    finally:
        # ALWAYS try to trigger the check, regardless of success or failure
        logger.info(f"[BG Task] Task {task_id}: Selenium thread finished. Triggering comparison check.")
        try:
            _check_and_trigger_comparison(task_id, upload_folder_path)
        except Exception as check_err:
            # Log error during check trigger but don't prevent thread completion
            logger.error(f"[BG Task] Task {task_id}: Error calling _check_and_trigger_comparison from Selenium thread: {check_err}", exc_info=True)

def process_documents_async_combined(task_id, saved_files_data):
    """Processes documents in a background thread."""
    logger.info(f"[BG Task] Task {task_id}: Starting document processing for {len(saved_files_data)} files.")
    _update_combined_status(task_id, 'docs', 'running', 'Iniciando procesamiento de documentos...')

    processed_config_path = None
    error_message = None
    # Determine temp_dir from the saved file paths
    temp_dir = os.path.dirname(saved_files_data[0]['path']) if saved_files_data else None

    if not temp_dir or not os.path.exists(temp_dir):
        error_message = "Directorio temporal no encontrado o archivos no proporcionados."
        logger.error(f"[BG Task] Task {task_id}: {error_message}")
        _update_combined_status(task_id, 'docs', 'error', error_message, error_details=error_message)
        # Trigger comparison check even if docs fail early
        # _check_and_trigger_comparison(task_id, upload_folder_path) # Need upload_folder_path here
        logger.info(f"[BG Task] Task {task_id}: Docs thread finished early (error). Comparison check will be triggered by the main logic or selenium thread.")
        return

    # Define the output path for the extracted config within the temp dir
    output_filename = f"{task_id}_extracted_config.json"
    output_path = os.path.join(temp_dir, output_filename)
    # This is also the upload_folder_path needed for cleanup
    upload_folder_path_for_cleanup = temp_dir

    try:
        json_files = [f for f in saved_files_data if f['path'].lower().endswith('.json')]
        other_files = [f for f in saved_files_data if not f['path'].lower().endswith('.json')]

        if json_files and other_files:
            error_message = "No se puede procesar un archivo JSON junto con otros tipos de archivo."
            _update_combined_status(task_id, 'docs', 'error', error_message, error_details=error_message)
        elif json_files:
            if len(json_files) > 1:
                error_message = "Solo se puede procesar un archivo JSON a la vez."
                _update_combined_status(task_id, 'docs', 'error', error_message, error_details=error_message)
            else:
                json_file_info = json_files[0]
                fname = os.path.basename(json_file_info['path'])
                _update_combined_status(task_id, 'docs', 'running', f"Procesando JSON: {fname}...")
                try:
                    shutil.copy2(json_file_info['path'], output_path)
                    processed_config_path = output_path
                    logger.info(f"[BG Task] Task {task_id}: JSON processed, config saved to {processed_config_path}")
                except Exception as e:
                    error_message = f"Error copiando JSON {fname}: {e}"
                    _update_combined_status(task_id, 'docs', 'error', "Error procesando JSON", error_details=str(e))
        elif other_files:
            _update_combined_status(task_id, 'docs', 'running', f"Preparando {len(other_files)} archivo(s) para análisis con IA...")
            file_paths_for_openai = [f['path'] for f in other_files]

            if file_paths_for_openai:
                _update_combined_status(task_id, 'docs', 'running', f"Enviando {len(file_paths_for_openai)} archivo(s) a OpenAI...")
                try:
                    processor = OpenAIProcessor()
                    extracted_data = processor.process_multiple_sources(file_paths_for_openai)
                    if not extracted_data or not isinstance(extracted_data, dict):
                        raise ValueError("OpenAI no devolvió datos válidos o el formato es incorrecto.")
                    if 'error' in extracted_data:
                        raise ValueError(f"Error reportado por OpenAI: {extracted_data['error']}")

                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(extracted_data, f, ensure_ascii=False, indent=2)
                    processed_config_path = output_path
                    logger.info(f"[BG Task] Task {task_id}: OpenAI processed files, config saved to {processed_config_path}")
                    _update_combined_status(task_id, 'docs', 'running', 'Archivos procesados por OpenAI.')
                except Exception as e:
                    error_message = f"Error durante el procesamiento con OpenAI: {e}"
                    logger.error(f"[BG Task] Task {task_id}: {error_message}", exc_info=True)
                    _update_combined_status(task_id, 'docs', 'error', "Error en comunicación con OpenAI", error_details=str(e))
            else:
                # This case should not happen if other_files is not empty, but handle defensively
                error_message = "No se encontraron archivos válidos para enviar a OpenAI (caso inesperado)."
                _update_combined_status(task_id, 'docs', 'error', error_message, error_details=error_message)
        else:
             # No valid files were provided initially (handled in the route, but double-check)
             if saved_files_data: # If list wasn't empty, means files were invalid type
                 error_message = "No se proporcionaron archivos de tipo procesable (JSON, PDF, Imagen, Texto)."
                 _update_combined_status(task_id, 'docs', 'error', error_message, error_details=error_message)
             # If saved_files_data was empty, the initial check in this function already handled it.

        # --- Final status update for docs section --- 
        if not error_message and processed_config_path:
            _update_combined_status(task_id, 'docs', 'completed', 'Procesamiento de documentos completado.', result_path=processed_config_path)
        elif not error_message:
             # No processing error, but no output path generated (e.g. no files passed OpenAI check)
             # or only JSON was processed but failed.
             _update_combined_status(task_id, 'docs', 'error', error_message or 'No se generó configuración final de documentos.')

    except Exception as e:
        error_message = f"Error crítico durante el procesamiento de documentos: {str(e)}"
        logger.error(f"[BG Task] Task {task_id}: {error_message}", exc_info=True)
        _update_combined_status(task_id, 'docs', 'error', "Error crítico durante el procesamiento", error_details=str(e))

    finally:
        # Always trigger comparison check after Docs part finishes or fails
        logger.info(f"[BG Task] Task {task_id}: Docs thread finished. Triggering comparison check.")
        # Pass the upload_folder_path determined earlier for potential cleanup
        _check_and_trigger_comparison(task_id, upload_folder_path_for_cleanup)

# --- Cleanup Function ---

def _check_and_cleanup_task(task_id, upload_folder_path):
    """Checks the final status of a task and cleans up temp files if completed or failed."""
    should_cleanup = False
    overall_status = None
    task_exists = False
    cleanup_flag_set = False

    with combined_status_lock:
        if task_id in combined_revision_status:
            task_exists = True
            status = combined_revision_status[task_id]
            overall_status = status.get('status')
            cleanup_flag_set = status.get('_cleanup_started', False)
            if overall_status in ['completed', 'error'] and not cleanup_flag_set:
                 status['_cleanup_started'] = True # Mark cleanup as initiated within lock
                 should_cleanup = True
        else:
            # Task already cleaned up or not found
            logger.warning(f"[BG Task] Task {task_id}: Cleanup check called, but task not found in status dict.")
            return

    if should_cleanup:
        logger.info(f"[BG Task] Task {task_id}: Final status is '{overall_status}'. Cleaning up temporary files.")
        # Construct the temp_dir path using the passed upload_folder_path
        # Note: This path is specific to the *task*, usually upload_folder/task_id
        temp_dir = upload_folder_path # Assumes upload_folder_path is the specific task dir
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"[BG Task] Task {task_id}: Removed temporary directory {temp_dir}")
            except Exception as e:
                logger.error(f"[BG Task] Task {task_id}: Error removing temporary directory {temp_dir}: {e}")
        elif temp_dir:
             logger.warning(f"[BG Task] Task {task_id}: Cleanup requested, but temporary directory not found: {temp_dir}")
        else:
            logger.error(f"[BG Task] Task {task_id}: Cleanup requested, but upload_folder_path was None or empty.")

        # Schedule removal of the status entry from memory after a delay
        def remove_status_entry(tid):
            with combined_status_lock:
                if tid in combined_revision_status:
                    # Double check status and cleanup flag before removing
                    final_status = combined_revision_status[tid].get('status')
                    is_cleaned = combined_revision_status[tid].get('_cleanup_started', False)
                    if final_status in ['completed', 'error'] and is_cleaned:
                       popped_item = combined_revision_status.pop(tid, None)
                       if popped_item:
                           logger.info(f"[BG Task] Task {tid}: Removed status entry from memory after delay.")
                       # else: Already removed by another thread/timer?
                    # else: Status might have changed again, or cleanup wasn't fully marked? Don't remove yet.

        removal_delay_seconds = 600.0 # 10 minutes
        logger.info(f"[BG Task] Task {task_id}: Scheduling status entry removal in {removal_delay_seconds} seconds.")
        removal_timer = threading.Timer(removal_delay_seconds, remove_status_entry, args=(task_id,))
        removal_timer.daemon = True # Allow app to exit even if timer is pending
        removal_timer.start()
    elif task_exists and not cleanup_flag_set:
        # Log if cleanup wasn't triggered (e.g., task still running)
        logger.debug(f"[BG Task] Task {task_id}: Cleanup check called, but conditions not met (Status: {overall_status}, Cleanup Started: {cleanup_flag_set}).")
    elif task_exists and cleanup_flag_set:
         logger.debug(f"[BG Task] Task {task_id}: Cleanup check called, but cleanup already started.") 