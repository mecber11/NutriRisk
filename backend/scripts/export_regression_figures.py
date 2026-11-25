"""Re-export genuine regression evidence at 600 dpi with figure-specific notes."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from app.core.config import settings
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def export():
    root=settings.storage_dir/'research'
    run_id=json.loads((root/'latest_real.json').read_text())['id']
    folder=root/run_id
    result=json.loads((folder/'results.json').read_text(encoding='utf-8'))
    pred=pd.read_csv(folder/'predictions.csv')
    blocks=pd.read_csv(folder/'regional_metrics.csv')
    ep=pd.read_csv(folder/'epochs.csv')
    models=[x for x in result['models'] if not x['algorithm'].startswith('baseline_')]
    labels={x['algorithm']:x['label'] for x in result['models']}
    catalog=[]
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    def save(fig,name,title,interpretation,explanation,limitations):
        fig.tight_layout()
        for ext in ['png','svg','pdf']:fig.savefig(folder/'figures'/f'{name}.{ext}',dpi=600,bbox_inches='tight')
        from PIL import Image
        with Image.open(folder/'figures'/f'{name}.png') as im:width,height=im.size
        catalog.append(dict(name=name,title=title,path='figures/'+name,formats=['png','svg','pdf'],dpi=600,width_pixels=width,height_pixels=height,interpretation=interpretation,explanation=explanation,limitations=limitations))
        plt.close(fig)
    ordered=sorted(result['models'],key=lambda x:x['metrics']['test']['mae'])
    fig,ax=plt.subplots(figsize=(9,5));ax.barh([labels[x['algorithm']] for x in ordered],[100*x['metrics']['test']['mae'] for x in ordered],color=['#e5a75c' if x['algorithm'].startswith('baseline_') else '#168b94' for x in ordered]);ax.invert_yaxis();ax.set_xlabel('MAE de prueba (puntos porcentuales)');ax.set_title('Estimación continua de prevalencia nacional')
    winner=min(models,key=lambda x:x['metrics']['test']['mae'])
    save(fig,'01_model_mae','MAE de transferencia geográfica en 2023',f'{winner["label"]} obtuvo el menor MAE observado entre los cinco modelos: {winner["metrics"]["test"]["mae"]*100:.3f} puntos porcentuales. La persistencia histórica tiene un error mucho menor.','Cada barra es la media del error absoluto frente a la prevalencia JME de los 161 países externos. Se excluyeron regiones completas del ajuste.','La persistencia usa la etiqueta de 2022 del país. No se demostró superioridad estadística entre los cinco modelos; la tarea es regresión nacional, no diagnóstico individual.')
    fig,axes=plt.subplots(2,3,figsize=(10,6));maximum=max(pred.observed.max(),pred.predicted.max())*100;limit=max(60,float(np.ceil(maximum/10)*10))
    for ax,m in zip(axes.flat,models):
        rows=pred[pred.algorithm==m['algorithm']];ax.scatter(rows.observed*100,rows.predicted*100,s=10,alpha=.65,color='#168b94');ax.plot([0,limit],[0,limit],'--',color='#a67b65');ax.set(title=m['label'],xlabel='Prevalencia publicada (%)',ylabel='Estimada (%)',xlim=(0,limit),ylim=(0,limit))
    axes.flat[-1].axis('off')
    save(fig,'02_observed_predicted','Prevalencia publicada frente a estimada','Los puntos alejados de la diagonal representan países con mayor error de estimación. Hay heterogeneidad entre modelos y países.','La diagonal es igualdad entre prevalencia publicada y estimada. Cada punto corresponde a un país de prueba; no es un niño ni una encuesta independiente.','Las prevalencias de referencia JME son modeladas. La dispersión no demuestra causalidad, calibración probabilística de clasificación ni utilidad clínica.')
    table=blocks[blocks.algorithm.isin([x['algorithm'] for x in models])].pivot(index='region',columns='algorithm',values='mae')
    fig,ax=plt.subplots(figsize=(10,5));image=ax.imshow(table.to_numpy()*100,aspect='auto',cmap='YlGnBu');ax.set_xticks(range(len(table.columns)),[labels[x] for x in table.columns],rotation=15,ha='right');ax.set_yticks(range(len(table)),[x.strip() for x in table.index]);fig.colorbar(image,ax=ax,label='MAE (puntos porcentuales)')
    for i in range(len(table)):
        for j in range(len(table.columns)):ax.text(j,i,f'{table.iloc[i,j]*100:.2f}',ha='center',va='center',fontsize=8,color='white' if table.iloc[i,j]*100>8 else '#173847')
    save(fig,'03_region_errors','Heterogeneidad del MAE por región','El error cambia de una región a otra; un buen promedio global puede ocultar fallos regionales.','Cada celda es el MAE de los países de una región excluida en entrenamiento. Los valores se expresan en puntos porcentuales y una mayor intensidad indica mayor error.','Las regiones tienen tamaños desiguales y Norteamérica contiene un país. No son bloques independientes de igual precisión.')
    rows=ep[(ep.algorithm=='cnn_lstm')&(ep.stage=='outer_fit')];fig,axes=plt.subplots(1,2,figsize=(10,4));regions=list(result['data_summary']['regions'])
    for fold,g in rows.groupby('fold'):
        for ax,key in zip(axes,['train_mse','validation_mse']):ax.plot(g.epoch,g[key],label=f'Pliegue {int(fold)+1}')
    for ax,title in zip(axes,['Entrenamiento','Seguimiento de validación']):ax.set(title=title,xlabel='Época',ylabel='MSE (fracción al cuadrado)');ax.legend(fontsize=7,ncol=2)
    save(fig,'04_cnn_learning','Curvas de aprendizaje CNN-LSTM de regresión','Las curvas muestran cómo evolucionó la pérdida de ajuste y seguimiento durante las épocas finales de cada pliegue.','La red minimiza error cuadrático en prevalencia. Las épocas se fijaron mediante selección interna; el seguimiento exterior de 2022 no determina una parada temprana.','Una pérdida decreciente no demuestra generalización. La prueba externa de 2023 y sus errores se evalúan por separado; estas curvas no pertenecen a clasificación BCE.')
    (folder/'figures.json').write_text(json.dumps({'figures':catalog},ensure_ascii=False,indent=2),encoding='utf-8')
    from scripts.package_real import complete
    complete(run_id)
    print('FOUR_REGRESSION_FIGURES_600_DPI',run_id)
if __name__=='__main__':export()
