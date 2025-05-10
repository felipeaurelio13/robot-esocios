// static/js/comparison-grid.js
document.addEventListener('DOMContentLoaded', function () {
    console.log('[CompareGrid] >>> DOMContentLoaded: Iniciando script.');

    const jsonDataElement = document.getElementById('question-data');
    const gridContainer = document.getElementById('question-comparison-container');
    const addExpectedBtn = document.getElementById('add-blank-expected-btn');
    const addActualBtn = document.getElementById('add-blank-actual-btn');
    const compareBtn = document.getElementById('compare-rows-btn');

    if (!gridContainer) {
        console.error('[CompareGrid] >>> ERROR CRÍTICO: No se encontró #question-comparison-container. Abortando.');
        return;
    }
    if (!addExpectedBtn || !addActualBtn || !compareBtn) {
        console.warn('[CompareGrid] >>> WARN: No se encontraron los botones de control del grid.');
        // Permitir que continúe, quizás los botones no son esenciales para la funcionalidad básica
    }

    // Cambiar a un único array de objetos para almacenar todos los datos de cada fila
    let comparisonData = [];
    const BLANK_SPACE_MARKER = "[ESPACIO INSERTADO]";

    // --- Carga y Procesamiento de Datos JSON --- 
    if (!jsonDataElement) {
        console.warn('[CompareGrid] >>> WARN: No se encontró #question-data.');
    } else {
        const rawJson = jsonDataElement.textContent;
        if (rawJson) {
            try {
                const originalData = JSON.parse(rawJson);
                if (Array.isArray(originalData)) {
                    // Poblar comparisonData con objetos
                    comparisonData = originalData.map(item => ({
                        expected: item.expected !== null && item.expected !== undefined ? String(item.expected) : '',
                        actual: item.actual !== null && item.actual !== undefined ? String(item.actual) : '',
                        // Almacenar diff_type, default a 'major' si no existe por alguna razón
                        diff_type: item.diff_type || 'major', 
                        // Guardar el diff_html si existe para posible uso futuro (opcional)
                        diff_html: item.diff_html || null 
                    }));
                    console.log(`[CompareGrid] INFO: Datos cargados: ${comparisonData.length} items.`);
                } else { console.error('[CompareGrid] ERROR: JSON no es array.'); }
            } catch (e) { console.error('[CompareGrid] ERROR CRÍTICO: Fallo al parsear JSON:', e); }
        } else { console.warn("[CompareGrid] WARN: #question-data vacío."); }
    }

    // --- Función para Crear una Celda del Grid --- 
    function createCell(content, row, col, isBlankSpace = false, isNumber = false, itemIndex = -1) {
        const cell = document.createElement('div');
        cell.classList.add('comparison-cell');
        cell.style.gridRow = row;
        cell.style.gridColumn = col;
        // Usar itemIndex (índice en comparisonData) como data-row
        cell.setAttribute('data-row', itemIndex); 
        cell.setAttribute('data-col', col);

        const textContentDiv = document.createElement('div');
        textContentDiv.classList.add('cell-content');
        textContentDiv.setAttribute('data-original-text', content);

        if (isBlankSpace) {
            cell.classList.add('blank-space-cell');
            textContentDiv.textContent = content;
            cell.appendChild(textContentDiv);

            const actionsDiv = document.createElement('div');
            actionsDiv.classList.add('cell-actions');
            const moveUpBtn = document.createElement('button');
            moveUpBtn.classList.add('btn', 'btn-sm', 'btn-outline-secondary');
            moveUpBtn.innerHTML = '▲';
            moveUpBtn.title = 'Mover espacio hacia arriba';
            // Actualizar para trabajar con comparisonData
            moveUpBtn.addEventListener('click', () => moveItem(itemIndex, col === 2 ? 'expected' : 'actual', 'up')); 
            const moveDownBtn = document.createElement('button');
            moveDownBtn.classList.add('btn', 'btn-sm', 'btn-outline-secondary');
            moveDownBtn.innerHTML = '▼';
            moveDownBtn.title = 'Mover espacio hacia abajo';
            moveDownBtn.addEventListener('click', () => moveItem(itemIndex, col === 2 ? 'expected' : 'actual', 'down'));
            const deleteBtn = document.createElement('button');
            deleteBtn.classList.add('btn', 'btn-sm', 'btn-outline-danger');
            deleteBtn.innerHTML = '🗑️';
            deleteBtn.title = 'Eliminar espacio';
            deleteBtn.addEventListener('click', () => deleteItem(itemIndex, col === 2 ? 'expected' : 'actual'));
            actionsDiv.appendChild(moveUpBtn);
            actionsDiv.appendChild(moveDownBtn);
            actionsDiv.appendChild(deleteBtn);
            cell.appendChild(actionsDiv);
        } else if (isNumber) {
            textContentDiv.textContent = content;
            cell.appendChild(textContentDiv);
        } else { // Celdas de texto editable
            textContentDiv.setAttribute('contenteditable', 'true');
            textContentDiv.textContent = content;
            cell.appendChild(textContentDiv);
            textContentDiv.addEventListener('blur', (e) => {
                const newText = e.target.textContent;
                // Usar itemIndex almacenado en data-row
                const r = parseInt(cell.getAttribute('data-row'), 10); 
                const originalContent = cell.querySelector('.cell-content').getAttribute('data-original-text');
                
                // Actualizar el objeto en comparisonData
                if (r >= 0 && r < comparisonData.length) {
                    const fieldToUpdate = col === 2 ? 'expected' : 'actual';
                    if (comparisonData[r][fieldToUpdate] !== newText) {
                       comparisonData[r][fieldToUpdate] = newText;
                       // Si se edita, invalidamos el diff_type precalculado
                       comparisonData[r].diff_type = 'edited'; // Marcar como editado para recalcular diff si es necesario
                       cell.querySelector('.cell-content').innerHTML = newText;
                       cell.querySelector('.cell-content').setAttribute('data-original-text', newText);
                       // Limpiar resaltados porque el texto cambió
                       clearAllHighlights(); 
                    }
                } else {
                     console.warn(`[CompareGrid] Blur en celda con data-row inválido: ${r}`);
                }
            });
        }
        return cell;
    }

    // --- Función Principal de Redibujado del Grid --- 
    function redrawGrid() {
        console.log('[CompareGrid] >>> INFO: Llamando a redrawGrid().');
        const existingCells = gridContainer.querySelectorAll('.comparison-cell');
        existingCells.forEach(cell => cell.remove());
        // Usar la longitud de comparisonData
        const numRows = comparisonData.length; 
        console.log(`[CompareGrid] Renderizando ${numRows} filas de datos.`);
        
        for (let i = 0; i < numRows; i++) {
            const item = comparisonData[i];
            const gridRowIndex = i + 2; // El índice del grid sigue siendo i + 2
            
            // Pasar el índice 'i' del array comparisonData a createCell
            const numberCell = createCell(i + 1, gridRowIndex, 1, false, true, i); 
            gridContainer.appendChild(numberCell);

            const expectedText = item.expected;
            const isExpectedBlank = expectedText === BLANK_SPACE_MARKER;
            const expectedCell = createCell(expectedText, gridRowIndex, 2, isExpectedBlank, false, i);
            gridContainer.appendChild(expectedCell);

            const actualText = item.actual;
            const isActualBlank = actualText === BLANK_SPACE_MARKER;
            const actualCell = createCell(actualText, gridRowIndex, 3, isActualBlank, false, i);
            gridContainer.appendChild(actualCell);
        }
        console.log('[CompareGrid] >>> INFO: Redibujado de grid completado.');
    }

    // --- Limpiar TODOS los Resaltados --- 
    function clearAllHighlights() {
        const allNumCells = gridContainer.querySelectorAll(`.comparison-cell[data-col="1"][data-row]`);
        allNumCells.forEach(cell => {
            // Eliminar clases de comparación anteriores Y la nueva
            cell.classList.remove('match-success', 'match-fail', 'match-subtle-diff'); 
            const indicator = cell.querySelector('.match-indicator');
            if (indicator) indicator.remove();
        });
        const allTextCells = gridContainer.querySelectorAll(`.comparison-cell[data-col="2"][data-row] .cell-content, .comparison-cell[data-col="3"][data-row] .cell-content`);
        allTextCells.forEach(contentDiv => {
            // Restaurar texto original SIN resaltados de palabras
            const originalText = contentDiv.getAttribute('data-original-text'); 
            contentDiv.innerHTML = originalText; 
        });
        console.log('[CompareGrid] >>> Todos los resaltados limpiados.');
    }

    // --- Funciones Auxiliares para Diff de Palabras --- 
    function normalizeTextForDiff(text) {
        if (typeof text !== 'string') return '';
        // Quitar puntuación común, números al inicio (ej. "1.") y espacios extra.
        // ¡Asegurarse que esta lógica sea SIMILAR a la de Python!
        text = text.toLowerCase();
        // Quitar prefijos como "1.", "a)" etc.
        text = text.replace(/^\s*[a-z0-9][\.\)]\s*/, '').trim();
        // Quitar puntuación (manteniendo guión si se quiere)
        const punctuationToRemove = /[.,;:()\"'¿?¡!]/g; // Ajustar si es necesario
        text = text.replace(punctuationToRemove, '');
        // Normalizar espacios
        text = text.replace(/\s+/g, ' ').trim();
        return text;
    }
        // (getWordSet sigue siendo útil)
        function getWordSet(text) {
            return new Set(normalizeTextForDiff(text).split(' ').filter(word => word.length > 0));
        }

        // --- Comparar y Resaltar --- 
        function compareAndHighlightRows() {
            clearAllHighlights();
            console.log('[CompareGrid] >>> ACTION: Comparando y resaltando filas usando diff_type...');
            const numRows = comparisonData.length;
            let matchCount = 0, subtleCount = 0, mismatchCount = 0;
            
            // Obtener las celdas una vez
            const numberCells = Array.from(gridContainer.querySelectorAll(`.comparison-cell[data-col="1"][data-row]`));
            const expectedCellsContent = Array.from(gridContainer.querySelectorAll(`.comparison-cell[data-col="2"][data-row] .cell-content`));
            const actualCellsContent = Array.from(gridContainer.querySelectorAll(`.comparison-cell[data-col="3"][data-row] .cell-content`));

            for (let i = 0; i < numRows; i++) {
                const item = comparisonData[i];
                const numCell = numberCells[i] || null;
                const expectedContentDiv = expectedCellsContent[i] || null;
                const actualContentDiv = actualCellsContent[i] || null;

                if (!numCell || !expectedContentDiv || !actualContentDiv) {
                     console.warn(`[CompareGrid] Fila ${i + 1} (Índice ${i}): Faltan elementos DOM. Saltando.`); continue;
                }
                 // Limpiar clases e indicador específico de esta fila (ya hecho en clearAllHighlights, pero por seguridad)
                 numCell.classList.remove('match-success', 'match-fail', 'match-subtle-diff');
                 const oldIndicator = numCell.querySelector('.match-indicator');
                 if (oldIndicator) oldIndicator.remove();
                 
                const expectedText = item.expected || '';
                const actualText = item.actual || '';

                // Ignorar filas con espacios en blanco insertados
                if (expectedText === BLANK_SPACE_MARKER || actualText === BLANK_SPACE_MARKER || item.diff_type === 'blank') { continue; }

                const indicatorSpan = document.createElement('span');
                indicatorSpan.classList.add('match-indicator');

                // Usar item.diff_type para determinar el estilo
                switch (item.diff_type) {
                    case 'none': // Coincidencia literal exacta
                        numCell.classList.add('match-success');
                        indicatorSpan.innerHTML = '✓'; indicatorSpan.style.color = 'green'; indicatorSpan.title = 'Coincidencia exacta';
                        numCell.appendChild(indicatorSpan);
                        matchCount++;
                        // No aplicar más marcado si es éxito
                        break;
                    case 'sutil': // Diferencia sutil (normalizado coincide, literal no)
                        numCell.classList.add('match-subtle-diff'); // NUEVA CLASE CSS
                        indicatorSpan.innerHTML = '~'; indicatorSpan.style.color = 'orange'; indicatorSpan.title = 'Diferencia sutil (ej. espacios, puntuación)';
                        numCell.appendChild(indicatorSpan);
                        subtleCount++;
                         // Aplicar marcado de diferencias (inline y palabras)
                        applyDifferenceMarkup(expectedContentDiv, actualContentDiv, expectedText, actualText);
                        break;
                    case 'major': // Diferencia mayor (ni literal ni normalizado coinciden)
                    case 'edited': // Tratar editado como diferencia mayor por ahora
                    default: // Default a major si diff_type es inesperado
                        numCell.classList.add('match-fail'); // CLASE EXISTENTE
                        indicatorSpan.innerHTML = '✗'; indicatorSpan.style.color = 'red'; indicatorSpan.title = 'Diferencia significativa';
                        numCell.appendChild(indicatorSpan);
                        mismatchCount++;
                        // Aplicar marcado de diferencias (inline y palabras)
                        applyDifferenceMarkup(expectedContentDiv, actualContentDiv, expectedText, actualText);
                        break;
                }
            }
             console.log(`[CompareGrid] >>> Comparación completa: ${matchCount} exactas, ${subtleCount} sutiles, ${mismatchCount} mayores.`);
        }
        
        // --- Función para aplicar marcado de diferencias (inline y palabras) --- NUEVA VERSIÓN
        function applyDifferenceMarkup(expectedDiv, actualDiv, expectedText, actualText) {
            // Obtener el texto original plano para cálculos
            const originalExpectedText = expectedDiv.getAttribute('data-original-text') || '';
            const originalActualText = actualDiv.getAttribute('data-original-text') || '';
            
            // --- 1. Calcular datos para marcado (basado en texto original) --- 
            let diffIndex = -1;
            const trimmedExpected = originalExpectedText.trim();
            const trimmedActual = originalActualText.trim();
            const minLength = Math.min(trimmedExpected.length, trimmedActual.length);
            for (let k = 0; k < minLength; k++) {
                if (trimmedExpected[k] !== trimmedActual[k]) {
                    diffIndex = k;
                    break;
                }
            }
            if (diffIndex === -1 && trimmedExpected.length !== trimmedActual.length) {
                diffIndex = minLength;
            }

            const expectedWordsSet = getWordSet(originalExpectedText); // Normaliza internamente
            const actualWordsSet = getWordSet(originalActualText);   // Normaliza internamente
            const missingWords = [...expectedWordsSet].filter(word => !actualWordsSet.has(word));
            const extraWords = [...actualWordsSet].filter(word => !expectedWordsSet.has(word));

            // --- 2. Construir el HTML final para cada celda --- 
            // Aplicar marcado solo si hay diferencias (subtle o major)
            expectedDiv.innerHTML = buildHighlightedHTML(originalExpectedText, missingWords, 'diff-word-missing', diffIndex);
            actualDiv.innerHTML = buildHighlightedHTML(originalActualText, extraWords, 'diff-word-extra', diffIndex);
        }

        // --- NUEVA FUNCIÓN: Construir HTML con resaltado de palabras y marcador inline --- 
        function buildHighlightedHTML(originalText, wordsToHighlight, wordHighlightClass, inlineMarkerIndex) {
            if (!originalText) return ''; // Devolver vacío si no hay texto

            const highlightSet = new Set(wordsToHighlight.map(w => w.toLowerCase())); // Normalizar palabras a resaltar
            // Regex para encontrar palabras (incluyendo acentos/ñ)
            const wordRegex = /([\wáéíóúüñÁÉÍÓÚÜÑ]+)|(\S+)/g; // Captura palabras o cualquier no-espacio
            let resultHTML = '';
            let lastIndex = 0;
            let match;

            // Aplicar resaltado de palabras
            while ((match = wordRegex.exec(originalText)) !== null) {
                const word = match[0]; // La palabra/token encontrado
                const wordStartIndex = match.index;
                
                // Añadir texto entre la última coincidencia y esta
                resultHTML += escapeHTML(originalText.substring(lastIndex, wordStartIndex));
                
                // Normalizar palabra encontrada para chequear si debe resaltarse
                const normalizedWord = normalizeTextForDiff(word);
                
                if (normalizedWord && highlightSet.has(normalizedWord)) {
                     // Resaltar esta palabra
                     resultHTML += `<span class="${wordHighlightClass}">${escapeHTML(word)}</span>`;
                } else {
                    // No resaltar, añadir como texto normal (escapado)
                     resultHTML += escapeHTML(word);
                }
                lastIndex = wordStartIndex + word.length;
            }
            // Añadir el resto del texto después de la última palabra
            resultHTML += escapeHTML(originalText.substring(lastIndex));

            // Insertar el marcador inline si corresponde y el índice es válido
            if (inlineMarkerIndex !== -1 && inlineMarkerIndex <= originalText.length) {
                 // Necesitamos encontrar la posición correcta en el HTML construido
                 // Esto sigue siendo complejo. Una aproximación es buscar el carácter
                 // número `inlineMarkerIndex` ignorando las etiquetas HTML.
                 // Simplificación: Insertar directamente en el HTML, puede fallar si el índice cae dentro de una palabra resaltada.
                 // TODO: Mejorar la inserción del marcador inline para ser consciente del HTML.
                 const markerHTML = '<span class="diff-inline-marker" title="Primer punto de diferencia"></span>';
                  try {
                    // Intento simple de inserción (puede necesitar mejora)
                     let visibleCharCount = 0;
                     let insertPos = -1;
                     let inTag = false;
                     for(let i=0; i < resultHTML.length; i++) {
                         if (resultHTML[i] === '<') inTag = true;
                         if (!inTag) {
                             if (visibleCharCount === inlineMarkerIndex) {
                                 insertPos = i;
                                 break;
                             }
                             visibleCharCount++;
                         }
                         if (resultHTML[i] === '>') inTag = false;
                     }
                     // Si no se encontró posición exacta (ej. índice > longitud visible), añadir al final.
                     if (insertPos === -1) insertPos = resultHTML.length; 
                    
                     resultHTML = resultHTML.substring(0, insertPos) + markerHTML + resultHTML.substring(insertPos);

                  } catch (e) {
                      console.error("[CompareGrid] Error insertando marcador inline en HTML:", e);
                      // No añadir marcador si falla
                  }
            }
            
            return resultHTML;
        }
        
        // --- Helper para escapar HTML --- 
        function escapeHTML(str) {
            if (!str) return '';
            return str.replace(/[&<>'\"/]/g, function (s) {
                const entityMap = {
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#39;', // o &apos;
                    '/': '&#x2F;'
                };
                return entityMap[s];
            });
        }

        // --- Funciones de Manipulación (Insertar, Mover, Eliminar Espacios) ---
        function insertBlankSpace(columnIndex) {
            const activeElement = document.activeElement;
            let insertIndex = comparisonData.length; // Por defecto al final
            if (activeElement && activeElement.closest('.comparison-cell')) {
                const cell = activeElement.closest('.comparison-cell');
                const focusedRow = parseInt(cell.getAttribute('data-row'), 10);
                 // Insertar DESPUÉS de la fila enfocada
                if (!isNaN(focusedRow) && focusedRow >= 0) { 
                    insertIndex = focusedRow + 1;
                } 
            }
             console.log(`[CompareGrid] Insertando espacio en col ${columnIndex}, índice ${insertIndex}`);
            
             // Crear un objeto 'vacío' para la otra columna
             const newItem = {
                 expected: columnIndex === 2 ? BLANK_SPACE_MARKER : '', 
                 actual: columnIndex === 3 ? BLANK_SPACE_MARKER : '',
                 diff_type: 'blank' // Marcar como espacio en blanco
             };

            // Insertar en comparisonData
            comparisonData.splice(insertIndex, 0, newItem);
            redrawGrid();
            clearAllHighlights();
        }

        function moveItem(index, field, direction) { // field es 'expected' o 'actual'
            if (index < 0 || index >= comparisonData.length) return;

            const swapIndex = direction === 'up' ? index - 1 : index + 1;
            if (swapIndex < 0 || swapIndex >= comparisonData.length) return;

            // Solo intercambiamos el valor específico ('expected' o 'actual')
            // Asumiendo que movemos un espacio en blanco, el otro lado debe permanecer
            const temp = comparisonData[index][field];
            comparisonData[index][field] = comparisonData[swapIndex][field];
            comparisonData[swapIndex][field] = temp;
            
            // Recalcular diff_type para las filas afectadas si no son blank
            if (comparisonData[index][field] !== BLANK_SPACE_MARKER) comparisonData[index].diff_type = 'edited';
            if (comparisonData[swapIndex][field] !== BLANK_SPACE_MARKER) comparisonData[swapIndex].diff_type = 'edited';


            redrawGrid();
             clearAllHighlights(); // Limpiar resaltado después de mover
        }

        function deleteItem(index, field) { // field es 'expected' o 'actual'
             if (index < 0 || index >= comparisonData.length) return;
             
             // Verificar si la otra celda en la fila está vacía o también es un marcador
             const otherField = field === 'expected' ? 'actual' : 'expected';
             if (comparisonData[index][otherField] === '' || comparisonData[index][otherField] === BLANK_SPACE_MARKER) {
                 // Si la otra celda está vacía/marcador, eliminar toda la fila
                 comparisonData.splice(index, 1);
             } else {
                // Si la otra celda tiene contenido, solo vaciar el marcador actual
                comparisonData[index][field] = ''; 
                comparisonData[index].diff_type = 'edited'; // Marcar como editado
             }

            redrawGrid();
             clearAllHighlights(); // Limpiar resaltado después de eliminar
        }


        // --- Inicialización y Event Listeners ---
        redrawGrid(); // Dibujar el grid inicial con los datos cargados

        if (addExpectedBtn) addExpectedBtn.addEventListener('click', () => insertBlankSpace(2));
        if (addActualBtn) addActualBtn.addEventListener('click', () => insertBlankSpace(3));
        if (compareBtn) compareBtn.addEventListener('click', compareAndHighlightRows);

        console.log('[CompareGrid] >>> Script inicializado y listeners añadidos.');
    }); 