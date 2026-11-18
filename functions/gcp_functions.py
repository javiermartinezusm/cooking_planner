import os
import json
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

def get_food_from_bigquery(codes: list[int]) -> list[dict]:
    # Cargar las variables de entorno desde .env
    load_dotenv()

    project_id = os.getenv("GCP_PROJECT_ID")
    sa_key_str = os.getenv("GCP_SA_KEY")
    products_table = os.getenv("GCP_PRODUCTS_TABLE")

    # Si la lista de códigos está vacía, no hacemos nada
    if not codes:
        return []

    # Crear conexion a BigQuery
    sa_info = json.loads(sa_key_str)
    credentials = service_account.Credentials.from_service_account_info(sa_info)
    client = bigquery.Client(credentials=credentials, project=project_id)

    # Ejecutar la consulta
    query = f"""
    SELECT codigo, producto, unidad_medida, cantidad_unidad, es_comida
    FROM {products_table}
    WHERE codigo in ({", ".join(f"{code}" for code in codes)})
    """

    query_job = client.query(query)
    results = query_job.result()
    resultados_dict = [dict(row) for row in results]
    return resultados_dict

def update_products_in_bigquery(products: list[dict]) -> bool:
    # Cargar las variables de entorno desde .env
    load_dotenv()

    project_id = os.getenv("GCP_PROJECT_ID")
    sa_key_str = os.getenv("GCP_SA_KEY")
    products_table = os.getenv("GCP_PRODUCTS_TABLE")

    # Crear conexion a BigQuery
    sa_info = json.loads(sa_key_str)
    credentials = service_account.Credentials.from_service_account_info(sa_info)
    client = bigquery.Client(credentials=credentials, project=project_id)

    # Si la lista de productos está vacía, no hacemos nada
    if not products:
        print(f"No hay productos para actualizar en BigQuery.\nSe ingresó como products: {products}")
        return False
    values_list = []
    for p in products:
        codigo = p["codigo"]
        producto = p["producto"].replace("'", "''")
        unidad_medida = p["unidad_medida"]
        cantidad_unidad = p["cantidad_unidad"]
        es_comida = str(p["es_comida"]).upper()
        values_list.append(f"({codigo}, '{producto}', '{unidad_medida}', {cantidad_unidad}, {es_comida})")
    # Ejecutar la consulta SQL de inserción
    query = f"""
    INSERT INTO {products_table} (codigo, producto, unidad_medida, cantidad_unidad, es_comida)
    VALUES {", ".join(values_list)}
    """
    query_job = client.query(query)
    query_job.result()  # Espera a que termine de ejecutarse la inserción en BigQuery
    return True
    #except Exception as e:
    #    print(f"Error al actualizar productos en BigQuery: {e}")
    #    return False