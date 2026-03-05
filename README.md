# 🏺 onto-property-crime

**onto-property-crime** is an ecosystem developed for **Atenea Research Group** focused on the management and judicial classification of police reports guided by ontology and knowledge graphs. The system extracts semantic data, stores it in graphs, and provides a visual interface for technical and legal analysis.

**onto-property-crime** is an ecosystem developed for the **Atenea Research Group** focused on the management and qualification of knowledge graphs. The system allows for semantic data ingestion, its storage in graphs, and a visual interface for its analysis.

## 🏗️ System Architecture

The project is fully dockerized and consists of:
* **Neo4j 5.x:** Graph database with RDF support via `n10s` (neosemantics).
* **FastAPI:** Python backend for business logic and data processing.
* **React + Vite:** Interactive frontend with Hot Reload configured for Docker environments.

---

## 📥 Installation and Deployment (Clean Machine)

Follow these steps to deploy the environment from scratch:

### Prerequisites
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
* [Git](https://git-scm.com/) installed.

### Clone the repository
```
git clone https://github.com/atenearesearchgroup/onto-property-crime.git
cd ReportGraphQualifier
```

* Activation and startup of the docker modules
```
docker-compose up -d
```

* Check that the modules are running
```
docker-compose ps
```

* Result
```
             Name                            Command               State                       Ports
------------------------------------------------------------------------------------------------------------------------
reportgraphqualifier_backend_1    uvicorn api:app --host 0.0 ...   Up      0.0.0.0:8000->8000/tcp,:::8000->8000/tcp
reportgraphqualifier_database_1   tini -g -- /startup/docker ...   Up      7473/tcp,
                                                                           0.0.0.0:7474->7474/tcp,:::7474->7474/tcp,
                                                                           0.0.0.0:7687->7687/tcp,:::7687->7687/tcp
reportgraphqualifier_frontend_1   docker-entrypoint.sh npm r ...   Up      0.0.0.0:5173->5173/tcp,:::5173->5173/tcp
```

---

## 📝 SoftwareX Note to Reviewers

> **Important Note:** In order to activate the information extraction module, reviewers must request the `OPENROUTER_API_KEY` for the `backend/.env` file by contacting **xxx@xxxx.xx** prior to using the tool.