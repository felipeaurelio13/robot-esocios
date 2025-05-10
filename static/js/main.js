// Funcionalidad para el arrastrar y soltar archivos
document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('drop-zone');
    
    if (dropZone) {
        // Prevenir comportamiento por defecto para permitir soltar archivos
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        // Resaltar la zona de soltar cuando se arrastra un archivo sobre ella
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, unhighlight, false);
        });

        function highlight() {
            dropZone.classList.add('highlight');
        }

        function unhighlight() {
            dropZone.classList.remove('highlight');
        }

        // Manejar los archivos soltados
        dropZone.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            handleFiles(files);
        }

        function handleFiles(files) {
            const fileInput = document.getElementById('file-input');
            const submitButton = document.getElementById('submit-procesar');
            const errorDiv = document.getElementById('file-validation-error');
            
            if (fileInput) {
                fileInput.files = files;
                // Mostrar los nombres de los archivos seleccionados
                updateFileList(files);
                
                // --- Validación de Archivos --- 
                let jsonCount = 0;
                let otherCount = 0;
                for (let i = 0; i < files.length; i++) {
                    if (files[i].name.toLowerCase().endsWith('.json')) {
                        jsonCount++;
                    } else {
                        otherCount++;
                    }
                }
                
                let errorMessage = '';
                let disableSubmit = false;
                
                if (jsonCount > 0 && otherCount > 0) {
                    errorMessage = 'Error: No se puede mezclar un archivo JSON con otros tipos de archivo.';
                    disableSubmit = true;
                } else if (jsonCount > 1) {
                    errorMessage = 'Error: Solo se puede procesar un archivo JSON a la vez.';
                    disableSubmit = true;
                } else if (files.length === 0) {
                    // No disable submit if no files are selected (user might select later)
                    errorMessage = ''; 
                    disableSubmit = false; 
                } else {
                    errorMessage = ''; // No error
                    disableSubmit = false;
                }
                
                if (errorDiv) {
                    errorDiv.textContent = errorMessage;
                }
                if (submitButton) {
                    submitButton.disabled = disableSubmit;
                }
                // --- Fin Validación --- 
            }
        }

        // Actualizar la lista de archivos seleccionados
        function updateFileList(files) {
            const fileList = document.getElementById('file-list');
            if (fileList) {
                fileList.innerHTML = '';
                for (let i = 0; i < files.length; i++) {
                    const file = files[i];
                    const item = document.createElement('div');
                    item.className = 'file-item';
                    item.innerHTML = `
                        <i class="bi bi-file-earmark"></i>
                        <span>${file.name}</span>
                        <small>(${formatFileSize(file.size)})</small>
                    `;
                    fileList.appendChild(item);
                }
            }
        }

        // Formatear el tamaño del archivo
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        // Manejar la selección de archivos a través del botón
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.addEventListener('change', function() {
                updateFileList(this.files);
            });
        }
    }

    // Mostrar spinner de carga al enviar formularios
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const spinner = document.querySelector('.loading-spinner');
            if (spinner) {
                spinner.style.display = 'block';
            }
        });
    });

    // Inicializar gráficos si existen elementos canvas
    initCharts();

    // Función para animar la aparición de la validación de opciones
    const validationCard = document.querySelector('.validation-options-card');
    
    if (validationCard) {
        // Aplicar animación de entrada
        setTimeout(() => {
            validationCard.style.transition = 'all 0.3s ease';
            
            // Aplicar animación secuencial a los items de validación
            const validationItems = validationCard.querySelectorAll('.list-group-item');
            validationItems.forEach((item, index) => {
                setTimeout(() => {
                    item.classList.add('validation-highlight');
                }, index * 200); // Retraso secuencial para cada item
            });
        }, 300);
        
        // Permitir hacer clic en los elementos para resaltar
        const validationItems = validationCard.querySelectorAll('.list-group-item');
        validationItems.forEach(item => {
            item.addEventListener('click', function() {
                // Remover clase de todos los items
                validationItems.forEach(i => i.classList.remove('validation-highlight'));
                // Añadir clase solo al elemento clickeado
                this.classList.add('validation-highlight');
            });
        });
    }

    // Setup polling if on the progress page
    setupCombinedProgressPolling(); 
});

// Inicializar gráficos con Chart.js
function initCharts() {
    // Gráfico de estado de revisiones
    const revisionStatusChart = document.getElementById('revision-status-chart');
    if (revisionStatusChart) {
        const matchCount = parseInt(revisionStatusChart.getAttribute('data-match-count') || 0);
        const mismatchCount = parseInt(revisionStatusChart.getAttribute('data-mismatch-count') || 0);
        
        new Chart(revisionStatusChart, {
            type: 'doughnut',
            data: {
                labels: ['Coincide', 'No Coincide'],
                datasets: [{
                    data: [matchCount, mismatchCount],
                    backgroundColor: ['#198754', '#dc3545'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    // Gráfico de diferencias por sección
    const differencesBySectionChart = document.getElementById('differences-by-section-chart');
    if (differencesBySectionChart) {
        const sections = JSON.parse(differencesBySectionChart.getAttribute('data-sections') || '[]');
        const counts = JSON.parse(differencesBySectionChart.getAttribute('data-counts') || '[]');
        
        new Chart(differencesBySectionChart, {
            type: 'bar',
            data: {
                labels: sections,
                datasets: [{
                    label: 'Diferencias',
                    data: counts,
                    backgroundColor: '#0d6efd',
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
    }
}

// Función para mostrar/ocultar detalles de diferencias
function toggleDifferences(id) {
    const element = document.getElementById(id);
    if (element) {
        if (element.style.display === 'none') {
            element.style.display = 'block';
        } else {
            element.style.display = 'none';
        }
    }
}

// Función para copiar JSON al portapapeles
function copyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    
    // Mostrar mensaje de éxito
    const toast = document.createElement('div');
    toast.className = 'position-fixed bottom-0 end-0 p-3';
    toast.style.zIndex = '5';
    toast.innerHTML = `
        <div class="toast show" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <strong class="me-auto">Revisor de Juntas</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                JSON copiado al portapapeles
            </div>
        </div>
    `;
    document.body.appendChild(toast);
    
    // Eliminar el toast después de 3 segundos
    setTimeout(() => {
        document.body.removeChild(toast);
    }, 3000);
}

// --- Combined Revision Progress Polling --- 
function setupCombinedProgressPolling() {
    const taskIdElement = document.getElementById('task-id');
    if (!taskIdElement) return; // Only run on progress page

    const taskId = taskIdElement.textContent;
    const overallStatusEl = document.getElementById('overall-status');
    const seleniumStatusEl = document.getElementById('selenium-status');
    const seleniumMessageEl = document.getElementById('selenium-message');
    const docsStatusEl = document.getElementById('docs-status');
    const docsMessageEl = document.getElementById('docs-message');
    const comparisonStatusEl = document.getElementById('comparison-status');
    const comparisonMessageEl = document.getElementById('comparison-message');
    const errorAlertEl = document.getElementById('error-alert');
    const errorDetailsEl = document.getElementById('error-details');
    const successAlertEl = document.getElementById('success-alert');
    const reportLinkEl = document.getElementById('report-link');
    const progressSectionsEl = document.getElementById('progress-sections');

    let intervalId = null;
    // Construct the base URL using a data attribute or global var if needed, otherwise hardcode
    // Assuming url_for generated the correct path in the template previously
    const statusUrlBase = '/combined-status/'; // Adjust if your routing is different

    const statusIcons = {
        pending: 'bi-hourglass-split text-muted',
        running: 'spinner-border spinner-border-sm text-primary',
        progress: 'spinner-border spinner-border-sm text-primary',
        completed: 'bi-check-circle-fill text-success',
        error: 'bi-x-octagon-fill text-danger',
        warning: 'bi-exclamation-triangle-fill text-warning'
    };

    function updateStatusElement(element, status, defaultIcon = 'bi-question-circle') {
        if (!element) return; // Guard against missing elements
        const iconClass = statusIcons[status] || defaultIcon;
        let iconHtml = '';
        const statusText = status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown';
        
        if (iconClass.includes('spinner-border')) {
            iconHtml = `<span class="${iconClass} me-2" role="status" aria-hidden="true"></span>`;
        } else {
            iconHtml = `<i class="bi ${iconClass} me-2"></i>`;
        }
        element.innerHTML = `${iconHtml}<span class="status-text">${statusText}</span>`;
    }

    function fetchStatus() {
        const url = `${statusUrlBase}${taskId}?nocache=${Date.now()}`;

        fetch(url)
            .then(response => {
                if (!response.ok) {
                    if (response.status === 404) {
                        throw new Error(`Tarea no encontrada (ID: ${taskId}). Puede que haya sido eliminada o expirado.`);
                    }
                    throw new Error(`Error HTTP! Estado: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("Status data received:", data);
                
                // Ensure elements exist before updating
                if (!overallStatusEl || !progressSectionsEl || !errorAlertEl || !successAlertEl) {
                    console.error("Core status elements missing from page. Stopping poll.");
                    if(intervalId) clearInterval(intervalId);
                    intervalId = null;
                    return;
                }

                // --- Update Progress Sections --- 
                if (data.status !== 'completed' && data.status !== 'error' && data.status !== 'not_found') {
                    updateStatusElement(overallStatusEl, data.status || 'unknown');
                    
                    // Update specific sections if they exist
                    if (data.selenium) {
                        updateStatusElement(seleniumStatusEl, data.selenium.status || 'unknown');
                        if(seleniumMessageEl) seleniumMessageEl.textContent = data.selenium.message || 'N/A';
                        seleniumStatusEl?.closest('.card')?.classList.toggle('border-danger', data.selenium.status === 'error');
                        seleniumStatusEl?.closest('.card')?.classList.toggle('border-warning', data.selenium.status === 'warning');
                    }
                    if (data.docs) {
                        updateStatusElement(docsStatusEl, data.docs.status || 'unknown');
                        if(docsMessageEl) docsMessageEl.textContent = data.docs.message || 'N/A';
                        docsStatusEl?.closest('.card')?.classList.toggle('border-danger', data.docs.status === 'error');
                        docsStatusEl?.closest('.card')?.classList.toggle('border-warning', data.docs.status === 'warning');
                    }
                    if (data.comparison) {
                        updateStatusElement(comparisonStatusEl, data.comparison.status || 'unknown');
                        if(comparisonMessageEl) comparisonMessageEl.textContent = data.comparison.message || 'N/A';
                        comparisonStatusEl?.closest('.card')?.classList.toggle('border-danger', data.comparison.status === 'error');
                        comparisonStatusEl?.closest('.card')?.classList.toggle('border-warning', data.comparison.status === 'warning');
                    }
                }
                // --- Handle Final States --- 
                else if (data.status === 'completed') {
                    console.log("Task completed. Stopping polling.");
                    if (intervalId) clearInterval(intervalId);
                    intervalId = null; 
                    progressSectionsEl.classList.add('d-none'); 
                    errorAlertEl.classList.add('d-none');
                    successAlertEl.classList.remove('d-none');
                    if (data.report_url) {
                        if(reportLinkEl) {
                           reportLinkEl.href = data.report_url;
                           reportLinkEl.classList.remove('disabled');
                           reportLinkEl.textContent = 'Ver Informe Final';
                           // *** ADD REDIRECT HERE ***
                           console.log("Redirecting to report URL:", data.report_url);
                           window.location.href = data.report_url; 
                        }
                    } else {
                        if(reportLinkEl) {
                           reportLinkEl.textContent = 'Informe no disponible';
                           reportLinkEl.classList.add('disabled');
                        }
                        console.warn("Task completed but no report URL found.");
                    }
                } else if (data.status === 'error') {
                    console.log("Task failed. Stopping polling.");
                    if (intervalId) clearInterval(intervalId);
                    intervalId = null;
                    progressSectionsEl.classList.add('d-none');
                    successAlertEl.classList.add('d-none');
                    errorAlertEl.classList.remove('d-none'); 
                    if(errorDetailsEl) errorDetailsEl.textContent = data.error || 'Se produjo un error desconocido.';
                } else if (data.status === 'not_found') {
                    console.log("Task not found during polling. Stopping polling.");
                    if (intervalId) clearInterval(intervalId);
                    intervalId = null;
                    progressSectionsEl.classList.add('d-none');
                    successAlertEl.classList.add('d-none');
                    errorAlertEl.classList.remove('d-none');
                    if(errorDetailsEl) errorDetailsEl.textContent = data.message || `La tarea con ID ${taskId} ya no está disponible. Puede haber expirado.`;
                }

            })
            .catch(error => {
                console.error('Error fetching status:', error);
                if (intervalId) clearInterval(intervalId); 
                intervalId = null;
                // Ensure elements exist before showing error
                 if (overallStatusEl) overallStatusEl.innerHTML = `<i class="bi bi-wifi-off me-2 text-danger"></i> Error de conexión`;
                 if (progressSectionsEl) progressSectionsEl.classList.add('d-none');
                 if (successAlertEl) successAlertEl.classList.add('d-none');
                 if (errorAlertEl) errorAlertEl.classList.remove('d-none');
                 if (errorDetailsEl) errorDetailsEl.textContent = `Error al obtener estado: ${error.message}. Intenta refrescar la página o revisa la conexión.`;
            });
    }

    // Start polling logic
    function startPollingIfNeeded() {
        const url = `${statusUrlBase}${taskId}?nocache=${Date.now()}`;
        fetch(url)
            .then(res => res.ok ? res.json() : Promise.reject(new Error(res.statusText)))
            .then(initialData => {
                if (initialData && initialData.status !== 'completed' && initialData.status !== 'error' && initialData.status !== 'not_found') {
                    if (!intervalId) {
                        console.log("Starting polling interval.");
                        fetchStatus(); // Fetch immediately
                        intervalId = setInterval(fetchStatus, 3000);
                    }
                } else {
                    console.log("Initial status is final, ensuring UI reflects this.");
                    fetchStatus(); // Call once to update UI to final state
                }
            })
            .catch(error => {
                console.error('Error during initial status check:', error);
                 if (errorAlertEl) errorAlertEl.classList.remove('d-none');
                 if (errorDetailsEl) errorDetailsEl.textContent = `Error al verificar estado inicial: ${error.message}`;
                 if (progressSectionsEl) progressSectionsEl.classList.add('d-none');
            });
    }

    startPollingIfNeeded();

    // Optional: Pause polling when tab is hidden
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            if (intervalId) {
                console.log("Page hidden, pausing polling.");
                clearInterval(intervalId);
                intervalId = null;
            }
        } else {
            console.log("Page visible, restarting polling if needed.");
            startPollingIfNeeded(); // Will only restart if status is not final
        }
    });
}
