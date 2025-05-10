# Roadmap: Automatización de Creación de Organizaciones en E-Socios

El objetivo es automatizar el proceso de creación de nuevas organizaciones en la plataforma E-Socios, utilizando datos de un Google Sheets y subiendo archivos locales.

## Fases del Proyecto

1.  **Configuración Inicial y Acceso a Google Sheets:**
    *   [x] Instalar las bibliotecas necesarias para interactuar con Google Sheets (ej. `gspread`, `google-auth`).
    *   [x] Implementar la lógica para autenticarse con Google Sheets y acceder al documento especificado.
    *   [x] Definir una función para leer los datos de las columnas relevantes (Slug, Nombre de la organización, Organización padre) de la hoja especificada.

2.  **Navegación y Login en E-Socios:**
    *   [x] Reutilizar y adaptar el proceso de login existente en el proyecto para la URL `https://esocios.evoting.com/superadmin/login`.
    *   [x] Asegurar que el login sea exitoso y se manejen posibles errores (credenciales incorrectas, cambios en la página de login).

3.  **Navegación a la Página de Creación de Organización:**
    *   [x] Una vez logueado, navegar a la página de administración de organizaciones (similar a `esocios-organizaciones.html`).
    *   [x] Implementar la lógica para hacer clic en el botón "Crear organización".
    *   [x] Esperar a que la página de creación de organización (similar a `nueva-organizacion.html`) cargue completamente.

4.  **Rellenar Datos de la Organización:**
    *   Para cada fila del Google Sheets (cada `slug`):
        *   [x] **Nombre de la organización:** Localizar el campo "Nombre de la organización" e ingresar el valor de la Columna B.
        *   [x] **Organización padre:**
            *   [x] Localizar el campo de búsqueda/selección para "Organización padre".
            *   [x] Ingresar el valor de la Columna C (ej. "ANEF [9snl2kce]") y seleccionar la opción correspondiente.
        *   [x] **Logo de la organización:**
            *   [x] Localizar el botón de carga de archivos para "Logo de la organización".
            *   [x] Simular el clic y utilizar la funcionalidad de Selenium para enviar la ruta del archivo `logo-anef.png` (ubicado en la raíz del proyecto).
        *   [x] **Imagen para el inicio de sesión de usuario:**
            *   [x] Localizar el botón de carga de archivos para "Imagen para el inicio de sesión de usuario".
            *   [x] Simular el clic y enviar la ruta del archivo `Iniciosesion_esocios.png` (ubicado en la raíz del proyecto).

5.  **Configurar Funcionalidades de Pago:**
    *   [x] Localizar el switch "Descarga de usuarios" y activarlo.
    *   [x] Localizar el switch "Gráficos personalizados" y activarlo.

6.  **Crear Campos Adicionales para Usuarios:**
    *   Para cada campo adicional especificado:
        *   **Apellido (texto):**
            *   [x] Hacer clic en el botón "TIPO TEXTO".
            *   [x] Localizar el input "Nombre del dato" e ingresar "Apellido".
            *   [x] Activar el switch "Mostrar al usuario".
        *   **Sexo (texto):**
            *   [x] Hacer clic en el botón "TIPO TEXTO".
            *   [x] Localizar el input "Nombre del dato" e ingresar "Sexo".
            *   [x] Activar el switch "Mostrar al usuario".
        *   **Región (texto):**
            *   [x] Hacer clic en el botón "TIPO TEXTO".
            *   [x] Localizar el input "Nombre del dato" e ingresar "Región".
            *   [x] Activar el switch "Mostrar al usuario".
        *   **Provincia (texto):**
            *   [x] Hacer clic en el botón "TIPO TEXTO".
            *   [x] Localizar el input "Nombre del dato" e ingresar "Provincia".
            *   [x] Activar el switch "Mostrar al usuario".
        *   **Comuna (texto):**
            *   [x] Hacer clic en el botón "TIPO TEXTO".
            *   [x] Localizar el input "Nombre del dato" e ingresar "Comuna".
            *   [x] Activar el switch "Mostrar al usuario".
        *   **RSU/RAF (número):**
            *   [x] Hacer clic en el botón "TIPO NÚMERO" (o el equivalente si es diferente al de texto).
            *   [x] Localizar el input "Nombre del dato" e ingresar "RSU/RAF".
            *   [x] Activar el switch "Mostrar al usuario".

7.  **Finalizar Creación:**
    *   [x] Localizar y hacer clic en el botón "AGREGAR" (confirmar selector CSS/XPath).
    *   [x] Esperar la confirmación o manejar posibles errores en el envío del formulario.
    *   [x] Implementar un mecanismo de log o reporte para cada organización creada (o fallida).

8.  **Iteración y Manejo de Errores General:**
    *   [x] Implementar un bucle principal que itere sobre las filas del Google Sheets.
    *   [x] Añadir manejo de excepciones robusto en cada paso (ej. timeouts, elementos no encontrados, errores de carga de página, errores de Google Sheets API).
    *   [x] Incluir logging detallado para facilitar la depuración.
    *   [x] Considerar la posibilidad de reintentos para operaciones fallidas.

9.  **Estructura del Proyecto y Refactorización:**
    *   [x] Organizar el nuevo código en módulos y funciones siguiendo las `required_instructions`.
    *   [x] Crear un script principal para ejecutar todo el proceso.
    *   [x] Actualizar `requirements.txt` con las nuevas dependencias.
    *   [ ] Escribir pruebas unitarias para las funciones críticas (ej. lectura de Google Sheets, parsing de datos).

10. **Documentación:**
    *   [ ] Actualizar el `readme.md` del proyecto para reflejar la nueva funcionalidad.
    *   [x] Añadir docstrings a todas las nuevas funciones y clases.
    *   [ ] Documentar el proceso de configuración de credenciales para Google Sheets. 