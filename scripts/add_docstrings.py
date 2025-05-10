"""
Módulo para mejorar la documentación del código con docstrings.
Este script actualiza los archivos Python del proyecto añadiendo o mejorando
los docstrings según el estándar de Google.
"""
import os
import re
import sys

def find_python_files(directory):
    """
    Encuentra todos los archivos Python en el directorio especificado y sus subdirectorios.
    
    Args:
        directory (str): Directorio raíz donde buscar archivos Python.
        
    Returns:
        list: Lista de rutas a archivos Python encontrados.
    """
    python_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

def main():
    """
    Función principal que ejecuta el script.
    """
    # Obtener el directorio raíz del proyecto
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Encontrar archivos Python
    src_dir = os.path.join(project_dir, 'src')
    python_files = find_python_files(src_dir)
    
    print(f"Encontrados {len(python_files)} archivos Python para documentar.")
    
    # Procesar cada archivo
    for file_path in python_files:
        print(f"Procesando {file_path}...")
        
        # Leer el contenido del archivo
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar si el archivo ya tiene docstrings
        if '"""' in content:
            print(f"  El archivo ya tiene docstrings. Saltando.")
            continue
        
        # Aquí se implementaría la lógica para añadir docstrings
        # Este es un ejemplo simplificado que solo añade un docstring al inicio del archivo
        if not content.startswith('"""'):
            module_name = os.path.basename(file_path)
            docstring = f'"""\n{module_name} - Módulo del Revisor de Juntas para EVoting.\n"""\n'
            content = docstring + content
            
            # Escribir el contenido actualizado
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"  Añadido docstring al módulo.")
    
    print("Documentación completada.")

if __name__ == "__main__":
    main()
