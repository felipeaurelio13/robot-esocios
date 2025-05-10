# E-Socios Organization Creation Bot

Este proyecto automatiza el proceso de creación de nuevas organizaciones en la plataforma E-Socios. Lee los datos de una hoja de cálculo de Google, inicia sesión en el panel de superadministrador de E-Socios, navega al formulario de creación de organizaciones y completa los detalles requeridos, incluyendo la carga de logotipos y la configuración de campos de usuario adicionales.

## Tabla de Contenidos
1.  [Prerrequisitos](#prerrequisitos)
2.  [Configuración](#configuración)
    *   [Clonar el Repositorio](#1-clonar-el-repositorio)
    *   [Crear un Entorno Virtual](#2-crear-un-entorno-virtual)
    *   [Instalar Dependencias](#3-instalar-dependencias)
    *   [Configurar Credenciales de Google Cloud](#4-configurar-credenciales-de-google-cloud)
    *   [Configurar Archivo `.env`](#5-configurar-archivo-env)
    *   [Colocar Archivos de Imagen](#6-colocar-archivos-de-imagen)
    *   [Preparar Google Sheet](#7-preparar-google-sheet)
3.  [Ejecución del Bot](#ejecución-del-bot)
4.  [Estructura del Proyecto](#estructura-del-proyecto)
5.  [Modo Headless](#modo-headless)
6.  [Solución de Problemas](#solución-de-problemas)

## Prerrequisitos
*   Python 3.8 o superior
*   `pip` (manejador de paquetes de Python)
*   Acceso a un proyecto de Google Cloud con la API de Google Sheets habilitada.
*   Credenciales de superadministrador para la plataforma E-Socios.

## Configuración

Sigue estos pasos para configurar el proyecto en tu máquina local:

### 1. Clonar el Repositorio
```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_DIRECTORIO_DEL_PROYECTO>
```

### 2. Crear un Entorno Virtual
Se recomienda encarecidamente utilizar un entorno virtual para aislar las dependencias del proyecto.
```bash
python -m venv venv
```
Activa el entorno virtual:
*   En macOS y Linux:
    ```bash
    source venv/bin/activate
    ```
*   En Windows:
    ```bash
    .\venv\Scripts\activate
    ```

### 3. Instalar Dependencias
Instala todas las bibliotecas de Python necesarias utilizando el archivo `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Configurar Credenciales de Google Cloud
1.  Asegúrate de tener un archivo JSON de clave de cuenta de servicio de Google Cloud con permisos para acceder a la API de Google Sheets.
2.  Coloca este archivo JSON en la raíz del proyecto. El nombre de archivo esperado por defecto en `src/google_sheets_client.py` es `actualizacion-padron-b0c0035f9580.json`. Si tu archivo tiene un nombre diferente, actualiza la referencia en `src/google_sheets_client.py` o, preferiblemente, usa la variable de entorno `GOOGLE_APPLICATION_CREDENTIALS`.
3.  Asegúrate de que la cuenta de servicio tenga permisos de lectura sobre la Google Sheet que utilizarás.

### 5. Configurar Archivo `.env`
Crea un archivo llamado `.env` en la raíz del proyecto. Puedes copiar `env.example` (si existe) o crearlo desde cero. Este archivo almacenará tus credenciales y configuraciones sensibles.

Añade las siguientes variables al archivo `.env`:

```plaintext
# Credenciales de E-Socios
EVOTING_USERNAME="tu_usuario_esocios"
EVOTING_PASSWORD="tu_contraseña_esocios"

# Configuración de Google Sheets
# (Estos valores son referenciados en src/esocios_runner.py -> main_esocios_flow)
# Se recomienda mover la lógica de lectura de estas variables desde el código a una lectura de .env
GOOGLE_SHEET_URL="https://docs.google.com/spreadsheets/d/ID_DE_TU_HOJA/edit"
GOOGLE_SHEET_NAME="NombreDeTuPestaña" # ej. Slugs

# Ruta al archivo de credenciales de Google Cloud (opcional si el archivo está en la raíz y se llama como se espera)
# GOOGLE_APPLICATION_CREDENTIALS="actualizacion-padron-b0c0035f9580.json"

# Modo Headless para Selenium (True para ejecutar sin interfaz gráfica, False para ver el navegador)
HEADLESS_MODE=False
```

**Importante:**
*   Asegúrate de que el archivo `.env` esté listado en tu `.gitignore` para evitar subir credenciales al repositorio.
*   La implementación actual en `src/esocios_runner.py` tiene la URL de la hoja de cálculo y el nombre de la pestaña codificados. Para una mejor práctica, considera modificar `src/esocios_runner.py` para leer `GOOGLE_SHEET_URL` y `GOOGLE_SHEET_NAME` desde las variables de entorno.

### 6. Colocar Archivos de Imagen
El bot espera encontrar dos archivos de imagen en la raíz del proyecto, que se cargarán durante la creación de la organización:
*   `logo-anef.png` (Logo de la organización)
*   `Iniciosesion_esocios.png` (Imagen para el inicio de sesión de usuario)

Asegúrate de que estos archivos estén presentes en el directorio raíz del proyecto.

### 7. Preparar Google Sheet
La Google Sheet especificada en `GOOGLE_SHEET_URL` (o codificada en `src/esocios_runner.py`) debe tener una pestaña con el nombre especificado en `GOOGLE_SHEET_NAME`. Esta pestaña debe contener al menos las siguientes columnas, con los datos comenzando desde la segunda fila:
*   `Slug` (Columna A): Identificador único para la organización.
*   `Nombre Organización` (Columna B): Nombre completo de la organización a crear.
*   `Organización padre` (Columna C): Nombre de la organización padre tal como aparece en E-Socios (puede incluir un ID entre corchetes, ej., "NOMBRE PADRE [xxxxxx]"). Si no hay padre, esta celda puede estar vacía.

## Ejecución del Bot

Una vez completada la configuración, puedes ejecutar el bot desde el directorio raíz del proyecto usando el siguiente comando:

```bash
python -m src.esocios_runner
```

El bot comenzará a procesar las filas de la Google Sheet una por una, intentando crear cada organización en E-Socios. El progreso y los errores se registrarán en la consola.

## Estructura del Proyecto

```
.
├── .env                            # Archivo de variables de entorno (debe ser creado por el usuario)
├── .gitignore                      # Especifica archivos ignorados por Git
├── actualizacion-padron-b0c0035f9580.json # Ejemplo de nombre de archivo de credenciales de GCloud (reemplazar con el tuyo)
├── logo-anef.png                   # Logo de la organización
├── Iniciosesion_esocios.png        # Imagen de inicio de sesión
├── requirements.txt                # Dependencias de Python
├── README.md                       # Este archivo
├── ROADMAP.md                      # Hoja de ruta del desarrollo (puede estar desactualizado)
└── src/
    ├── __init__.py
    ├── auth_manager.py             # Maneja el login en E-Socios
    ├── config.py                   # Carga configuraciones (principalmente desde .env)
    ├── esocios_runner.py           # Script principal que orquesta el bot
    ├── google_sheets_client.py     # Interactúa con la API de Google Sheets
    ├── webdriver_setup.py          # Configura la instancia de Selenium WebDriver
    └── (otros módulos de utilidad)
```

## Modo Headless

El bot puede ejecutarse en modo "headless", lo que significa que el navegador Chrome no se abrirá visualmente. Esto es útil para ejecuciones en servidores o para un funcionamiento más rápido.
Para controlar esto, establece la variable `HEADLESS_MODE` en tu archivo `.env`:
*   `HEADLESS_MODE=True`: Ejecuta en modo headless.
*   `HEADLESS_MODE=False`: Ejecuta con el navegador visible.

## Solución de Problemas

*   **`ModuleNotFoundError: No module named 'src'`**: Asegúrate de estar ejecutando el script como un módulo desde el directorio raíz del proyecto: `python -m src.esocios_runner`.
*   **Errores de Google Sheets**:
    *   Verifica que el archivo JSON de credenciales de Google Cloud sea correcto y accesible.
    *   Asegúrate de que la cuenta de servicio tenga permisos para leer la Google Sheet.
    *   Confirma que la URL de la hoja y el nombre de la pestaña sean correctos.
*   **Errores de Selenium/WebDriver**:
    *   Asegúrate de tener Google Chrome instalado. `webdriver-manager` debería descargar el `chromedriver` correcto automáticamente.
    *   Si los selectores (IDs, XPaths) fallan, la interfaz de usuario de E-Socios puede haber cambiado. Necesitarás actualizar los selectores en `src/esocios_runner.py`.
    *   Los timeouts pueden ocurrir si la conexión a internet es lenta o si la página tarda demasiado en cargar. Puedes ajustar los tiempos de espera de `WebDriverWait` en el código si es necesario.
*   **Archivos no encontrados**: Verifica que `logo-anef.png` e `Iniciosesion_esocios.png` estén en la raíz del proyecto.

Para problemas más detallados, revisa los logs generados en la consola. Los errores suelen incluir capturas de pantalla (`.png`) guardadas en el directorio raíz del proyecto, que pueden ayudar a diagnosticar problemas con la interfaz de usuario.
