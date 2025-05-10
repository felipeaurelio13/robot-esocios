import os
import logging

from flask import (
    Blueprint,
    redirect,
    url_for,
    flash,
    current_app,
)
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Define the blueprint
delete_bp = Blueprint('delete', __name__)

# === Delete Route ===

@delete_bp.route('/eliminar-revision/<filename>', methods=['POST'])
def eliminar_revision(filename):
    """Handles the deletion of a report file."""
    if '..' in filename or filename.startswith('/'):
        flash('Nombre de archivo inválido.', 'danger')
        return redirect(url_for('main.dashboard')) # Redirect to main blueprint dashboard

    # Use current_app.config
    report_path = os.path.join(current_app.config['REPORTS_DIR'], secure_filename(filename))

    if not os.path.exists(report_path):
        flash(f'El informe "{filename}" no existe o ya fue eliminado.', 'warning')
    else:
        try:
            logger.info(f"[Delete] Attempting to delete report: {report_path}")
            os.remove(report_path)
            flash(f'Informe "{filename}" eliminado exitosamente.', 'success')
            logger.info(f"[Delete] Report deleted: {report_path}")
            # Note: Associated temp files (in uploads/<task_id>) are cleaned up
            # by the background task's _check_and_cleanup_task function based on status,
            # not directly linked to report deletion here.
        except OSError as e:
            flash(f'Error al eliminar el informe "{filename}": {e}', 'danger')
            logger.error(f"[Delete] Error deleting report {report_path}: {e}")
        except Exception as e:
             flash(f'Error inesperado al eliminar el informe "{filename}": {str(e)}', 'danger')
             logger.error(f"[Delete] Unexpected error deleting report {report_path}: {e}")

    return redirect(url_for('main.dashboard')) # Redirect back to main dashboard 