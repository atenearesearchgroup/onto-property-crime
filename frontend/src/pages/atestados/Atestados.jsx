import './Atestados.css';
import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { FiUpload, FiTrash2, FiDownload, FiLoader, FiSearch, FiDatabase, FiShare2, FiFileText, FiCheck, 
  FiRefreshCw } from 'react-icons/fi';
import { MdExtension } from 'react-icons/md';
import docs from '../../assets/docs.png';
import noArchivo from '../../assets/noArchivo.png';
import { useApp } from '../../AppContext';

// --- COMPONENTE STEPPER (OPCIÓN 1) ---
const Stepper = ({ currentStep, t }) => {
  const steps = [
    { id: 1, icon: <FiUpload />, label: t('atestados.steps.step1') },
    { id: 2, icon: <FiSearch />, label: t('atestados.steps.step2') },
    { id: 3, icon: <FiDownload />, label: t('atestados.steps.step3') },
    { id: 4, icon: <MdExtension />, label: t('atestados.steps.step4') },
    { id: 5, icon: <FiDatabase />, label: t('atestados.steps.step5') },
  ];

  return (
    <div className="stepper-container">
      {steps.map((step, index) => {
        const isCompleted = currentStep > step.id;
        const isActive = currentStep === step.id;
        
        return (
          <div key={step.id} className={`step-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
            {/* Círculo del paso */}
            <div className="step-circle">
              {isCompleted ? <FiCheck className="step-check-icon" /> : step.icon}
            </div>
            
            {/* Etiqueta */}
            <span className="step-label">{step.label}</span>

            {/* Línea conectora (excepto en el último elemento) */}
            {index !== steps.length - 1 && (
              <div className={`step-line ${currentStep > step.id ? 'line-completed' : ''}`}></div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default function Atestados() {
  const [file, setFile] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [loading, setLoading] = useState(false);
  const [popup, setPopup] = useState(false);
  const [error, setError] = useState(null);
  const overlayRef = useRef(null);
  const fileInputRef = useRef(null);
  const [inferring, setInferring] = useState(false);
  const { t } = useApp();

  const jsonFileInputRef = useRef(null);

  const [importing, setImporting] = useState(false);
  const [importSuccess, setImportSuccess] = useState(null); 
  const [ttlBlob, setTtlBlob] = useState(null);
  const [taskId, setTaskId] = useState(null);

  const [actionHistory, setActionHistory] = useState({
    procesar: { status: 'esperando', msg: t('atestados.messages.waiting') },
    inferir: { status: 'esperando', msg: t('atestados.messages.waiting') },
    descargar: { status: 'esperando', msg: t('atestados.messages.waiting') },
    neo4j: { status: 'esperando', msg: t('atestados.messages.waiting') }
  });

  const [debugJson, setDebugJson] = useState(null);

  // --- DEFINICIÓN DE PASOS CON ICONOS ---
  const steps = [
    { id: 1, icon: <FiUpload />, label: t('atestados.steps.step1') },
    { id: 2, icon: <FiSearch />, label: t('atestados.steps.step2') },
    { id: 3, icon: <FiDownload />, label: t('atestados.steps.step3') },
    { id: 4, icon: <MdExtension />, label: t('atestados.steps.step4') }, // Icono Puzzle
    { id: 5, icon: <FiDatabase />, label: t('atestados.steps.step5') },
  ];

  // Lógica para determinar el paso actual automáticamente
  const getCurrentStep = () => {
    if (actionHistory.neo4j.status === 'ok') return 6; // Todo completado
    if (ttlBlob) return 5; // Listo para importar (Paso 4 hecho)
    // El paso 3 es descarga opcional, pero si tenemos resultado, estamos técnicamente listos para inferir (paso 4)
    // Visualmente, si hay resultado, marcamos que hemos pasado el 2.
    if (resultado) return 3; 
    if (file) return 2; // Archivo seleccionado, listo para procesar
    return 1; // Inicio
  };

  const activeStep = getCurrentStep();

  const StatusBadge = ({ status }) => {
    const styles = {
      ok: { color: '#28a745', fontWeight: 'bold' },
      error: { color: '#dc3545', fontWeight: 'bold' },
      esperando: { color: '#6c757d' }
    };
    const labelKey = status === 'ok' ? 'common.status.ok' : 
                     status === 'error' ? 'common.status.error' : 
                     'common.status.waiting';

    return <span style={styles[status] || styles.esperando}>{t(labelKey)}</span>;
  };

  const ARTICULOS_DEFAULT = [
    "Article240_1", "Article242_1", "Article234_1", "Article234_2", 
    "Article234_3", "Article235_1", "Article235_2", "Article236_1", 
    "Article236_2", "Article240_2", "Article241_1", "Article241_4", 
    "Article242_2", "Article242_3", "Article242_4"
  ];

  // Manejo de accesibilidad para el popup
  useEffect(() => {
    if (!popup) return;
    const overlay = overlayRef.current;
    if (overlay) overlay.focus();

    const handleKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setPopup(false);
      }
    };
    overlay?.addEventListener('keydown', handleKey);
    return () => { 
      overlay?.removeEventListener('keydown', handleKey); 
    };
  }, [popup]);

  // --- EFECTO DE POLLING ---
  useEffect(() => {
    let intervalId;
    if (taskId) {
      intervalId = setInterval(async () => {
        try {
          console.log("Consultando estado de la tarea:", taskId);
          const response = await axios.get(`http://localhost:8000/check_task/${taskId}`);
          const { status, result } = response.data;
          
          if (status === 'completado') {
            clearInterval(intervalId);
            setTaskId(null);
            setLoading(false);
            setPopup(false);
            setResultado(result.grafo_json);
            setDebugJson(result.grafo_json);
            
            if (result) {
              const fileName = result.archivo_procesado || 'resultado_analisis.json';
              const jsonString = JSON.stringify(result.grafo_json, null, 2);
              const blob = new Blob([jsonString], { type: 'application/json' });
              const url = window.URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = fileName.endsWith('.json') ? fileName : `${fileName}.json`;
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
              window.URL.revokeObjectURL(url);
            }
            
            setActionHistory(prev => ({ 
              ...prev, 
              procesar: { status: 'ok', msgKey: 'atestados.msg.success' } 
            }));
          } 
          else if (status === 'error') {
            clearInterval(intervalId);
            setTaskId(null);
            setLoading(false);
            setPopup(false);
            setActionHistory(prev => ({ 
              ...prev, 
              procesar: { status: 'error', msgKey: 'atestados.msg.error' } 
            }));
          }
          else {
            setPopup(true);
          }
        } catch (err) {
          console.error("Error consultando estado:", err);
          clearInterval(intervalId);
          setTaskId(null);
          setLoading(false);
          setPopup(false);
        }
      }, 3000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [taskId]);

  const handleChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      setFile(selected);
      setResultado(null);
      setTtlBlob(null);
      setDebugJson(null);
      setActionHistory({
        procesar: { status: 'esperando', msg: '-' },
        descargar: { status: 'esperando', msg: '-' },
        inferir: { status: 'esperando', msg: '-' },
        neo4j: { status: 'esperando', msg: '-' }
      });
      setError(null);
    }
  };

  const handleDelete = () => {
    setFile(null);
    setResultado(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setPopup(true);
    setError(null);
    
    setActionHistory(prev => ({ 
        ...prev, 
        procesar: { status: 'procesando', msgKey: 'atestados.msg.processing' } 
    }));

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8000/procesarG/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.data.task_id) {
        setTaskId(response.data.task_id);
      } else {
        throw new Error("No se recibió task_id");
      }
    } catch (err) {
      console.error(err);
      setActionHistory(prev => ({ ...prev, procesar: { status: 'error', msg: err.message }}));
      setLoading(false);
      setPopup(false);
    }
  };

  const handleManualJsonUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setFile(file);
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsedJson = JSON.parse(event.target.result);
        setDebugJson(parsedJson);
        setResultado(parsedJson);
        descargarRDF(parsedJson);
      } catch (err) {
        alert("Error: El archivo seleccionado no es un JSON válido.");
      }
    };
    reader.readAsText(file);
  };

  const handleGenRDFClick = () => {
    if (resultado) {
      descargarRDF(resultado);
    } else {
      jsonFileInputRef.current.click();
    }
  };

  const handleInferirClick = () => {
    if (resultado) {
      handleInferencia(resultado);
    } else {
      jsonFileInputRef.current.click();
    }
  };

  const descargarRDF = async (json) => {
    try {
      const response = await axios.post("http://localhost:8000/generar_rdfG/", json, {
        responseType: 'blob'   
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', json.nombre_grafo + '.rdf');
      document.body.appendChild(link);
      link.click();
      link.remove();
      setActionHistory(prev => ({ ...prev, descargar: { status: 'ok', msg: t('atestados.messages.success') }}));
      setDebugJson(null);
    } catch (err) {
      console.error("Error al descargar el RDF:", err);
      setActionHistory(prev => ({ ...prev, descargar: { status: 'error', msg: t('atestados.messages.error') }}));
    }
  };

  const handleInferencia = async (json) => {
    if (!resultado) return;
    setInferring(true);
    setError(null);
    try {
        const response = await axios.post("http://localhost:8000/inferir_grafo_ttls/", json, {
        responseType: 'blob'   
        });
        const blob = new Blob([response.data], { type: 'text/turtle' });
        setTtlBlob(blob);

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', json.nombre_grafo + '.ttls');
        document.body.appendChild(link);
        link.click();
        link.remove();
        setActionHistory(prev => ({ ...prev, inferir: { status: 'ok', msg: t('atestados.messages.success') }}));
        setDebugJson(null);
    } catch (err) {
        console.error("Error en la inferencia:", err);
        setActionHistory(prev => ({ ...prev, inferir: { status: 'error', msg: t('atestados.messages.error') }}));
    } finally {
        setInferring(false);
    }
  };

  const handleImportNeo4j = async () => {
    if (!ttlBlob) return;
    setImporting(true);
    setImportSuccess(null);
    try {
      const fileToUpload = new File([ttlBlob], "grafo_importar.ttl", { type: "text/turtle" });
      const formData = new FormData();
      const file_name = file.name.split('.').slice(0, -1).join('.')

      formData.append('file', fileToUpload);
      formData.append('root_name', file_name);
      formData.append('articles', JSON.stringify(ARTICULOS_DEFAULT));
      formData.append('llm_type', "ttls");

      const response = await axios.post('http://localhost:8000/cargaNeo4j/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });

      if (response.data.status === "success") {
        setActionHistory(prev => ({ ...prev, neo4j: { status: 'ok', msg: response.data.mensaje }}));
        setDebugJson(response.data);
      } else {
        setActionHistory(prev => ({ ...prev, neo4j: { status: 'error', msg: response.data.mensaje }}));
      }
    } catch (err) {
      console.error("Error en la importación:", err);
      setActionHistory(prev => ({ ...prev, neo4j: { status: 'error', msg: 'Error de conexión' }}));
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="atestados-wrapper">
      <h1>{t('atestados.principalTitle')}</h1>
      <p className="subtitulo">{t('atestados.subtitle')}</p>
      
      <input 
        type="file" 
        ref={jsonFileInputRef} 
        style={{ display: 'none' }} 
        accept=".json"
        onChange={handleManualJsonUpload}
      />

      {/* COMPONENTE STEPPER MODERNO */}
      {/* <Stepper currentStep={activeStep} t={t} /> */}
      {/* --- STEPPER CON ICONOS (CORREGIDO) --- */}
      <div className="pasos-container">
        {steps.map((step, index) => {
            const isCompleted = activeStep > step.id;
            const isActive = activeStep === step.id;
            
            return (
            <div key={step.id} className={`paso-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
                {/* La línea solo aparece ANTES del paso, excepto en el primero */}
                {index !== 0 && (
                  <div className={`linea-conectora ${activeStep >= step.id ? 'line-completed' : ''}`}></div>
                )}
                
                <div className="paso-circulo">
                  {/* Si está completado: Check. Si no: Icono representativo del paso */}
                  {isCompleted ? <FiCheck /> : step.icon}
                </div>
                <div className="paso-etiqueta">{step.label}</div>
            </div>
            );
        })}
      </div>

      {/* CONTENEDOR DE BOTONES ALINEADOS HORIZONTALMENTE */}
      <div className="acciones-atestados">
        <input
          type="file"
          accept=".pdf,.docx"
          ref={fileInputRef}
          onChange={handleChange}
          style={{ display: 'none' }}
        />
        
        {/* BOTÓN 1: SELECCIONAR */}
        <button 
          className="btn archivo-btn" 
          onClick={() => fileInputRef.current.click()}
          aria-label= {t('atestados.btns.select')}
        >
          <FiUpload style={{ marginRight: '8px' }} />
          1. {t('atestados.btns.select')}
        </button>

        {/* BOTÓN 2: PROCESAR */}
        <button 
          className="btn procesar-btn" 
          onClick={handleUpload} 
          disabled={!file || loading}
          aria-label={t('atestados.btns.process')}
        >
          {loading ? <FiRefreshCw className="spinner-mini" /> : <FiRefreshCw className="icon-static" style={{ marginRight: '8px' }} />} 
          2. {t('atestados.btns.process')}
        </button>

        {/* BOTÓN 3: DESCARGAR */}
          <button 
            className="btn descargar-btn" 
            onClick={handleGenRDFClick} 
            disabled={loading}
            title={!resultado ? t('atestados.btns.download_tooltip') : t('atestados.btns.download')}
          >
            <FiDownload style={{ marginRight: '8px' }} />
           3. {t('atestados.btns.download')} {(!resultado ? '*' : '')}
          </button>

        {/* BOTÓN 4: INFERIR */}
        <button 
          className="btn inferir-btn" 
          onClick={handleInferirClick} 
          disabled={!resultado || loading}
        >
          {inferring ? <FiLoader className="spinner-mini" /> : <MdExtension style={{ marginRight: '8px' }} />}
          4. {t('atestados.btns.infer')}
        </button>

        {/* BOTÓN 5: IMPORTAR A NEO4J */}
        <button 
          className="btn importar-btn" 
          onClick={handleImportNeo4j} 
          disabled={!ttlBlob || loading}
        >
          {importing ? <FiLoader className="spinner-mini-import" /> : <FiDatabase style={{ marginRight: '8px' }} />}
          5. {t('atestados.btns.import')}
        </button>
      </div>

      <div className="procesamiento-grid">
        {/* Lado Izquierdo: Vista previa del archivo */}
        <div className="archivo-container">
          <div className="preview-card">
            <img src={file ? docs : noArchivo} alt="Vista previa" />
            <p className="file-name">{file ? file.name : t('atestados.preview.no_file')}</p>
            {file && (
              <button className="delete-btn" onClick={handleDelete} title="Eliminar archivo">
                <FiTrash2 />
              </button>
            )}
          </div>
        </div>

        <div className="resultado-container">
          <div className="resultado-card">
            <h3>{t('atestados.panel.title')}</h3>
            
            <table className="status-table">
              <thead>
                <tr>
                  <th>{t('atestados.panel.col_action')}</th>
                  <th>{t('atestados.panel.col_status')}</th>
                  <th>{t('atestados.panel.col_detail')}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>{t('atestados.panel.actions.process')}</strong></td>
                  <td><StatusBadge status={actionHistory.procesar.status} /></td>
                  <td>{actionHistory.procesar.msg}</td>
                </tr>
                <tr>
                  <td><strong>{t('atestados.panel.actions.download')}</strong></td>
                  <td><StatusBadge status={actionHistory.descargar.status} /></td>
                  <td>{actionHistory.descargar.msg}</td>
                </tr>
                <tr>
                  <td><strong>{t('atestados.panel.actions.infer')}</strong></td>
                  <td><StatusBadge status={actionHistory.inferir.status} /></td>
                  <td>{actionHistory.inferir.msg}</td>
                </tr>
                <tr>
                  <td><strong>{t('atestados.panel.actions.import')}</strong></td>
                  <td><StatusBadge status={actionHistory.neo4j.status} /></td>
                  <td>{actionHistory.neo4j.msg}</td>
                </tr>
              </tbody>
            </table>

            <details className="json-details" style={{ marginTop: '20px' }}>
              <summary>{t('atestados.debug.title')}</summary>
              <div className="json-viewer">
                {debugJson ? (
                  <pre>{JSON.stringify(debugJson, null, 2)}</pre>
                ) : (
                  <p className="placeholder-text">{t('atestados.debug.no_data')}</p>
                )}
              </div>
            </details>
          </div>
        </div>
      </div>

      {popup && (
        <div className="popup-overlay" ref={overlayRef} tabIndex="-1" role="dialog">
          <div className="popup-loader">
            <div className="spinner" />
            <p>{t('atestados.loading.title')}</p>
            <small>{t('atestados.loading.wait')}</small>
          </div>
        </div>
      )}
    </div>
  );
}