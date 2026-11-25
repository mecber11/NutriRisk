"""Append fresh child-classification figures to an existing territory study.

Useful when adding a new visualization without rerunning a sealed experiment.
Scientific target and provenance remain separate in classification_metrics.json.
"""
import argparse
import json
import zipfile
from app.core.config import settings  # Set writable Matplotlib configuration before import.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from app.services.research import classification_figures, research_root, save_json, log_integrations, architecture_figure

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    parser.add_argument('--architecture-only', action='store_true')
    args = parser.parse_args()
    folder = research_root() / args.run_id
    manifest = json.loads((folder / 'figures.json').read_text(encoding='utf-8'))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','savefig.facecolor':'white'})
    def save(fig, name, title):
        fig.text(.5,.01,'NutriRisk AI · Datos sintéticos · Evaluación exploratoria',ha='center',fontsize=9,color='#526173')
        for extension in ('png','svg','pdf'):
            fig.savefig(folder / f'{name}.{extension}',dpi=600,bbox_inches='tight',pad_inches=.2)
        manifest['figures'] = [figure for figure in manifest['figures'] if figure['name'] != name]
        manifest['figures'].append({'name':name,'title':title,'formats':['png','svg','pdf'],'dpi':600})
        plt.close(fig)
    save(architecture_figure(),'arquitectura','Arquitectura tecnológica')
    if not args.architecture_only:
        classification_figures(folder,save)
    save_json(folder / 'figures.json',manifest)
    with zipfile.ZipFile(folder / 'figuras_alta_calidad.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in folder.iterdir():
            if path.suffix in ('.png','.svg','.pdf','.csv') or path.name in ('results.json','figures.json','classification_metrics.json'):
                archive.write(path,path.name)
    log_integrations(folder,json.loads((folder / 'results.json').read_text(encoding='utf-8')))
    print(f"Figures: {len(manifest['figures'])}",flush=True)
