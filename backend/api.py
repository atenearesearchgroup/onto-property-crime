# Añadir estas importaciones al inicio de tu archivo
import tempfile
import json
import datetime
import time
from fastapi import APIRouter, FastAPI, File, Form, Response, UploadFile, HTTPException, Query
from platformdirs import user_downloads_path
import urllib
from rdfFile import crear_rdf2 
from entities import Atestado, AnalisisAtestado, ListaAnalisis
import decisionTree
from atestadoToText import generar_descripcion
from fastapi.responses import StreamingResponse, JSONResponse
from documents import leer_pdf, leer_docx, leer_pdf_memoria, leer_docx_memoria
import os
import requests
from reasonerFromFile import reasoner, reasoner_ttl , reasoner_ttls, clean_uri #,  reasoner_debug ,construir_articulos_inferidos, reasoner_v1, construir_articulos_inferidos_v1
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Tuple
from fastapi.responses import FileResponse
# --- Añadir a las importaciones existentes ---
from neo4j_manager import neo4j_client  # Importamos el manager recién creado
import uuid
import io

from dotenv import load_dotenv

load_dotenv()

# --- Modelo para la petición ---
class Neo4jImportRequest(BaseModel):
    file_path: str
    root_name: str  # Ejemplo: "Atestado"
    articles: list  # Ejemplo: ["Article234_1", "Article242"]
    llm_type: str

# Importar las clases del script de ontología (ajustar la ruta según tu estructura)
#from ontology_bfs_traversal_v9 import OntologyTraversal
from ontology_traversal import OntologyTraversal

# Modelos Pydantic para validación de entrada
class OntologyTraversalRequest(BaseModel):
    class_name: str
    max_depth: Optional[int] = None
    include_metadata: bool = True

# Variable global para mantener la ontología cargada (opcional - para mejor performance)
global_traversal = None

ontology_file_path = f"{os.getenv('ONTOLOGY_PATH')}/{os.getenv('ONTOLOGY')}"  # Configurar con la ruta de tu ontología



app = FastAPI()
router = APIRouter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLASSES_TO_ANALYSE = os.getenv("CLASSES_TO_ANALYSE")

def get_ontology_traversal():
    """Obtiene o inicializa el traversal de ontología"""
    global global_traversal, ontology_file_path
    
    if global_traversal is None:
        global_traversal = OntologyTraversal()
        
        # Opción 1: Cargar ontología desde archivo
        if ontology_file_path and os.path.exists(ontology_file_path):
            try:
                global_traversal.load_ontology(ontology_file_path)
                print(f"✅ Ontología cargada desde: {ontology_file_path}")
            except Exception as e:
                print(f"⚠️ Error cargando ontología, usando ejemplo: {e}")
                global_traversal.create_sample_ontology()
        else:
            # Opción 2: Usar ontología de ejemplo
            print(f"📝 Ontología no cargada: {ontology_file_path}")
            global_traversal.create_sample_ontology()
    
    return global_traversal

@app.post("/ontologia/recorrer_bfs/")
async def recorrer_ontologia_bfs(request: OntologyTraversalRequest):
    """Recorre la ontología en amplitud desde una clase dada y devuelve JSON.
    
    Ejecuta un recorrido BFS (Breadth-First Search) desde la clase especificada,
    recopilando información sobre clases, equivalencias, subclases e instancias.
    
    Parameters
    ----------
    request: OntologyTraversalRequest
        - class_name: Nombre de la clase desde la cual iniciar el recorrido
        - max_depth: Profundidad máxima del recorrido (opcional)
        - include_metadata: Incluir metadatos en la respuesta
    
    Returns
    -------
    JSONResponse
        JSON con la estructura de clases recorrida, equivalencias y metadatos
    
    Raises
    ------
    HTTPException
        404: Si la clase no se encuentra en la ontología
        500: Si ocurre un error durante el procesamiento
    """
    try:
        # Obtener el traversal de ontología
        traversal = get_ontology_traversal()
        
        # Verificar que la ontología esté cargada
        if not traversal.ontology:
            raise HTTPException(
                status_code=500, 
                detail="No hay ontología cargada en el sistema"
            )
        
        # Verificar que la clase existe
        print(f"📝 request.class_name: {request.class_name}")
        if not hasattr(traversal.ontology, request.class_name):
            available_classes = [cls.name for cls in traversal.ontology.classes()] #[:10]  # Primeras 10
            raise HTTPException(
                status_code=404,
                detail=f"Clase '{request.class_name}' no encontrada. "
                       f"Clases disponibles (muestra): {available_classes}"
            )
        
        print(f"🔍 Iniciando recorrido BFS desde: {request.class_name}")
        
        # Crear archivo temporal para la exportación JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            temp_json_path = tmp_file.name
        
        try:
            # Exportar a JSON usando el método del traversal
            json_file_path = traversal.export_classes_to_json(
                start_class=request.class_name,
                output_file=temp_json_path,
                max_depth=request.max_depth,
                include_metadata=request.include_metadata,
                traversal_method="dfs"
            )
            
            # Leer el JSON generado
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # Añadir información adicional sobre el recorrido
            if request.include_metadata and "metadata" in json_data:
                json_data["metadata"]["api_endpoint"] = "/ontologia/recorrer_bfs/"
                json_data["metadata"]["request_parameters"] = {
                    "class_name": request.class_name,
                    "max_depth": request.max_depth,
                    "include_metadata": request.include_metadata
                }
            
            print(f"✅ Recorrido completado. Clases procesadas: {len(json_data.get('classes', {}))}")
            
            return JSONResponse(
                content=json_data,
                status_code=200,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "X-Total-Classes": str(len(json_data.get('classes', {}))),
                    "X-Start-Class": request.class_name
                }
            )
            
        finally:
            # Limpiar archivo temporal
            if os.path.exists(temp_json_path):
                os.remove(temp_json_path)
                
    except HTTPException:
        # Re-lanzar HTTPExceptions sin modificar
        raise
    except Exception as e:
        print(f"❌ Error en recorrido BFS: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno durante el recorrido: {str(e)}"
        )

@app.post("/ontologia/recorrer_bfs_simple/")
async def recorrer_ontologia_bfs_simple(
    class_name: str = Form(...),
    max_depth: Optional[int] = Form(None),
    include_metadata: bool = Form(True)
):
    """Versión simplificada del endpoint BFS usando Form parameters.
    
    Alternativa al endpoint principal que acepta parámetros como form-data
    en lugar de JSON body, útil para integraciones más simples.
    
    Parameters
    ----------
    class_name: str
        Nombre de la clase desde la cual iniciar el recorrido
    max_depth: int, optional
        Profundidad máxima del recorrido
    include_metadata: bool
        Si incluir metadatos en la respuesta
    
    Returns
    -------
    JSONResponse
        JSON con la estructura de clases recorrida
    """
    request_obj = OntologyTraversalRequest(
        class_name=class_name,
        max_depth=max_depth,
        include_metadata=include_metadata
    )
    
    return await recorrer_ontologia_bfs(request_obj)

@app.get("/ontologia/clases/")
async def listar_clases_ontologia():
    """Lista todas las clases disponibles en la ontología.
    
    Endpoint de utilidad para descubrir qué clases están disponibles
    para usar como punto de partida en el recorrido BFS.
    
    Returns
    -------
    dict
        Lista de clases disponibles con sus nombres y metadatos básicos
    """
    try:
        traversal = get_ontology_traversal()
        
        if not traversal.ontology:
            raise HTTPException(
                status_code=500,
                detail="No hay ontología cargada en el sistema"
            )
        
        # Obtener todas las clases
        classes_info = []
        for cls in traversal.ontology.classes():
            # Extraer comentarios y seeAlso (pueden devolver listas)
            comment_values = getattr(cls, "comment", [])
            see_also_values = getattr(cls, "seeAlso", [])

            #if cls.name != "Thing":  # Excluir la clase Thing de OWL
            class_info = {
                "name": cls.name,
                "iri": str(cls.iri) if hasattr(cls, 'iri') else None,
                "subclasses_count": len(list(cls.subclasses())),
                "instances_count": len(list(cls.instances())),
                "has_equivalents": len(list(cls.equivalent_to)) > 0,
                "comments": [str(c) for c in comment_values] if comment_values else [],
                "seeAlso": [str(s) for s in see_also_values] if see_also_values else []
            }
            classes_info.append(class_info)
            # print("Naaaaaaaame: ", cls.name)
            # for prop in cls.get_properties(cls):
            #     print("Property: ", prop)
            #     print("Value: ", prop[cls])
            
        
        # Ordenar por nombre
        classes_info.sort(key=lambda x: x['name'])
        
        return {
            "total_classes": len(classes_info),
            "classes": classes_info,
            "ontology_iri": str(traversal.ontology.base_iri) if traversal.ontology else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listando clases: {str(e)}"
        )

@app.post("/ontologia/cargar/")
async def cargar_ontologia(file: UploadFile = File(...)):
    """Carga una nueva ontología desde un archivo OWL/RDF.
    
    Permite cargar dinámicamente una ontología desde un archivo subido,
    reemplazando la ontología actual en memoria.
    
    Parameters
    ----------
    file: UploadFile
        Archivo OWL/RDF con la ontología a cargar
    
    Returns
    -------
    dict
        Información sobre la ontología cargada
    """
    global global_traversal
    
    try:
        # Verificar extensión del archivo
        if not file.filename.lower().endswith(('.owl', '.rdf', '.ttl')):
            raise HTTPException(
                status_code=400,
                detail="Formato de archivo no soportado. Use .owl, .rdf o .ttl"
            )
        
        # Guardar archivo temporal
        contenido = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.owl') as tmp_file:
            tmp_file.write(contenido)
            temp_path = tmp_file.name
        
        try:
            # Crear nuevo traversal y cargar ontología
            new_traversal = OntologyTraversal()
            new_traversal.load_ontology(f"file://{temp_path}")
            
            # Si la carga es exitosa, reemplazar el traversal global
            global_traversal = new_traversal
            
            # Obtener estadísticas de la nueva ontología
            classes_count = len(list(new_traversal.ontology.classes()))
            individuals_count = len(list(new_traversal.ontology.individuals()))
            properties_count = len(list(new_traversal.ontology.properties()))
            
            return {
                "status": "success",
                "filename": file.filename,
                "ontology_iri": str(new_traversal.ontology.base_iri),
                "statistics": {
                    "classes": classes_count,
                    "individuals": individuals_count,
                    "properties": properties_count
                }
            }
            
        finally:
            # Limpiar archivo temporal
            os.remove(temp_path)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error cargando ontología: {str(e)}"
        )

# # Ruta de api para procesar atestados (tu código original)
# @app.post("/procesar/")
# async def procesar_atestado(file: UploadFile):
#     """Procesa un atestado subido por el usuario.

#     Lee el archivo proporcionado (PDF o DOCX), lo envía al árbol de
#     decisión basado en LLM y, si procede, genera una descripción
#     resumida del atestado.

#     Parameters
#     ----------
#     file: UploadFile
#         Archivo que contiene el atestado en formato PDF o DOCX.

#     Returns
#     -------
#     dict | str
#         Diccionario con los datos del ``Atestado`` y su descripción o
#         un mensaje de error/estado en caso de que no se determine un
#         atestado válido.
#     """
#     try:
#         extension = os.path.splitext(file.filename)[1].lower()
#         contenido = await file.read()

#         temp_path = f"/tmp/{file.filename}"
#         print(f"temp_path = {temp_path}")
#         with open(temp_path, "wb") as f:
#             f.write(contenido)

#         if extension == ".pdf":
#             texto = leer_pdf(temp_path)
#         elif extension == ".docx":
#             texto = leer_docx(temp_path)
#         else:
#             return {"error": "Formato de archivo no soportado. Usa PDF o DOCX."}
        
#         resultado = decisionTree.delitoPropiedad(decisionTree.AtestadoLLM(texto)) 

#         '''
#         resultado = decisionTree.analizarAtestado(decisionTree.AtestadoLLM(texto))
#         '''

#         if isinstance(resultado, Atestado):
#             descripcion = generar_descripcion(resultado)
#         else:
#             descripcion = resultado

#         print(f"Descripción generada: {descripcion}")

#         if isinstance(resultado, Atestado):
#             resultado_dict = resultado.model_dump()
#             resultado_dict["descripcion"] = descripcion
#             # print(f"Resultado del procesamiento: {resultado_dict}")
#             return resultado_dict
#         else:
#             resultado_str = str(resultado)
#             # print(f"Resultado del procesamiento: {resultado_str}")
#             return resultado_str

#     except Exception as e:
#         return {"error": str(e)}
    
# Ruta de api para procesar atestados (tu código original)
@app.post("/procesarG/")
async def procesar_atestadoG(file: UploadFile):
    """Procesa un atestado subido por el usuario.

    Lee el archivo proporcionado (PDF o DOCX), lo envía al árbol de
    decisión basado en LLM y, si procede, genera una descripción
    resumida del atestado.

    Parameters
    ----------
    file: UploadFile
        Archivo que contiene el atestado en formato PDF o DOCX.

    Returns
    -------
    dict | str
        Diccionario con los datos del ``Atestado`` y su descripción o
        un mensaje de error/estado en caso de que no se determine un
        atestado válido.
    """
    try:
        extension = os.path.splitext(file.filename)[1].lower()
        nombre = clean_uri(os.path.splitext(file.filename)[0])
        
        # 1. Leer el contenido del archivo directamente a memoria
        contenido_bytes = await file.read()

        # 2. Extraer texto sin guardar en disco
        # Nota: Asegúrate de que tus funciones leer_pdf/leer_docx acepten bytes 
        # o usa io.BytesIO para simular un archivo en memoria
        
        file_memory = io.BytesIO(contenido_bytes)
        texto = leer_pdf_memoria(file_memory) if extension == ".pdf" else leer_docx_memoria(file_memory)

        # Recuperar el listado de clases en profundidad
        traversal = get_ontology_traversal()
        if not traversal.ontology:
            raise HTTPException(
                status_code=500,
                detail="No hay ontología cargada en el sistema"
            )
 
        resultado = decisionTree.analizarAtestado(decisionTree.AtestadoLLM(texto), nombre, json.loads(CLASSES_TO_ANALYSE), traversal)
        return JSONResponse(content=resultado, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}

# # Resto de tu código original...
# @app.post("/generar_rdf/")
# async def generar_rdf(atestado: Atestado):
#     """Crear y devolver un fichero RDF para el ``Atestado`` recibido."""
#     try:
#         nombre_archivo = crear_rdf(atestado)
#         ruta_completa = os.path.join(user_downloads_path(), nombre_archivo)
#         rdf_file = open(ruta_completa, "rb")
#         return StreamingResponse(
#             rdf_file,
#             media_type="application/xml",
#             headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
#         )
#     except Exception as e:
#         return {"error": str(e)}
    
@app.post("/generar_rdfGF/")
# async def generar_rdf(analisis: AnalisisAtestado): 
async def generar_rdfGF(file: UploadFile):
    """Crear y devolver un fichero RDF para el ``Atestado`` recibido."""
    try:
        # Abre el archivo JSON en modo lectura uso temporal 
        contents = await file.read()
        string_contents = contents.decode("utf-8")
        data = json.loads(string_contents)

        print(f"\n📌generar_rdfG - data:  {len(data)} - filename: {file.filename}")
        nombre_archivo = crear_rdf2(data.get("respuestas",[]), data.get("nombre_grafo","AtestadoPruebaaaaa"))
        print(f"\n📌generar_rdfG - nombre_archivo:  {nombre_archivo} ")

        ruta_completa = os.path.join(user_downloads_path(), nombre_archivo)
        rdf_file = open(ruta_completa, "rb")

        return StreamingResponse(
            rdf_file,
            media_type="application/xml",
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
        )
    except Exception as e:
        return {"error": str(e)}
    
@app.post("/generar_rdfG/")
# async def generar_rdf(analisis: AnalisisAtestado): 
async def generar_rdfG(data: ListaAnalisis):
    """Crear y devolver un fichero RDF para el ``Atestado`` recibido."""
    try:
        nombre_grafo = data.nombre_grafo
        print(f"\n📌generar_rdfG - data: {nombre_grafo}")
        data_dict = data.model_dump()
        nombre_archivo = crear_rdf2(data_dict.get("respuestas",[]), data_dict.get("nombre_grafo","AtestadoPrueba"))
  
        print(f"\n📌generar_rdfG - nombre_archivo:  {nombre_archivo} ")
        ruta_completa = os.path.join(user_downloads_path(), nombre_archivo)
        rdf_file = open(ruta_completa, "rb")
        print(f"\n📌generar_rdfG - ruta_completa:  {ruta_completa} ")

        return StreamingResponse(
            rdf_file,
            media_type="application/xml",
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
        )
    except Exception as e:
        return {"error": str(e)}
    finally:
        if os.path.exists(ruta_completa): 
            os.remove(ruta_completa)
            print(f"\n📌inferir_grafo_ttls - Borrar - {ruta_completa}")
    
@app.post("/ver_grafo_pdf/")
async def ver_grafo_pdf(rdf: str = Form(...), formato: str = Form(default="xml")):
    """Devuelve un documento PDF representando el grafo RDF recibido."""
    try:
        
        # 2. Preparamos la petición al servicio rdf-grapher
        # encoded_rdf = urllib.parse.quote_plus(rdf_filtrado)
        encoded_rdf = urllib.parse.quote_plus(rdf)
        # Cambiamos 'to=png' por 'to=pdf'
        body = f"rdf={encoded_rdf}&from={formato}&to=pdf"
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        res = requests.post(
            "https://www.ldf.fi/service/rdf-grapher",
            data=body,
            headers=headers,
            timeout=15 # Aumentamos un poco el timeout ya que los PDF pueden pesar más
        )
        
        if res.status_code != 200:
            return {"error": f"ldf.fi devolvió {res.status_code}"}
        
        # 3. Devolvemos la respuesta con el media_type correcto para PDF
        return Response(
            content=res.content, 
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=grafo.pdf"}
        )
        
    except Exception as e:
        return {"error": str(e)}   

@app.post("/ver_grafo_png/")
async def ver_grafo(rdf: str = Form(...), formato: str = Form(default="xml")):
    """Devuelve una imagen PNG representando el grafo RDF recibido."""
    try:
        grafo_filtrado = filtrar_grafo(rdf, formato=formato)
        rdf_filtrado = grafo_filtrado.serialize(format=formato)
        encoded_rdf = urllib.parse.quote_plus(rdf_filtrado)
        body = f"rdf={encoded_rdf}&from={formato}&to=png"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        res = requests.post(
            "https://www.ldf.fi/service/rdf-grapher",
            data=body,
            headers=headers,
            timeout=10
        )

        if res.status_code != 200:
            return {"error": f"ldf.fi devolvió {res.status_code}"}
        return Response(content=res.content, media_type="image/png")
    
    except Exception as e:
        return {"error": str(e)}
    
@app.post("/inferencias/")
async def inferencias(file: UploadFile = File(...)):
    """
    Endpoint que recibe un RDF, ejecuta el razonamiento y devuelve
    el contenido Turtle de los individuos y del mundo completo.
    """
    contenido = await file.read()
    
    # 1. Guardar archivo temporal de entrada
    with tempfile.NamedTemporaryFile(delete=False, suffix=".rdf") as tmp:
        tmp.write(contenido)
    tmp_path = tmp.name
    
    try:
        print(f"hola")
        # 2. Llamar a la función de razonamiento
        path_world, path_inds = reasoner_ttl(tmp_path)
        
        if not path_world or not path_inds:
            raise HTTPException(status_code=500, detail="Error en el procesamiento de la ontología")

        if path_inds and os.path.exists(path_inds):
            return FileResponse(
                path=path_inds, 
                filename="inferencias.ttl",
                media_type="text/turtle" #"application/rdf+xml"# Cambiamos el tipo MIME a Turtle
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpieza de archivos temporales
        if os.path.exists(tmp_path): os.remove(tmp_path)
        # Opcionalmente puedes borrar los .ttl generados aquí tras leerlos

@app.post("/inferir_grafo_ttls/")
# async def generar_rdf(analisis: AnalisisAtestado): 
async def inferir_grafo_ttls(data: ListaAnalisis):
    """ 1. Generar un fichero rdf
        2. Inferir con hermit herencia de clases 
        3. Transformar rdf a ttls y añadir referencias a objetos
        4. Devolver un fichero ttls para el 'grafo' recibido."""
    try:
        # 1. Generar un fichero rdf
        nombre_grafo = data.nombre_grafo
        print(f"\n📌inferir_grafo_ttls - tipo - data:  {type(data)} {nombre_grafo}")

        data_dict = data.model_dump()
        nombre_archivo = crear_rdf2(data_dict.get("respuestas",[]), data_dict.get("nombre_grafo","AtestadoPrueba"))

        print(f"\n📌inferir_grafo_ttls - nombre_archivo:  {nombre_archivo} ")
        ruta_completa = os.path.join(user_downloads_path(), nombre_archivo)
        
        # 1.2 .Guardar archivo temporal de entrada
        with open(ruta_completa, "rb") as f_original:
            contenido_rdf = f_original.read()  # <--- LEEMOS los bytes del archivo

        with tempfile.NamedTemporaryFile(delete=False, suffix=".rdf") as tmp:
            tmp.write(contenido_rdf)
        tmp_path = tmp.name
    
        # 2. Inferir con hermit herencia de clases 
        path_world, path_inds = reasoner_ttls(tmp_path,  data_dict.get("respuestas",[]))
        
        if not path_world or not path_inds:
            raise HTTPException(status_code=500, detail="Error en el procesamiento de la ontología")

        # 4. Devolver un fichero ttls para el 'grafo' recibido.
        if path_inds and os.path.exists(path_inds):
            print(f"\n📌inferir_grafo_ttls - generar - {nombre_grafo}.ttl")
            content_file = open(path_inds, "rb")
            print(f"\n📌generar_rdfG - ruta_completa:  {ruta_completa} ")
            return StreamingResponse(
                content_file,
                media_type="application/xml",
                headers={"Content-Disposition": f"attachment; filename={nombre_grafo}.ttl"}
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpieza de archivos temporales 
        if os.path.exists(tmp_path): 
            os.remove(tmp_path)
            print(f"\n📌inferir_grafo_ttls - Borrar - {tmp_path}")
        if os.path.exists(ruta_completa): 
            os.remove(ruta_completa)
            print(f"\n📌inferir_grafo_ttls - Borrar - {ruta_completa}") 
        if os.path.exists(path_inds): 
            os.remove(path_inds)
            print(f"\n📌inferir_grafo_ttls - Borrar - {path_inds}")
        


@app.post("/ws_inferencias/")
async def ws_inferencias(file: UploadFile = File(...)):
    
    contenido = await file.read()
    
    # 1. Guardar archivo de entrada
    with tempfile.NamedTemporaryFile(delete=False, suffix=".rdf") as tmp:
        tmp.write(contenido)
        tmp_path = tmp.name
    
    try:
        world_inferido, path_ttl_generado = reasoner_ttl(tmp_path)
        
        # Opcional: imprimir por consola para trazabilidad
        # construir_articulos_inferidos(world_inferido)
        if path_ttl_generado and os.path.exists(path_ttl_generado):
            return FileResponse(
                path=path_ttl_generado, 
                filename="inferencias.ttl",
                media_type="text/turtle" # Cambiamos el tipo MIME a Turtle
            )
  
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(world_inferido):
            os.remove(world_inferido)

@app.post("/ontologia/recorrido_dfs/")
async def recorrido_dfs(request: OntologyTraversalRequest):
    """
    Recorrido DFS modificado: explora subclases y dependencias por 'equivalent_to'.
    Si una clase no tiene subclases pero sí equivalencias, sigue por esas equivalencias.
    Devuelve la estructura recorrida y metadatos.
    """
    try:
        traversal = get_ontology_traversal()
        if not traversal.ontology:
            raise HTTPException(
                status_code=500,
                detail="No hay ontología cargada en el sistema"
            )
        if not hasattr(traversal.ontology, request.class_name):
            available_classes = [cls.name for cls in traversal.ontology.classes()] #[:10]
            raise HTTPException(
                status_code=404,
                detail=f"Clase '{request.class_name}' no encontrada. "
                       f"Clases disponibles (muestra): {available_classes}"
            )
        
        # Llamar a la función de DFS extendido 
        dfs_result = traversal.dfs_equivalent_and_subclasses(
            request.class_name, request.max_depth
        )
        # print(f"\n📌 dfs_result: {dfs_result}")

        # Preparar respuesta
        response = {
            "metadata": {},
            "classes": dfs_result["classes"],
            "traversal_info": {
                "method": "DFS_EXTENDIDO",
                "start_class": request.class_name,
                "total_visited": len(dfs_result["classes"]),
                "max_depth_reached": dfs_result["max_depth_reached"],
                "traversal_path": dfs_result["traversal_path"]
            }
        }
        if request.include_metadata:
            response["metadata"] = {
                "export_timestamp": datetime.datetime.now().isoformat(),
                "ontology_iri": str(traversal.ontology.base_iri) if traversal.ontology else "Unknown",
                "start_class": request.class_name,
                "max_depth": request.max_depth,
                "api_endpoint": "/ontologia/recorrido_dfs/",
                "request_parameters": {
                    "class_name": request.class_name,
                    "max_depth": request.max_depth,
                    "include_metadata": request.include_metadata
                }
            }
        return JSONResponse(content=response, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en recorrido DFS extendido: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno durante el recorrido DFS extendido: {str(e)}"
        )

@app.post("/procesar_y_generar_rdf_v0/")
async def procesar_y_generar_rdf_v0(file: UploadFile = File(...)):
    """
    Orquesta el procesamiento de un atestado y la generación del archivo RDF (versión v1).
    
    1. Llama internamente a la lógica de /procesar/ con el archivo subido.
    2. Convierte el resultado (diccionario) a un objeto Atestado (Pydantic).
    3. Genera el archivo RDF usando la lógica de /generar_rdf/.
    
    Parameters
    ----------
    file: UploadFile
        Archivo que contiene el atestado (PDF o DOCX).

    Returns
    -------
    StreamingResponse
        El archivo RDF generado.
    """
    
    # 1. Llamar a la función interna de /procesar/
    print("📝 Paso 1: Procesando atestado con /procesar/")
    
    try:
        # Asegurarse de que el puntero del archivo esté al inicio antes de llamar a la función interna.
        # (Aunque 'procesar_atestado' maneja su propia lectura, esto asegura la robustez).
        await file.seek(0)
        
        # Llamar a la función que implementa el endpoint /procesar/
        # (Nota: La función se llama 'procesar_atestado' en el scope de FastAPI, 
        # pero es la función asíncrona definida en @app.post("/procesar/")).
        resultado_procesamiento = await procesar_atestado(file)
        
    except HTTPException:
        # Re-lanzar HTTPExceptions sin modificar
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el paso de procesamiento: {str(e)}"
        )
        
    # 2. Verificar el resultado y convertir a Atestado Pydantic
    
    # Si el resultado es una cadena, es un mensaje de error o estado.
    if isinstance(resultado_procesamiento, str):
        raise HTTPException(
            status_code=400,
            detail=f"El procesamiento del atestado no resultó en un objeto Atestado válido. Resultado: {resultado_procesamiento}"
        )

    # Si es un diccionario (resultado exitoso de Atestado.model_dump())
    if isinstance(resultado_procesamiento, dict):
        try:
            # Eliminar 'descripcion', que es añadida por /procesar/ pero no está en el modelo Atestado
            atestado_data = resultado_procesamiento.copy()
            atestado_data.pop("descripcion", None)
            
            # Instanciar el modelo Pydantic Atestado
            atestado_obj = Atestado(**atestado_data) 
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error al crear el objeto Atestado a partir del resultado: {str(e)}"
            )
    else:
         raise HTTPException(
            status_code=500,
            detail=f"Resultado de procesamiento inesperado: {type(resultado_procesamiento)}"
        )
        
    # 3. Generar el archivo RDF usando la lógica de /generar_rdf/
    print("💾 Paso 2: Generando RDF con la lógica de /generar_rdf/")
    try:
        # Lógica interna de /generar_rdf/: crear_rdf(atestado)
        nombre_archivo = crear_rdf(atestado_obj)
        
        # Lógica interna de /generar_rdf/: abrir el archivo y devolver StreamingResponse
        ruta_completa = os.path.join(user_downloads_path(), nombre_archivo)
        rdf_file = open(ruta_completa, "rb")
        
        return StreamingResponse(
            rdf_file,
            media_type="application/xml",
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el paso de generación de RDF: {str(e)}"
        )
    
# --- Nuevo Endpoint ---
@app.post("/cargaNeo4jFile/")
async def carga_neo4jFile(request: Neo4jImportRequest):
    """
    Importa un archivo Turtle (.ttl) generado previamente en Neo4j.
    La configuración del servidor (Namespaces/n10s) se realiza automáticamente
    en la primera llamada a este servicio.
    """
    if not request.articles:
        raise HTTPException(
            status_code=404, 
            detail=f"Elementos del articulado a contrastar no encontrados"
        )
    
    if not request.root_name:
        raise HTTPException(
            status_code=404, 
            detail=f"Nombre del grafo no encontrado"
        )
    
    if not request.llm_type:
        raise HTTPException(
            status_code=404, 
            detail=f"Nombre del grafo no encontrado"
        )

    try:
        # 1. Importación del RDF (usando la lógica de traducción de rutas si es necesario)
        resultado_import = neo4j_client.import_turtle(request.file_path, request.llm_type, request.root_name)
        
        if resultado_import["terminationStatus"] == "OK":
            
            # PASO 2: Curación de datos (Nombres cortos y limpieza de URIs)
            print("🧹 Paso 2: Ejecutando curación de datos...")
            res_curacion = neo4j_client.curar_datos(request.root_name)
            
            # PASO 3: Generación de nodos raíz (Estructura de artículos)
            print(f"🌿 Paso 3: Generando clones para {request.root_name}...")
            total_creados = neo4j_client.generate_root(request.root_name, request.articles)
            
            # PASO 4: Clonación de subgrafos (Copia del atestado para cada artículo)
            print(f"📊 Paso 4: Clonando subgrafos para {len(request.articles)} artículos...")
            total_subgrafo = neo4j_client.generate_subgraphs(request.root_name, request.articles)
            
            # PASO 5: Decoración de probabilidades (Cálculo lógico/probabilístico)
            print("🎲 Paso 5: Calculando probabilidades de aplicación...")
            relaciones_prob = neo4j_client.decorate_probabilities(request.root_name, request.articles)
            
            return {
                "status": "success",
                "resumen": {
                    "triplas_importadas": resultado_import["triplesLoaded"],
                    "articulos_analizados": len(request.articles),
                    "curacion": res_curacion,
                    "procesamiento_grafo": {
                        "clones_creados": total_creados,
                        "articulos": request.articles,
                        "elementos_clonados": total_subgrafo,
                        "decoraciones_probabilisticas": relaciones_prob
                    }
                },
                "mensaje": "Flujo completo finalizado: El grafo está listo para análisis de probabilidad."
            }
        else:
            raise HTTPException(status_code=500, detail="Error en Neosemantics (KO)")

    except Exception as e:
        print(f"❌ Error en cargaNeo4j: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error durante la comunicación con Neo4j: {str(e)}"
        )
    
# --- Nuevo Endpoint ---
@app.post("/cargaNeo4j/")
async def carga_neo4j(
    file: UploadFile = File(...),
    root_name: str = Form(...),
    articles: str = Form(...), # Se recibe como string JSON por ser FormData
    llm_type: str = Form(...)
):
    """
    Importa un archivo Turtle (.ttl) generado previamente en Neo4j.
    La configuración del servidor (Namespaces/n10s) se realiza automáticamente
    en la primera llamada a este servicio.
    """

    # 1. Guardar el archivo recibido temporalmente para que Neo4j lo lea
    # Docker environtment
    temp_dir =os.getenv("ONTOLOGY_PATH")
    # temp_dir = tempfile.gettempdir() 
    filename = f"import/{uuid.uuid4()}_inferencias.ttl"
    temp_path = os.path.join(temp_dir, filename)
    print(f"📌 temp_path: {temp_path}")

    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # 1. Validar existencia del fichero
    if not os.path.exists(temp_path):
        raise HTTPException(
            status_code=404, 
            detail=f"Fichero no encontrado en la ruta: {temp_path}"
        )

    if not articles:
        raise HTTPException(
            status_code=404, 
            detail=f"Elementos del articulado a contrastar no encontrados"
        )
    
    if not root_name:
        raise HTTPException(
            status_code=404, 
            detail=f"Nombre del grafo no encontrado"
        )
    
    if not llm_type:
        raise HTTPException(
            status_code=404, 
            detail=f"Nombre del grafo no encontrado"
        )
    
    # Transformar el string JSON en una lista de Python
    l_articles = json.loads(articles)

    # Limpiar el nombre del elemento root class
    name = clean_uri(root_name)
    
    # Validar que efectivamente es una lista
    if not isinstance(l_articles, list):
        raise ValueError("El campo articles debe ser una lista")
    
    try:
        # 1. Importación del RDF (usando la lógica de traducción de rutas si es necesario)
        resultado_import = neo4j_client.import_turtle(temp_path, llm_type, name)
        
        if resultado_import["terminationStatus"] == "OK":
            
            # PASO 2: Curación de datos (Nombres cortos y limpieza de URIs)
            print("🧹 Paso 2: Ejecutando curación de datos...")
            res_curacion = neo4j_client.curar_datos(name)
            
            # PASO 3: Generación de nodos raíz (Estructura de artículos)
            print(f"🌿 Paso 3: Generando clones para {name}...")
            total_creados = neo4j_client.generate_root(name, l_articles)
            # total_creados = 0
            
            # PASO 4: Clonación de subgrafos (Copia del atestado para cada artículo)
            print(f"📊 Paso 4: Clonando subgrafos para {len(l_articles)} artículos...")
            total_subgrafo = neo4j_client.generate_subgraphs(name, l_articles)
            # total_subgrafo = 0
            
            # PASO 5: Decoración de probabilidades (Cálculo lógico/probabilístico)
            print("🎲 Paso 5: Calculando probabilidades de aplicación...")
            relaciones_prob = neo4j_client.decorate_probabilities(name, l_articles)
            # relaciones_prob = 0
            
            return {
                "status": "success",
                "resumen": {
                    "triplas_importadas": resultado_import["triplesLoaded"],
                    "articulos_analizados": len(l_articles),
                    "curacion": res_curacion,
                    "procesamiento_grafo": {
                        "clones_creados": total_creados,
                        "articulos": articles,
                        "elementos_clonados": total_subgrafo,
                        "decoraciones_probabilisticas": relaciones_prob
                    }
                },
                "mensaje": "Flujo completo finalizado: El grafo está listo para análisis de probabilidad."
            }
        else:
            raise HTTPException(status_code=500, detail="Error en Neosemantics (KO)")

    except Exception as e:
        print(f"❌ Error en cargaNeo4j: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error durante la comunicación con Neo4j: {str(e)}"
        )
    finally:
        if os.path.exists(temp_path): 
            os.remove(temp_path)
            print(f"\n📌carga_neo4j - Borrar - {temp_path}")
    

@app.post("/procesarReferenciasBase/")
async def procesar_referencias(file: UploadFile = File(...), article: str = Form(...)):
    """Procesa un atestado y recupera referencias desde Neo4j."""
    
    # 1. Validaciones iniciales
    if not article:
        raise HTTPException(status_code=400, detail="El parámetro 'article' es obligatorio")

    if article == "\"\"":
        art = None
    else:
        art = article

    print (f"{art}")

    extension = os.path.splitext(file.filename)[1].lower()
    if extension not in [".pdf", ".docx"]:
        raise HTTPException(status_code=400, detail="Formato no soportado. Use PDF o DOCX.")

    try:
        # 2. Guardar archivo temporal de forma segura
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. Extraer texto según extensión
        if extension == ".pdf":
            texto = leer_pdf(temp_path)
        else:
            texto = leer_docx(temp_path)
        
        # 4. Llamada a Neo4j (Nota: 'texto' se pasa si tu lógica lo requiere, 
        # pero aquí usamos 'article' para la query según tu código)
        resultado = neo4j_client.recuperar_referencias(art)

        # Limpieza
        os.remove(temp_path)

        return {"artículo": article, "referencias": resultado}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import os
import shutil
import re
from fastapi import UploadFile, HTTPException, File, Form

# @app.post("/procesarReferenciasSinHTML/")
# async def procesar_referencias_sin_html(file: UploadFile = File(...), article: str = Form(...)):
#     """Procesa un atestado, busca referencias en el texto y lo enriquece."""
    
#     if not article:
#         raise HTTPException(status_code=400, detail="El parámetro 'article' es obligatorio")

#     extension = os.path.splitext(file.filename)[1].lower()
#     if extension not in [".pdf", ".docx"]:
#         raise HTTPException(status_code=400, detail="Formato no soportado. Use PDF o DOCX.")

#     temp_path = f"/tmp/{file.filename}"
#     try:
#         # 1. Guardar y leer archivo
#         with open(temp_path, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)

#         texto_enriquecido = leer_pdf(temp_path) if extension == ".pdf" else leer_docx(temp_path)
        
#         # 2. Obtener referencias de Neo4j 
#         # (Se asume que devuelve lista de tuplas: [(origen, relación, destino, ref), ...])
#         referencias = neo4j_client.recuperar_referencias(article)

#         # 3. Enriquecer el texto
#         # Diccionario para emoticonos numéricos (1-10) o formato genérico (n)
#         def obtener_circulo(n):
#             circulos = {
#                 1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤", 
#                 6: "⑥", 7: "⑦", 8: "⑧", 9: "⑨", 10: "⑩"
#             }
#             return circulos.get(n, f"({n})")

#         for i, ref_tuple in enumerate(referencias, start=1):
#             # La referencia es el cuarto elemento de la tupla: rel.ns0__referencia
#             nombre_referencia = str(ref_tuple[3]) 
#             emoticono = obtener_circulo(i)
            
#             # Reemplazamos en el texto (usando regex para evitar reemplazos parciales de palabras)
#             # Ejemplo: Si la referencia es "REF-100", busca "REF-100" y pone "REF-100 ①"
#             patron = re.compile(re.escape(nombre_referencia), re.IGNORECASE)
#             texto_enriquecido = patron.sub(f"{nombre_referencia} {emoticono}", texto_enriquecido)

#         # 4. Limpieza
#         if os.path.exists(temp_path):
#             os.remove(temp_path)

#         return {
#             "artículo": article,
#             "total_referencias_encontradas": len(referencias),
#             "texto_procesado": texto_enriquecido
#         }

#     except Exception as e:
#         if os.path.exists(temp_path):
#             os.remove(temp_path)
#         raise HTTPException(status_code=500, detail=str(e))




# --- ENDPOINT ---
@app.post("/procesarReferencias/")
async def procesar_referencias(file: UploadFile = File(...), root_name = Form(...)):
    if not file:
        raise HTTPException(status_code=400, detail="Documento no proporcionado")
    
    if not root_name:
        raise HTTPException(status_code=400, detail="Nombre de root_class no proporcionado")

    ext = os.path.splitext(file.filename)[1].lower()
    
    try:
        # 1. Leer el contenido del archivo directamente a memoria
        contenido_bytes = await file.read()

        # 2. Extraer texto sin guardar en disco
        # Nota: Asegúrate de que tus funciones leer_pdf/leer_docx acepten bytes 
        # o usa io.BytesIO para simular un archivo en memoria
        
        file_memory = io.BytesIO(contenido_bytes)
        texto_raw = leer_pdf_memoria(file_memory) if ext == ".pdf" else leer_docx_memoria(file_memory)
        
        # 3. Obtener datos de Neo4j
        # Limpiar el nombre del elemento root class
        name = clean_uri(root_name)
        referencias_data = neo4j_client.recuperar_referencias(name)

        # 4. Enriquecer (usando la lógica de comillas y retroceso)
        texto_enriquecido = enriquecer_texto_con_estrategia(texto_raw, referencias_data)
        
        # 5. Generar HTML
        html_final = generar_documento_html_azul(texto_enriquecido, "")

        return {
            "status": "ok", 
            "referencias_encontradas": len(referencias_data),
            "html_content": html_final
        }

    except Exception as e:
        # Importante: loguear el error para debug
        print(f"Error en procesar_referencias: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # # Limpieza del archivo de entrada siempre
        # if os.path.exists(temp_in):
        #     os.remove(temp_in)
        pass

# --- ESTRATEGIA DE BÚSQUEDA ---
def buscar_y_marcar(texto: str, frag: str, badge_html: str, tooltip_text: str, i: int) -> str:
    """Aplica la estrategia de búsqueda e inserta el badge con tooltip."""

    fragmento = frag.replace('\\"', 'TEMP_QUOTE').replace('"', '').replace('TEMP_QUOTE', '"').strip()
    if len(fragmento) < 3: 
        return texto

    # Creamos el envoltorio con tooltip. 
    # Usamos el atributo 'title' para el tooltip nativo del navegador.
    enriquecimiento = f'<strong title="{tooltip_text}">{fragmento}</strong>{badge_html}'

    # 1. Intento exacto
    patron_exacto = re.compile(re.escape(fragmento), re.IGNORECASE)
    if patron_exacto.search(texto):
        print(f"\t✔ Encontrado exacto {i}: {fragmento}")
        return patron_exacto.sub(enriquecimiento, texto)

    # 2. Estrategia de retroceso
    palabras = fragmento.split()
    for j in range(1, len(palabras)):
        sub_frase = " ".join(palabras[j:])
        if len(sub_frase) < 10: 
            break 
        
        patron_sub = re.compile(re.escape(sub_frase), re.IGNORECASE)
        if patron_sub.search(texto):
            print(f"\t✔ Encontrado parcial {i}: {fragmento}")
            # Re-generamos el enriquecimiento para la sub_frase
            enriquecimiento_sub = f'<strong title="{tooltip_text}">{sub_frase}</strong>{badge_html}'
            return patron_sub.sub(enriquecimiento_sub, texto, count=1)
    
    print("\t❌ No Encontrado " + str(i) + ": " + fragmento) 
   
    return texto

def enriquecer_texto_con_estrategia(texto: str, referencias: List[Tuple]) -> str:
    """Procesa referencias y construye la terna para el tooltip."""
    texto_final = texto
    
    print(f"📌 Enriquecer_texto_con_estrategia Encontrando...")
    for i, ref_tuple in enumerate(referencias, start=1):
        # Terna de Neo4j: origen (0), relación (1), destino (2)
        # Formateamos el texto que aparecerá al dejar el ratón encima
        # tooltip_info = f"Origen: {ref_tuple[0]} | Relación: {ref_tuple[1]} | Destino: {ref_tuple[2]}"
        tooltip_info = f"{ref_tuple[0]} {ref_tuple[1]} {ref_tuple[2]}"
        
        # Estilo del badge (se mantiene igual, pero envuelto para soportar el tooltip si fuera necesario)
        badge = f'<span class="badge" title="{tooltip_info}">{i}</span>'
        
        referencia_raw = str(ref_tuple[3])
        fragmentos = referencia_raw.split('|')
        
        for frag in fragmentos:
            texto_final = buscar_y_marcar(texto_final, frag, badge, tooltip_info, i)
                
    return texto_final

# --- GENERACIÓN DE HTML (Mejorado para Tooltips) ---
def generar_documento_html_azul(texto_contenido: str, article: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; padding: 30px; background-color: #f4f7f6; }}
            .container {{ max-width: 900px; margin: auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h2 {{ color: #2c3e50; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
            .content {{ white-space: pre-wrap; word-wrap: break-word; font-size: 1.1em; }}
            
            /* Estilo para el texto con tooltip */
            strong {{ 
                color: #2980b9; 
                cursor: help; 
                border-bottom: 1px dashed #2980b9; 
                text-decoration: none;
            }}
            
            .badge {{ 
                display: inline-block; background-color: #007bff; color: white; 
                border-radius: 50%; width: 22px; height: 22px; text-align: center; 
                font-size: 13px; line-height: 22px; font-weight: bold; margin-left: 5px;
                box-shadow: 1px 1px 3px rgba(0,0,0,0.2);
                cursor: help;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Atestado Enriquecido {article}</h2>
            <div class="content">{texto_contenido}</div>
        </div>
    </body>
    </html>
    """

from fastapi.responses import HTMLResponse

@app.post("/recuperarTuplasGrafo/")
# async def recuperar_tuplas_grafo(article: Optional[str] = Query(None)): 
async def recuperar_tuplas_grafo(root_name: str = Form(...), article: str = Form(...)):
    """
    Recupera relaciones (3 o 4 campos) y nodos del grafo.
    Invocado con /recuperarTuplasGrafo/?article=NombreArticulo o sin parámetros para None.
    """
    try:
        # Normalizar el valor de article
        print (f"ℹ️ recuperarTuplasGrafo")
        art_param = None if (article is None or article == "None") else article
        name = clean_uri(root_name)
        print (f"ℹ️ article: {article} art_param: {art_param}")

        # 1. Invocar las funciones solicitadas
        relaciones = neo4j_client.recuperar_relaciones(name, art_param)
        print (f"✅ Recuperando relaciones: {relaciones}")
        elementos = neo4j_client.recuperar_nodos(name,  art_param)
        print (f"✅ Recuperando nodos: {elementos}")

        # 2. Generar el HTML con la lógica de columnas dinámica
        html_content = generar_documento_tablas_azul(relaciones, elementos, art_param)
        print (f"✅ HTML generado")

        return {
            "status": "ok", 
            "name": name,
            "relaciones_encontradas": len(relaciones),
            "nodos_encontrados": len(elementos),
            "relaciones": relaciones,
            "nodos" : elementos
        }

    except Exception as e:
        print(f"Error en recuperarTuplasGrafo: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/recuperarResultados/")
# async def recuperar_tuplas_grafo(article: Optional[str] = Query(None)): 
async def recuperar_resultados(root_name: str = Form(...)):
    """
    Recupera relaciones (3 o 4 campos) y nodos del grafo.
    Invocado con /recuperarResultados/?article=NombreArticulo o sin parámetros para None.
    """
    try:
        # Normalizar el valor de article
        print (f"ℹ️ recuperarResultados")
        name = clean_uri(root_name)


        # 1. Invocar las funciones solicitadas
        resultados_probabilidad = neo4j_client.recuperar_resultados(name) 
        print (f"✅ Recuperando resultados_probabilidad: {resultados_probabilidad}")

        return {
            "status": "ok", 
            "name": name,
            "num_articulos": len(resultados_probabilidad),
            "resultados_probabilidad": resultados_probabilidad
        }

    except Exception as e:
        print(f"Error en recuperarResultados: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recuperarTuplasGrafoHTML/")
# async def recuperar_tuplas_grafo(article: Optional[str] = Query(None)): 
async def recuperar_tuplas_grafo_html(root_name: str = Form(...), article: str = Form(...)):
    """
    Recupera relaciones (3 o 4 campos) y nodos del grafo.
    Invocado con /recuperarTuplasGrafo/?article=NombreArticulo o sin parámetros para None.
    """

    try:
        # Normalizar el valor de article
        print (f"ℹ️ recuperarTuplasGrafo")
        art_param = None if (article is None or article == "None") else article
        name = clean_uri(root_name)
        print (f"ℹ️ article: {article} art_param: {art_param}")

        # 1. Invocar las funciones solicitadas
        relaciones = neo4j_client.recuperar_relaciones(name, art_param)
        print (f"✅ Recuperando relaciones: {relaciones}")
        elementos = neo4j_client.recuperar_nodos(name,  art_param)
        print (f"✅ Recuperando nodos: {elementos}")

        # 2. Generar el HTML con la lógica de columnas dinámica
        html_content = generar_documento_tablas_azul(relaciones, elementos, art_param)
        print (f"✅ HTML generado")

        return {
            "status": "ok", 
            "relaciones_encontradas": len(relaciones),
            "nodos_encontrados": len(elementos),
            "html_content": html_content
        }

    except Exception as e:
        print(f"Error en recuperarTuplasGrafo: {e}")
        raise HTTPException(status_code=500, detail=str(e))



def generar_documento_tablas_azul(relaciones: List[Tuple], elementos: List[Tuple], article_name: str = None) -> str:
    # Determinar si hay 4 columnas (cuando hay referencia) o 3
    tiene_referencia = len(relaciones) > 0 and len(relaciones[0]) == 4
    header_art = article_name if article_name else "General (None)"

    # Cabecera de relaciones
    thead_rel = "<th>Origen</th><th>Relación</th><th>Destino</th>"
    if tiene_referencia:
        thead_rel += "<th>Tipo</th>"

    # Construir filas de relaciones
    filas_rel = ""
    for r in relaciones:
        filas_rel += "<tr>"
        filas_rel += f"<td>{r[0]}</td><td><span class='rel-tag'>{r[1]}</span></td><td>{r[2]}</td>"
        if tiene_referencia:
            filas_rel += f"<td class='ref-text'>{r[3]}</td>"
        filas_rel += "</tr>"

    # Construir filas de elementos
    filas_el = ""
    for el in elementos:
        filas_el += f"<tr><td><strong>{el[0]}</strong></td><td>{el[1]}</td><td class='prop-text'>{el[2]}</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; padding: 30px; background-color: #f4f7f6; }}
            .container {{ max-width: 1100px; margin: auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            h1 {{ color: #2c3e50; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
            h2 {{ color: #2980b9; margin-top: 30px; border-left: 5px solid #007bff; padding-left: 15px; margin-bottom: 20px; }}
            
            /* Ajustes para DataTables para seguir la estética azul */
            .dataTables_wrapper .dataTables_paginate .paginate_button.current {{
                background: #007bff !important; color: white !important; border: 1px solid #007bff !important;
            }}
            table.dataTable thead th {{ background-color: #007bff; color: white; border-bottom: 1px solid #0056b3; }}
            .rel-tag {{ background: #e1f0ff; color: #007bff; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em; }}
            .ref-text {{ font-style: italic; color: #666; }}
            .prop-text {{ color: #2c3e50; font-family: monospace; font-size: 0.9em; }}
            .dataTables_filter input {{ border: 1px solid #ddd; border-radius: 4px; padding: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Visor de Grafo - Artículo: {header_art}</h1>
            
            <h2>Relaciones</h2>
            <table id="tablaRelaciones" class="display">
                <thead><tr>{thead_rel}</tr></thead>
                <tbody>{filas_rel}</tbody>
            </table>

            <br><hr><br>

            <h2>Elementos (Nodos)</h2>
            <table id="tablaElementos" class="display">
                <thead><tr><th>Nombre</th><th>Tipos</th><th>Propiedades</th></tr></thead>
                <tbody>{filas_el}</tbody>
            </table>
        </div>

        <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        
        <script>
            $(document).ready(function() {{
                $('#tablaRelaciones').DataTable({{
                    "pageLength": 10,
                    "language": {{
                        "url": "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json"
                    }}
                }});
                $('#tablaElementos').DataTable({{
                    "pageLength": 10,
                    "language": {{
                        "url": "//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json"
                    }}
                }});
            }});
        </script>
    </body>
    </html>
    """