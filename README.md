# 🏺 ReportGraphQualifier

**ReportGraphQualifier** es un ecosistema desarrollado para **Atenea Research Group** enfocado en la gestión y calificación de grafos de conocimiento (Knowledge Graphs). El sistema permite la ingesta de datos semánticos, su almacenamiento en grafos y una interfaz visual para su análisis.

## 🏗️ Arquitectura del Sistema

El proyecto está completamente dockerizado y se compone de:
* **Neo4j 5.x:** Base de datos de grafos con soporte RDF mediante `n10s` (neosemantics).
* **FastAPI:** Backend en Python para la lógica de negocio y procesamiento de datos.
* **React + Vite:** Frontend interactivo con Hot Reload configurado para entornos Docker.

---

## 📥 Instalación y Despliegue (Máquina Limpia)

Sigue estos pasos para desplegar el entorno desde cero:

### 1. Requisitos previos
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y en ejecución.
* [Git](https://git-scm.com/) instalado.

### 2. Clonar el repositorio
```bash
git clone https://github.com/atenearesearchgroup/onto-property-crime.git

cd ReportGraphQualifier

* Activación y arranque de los módulos del docker
```bash
docker-compose up -d

* Comprobar que los módulos están activos
```bash
docker-compose ps

* Resultado
```bash
             Name                            Command               State                       Ports
------------------------------------------------------------------------------------------------------------------------
reportgraphqualifier_backend_1    uvicorn api:app --host 0.0 ...   Up      0.0.0.0:8000->8000/tcp,:::8000->8000/tcp
reportgraphqualifier_database_1   tini -g -- /startup/docker ...   Up      7473/tcp,
                                                                           0.0.0.0:7474->7474/tcp,:::7474->7474/tcp,
                                                                           0.0.0.0:7687->7687/tcp,:::7687->7687/tcp
reportgraphqualifier_frontend_1   docker-entrypoint.sh npm r ...   Up      0.0.0.0:5173->5173/tcp,:::5173->5173/tcp
