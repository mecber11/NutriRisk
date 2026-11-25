import ClassificationResults, { ClassificationFigures } from '../components/ClassificationResults';
import ClassificationHyperparameters from '../components/ClassificationHyperparameters';
import PublicDatasetExplorer from '../components/PublicDatasetExplorer';
import { VisualExplanation } from '../components/VisualExplanation';
import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, downloadFile, getAccessToken } from '../api/client';
import { Badge, Card, ErrorBox, Loading } from '../components/ui';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';

type RecordData = Record<string, any>;
const fmt = (x: unknown, scale = 1) => typeof x === 'number' ? (x * scale).toFixed(4) : '—';
const names: Record<string,string> = {
  random_forest:'Random Forest',xgboost:'XGBoost',catboost:'CatBoost',spatial_xgboost:'XGBoost + GP espacial',cnn_lstm:'CNN-LSTM',baseline_mean:'Media de entrenamiento',baseline_persistence:'Persistencia histórica',
  train:'Entrenamiento',validation:'Validación',
  n_estimators:'Número de árboles',max_depth:'Profundidad máxima',min_samples_leaf:'Mínimo de muestras por hoja',max_features:'Fracción de variables',iterations:'Iteraciones',depth:'Profundidad',learning_rate:'Tasa de aprendizaje',l2_leaf_reg:'Regularización L2',reg_lambda:'Regularización lambda',subsample:'Fracción de muestras',hidden:'Unidades LSTM',channels:'Canales convolucionales',weight_decay:'Decaimiento de pesos',epochs:'Épocas',
  algorithm:'Modelo',region:'Región',held_out_region:'Región excluida',fold:'Pliegue',trial:'Ensayo',validation_mae:'MAE de validación',parameters:'Hiperparámetros',train_n:'Casos de entrenamiento',validation_n:'Casos de validación',
  statistic:'Estadístico',pvalue:'Valor p',skewness:'Asimetría',excess_kurtosis:'Exceso de curtosis',warning:'Interpretación',test:'Prueba',expected:'Valor esperado',permutations:'Permutaciones',weights:'Vecindad',coordinate_proxy:'Capitales como aproximación',mae:'MAE',rmse:'RMSE',r2:'R²',n:'Casos',
  range:'Intervalo',log:'Escala logarítmica',gp_fixed:'Configuración espacial fija',length_scale_degrees:'Escala geográfica (grados)',signal_variance:'Varianza de señal',white_noise:'Ruido blanco',alpha:'Regularización del proceso gaussiano',optimizer:'Optimizador',training_unit:'Unidad de ajuste',file:'Archivo',url:'Fuente original',sha256:'Huella de integridad',bytes:'Tamaño (bytes)',retrieved_utc:'Fecha de descarga',api_metadata:'Metadatos de origen',
  gdp_per_capita_constant_usd:'PIB real por habitante',basic_drinking_water_pct:'Acceso a agua básica',basic_sanitation_pct:'Saneamiento básico',electricity_access_pct:'Acceso a electricidad',urban_population_pct:'Población urbana',population_density:'Densidad de población',fertility_births_per_woman:'Fertilidad',female_secondary_enrollment_pct:'Matrícula secundaria femenina',pm25_exposure:'Exposición a PM2.5',stunting_prevalence_pct:'Prevalencia de retraso del crecimiento',
};
const label=(key:string)=>names[key] || key.replace(/_/g,' ');
const downloadLabels:Record<string,string>={'evidence.zip':'Evidencia completa','results.json':'Resultados completos','metrics.csv':'Métricas','predictions.csv':'Predicciones','regional_metrics.csv':'Métricas regionales','pairwise_statistics.csv':'Pruebas por pares','epochs.csv':'Curvas de entrenamiento','trials.csv':'Ensayos e hiperparámetros','country_panel.csv':'Datos públicos','manifest.json':'Procedencia de los datos','artifact_hashes.json':'Integridad de archivos','verification.json':'Verificaciones realizadas','README.md':'Guía de los datos'};
const num=(value:number)=>value!==0&&Math.abs(value)<.0001?value.toExponential(2):Number.isInteger(value)?String(value):value.toLocaleString('es-PE',{maximumFractionDigits:4});
function Value({value}:{value:unknown}) {
  if(value==null)return <>—</>;
  if(typeof value==='number')return <>{num(value)}</>;
  if(typeof value==='boolean')return <>{value?'Sí':'No'}</>;
  if(typeof value==='string'){
    if(value.trim().startsWith('{')){try{return <Value value={JSON.parse(value)}/>;}catch{/* plain text */}}
    return <>{names[value] || value}</>;
  }
  if(Array.isArray(value))return <>{value.map((x,i)=><span key={i}>{i>0?' · ':''}<Value value={x}/></span>)}</>;
  return <dl className="research-values">{Object.entries(value as RecordData).map(([key,v])=><div key={key}><dt>{label(key)}</dt><dd><Value value={v}/></dd></div>)}</dl>;
}
function DataDetails({value}:{value:unknown}) {return <Table rows={Object.entries((value||{}) as RecordData).map(([key,v])=>({Campo:label(key),Valor:v}))}/>;}
function Table({rows}: {rows: RecordData[]}) {
  if (!rows.length) return <p>Sin registros.</p>;
  const keys = Array.from(new Set(rows.flatMap(Object.keys)));
  return <div style={{overflowX:'auto'}}><table className="data-table"><thead><tr>{keys.map(k=><th key={k}>{label(k)}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={i}>{keys.map(k=><td key={k}><Value value={row[k]}/></td>)}</tr>)}</tbody></table></div>;
}
function SearchSpace({algorithm,space}:{algorithm:string;space:RecordData}) {
  const configuration=algorithm==='spatial_xgboost'?space.xgboost:space;
  const categorical=['n_estimators','iterations','hidden','channels','epochs'];
  return <><Table rows={Object.entries(configuration).map(([key,v])=>({Hiperparámetro:label(key),Tipo:categorical.includes(key)?'Opciones discretas':'Intervalo de búsqueda',Valores:Array.isArray(v)?v.join(categorical.includes(key)?' / ':' a '):(v as RecordData).range?.join(' a '),Escala:(v as RecordData).log?'Logarítmica':'Lineal'}))}/>{algorithm==='spatial_xgboost'&&<><p>El componente espacial usa una configuración fija.</p><DataDetails value={space.gp_fixed}/></>}</>;
}
function DifferencePlot({pairs}:{pairs:RecordData[]}) {
  const lo=Math.min(0,...pairs.map(p=>p.bootstrap_mean_difference_ci.lower*100));
  const hi=Math.max(0,...pairs.map(p=>p.bootstrap_mean_difference_ci.upper*100));
  const x=(v:number)=>400+(v-lo)/(hi-lo||1)*470;
  return <div style={{overflowX:'auto'}}><svg role="img" aria-label="Diferencias de MAE e intervalos de confianza por pares" viewBox="0 0 1000 440" style={{minWidth:720,width:'100%'}}>
    <line x1={x(0)} x2={x(0)} y1={15} y2={370} stroke="#94a3b8" strokeDasharray="5 4"/>
    {pairs.map((p,i)=>{const y=30+i*34;return <g key={p.a+p.b}><text x={5} y={y+5} fontSize={13} fill="#334155">{label(p.a)} / {label(p.b)}</text><line x1={x(p.bootstrap_mean_difference_ci.lower*100)} x2={x(p.bootstrap_mean_difference_ci.upper*100)} y1={y} y2={y} stroke="#168b94" strokeWidth={3}/><circle cx={x(p.mean_mae_difference*100)} cy={y} r={5} fill="#0f4c5c"/></g>;})}
    {[lo,0,hi].map((v,i)=><text key={i} x={x(v)} y={392} textAnchor="middle" fontSize={12} fill="#475569">{v.toFixed(2)}</text>)}
    <text x={635} y={425} textAnchor="middle" fontSize={13} fill="#334155">Diferencia de MAE en puntos porcentuales · IC 95 %</text>
  </svg></div>;
}
function Preview({name,title}: {name:string;title:string}) {
  const [url,setUrl]=useState('');
  useEffect(()=>{const controller=new AbortController(); let objectUrl=''; fetch(`/api/v1/research/real/files/${name}.svg`,{headers:{Authorization:`Bearer ${getAccessToken()}`},signal:controller.signal}).then(r=>{if(!r.ok)throw Error();return r.blob();}).then(b=>{objectUrl=URL.createObjectURL(b);setUrl(objectUrl);}).catch(()=>undefined); return()=>{controller.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);};},[name]);
  return url ? <img src={url} alt={title} style={{width:'100%',background:'white'}}/> : <p>Cargando figura…</p>;
}
export default function Research() {
  const query=useQuery({queryKey:['research','real'],queryFn:()=>api.get<RecordData>('/research/real/latest')});
  const trials=useQuery({queryKey:['research','real','trials'],queryFn:()=>api.get<{items:RecordData[]}>('/research/real/trials')});
  const audit=useQuery({queryKey:['research','audit'],queryFn:()=>api.get<{items:RecordData[]}>('/research/audit')});
  const [search,setSearch]=useState(''); const [page,setPage]=useState(0); const [error,setError]=useState('');
  const location=useLocation();
  const [tab,setTab]=useState('resumen');
  useEffect(()=>{setTab(location.pathname==='/datasets'?'datos':location.pathname==='/modelos'?'modelos':'resumen');window.scrollTo({top:0,behavior:'auto'});},[location.pathname]);
  function selectTab(next:string){setTab(next);window.scrollTo({top:0,behavior:'auto'});}
  const [statsView,setStatsView]=useState('comparacion');
  const [metricStage,setMetricStage]=useState('test');
  const [overviewModel,setOverviewModel]=useState('cnn_lstm');
  const [model,setModel]=useState('cnn_lstm'); const [region,setRegion]=useState('');
  async function download(name:string){try{setError('');await downloadFile(`/research/real/files/${name}`,name);}catch(e){setError(String(e));}}
  if(query.isLoading)return <Loading label="Cargando evidencia real…"/>;
  if(query.error || !query.data)return <ErrorBox message={String(query.error || 'No hay ejecución real')}/>;
  const {results:r,gallery,manifest:m,verification}=query.data; const s=r.statistics;
  const filtered=(trials.data?.items||[]).filter(row=>JSON.stringify(row).toLowerCase().includes(search.toLowerCase()));
  const regions=r.data_summary.regions as string[];
  const chosenRegion=region||regions[0];
  const fold=r.folds.find((f:RecordData)=>f.algorithm===model&&f.region===chosenRegion);
  const parameters=Object.entries(fold?.hyperparameters||{}).map(([key,value])=>({Hiperparámetro:label(key),'Valor seleccionado':value}));
  const candidates=(trials.data?.items||[]).filter(t=>t.algorithm===model&&t.held_out_region===chosenRegion).map(t=>({ensayo:Number(t.trial)+1,error:Number(t.validation_mae)*100}));
  let best=Infinity; const progress=candidates.map(t=>{best=Math.min(best,t.error);return {...t,mejor:best};});
  const metricChart=r.models.filter((x:RecordData)=>!x.algorithm.startsWith('baseline_')).map((x:RecordData)=>({modelo:label(x.algorithm),Entrenamiento:x.metrics.train.mae*100,Validación:x.metrics.validation.mae*100,Prueba:x.metrics.test.mae*100}));

  const comparable=r.models.filter((x:RecordData)=>!x.algorithm.startsWith('baseline_'));
  const ranked=[...comparable].sort((a:RecordData,b:RecordData)=>a.metrics.test.mae-b.metrics.test.mae);
  const winner=ranked[0];
  const rankedData=ranked.map((x:RecordData)=>({modelo:label(x.algorithm),mae:x.metrics.test.mae*100}));
  const countryPredictions=r.predictions.filter((x:RecordData)=>x.algorithm===overviewModel);
  const shortRegion=(x:string)=>({'East Asia & Pacific':'Asia oriental y Pacífico','Europe & Central Asia':'Europa y Asia central','Latin America & Caribbean':'América Latina y Caribe','Middle East, North Africa, Afghanistan & Pakistan':'Oriente Medio y norte de África','North America':'Norteamérica','South Asia':'Asia meridional','Sub-Saharan Africa':'África subsahariana'}[x.trim()]||x.trim());
  const regionalPrevalence=regions.map(region=>{const rows=countryPredictions.filter((x:RecordData)=>x.region===region);return {región:shortRegion(region),Publicada:rows.reduce((sum:number,x:RecordData)=>sum+x.observed,0)/rows.length*100,Estimada:rows.reduce((sum:number,x:RecordData)=>sum+x.predicted,0)/rows.length*100,países:rows.length};});
  const scatter=countryPredictions.map((x:RecordData)=>({publicada:x.observed*100,estimada:x.predicted*100,país:x.country_name}));
  const tabs=[
    ['resumen','Predicción de desnutrición (Recall / ROC-AUC)'],
    ['panorama','Panorama de desnutrición'],
    ['modelos','Estimación continua'],
    ['hiperparametros','Hiperparámetros'],
    ['estadistica','Pruebas estadísticas'],
    ['datos','Dataset de desnutrición y factores'],
    ['descargas','Figuras y descargas']
  ];
  return <div className="nr-workspace">
    <header className="nr-heading"><div><div className="nr-eyebrow">PREDICCIÓN DE DESNUTRICIÓN INFANTIL · IA CON DATOS REALES</div><h1>Predicción de desnutrición infantil con datos reales</h1><p>Modelos de aprendizaje automático para predecir el riesgo de desnutrición integrando determinantes públicos oficiales (Banco Mundial / UNICEF / OMS)</p></div><div className="nr-heading-actions"><Badge tone="ok">Modelos entrenados</Badge><button className="btn btn-primary" onClick={()=>void download('evidence.zip')}>↓ Exportar evidencia</button></div></header>
    {error&&<ErrorBox message={error}/>}
    <div className="nr-kpis">{[{value:r.data_summary.countries,title:'Países evaluados',detail:'Datos de desnutrición global',symbol:'◎'},{value:regions.length,title:'Regiones de evaluación',detail:'Validación geográfica',symbol:'◈'},{value:comparable.length,title:'Modelos predictivos',detail:'35 ajustes exteriores',symbol:'▥'},{value:r.protocol.completed_trial_fits,title:'Ensayos de optimización',detail:'10 por modelo y región',symbol:'⌁'}].map(kpi=><div className="nr-kpi" key={kpi.title}><div className="nr-kpi-icon" aria-hidden="true">{kpi.symbol}</div><div><span>{kpi.title}</span><strong>{kpi.value}</strong><small>{kpi.detail}</small></div></div>)}</div>
    <nav className="nr-tabs" role="tablist" aria-label="Secciones de investigación">{tabs.map(([key,title])=><button key={key} id={`tab-${key}`} role="tab" aria-selected={tab===key} aria-controls={`panel-${key}`} onClick={()=>selectTab(key)}>{title}</button>)}</nav>
    <section role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="nr-panel" key={tab}>
    {tab==='resumen'&&<ClassificationResults/>}
    {tab==='panorama'&&<>
      <div className="nr-section-heading"><div><h2>Panorama de la predicción de desnutrición</h2><p>Evaluación predictiva externa en 2023 · {r.data_summary.test_countries} países · 9 determinantes de desnutrición</p></div><label className="nr-inline-filter">Modelo de predicción<select aria-label="Modelo del resumen" value={overviewModel} onChange={e=>setOverviewModel(e.target.value)}>{comparable.map((x:RecordData)=><option value={x.algorithm} key={x.algorithm}>{label(x.algorithm)}</option>)}</select></label></div>
      <div className="nr-overview-grid">
        <Card title="Comparación de modelos predictivos" subtitle="Error absoluto medio en prueba externa · menor es mejor" actions={<span className="nr-unit">MAE · pp</span>}>
          <div className="nr-chart" style={{height:285}}><ResponsiveContainer><BarChart data={rankedData} layout="vertical" margin={{left:10,right:35,top:5,bottom:5}}><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tick={{fontSize:11}}/><YAxis type="category" dataKey="modelo" width={138} tick={{fontSize:11}} axisLine={false} tickLine={false}/><Tooltip formatter={(v:number)=>`${v.toFixed(3)} pp`}/><Bar isAnimationActive={false} dataKey="mae" name="MAE de prueba" radius={[0,5,5,0]} barSize={23}>{rankedData.map((x:RecordData,i:number)=><Cell key={x.modelo} fill={i===0?'#10a396':'#88aaaF'}/>) }<LabelList dataKey="mae" position="right" formatter={(v:number)=>v.toFixed(2)} style={{fontSize:11,fill:'#557584'}}/></Bar></BarChart></ResponsiveContainer></div><VisualExplanation interpretation="Las barras comparan el MAE de los cinco regresores en los mismos países de prueba. Menor error es mejor." explanation="El MAE promedia distancias absolutas entre prevalencia publicada y estimada, expresadas en puntos porcentuales." limitations="Esta figura pertenece a regresión. No es recall ni ROC-AUC y no demuestra superioridad estadística."/>
          <div className="nr-chart-note"><span className="nr-note-dot"/><div><strong>{label(winner.algorithm)} · {fmt(winner.metrics.test.mae,100)} pp</strong><span>Menor error observado entre los cinco modelos predictivos. Las diferencias no son estadísticamente significativas.</span></div></div>
        </Card>
        <Card title="Desnutrición infantil por región" subtitle="Promedio de prevalencia de retraso del crecimiento publicada vs estimada" actions={<span className="nr-unit">%</span>}>
          <div className="nr-chart" style={{height:285}}><ResponsiveContainer><BarChart data={regionalPrevalence} layout="vertical" margin={{left:5,right:15,top:5,bottom:5}}><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tick={{fontSize:11}}/><YAxis type="category" dataKey="región" width={160} tick={{fontSize:10}} axisLine={false} tickLine={false}/><Tooltip formatter={(v:number)=>`${v.toFixed(2)} %`}/><Legend iconType="circle" wrapperStyle={{fontSize:12}}/><Bar isAnimationActive={false} dataKey="Publicada" fill="#163e52" radius={[0,3,3,0]} barSize={8}/><Bar isAnimationActive={false} dataKey="Estimada" fill="#20ae9e" radius={[0,3,3,0]} barSize={8}/></BarChart></ResponsiveContainer></div><VisualExplanation interpretation="Se comparan prevalencias publicadas y estimadas para cada región con el modelo seleccionado." explanation="Cada barra promedia las prevalencias de los países de esa región; se recalcula desde las predicciones externas de 2023." limitations="Media simple de países sin ponderación poblacional; no es una estimación regional oficial ni un efecto causal."/>
          <div className="nr-caption">Promedios nacionales de desnutrición infantil (retraso del crecimiento) sin ponderación poblacional.</div>
        </Card>
      </div>
      <div className="nr-bottom-grid"><Card title="Qué concluye la comparación" subtitle="Pruebas sobre siete bloques regionales"><div className="nr-finding"><span className="nr-finding-value">{fmt(s.friedman.pvalue)}</span><div><strong>Valor p de Friedman</strong><p>No se detecta superioridad estadística entre los cinco modelos.</p></div></div><div className="nr-inline-summary"><span>Kendall W <strong>{fmt(s.kendall_w)}</strong></span><span>Contrastes significativos <strong>0 / 10</strong></span></div><button className="nr-text-button" onClick={()=>selectTab('estadistica')}>Explorar las pruebas estadísticas →</button></Card>
      <Card title="Cómo se evaluó" subtitle="Separación temporal y geográfica"><div className="nr-timeline"><div><span>01</span><strong>Entrenamiento</strong><small>2002–2021</small></div><div><span>02</span><strong>Validación</strong><small>2022</small></div><div><span>03</span><strong>Prueba externa</strong><small>2023</small></div></div><div className="nr-caption">Las etiquetas de la región evaluada se excluyeron del ajuste. Se utilizaron ventanas de tres años de determinantes de desnutrición.</div><button className="nr-text-button" onClick={()=>selectTab('datos')}>Consultar datos y metodología →</button></Card></div>
      <div className="nr-scope-note"><strong>Propósito del software</strong><span>Modelos de IA integrados en NutriRisk AI para predecir el riesgo poblacional de desnutrición infantil a partir de determinantes socioeconómicos, nutricionales y ambientales verificables.</span></div>
    </>}
    {tab==='modelos'&&<>
      <div className="nr-section-heading"><div><h2>Rendimiento de los modelos</h2><p>Errores, incertidumbre y comportamiento fuera de muestra.</p></div></div>
    <Card title="Métricas de entrenamiento, validación y prueba" subtitle="MAE y RMSE en puntos porcentuales (pp); R² adimensional. IC 95 % de prueba mediante 1 000 bootstrap de siete regiones.">
      <div style={{height:340}}><ResponsiveContainer><BarChart data={metricChart} margin={{bottom:45,left:10,right:20}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="modelo" angle={-15} textAnchor="end" height={65} tick={{fontSize:11}}/><YAxis label={{value:'MAE (pp)',angle:-90,position:'insideLeft'}}/><Tooltip formatter={(v:number)=>`${v.toFixed(3)} pp`}/><Legend/><Bar isAnimationActive={false} dataKey="Entrenamiento" fill="#9ccfca"/><Bar isAnimationActive={false} dataKey="Validación" fill="#2a9d8f"/><Bar isAnimationActive={false} dataKey="Prueba" fill="#164e63"/></BarChart></ResponsiveContainer></div><VisualExplanation interpretation="Las barras muestran el cambio del error absoluto entre ajuste, seguimiento y prueba externa." explanation="Las etapas usan etiquetas de años distintos. La prueba reúne predicciones de regiones que no estuvieron en el ajuste." limitations="Los ajustes de entrenamiento se solapan. Una diferencia de barras no constituye por sí sola un contraste estadístico."/>
      <div className="nr-table-toolbar"><h3>Detalle de métricas</h3><label>Etapa de evaluación<select aria-label="Etapa de evaluación" value={metricStage} onChange={e=>setMetricStage(e.target.value)}><option value="test">Prueba externa · 2023</option><option value="validation">Validación · 2022</option><option value="train">Entrenamiento · hasta 2021</option></select></label></div>
      <Table rows={r.models.filter((x:RecordData)=>x.metrics[metricStage]).map((x:RecordData)=>({Modelo:label(x.algorithm),'MAE (pp)':fmt(x.metrics[metricStage].mae,100),'RMSE (pp)':fmt(x.metrics[metricStage].rmse,100),'R²':fmt(x.metrics[metricStage].r2),'IC 95 % del MAE':metricStage==='test'?`${fmt(x.test_ci.mae.lower,100)} – ${fmt(x.test_ci.mae.upper,100)}`:'—','IC 95 % del RMSE':metricStage==='test'?`${fmt(x.test_ci.rmse.lower,100)} – ${fmt(x.test_ci.rmse.upper,100)}`:'—','IC 95 % de R²':metricStage==='test'?`${fmt(x.test_ci.r2.lower)} – ${fmt(x.test_ci.r2.upper)}`:'—'}))}/>
      <div className="nr-caption">Las referencias de media y persistencia se muestran en la tabla; la persistencia dispone de la etiqueta histórica del país y tiene una ventaja de información.</div>
      <p>Las métricas agregadas de entrenamiento y validación son promedios entre pliegues; los países se repiten en el entrenamiento externo. No representan una muestra adicional independiente. Las baselines sin ajuste no tienen métricas train/validation.</p>
    </Card>

      <div className="nr-overview-grid"><Card title="Prevalencia publicada frente a estimada" subtitle="Cada punto representa un país de prueba"><label className="nr-inline-filter">Modelo<select aria-label="Modelo del gráfico de dispersión" value={overviewModel} onChange={e=>setOverviewModel(e.target.value)}>{comparable.map((x:RecordData)=><option key={x.algorithm} value={x.algorithm}>{label(x.algorithm)}</option>)}</select></label><div style={{height:340}}><ResponsiveContainer><ScatterChart margin={{top:20,right:25,bottom:25,left:20}}><CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="publicada" name="Prevalencia publicada" unit=" %" label={{value:'Prevalencia publicada (%)',position:'insideBottom',offset:-15}}/><YAxis type="number" dataKey="estimada" name="Prevalencia estimada" unit=" %" label={{value:'Estimada (%)',angle:-90,position:'insideLeft'}}/><ZAxis range={[35,35]}/><Tooltip cursor={{strokeDasharray:'3 3'}}/><Scatter isAnimationActive={false} data={scatter} fill="#13a696" fillOpacity={.7}/></ScatterChart></ResponsiveContainer></div><VisualExplanation interpretation="Cada punto muestra el grado de coincidencia para un país entre prevalencia publicada y estimada." explanation="El eje horizontal es JME; el vertical es la predicción de regresión fuera de región. Las desviaciones revelan errores de estimación." limitations="No son observaciones clínicas individuales. Estas puntuaciones no se utilizan como probabilidades del clasificador."/><p className="nr-caption">Estimaciones fuera de la región de entrenamiento para {label(overviewModel)}.</p></Card>
      <Card title="Referencia histórica" subtitle="Comparador con información adicional"><div className="nr-baseline-value">{fmt(r.models.find((x:RecordData)=>x.algorithm==='baseline_persistence').metrics.test.mae,100)}<span>pp de MAE</span></div><h3>Persistencia del año anterior</h3><p className="nr-caption">Reutiliza la prevalencia publicada de 2022 del mismo país. Su error es mucho menor que el de los cinco modelos.</p><div className="nr-scope-note"><span>Dispone de una etiqueta histórica que los modelos transferibles no reciben. Su ventaja y el suavizado temporal de JME limitan cualquier afirmación de valor añadido.</span></div></Card></div>
      <details className="nr-details nr-block-details"><summary>Resultados regionales y limitaciones del estudio</summary>    <Card title="Resultados por región y límites de interpretación">
      <details><summary>Métricas regionales completas</summary><Table rows={r.regional_metrics}/></details>
      <ul>{r.limitations.map((text:string)=><li key={text}>{text}</li>)}</ul>
      <p>El entrenamiento y los archivos están terminados; esta pantalla consulta evidencia existente. No se declara validación de pacientes, despliegue clínico, ejecución de n8n, LangFlow, PostgreSQL, MLflow o MinIO a partir de estos resultados.</p>
    </Card>
</details>
    </>}
    {tab==='hiperparametros'&&<><ClassificationHyperparameters/><details className="nr-details nr-block-details"><summary>Ver la optimización del experimento de estimación continua</summary>
      <div className="nr-section-heading"><div><h2>Optimización e hiperparámetros</h2><p>Diez ensayos por modelo y región. Explora la búsqueda y la configuración seleccionada.</p></div></div>
      <Card title="Explorar un ajuste" subtitle="Los filtros actualizan parámetros, métricas y curva de optimización.">
        <div className="research-filters"><label>Modelo para explorar<select aria-label="Modelo para explorar" value={model} onChange={e=>setModel(e.target.value)}>{Object.keys(r.hyperparameter_space).map(key=><option key={key} value={key}>{label(key)}</option>)}</select></label><label>Región excluida<select aria-label="Región excluida" value={chosenRegion} onChange={e=>setRegion(e.target.value)}>{regions.map(key=><option key={key} value={key}>{shortRegion(key)}</option>)}</select></label></div>
        <div className="nr-tuning-grid"><div><h3>Configuración seleccionada</h3><Table rows={parameters}/></div><div><h3>Cómo evolucionó la búsqueda de hiperparámetros</h3><div style={{height:285}}><ResponsiveContainer><LineChart data={progress} margin={{left:5,right:25,bottom:15,top:10}}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="ensayo" label={{value:'Ensayo',position:'insideBottom',offset:-10}}/><YAxis width={48} tick={{fontSize:11}}/><Tooltip formatter={(v:number)=>`${v.toFixed(3)} pp`}/><Legend verticalAlign="top" wrapperStyle={{fontSize:11}}/><Line isAnimationActive={false} name="MAE de validación (pp)" dataKey="error" stroke="#9ab3c2" strokeWidth={2}/><Line isAnimationActive={false} name="Mejor resultado acumulado" dataKey="mejor" stroke="#0d9488" strokeWidth={3} type="stepAfter"/></LineChart></ResponsiveContainer></div><VisualExplanation interpretation="La curva muestra la pérdida de cada ensayo y el mejor resultado acumulado para el regresor y región seleccionados." explanation="Se prueban diez configuraciones y se selecciona la de menor MAE interno; la región exterior no interviene en esa selección." limitations="Este bloque es optimización de regresión. La clasificación minimiza log-loss y se muestra en la sección superior."/><p className="nr-caption">Validación interna en países separados. Menor MAE es mejor.</p></div></div>
        {fold&&<div className="nr-fold-metrics">{Object.entries(fold.metrics).map(([stage,x])=><div key={stage}><span>{label(stage==='test'?'Prueba externa':stage)}</span><strong>{fmt((x as RecordData).mae,100)} <small>pp</small></strong><small>MAE · R² {fmt((x as RecordData).r2)}</small></div>)}</div>}
      </Card>
      <div className="nr-overview-grid"><Card title="Espacio de búsqueda" subtitle={label(model)}><SearchSpace algorithm={model} space={r.hyperparameter_space[model]}/></Card><Card title="Configuraciones por región" subtitle="Siete ajustes externos del modelo seleccionado"><Table rows={r.folds.filter((x:RecordData)=>x.algorithm===model).map((x:RecordData)=>({Región:shortRegion(x.region),'MAE de prueba (pp)':fmt(x.metrics.test.mae,100),...Object.fromEntries(Object.entries(x.hyperparameters).map(([key,value])=>[label(key),value]))}))}/></Card></div>
      <details className="nr-details nr-block-details"><summary>Explorar el registro completo de 350 ensayos</summary>    <Card title="350 candidatos de optimización: registro íntegro y buscable">
      <label>Buscar modelo, región o parámetro <input value={search} onChange={e=>{setSearch(e.target.value);setPage(0);}}/></label>
      {trials.error&&<ErrorBox message={String(trials.error)}/>}
      <p>{filtered.length} registros · página {page+1} de {Math.max(1,Math.ceil(filtered.length/20))}. El MAE se presenta en puntos porcentuales; menor es mejor.</p>
      <Table rows={filtered.slice(page*20,page*20+20).map(t=>({Ensayo:Number(t.trial)+1,Modelo:label(t.algorithm),'Región excluida':t.held_out_region,'MAE de validación (pp)':Number(t.validation_mae)*100,'Hiperparámetros evaluados':JSON.parse(t.parameters),'Casos de entrenamiento':Number(t.train_n),'Casos de validación':Number(t.validation_n)}))}/><div className="chip-row"><button className="btn" disabled={!page} onClick={()=>setPage(page-1)}>Anterior</button><button className="btn" disabled={(page+1)*20>=filtered.length} onClick={()=>setPage(page+1)}>Siguiente</button></div>
    </Card>
</details>
    </details></>}
    {tab==='estadistica'&&<>
      <div className="nr-section-heading"><div><h2>Pruebas estadísticas</h2><p>Contrastes pareados, tamaños de efecto y diagnósticos de residuos.</p></div></div>
      <div className="nr-segmented" role="group" aria-label="Tipo de pruebas"><button aria-pressed={statsView==='comparacion'} onClick={()=>setStatsView('comparacion')}>Comparación de modelos</button><button aria-pressed={statsView==='diagnosticos'} onClick={()=>setStatsView('diagnosticos')}>Diagnósticos de residuos</button></div>
      {statsView==='comparacion'?<>    <Card title="Friedman, Kendall W y diez contrastes Wilcoxon con Holm">
      <div className="research-steps"><div><strong>Friedman</strong><span>p = {fmt(s.friedman.pvalue)}</span><small>No se detectan diferencias significativas entre los cinco modelos.</small></div><div><strong>Tamaño de efecto · Kendall W</strong><span>{fmt(s.kendall_w)}</span><small>Escala de 0 a 1; valores cercanos a cero indican poca concordancia.</small></div><div><strong>Comparaciones ajustadas</strong><span>{s.wilcoxon_holm.filter((p:RecordData)=>p.pvalue_holm<.05).length} de 10</span><small>Comparaciones significativas después de Holm, con α = 0,05.</small></div></div>
      <details className="nr-details"><summary>Hipótesis y metodología de los contrastes</summary><p>H₀ Friedman: los cinco modelos tienen distribuciones de rangos equivalentes del MAE regional. χ² = {fmt(s.friedman.statistic)}, p = {fmt(s.friedman.pvalue)}, siete bloques. Kendall W = {fmt(s.kendall_w)}. No se rechaza H₀; esto no demuestra equivalencia.</p>
      <p>H₀ Wilcoxon bilateral: diferencias regionales centradas en cero. Holm controla los diez contrastes. Diferencia = MAE(A) − MAE(B); valores positivos favorecen B. IC por 2 000 remuestreos regionales. Correlación biserial de rangos: tamaño de efecto adimensional.</p>
      </details>
      <DifferencePlot pairs={s.wilcoxon_holm}/><VisualExplanation interpretation="Los intervalos de las diferencias entre los cinco regresores incluyen cero; no se detecta una ventaja consistente." explanation="Se resta MAE de B al de A por región y se remuestrean regiones para el intervalo. El signo positivo favorece B y el negativo favorece A." limitations="Son contrastes de regresión exploratorios. No se trasladan a los nuevos clasificadores ni sustituyen sus métricas ROC-AUC y recall."/>
      <p>Los puntos muestran la diferencia media y las líneas su intervalo de confianza. Un intervalo que cruza cero incluye la posibilidad de que no haya diferencia.</p>
      <details className="nr-details"><summary>Ver los diez contrastes y sus tamaños de efecto</summary><Table rows={s.wilcoxon_holm.map((x:RecordData)=>({A:x.a,B:x.b,W:x.statistic,p_crudo:x.pvalue,p_Holm:x.pvalue_holm,diferencia_media_pp:fmt(x.mean_mae_difference,100),diferencia_mediana_pp:fmt(x.median_mae_difference,100),biserial:x.rank_biserial,'IC95 diferencia pp':`${fmt(x.bootstrap_mean_difference_ci.lower,100)} a ${fmt(x.bootstrap_mean_difference_ci.upper,100)}`}))}/>
      </details><p className="notice">Inferencia exploratoria: siete regiones, tamaños desiguales, entrenamiento solapado y estimaciones JME suavizadas dependientes espacialmente. Los p exactos tienen resolución gruesa; no existe conclusión clínica ni causal.</p>
    </Card>
</>:<>    <Card title="Diagnósticos completos: normalidad y autocorrelación espacial">
      <p>Shapiro–Wilk: H₀ residuos normales. Moran I: H₀ ausencia de autocorrelación espacial bajo permutaciones; 999 permutaciones, vecinos definidos por cinco capitales más cercanas. Las capitales son una aproximación geográfica. Todos los p de estos diagnósticos son crudos, descriptivos y exploratorios, sin corrección de multiplicidad.</p>
      <h3>Normalidad de los residuos · Shapiro–Wilk</h3><Table rows={s.normality.map((x:RecordData)=>({Modelo:label(x.algorithm),W:x.statistic,'Valor p':x.pvalue,Asimetría:x.skewness,'Exceso de curtosis':x.excess_kurtosis,Conclusión:x.pvalue<.05?'Se rechaza normalidad':'No se rechaza normalidad'}))}/>
      <h3>Dependencia espacial · Moran I</h3>
      <div style={{height:300}}><ResponsiveContainer><BarChart data={s.moran.map((x:RecordData)=>({Modelo:label(x.algorithm),'Moran I':x.statistic}))} margin={{bottom:35,left:10,right:20}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="Modelo" tick={{fontSize:11}} angle={-12} textAnchor="end" height={60}/><YAxis/><Tooltip/><ReferenceLine y={0} stroke="#94a3b8"/><Bar isAnimationActive={false} dataKey="Moran I" fill="#168b94"/></BarChart></ResponsiveContainer></div><VisualExplanation interpretation="Las barras positivas de Moran I indican agrupación geográfica de residuos semejantes." explanation="Se calcula dependencia residual usando cinco capitales vecinas y 999 permutaciones. La tabla presenta el valor p crudo." limitations="Diagnóstico exploratorio con capitales como aproximación; no demuestra mecanismos causales ni independencia cuando no rechaza."/>
      <Table rows={s.moran.map((x:RecordData)=>({Modelo:label(x.algorithm),'Moran I':x.statistic,'Valor esperado':x.expected,'Valor p':x.pvalue,Permutaciones:x.permutations,Conclusión:x.pvalue<.05?'Asociación espacial detectada':'Sin evidencia suficiente'}))}/>
    </Card>
</>}
    </>}
    {tab==='datos'&&<><PublicDatasetExplorer/><details className="nr-details nr-block-details"><summary>Protocolo de clasificación y estimación</summary><Card title="Cómo se utilizaron los datos"><p>Clasificación: país con prevalencia nacional publicada ≥20 %. El umbral de decisión del clasificador es 0,5. Se entrenaron cinco modelos con exclusión de siete regiones; ajuste hasta 2021, selección interna en 2022 y prueba en 2023.</p><p>Se usaron nueve determinantes y ventanas de tres años. La imputación y la estandarización se ajustaron exclusivamente en los países de entrenamiento. La selección de hiperparámetros minimizó log-loss interna.</p><p>La estimación continua de prevalencia es un experimento independiente. Sus MAE, RMSE y R² se muestran en «Estimación continua»; no se convierten en ROC-AUC ni recall.</p><p>Los países son las unidades evaluadas. No se dispone de microdatos clínicos infantiles en este panel.</p></Card></details></>}
    {tab==='descargas'&&<>
      <div className="nr-section-heading"><div><h2>Centro de descargas</h2><p>Resultados, datos y evidencia del experimento, organizados por contenido.</p></div></div>
      <div className="nr-download-feature"><div><span className="nr-eyebrow">PAQUETE REPRODUCIBLE</span><h3>Toda la evidencia del estudio</h3><p>Datos, código, modelos ajustados, resultados y verificaciones.</p></div><button className="btn btn-primary" onClick={()=>void download('evidence.zip')}>↓ Descargar paquete completo</button></div>
      <div className="nr-download-grid">{[{title:'Resultados y estadística',files:['results.json','metrics.csv','predictions.csv','regional_metrics.csv','pairwise_statistics.csv']},{title:'Entrenamiento',files:['trials.csv','epochs.csv','verification.json']},{title:'Datos y trazabilidad',files:['country_panel.csv','manifest.json','artifact_hashes.json','README.md']}].map(group=><Card key={group.title} title={group.title}>{group.files.map(file=><button className="nr-download-row" key={file} onClick={()=>void download(file)}><span>{downloadLabels[file]}<small>{file.endsWith('.csv')?'Tabla exportable':file.endsWith('.md')?'Documento de referencia':'Archivo de evidencia'}</small></span><span aria-hidden="true">↓</span></button>)}</Card>)}</div>
      <ClassificationFigures/><div className="nr-section-heading"><div><h2>Figuras de estimación continua</h2><p>Experimento de regresión independiente de la clasificación.</p></div></div>
    <div className="grid grid-2">{gallery.figures.map((figure:RecordData)=><Card key={figure.name} title={figure.title} subtitle="PNG a 600 dpi · SVG y PDF vectoriales"><Preview name={figure.name} title={figure.title}/><VisualExplanation interpretation={figure.interpretation||'Esta figura describe el experimento de estimación continua de prevalencia, independiente de la clasificación.'} explanation={figure.explanation||'Se utilizan predicciones de prevalencia y errores fuera de región, no puntuaciones de clasificación.'} limitations={figure.limitations||'Datos nacionales modelados; no representa rendimiento clínico individual.'}/><div className="chip-row">{figure.formats.map((ext:string)=><button className="btn btn-sm" key={ext} onClick={()=>void download(`${figure.name}.${ext}`)}>Descargar {ext.toUpperCase()}</button>)}</div></Card>)}</div>

      <details className="nr-details nr-block-details"><summary>Identificación de la ejecución y entorno reproducible</summary><DataDetails value={{Ejecución:r.id,Semilla:r.seed,'Duración (segundos)':r.elapsed_seconds,Python:r.python,...r.versions}}/></details>
    </>}
    </section>
  </div>;
}


