import logging
from flask import Blueprint, redirect, url_for, flash, jsonify

logger = logging.getLogger(__name__)

# Define the blueprint
obsolete_bp = Blueprint('obsolete', __name__)

# === Obsolete/Deprecated Routes ===

# Note: These routes are kept primarily to avoid breaking old bookmarks/links
# or integrations. They log a warning and redirect/return an error.

@obsolete_bp.route('/revision-progreso/<slug>')
def revision_progreso(slug):
    logger.warning("Accessed obsolete route /revision-progreso/<slug>")
    flash("Esta página de progreso ya no está en uso. Utilice el dashboard.", "warning")
    return redirect(url_for('main.dashboard')) # Redirect to main blueprint

@obsolete_bp.route('/estado-revision/<slug>')
def estado_revision(slug):
    logger.warning("Accessed obsolete route /estado-revision/<slug>")
    return jsonify({'status': 'obsolete', 'message': 'Use /combined-status/<task_id>'}), 404

@obsolete_bp.route('/procesar-documentos', methods=['GET', 'POST'])
def procesar_documentos():
    logger.warning("Accessed obsolete route /procesar-documentos")
    flash("Esta función ha sido integrada en 'Nueva Revisión'.", "info")
    # Redirect to the new revision form in the main blueprint
    return redirect(url_for('main.nueva_revision'))

@obsolete_bp.route('/estado-procesamiento/<task_id>')
def estado_procesamiento(task_id):
    logger.warning("Accessed obsolete route /estado-procesamiento/<task_id>")
    return jsonify({'status': 'obsolete', 'message': 'Use /combined-status/<task_id>'}), 404

@obsolete_bp.route('/procesamiento-progreso/<task_id>')
def procesamiento_progreso(task_id):
    logger.warning("Accessed obsolete route /procesamiento-progreso/<task_id>")
    flash("Esta página de progreso ya no está en uso.", "warning")
    return redirect(url_for('main.dashboard')) # Redirect to main blueprint

@obsolete_bp.route('/ver-configuracion/<filename>')
def ver_configuracion(filename):
    logger.warning("Accessed potentially obsolete route /ver-configuracion")
    flash("Las configuraciones intermedias ya no se visualizan directamente.", "info")
    return redirect(url_for('main.dashboard'))

@obsolete_bp.route('/descargar-configuracion/<filename>')
def descargar_configuracion(filename):
    logger.warning("Accessed potentially obsolete route /descargar-configuracion")
    flash("Las configuraciones intermedias ya no se descargan directamente.", "info")
    return redirect(url_for('main.dashboard'))

@obsolete_bp.route('/plantillas')
def plantillas():
    logger.warning("Accessed obsolete route /plantillas")
    flash("La gestión de plantillas JSON ya no está activa.", "info")
    return redirect(url_for('main.dashboard'))

@obsolete_bp.route('/guardar-como-plantilla', methods=['POST'])
def guardar_como_plantilla():
    logger.warning("Accessed obsolete route /guardar-como-plantilla")
    flash("La gestión de plantillas JSON ya no está activa.", "info")
    return redirect(url_for('main.dashboard'))

@obsolete_bp.route('/comparar-informe/<filename>', methods=['POST'])
def comparar_informe_vs_documentos(filename):
    logger.warning("Accessed obsolete route /comparar-informe")
    flash("La comparación manual ya no es necesaria; se realiza automáticamente.", "info")
    # Redirect to the main report view page
    return redirect(url_for('main.ver_informe', filename=filename)) 