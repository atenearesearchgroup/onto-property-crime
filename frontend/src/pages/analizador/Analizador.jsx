import './Analizador.css';
import '../atestados/Atestados.css'; // Importamos los estilos de Atestados
import { useRef, useState, useEffect } from 'react';
import axios from 'axios';
import noArchivo from '../../assets/noArchivo.png';
import docs from '../../assets/docs.png';
import { FiUpload, FiSearch, FiRotateCw, FiDownload, FiFileText, FiLoader, FiDatabase, FiShare2, FiTrash2, FiCheck  } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../AppContext';


// Componente para los semáforos de estado
const StatusBadge = ({ status }) => {
  const { t } = useApp();
  const styles = {
    ok: { color: '#28a745', fontWeight: 'bold' },
    error: { color: '#dc3545', fontWeight: 'bold' },
    esperando: { color: '#6c757d' }
  };
  const labels = { ok: '● Éxito', error: '● Error', esperando: '○ Pendiente' };
  return <span style={styles[status]}>{labels[status]}</span>;
};

export default function Analizador() {
  const [error, setError] = useState(null);
  const [popupTexto, setPopupTexto] = useState(null);
  const {t, file, setFile, actionStatus, setActionStatus,debugJson, setDebugJson } = useApp();
  

  const imageRef = useRef(null);
  const visualRef = useRef(null);
  const overlayRef = useRef(null);
  const fileInputRef = useRef(null);

  const navigate = useNavigate();

  // const [actionHistory, setActionHistory] = useState({
  //   referencias: { status: 'esperando'},
  //   resumen: { status: 'esperando' },
  //   resultados: { status: 'esperando' }
  // });

  // --- DEFINICIÓN DE PASOS CON ICONOS ---
  const steps = [
    { id: 1, icon: <FiUpload />, label: t('analizador.steps.step1') },
    { id: 2, icon: <FiDownload />, label: t('analizador.steps.step2') },
    { id: 3, icon: <FiSearch />, label: t('analizador.steps.step3') },
    { id: 4, icon: <FiRotateCw />, label: t('analizador.steps.step4') }, // Icono Puzzle
  ];

  // Lógica para determinar el paso actual automáticamente
  const getCurrentStep = () => {
    if (actionStatus.resultado.status === 'ok') return 5; // Todo completado
    if (actionStatus.resumen.status === 'ok') return 4; // Listo para importar (Paso 4 hecho)
    if (actionStatus.referencias.status === 'ok') return 3; 
    if (file) return 2; // Archivo seleccionado, listo para procesar
    return 1; // Inicio
  };

  const activeStep = getCurrentStep();



  useEffect(() => {
    if (!popupTexto) return;
    const overlay = overlayRef.current;
    if (overlay) overlay.focus();
    const handleKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setPopupTexto(null);
      }
    };
    overlay?.addEventListener('keydown', handleKey);
    return () => overlay?.removeEventListener('keydown', handleKey);
  }, [popupTexto]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      fileInputRef.current?.click();
    }
  };


  const handleDelete = () => {
    setFile(null);
    setError(null);
    setPopupTexto(null);
    setDebugJson(null); // Para mostrar el JSON
    setActionStatus(prev => ({
  ...prev,
      referencias: { status: 'esperando', msg: '-' },
      resumen: { status: 'esperando', msg: '-' },
      resultado: { status: 'esperando', msg: '-' }
    }));
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // 1. MODIFICACIÓN: Separar carga de generación.
  // Esta función ahora solo actualiza el estado del archivo.
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setDebugJson(null); // Limpiar resultados previos
      setActionStatus(prev => ({
      ...prev,
        referencias: { status: 'esperando', msg: '-' },
        resumen: { status: 'esperando', msg: '-' },
        resultado: { status: 'esperando', msg: '-' } 
      }));
    }
  };

  
const descargarReferencias = async () => {
    if (!file) return;
    setPopupTexto(t('analizador.loading.references'));

    try {
      const data = new FormData();
      data.append("file", file);
      data.append("root_name", file.name.split('.').slice(0, -1).join('.'));

      const response = await axios.post("http://localhost:8000/procesarReferencias/", data);

      const info = response.data;

      if (info.html_content) {
        // 1. Guardamos el HTML en el almacenamiento de la sesión
        sessionStorage.setItem('html_referencias', info.html_content);
        
        // 2. Abrimos la nueva pestaña apuntando a nuestra ruta de React
        window.open('/analizador/visor', '_blank');
        
        setDebugJson(info);
        setActionStatus(prev => ({
          ...prev,
          referencias: { status: 'ok', msg: `${info.referencias_encontradas} ` + t('analizador.ok.references') }
        }));
      }
    } catch (err) {
      console.error(err);
      setActionStatus(prev => ({
      ...prev, 
        referencias: { status: 'error', msg: t('common.error') } }));
    } finally {
      setPopupTexto(null);
    }
  };

  const descargarResumen = async () => {
    if (!file) return;
    setPopupTexto(t('analizador.loading.summary'));

    try {
      const data = new FormData();
      data.append("root_name", file.name.split('.').slice(0, -1).join('.'));
      data.append("article", "None");

      const response = await axios.post("http://localhost:8000/recuperarTuplasGrafo/", data);

      const info = response.data;
      // if (info.html_content) {
      if (info.status == "ok") {
        // Guardamos con una clave específica para el resumen
        // sessionStorage.setItem('html_visor_contenido', info.html_content);
        // sessionStorage.setItem('visor_titulo', 'Resumen de Tuplas y Relaciones');    
        // // Abrimos el visor
        // window.open('/analizador/visor', '_blank');
        
        setDebugJson(info);
        setActionStatus(prev => ({
          ...prev,
          resumen: { status: 'ok', msg: ` ${info.relaciones_encontradas} - ${info.nodos_encontradas} ` + t('analizador.ok.summary') }
        }));

        sessionStorage.setItem('datos_resumen_grafo', JSON.stringify(info));
        navigate('/analizador/resumen');
      }
    } catch (err) {
      console.error(err);
      setActionStatus(prev => ({
        ...prev,
        resumen: { status: 'error', msg:  t('common.error') }
      }));
    } finally {
      setPopupTexto(null);
    }
};

const verResultados = async () => {
    setPopupTexto(t('analizador.loading.results'));
    try {
      const data = new FormData();
      data.append("root_name", file.name.split('.').slice(0, -1).join('.'));
      const response = await axios.post('http://localhost:8000/recuperarResultados/', data);

       const info = response.data;
      if (info.status == "ok") {
        setDebugJson(info);
        setActionStatus(prev => ({
          ...prev,
          resultado: { status: 'ok', msg: `${info.num_articulos} ` + t('analizador.ok.results')}
        }));
        sessionStorage.setItem('datos_resultado_grafo', JSON.stringify(info));
        navigate('/analizador/resultado');
      }
    } catch (err) {
      console.error(err);
      setActionStatus(prev => ({
        ...prev,
        resultado: { status: 'error', msg: t('common.error') }
      }));
    } finally {
      setPopupTexto(null);
    }
  };

  return (
    <div className="analizador-wrapper">
      <h1 tabIndex="0">{t('analizador.title')}</h1>
      <p className="subtitulo" tabIndex="0">
        {t('analizador.subtitle')}
      </p>

      {/* Mostrar errores si existen */}
      {error && <p className="error-mensaje" style={{color: 'red', textAlign:'center'}}>{error}</p>}

      {/* <div className="pasos">
        <div className="paso" tabIndex="0"><span>1</span>{t('analizador.steps.step1')}</div>
        <div className="paso" tabIndex="0"><span>2</span>{t('analizador.steps.step2')}</div>
        <div className="paso" tabIndex="0"><span>3</span>{t('analizador.steps.step3')}</div>
        <div className="paso" tabIndex="0"><span>4</span> {t('analizador.steps.step4')}</div>
      </div> */}

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

      <div className="analizador-formulario">
        <input
          type="file"
          accept=".pdf,.docx"
          id="rdfInput"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        <label
          htmlFor="rdfInput"
          className="btn archivo-btn"
          aria-label="Seleccionar archivo"
          tabIndex="0"
          onKeyDown={handleKeyDown}
          style={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}
        >
          <FiUpload style={{ marginRight: '6px' }} />
          {/* Cambiamos el texto dinámicamente para feedback visual */}
          1. {file ? file.name : t('analizador.btns.select')}
        </label>


        <button
          className="btn referenciar-btn"
          onClick={descargarReferencias}
          disabled={!file} 
          aria-label="Atestado referenciado"
          style={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}
        >
          <FiDownload aria-hidden="true" style={{ marginRight: '6px' }} />
          2. {t('analizador.btns.references')}
        </button>
        {/* ----------------------------- */}

        {/* Botón Resumen */}
        <button
          className="btn analizar-btn"
          onClick={descargarResumen}
          disabled={!file} 
          aria-label="Resumen Atestado"
        >
          <FiSearch aria-hidden="true" style={{ marginRight: '6px' }} />
          3. {t('analizador.btns.summary')}
        </button>
        
        {/* Botón Resultado */}
        <button
          className="btn resultado-btn"
          onClick={verResultados}
          disabled={!file} 
          aria-label="Resultados Atestado"
        >
          {/* <FiRotateCw aria-hidden="true" style={{ marginRight: '6px' }} /> */}
          <FiRotateCw aria-hidden="true" style={{ marginRight: '6px' }} />
          4. {t('analizador.btns.results')}
        </button>
      </div>

      <div className="main-content">
        {/* COLUMNA IZQUIERDA: CARGA */}
        <div className="archivo-container">
          <div className="archivo-container">
            <div className="preview-card">
              <img src={file ? docs : noArchivo} alt="Vista previa" />
              <p className="file-name">{file ? file.name : t('analizador.preview.no_file')}</p>
              {file && (
                <button className="delete-btn" onClick={handleDelete} title="Eliminar archivo">
                  <FiTrash2 />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* COLUMNA DERECHA: RESULTADOS */}
        <div className="resultado-container">
          <div className="resultado-card">
            <h3>{t('analizador.panel.title')}</h3>
            <table className="status-table">
              <thead>
                <tr>
                  <th>{t('analizador.panel.col_process')}</th>
                  <th>{t('analizador.panel.col_status')}</th>
                  <th>{t('analizador.panel.col_detail')}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{t('analizador.panel.rows.references')}</td>
                  <td><StatusBadge status={actionStatus.referencias.status} /></td>
                  <td>{actionStatus.referencias.msg}</td>
                </tr>
                <tr>
                  <td>{t('analizador.panel.rows.summary')}</td>
                  <td><StatusBadge status={actionStatus.resumen.status} /></td>
                  <td>{actionStatus.resumen.msg}</td>
                </tr>
                <tr>
                  <td>{t('analizador.panel.rows.results')}</td>
                  <td><StatusBadge status={actionStatus.resultado.status} /></td>
                  <td>{actionStatus.resultado.msg}</td>
                </tr>
              </tbody>
            </table>

            <details className="json-details">
              <summary>{t('analizador.debug.title')}</summary>
              <div className="json-viewer">
                {debugJson ? (
                  <pre>{JSON.stringify(debugJson, null, 2)}</pre>
                ) : (
                  <p style={{ color: '#888' }}>{t('analizador.debug.waiting')}</p>
                )}
              </div>
            </details>
          </div>
        </div>
      </div>

      {/* Popups de carga */}
      {popupTexto && (
        <div className="popup-overlay">
          <div className="popup-loader">
            <div className="spinner" />
            <p>{popupTexto}</p>
          </div>
        </div>
      )}
    </div>
  );
}