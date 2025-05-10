# -*- coding: utf-8 -*-
"""
Blueprint for handling file downloads, e.g., PDF reports.
"""
import os
import json
import glob # Import glob for file searching
from flask import (
    Blueprint,
    render_template,
    Response,
    request,
    current_app,
    abort,
    url_for # Added url_for for potential future use or linking within PDF
)
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from datetime import datetime
from src.globals import combined_revision_status, combined_status_lock # Import shared status

# Create the Blueprint
download_bp = Blueprint('download', __name__)


def load_report_data(task_id):
    """Helper function to load the final comparison report JSON."""
    # Ensure REPORTS_DIR is accessed via current_app.config
    reports_dir = current_app.config.get('REPORTS_DIR')
    if not reports_dir:
        current_app.logger.error("REPORTS_DIR not configured in Flask app.")
        return None
        
    # Get task status to find the slug
    slug = None
    with combined_status_lock: # Access shared status safely
        task_status = combined_revision_status.get(task_id)
        if not task_status or 'slug' not in task_status:
            current_app.logger.warning(f"Estado o slug no encontrado en memoria para task_id: {task_id}. Intentando buscar archivo...")
            # Fallback: Search for the report file by pattern
            file_pattern = os.path.join(reports_dir, f"report_*_{task_id}.json")
            matching_files = glob.glob(file_pattern)
            if len(matching_files) == 1:
                report_path = matching_files[0]
                filename = os.path.basename(report_path)
                # Extract slug: report_{slug}_{task_id}.json
                parts = filename[:-5].split('_') # Remove .json and split
                if len(parts) == 3 and parts[0] == 'report' and parts[2] == task_id:
                    slug = parts[1]
                    current_app.logger.info(f"Slug '{slug}' extraído del nombre de archivo: {filename}")
                else:
                     current_app.logger.error(f"No se pudo extraer el slug del nombre de archivo con formato inesperado: {filename}")
                     return None
            elif len(matching_files) > 1:
                 current_app.logger.error(f"Múltiples archivos de reporte encontrados para task_id {task_id}: {matching_files}")
                 return None
            else:
                current_app.logger.error(f"No se encontró el archivo de reporte para task_id: {task_id} usando el patrón {file_pattern}")
                return None # Cannot determine filename without slug or file
        else:
            # Slug found in status dictionary
            slug = task_status.get('slug')
            current_app.logger.info(f"Slug '{slug}' encontrado en el estado en memoria para task_id: {task_id}")
    
    # Construct the correct report filename using slug and task_id
    report_filename = f"report_{slug}_{task_id}.json"
    report_path = os.path.join(reports_dir, report_filename)
    
    if not os.path.exists(report_path):
        current_app.logger.warning(f"Report file not found: {report_path}")
        return None
        
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        # Add task_id and generation time if not present (useful for template)
        if 'task_id' not in report_data:
            report_data['task_id'] = task_id
        if 'generation_time' not in report_data:
             report_data['generation_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return report_data
    except json.JSONDecodeError as e:
        current_app.logger.error(f"Error decoding JSON report {report_path}: {e}")
        return None
    except Exception as e:
        current_app.logger.error(f"Error loading report {report_path}: {e}", exc_info=True)
        return None


@download_bp.route('/download-report/<string:task_id>/pdf')
def download_report_pdf(task_id):
    """Generates and serves the comparison report as a PDF."""
    current_app.logger.info(f"Solicitud de descarga PDF para task_id: {task_id}")
    report_data = load_report_data(task_id)
    if report_data is None:
        current_app.logger.error(f"No se pudieron cargar los datos del reporte para task_id: {task_id}")
        abort(404, description="Reporte no encontrado o inválido.")

    try:
        # Renderizar la plantilla HTML específica para el PDF
        # Asegúrate que pdf_report_template.html esté en tu carpeta templates
        html_string = render_template('pdf_report_template.html', report=report_data)
        
        # Cargar el CSS para el PDF
        # Asegúrate que pdf_report_style.css esté en tu carpeta static/css
        css_path = os.path.join(current_app.static_folder, 'css', 'pdf_report_style.css')
        if not os.path.exists(css_path):
             current_app.logger.error(f"Archivo CSS para PDF no encontrado en: {css_path}")
             # Podrías generar el PDF sin CSS o abortar
             # Abortaremos por ahora para indicar el problema claramente
             abort(500, description="Archivo de estilo para PDF no encontrado.")

        # Configuración de fuentes (WeasyPrint buscará fuentes del sistema si no se especifica)
        font_config = FontConfiguration()
        
        # Crear el objeto HTML de WeasyPrint
        # base_url ayuda a WeasyPrint a resolver rutas relativas (como la del CSS en el HTML)
        html = HTML(string=html_string, base_url=request.host_url)
        
        # Cargar el CSS
        css = CSS(filename=css_path, font_config=font_config)
        
        # Generar el PDF en memoria
        current_app.logger.info(f"Generando PDF con WeasyPrint para task_id: {task_id}...")
        pdf_bytes = html.write_pdf(stylesheets=[css], font_config=font_config)
        current_app.logger.info(f"PDF generado correctamente para task_id: {task_id}. Tamaño: {len(pdf_bytes)} bytes.")
        
        # Crear la respuesta para descarga
        pdf_filename = f"reporte_comparativo_{task_id}.pdf"
        response = Response(pdf_bytes, mimetype='application/pdf')
        # Usar "attachment" para forzar la descarga
        response.headers['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
        
        return response

    except Exception as e:
        current_app.logger.error(f"Error crítico generando PDF para task_id: {task_id}: {e}", exc_info=True)
        abort(500, description="Error interno al generar el PDF del reporte.") 