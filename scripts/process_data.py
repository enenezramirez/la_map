"""
GeoRiesgos Saltillo - Script de Procesamiento de Datos Espaciales
----------------------------------------------------------------
Este script sirve como punto de partida para procesar y consolidar la información
de riesgos (CENAPRED) y servicios básicos (INEGI Censo/DENUE).

Aprenderás a usar GeoPandas para:
1. Cargar archivos espaciales (.shp, .geojson, etc.)
2. Filtrar información geográfica.
3. Proyectar coordenadas.
4. Cruzar capas espaciales (Spatial Joins).
5. Calcular índices numéricos y exportar a GeoJSON optimizado.
"""

import os
import pandas as pd
# Nota: Asegúrate de tener instalado geopandas en tu entorno virtual:
# pip install geopandas shapely
try:
    import geopandas as gpd
    from shapely.geometry import Point, Polygon
except ImportError:
    print("WARNING: GeoPandas no está instalado en este entorno virtual. Ejecuta 'pip install geopandas shapely' para comenzar.")
    gpd = None

def inicializar_carpetas():
    """Crea la estructura de carpetas necesaria para los datos."""
    rutas = ["data", "raw_data"]
    for ruta in rutas:
        if not os.path.exists(ruta):
            os.makedirs(ruta)
            print(f"Carpeta creada: {ruta}/")

def procesar_datos_ejemplo():
    """
    Función ejemplo para demostrar cómo se cargan, procesan y salvan
    datos geoespaciales con GeoPandas.
    """
    if gpd is None:
        print("Instala GeoPandas para poder ejecutar la lógica espacial.")
        return

    print("Iniciando procesamiento de datos...")

    # 1. EJEMPLO: Crear un mapa de prueba con puntos aleatorios en Saltillo
    # Coordenadas aproximadas de Saltillo Centro
    lat_saltillo = 25.423
    lon_saltillo = -100.992

    # Crear algunos puntos simulados (ejemplo: comercios o reportes)
    datos_puntos = {
        'ID': [1, 2, 3],
        'Nombre': ['Centro Comercial', 'Zona Industrial', 'Área Residencial Norte'],
        'Servicios': [95.5, 80.0, 98.2],  # Calificación ejemplo
        'latitud': [25.423, 25.450, 25.465],
        'longitud': [-100.992, -100.932, -101.005]
    }

    df = pd.DataFrame(datos_puntos)

    # Convertir el DataFrame clásico de Pandas en un GeoDataFrame
    # 'geometry' almacena los objetos geométricos (puntos en este caso)
    gdf_puntos = gpd.GeoDataFrame(
        df, 
        geometry=gpd.points_from_xy(df.longitud, df.latitud),
        crs="EPSG:4326"  # Sistema de coordenadas estándar WGS84 utilizado por GPS y Leaflet
    )

    # 2. EJEMPLO: Crear un polígono de prueba (zona de riesgo de inundación simulada)
    # Definimos las coordenadas de un cuadrante
    coordenadas_inundables = [
        (-101.010, 25.410),
        (-100.980, 25.410),
        (-100.980, 25.430),
        (-101.010, 25.430),
        (-101.010, 25.410)
    ]
    poligono_riesgo = Polygon(coordenadas_inundables)
    
    gdf_riesgos = gpd.GeoDataFrame(
        {'ID_Riesgo': [101], 'Tipo': ['Inundación Frecuente'], 'Nivel': ['Alto']},
        geometry=[poligono_riesgo],
        crs="EPSG:4326"
    )

    # 3. EJEMPLO: Comprobar intersecciones espaciales (Cruce de Datos)
    # ¿Cuáles puntos están dentro del área inundable?
    # Usamos un spatial join (.sjoin)
    puntos_en_riesgo = gpd.sjoin(gdf_puntos, gdf_riesgos, how="inner", predicate="intersects")
    
    print("\nResultados del cruce de datos:")
    print(f"Puntos analizados: {len(gdf_puntos)}")
    print(f"Puntos identificados en área de riesgo: {len(puntos_en_riesgo)}")
    for idx, row in puntos_en_riesgo.iterrows():
        print(f" - {row['Nombre']} está en zona de {row['Tipo']} ({row['Nivel']})")

    # 4. GUARDAR RESULTADOS EN GEOJSON
    # Leaflet cargará estos archivos directamente
    ruta_salida_puntos = os.path.join("data", "puntos_ejemplo.geojson")
    ruta_salida_riesgos = os.path.join("data", "riesgos_ejemplo.geojson")

    gdf_puntos.to_file(ruta_salida_puntos, driver="GeoJSON")
    gdf_riesgos.to_file(ruta_salida_riesgos, driver="GeoJSON")
    print(f"\nDatos guardados con éxito en la carpeta data/ en formato GeoJSON!")

if __name__ == "__main__":
    inicializar_carpetas()
    procesar_datos_ejemplo()
