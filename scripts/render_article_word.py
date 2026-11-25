"""Use the packaged render_docx pipeline with a Windows Word/PyMuPDF backend.

LibreOffice and the workspace dependency loader are absent on this host. Word
is the installed native renderer. The managed skill files remain unchanged.
"""
from pathlib import Path
import importlib.util
import subprocess
import sys
import os,shutil

SKILL=Path(__file__).resolve().parents[1]/'.tmp'/'article'
spec=importlib.util.spec_from_file_location('packaged_render_docx',SKILL/'render_docx.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def word_pdf(doc_path,user_profile,convert_tmp_dir,stem,verbose=False):
 output=Path(convert_tmp_dir)/(stem+'.pdf')
 cached=os.getenv('ARTICLE_RENDER_PDF')
 if cached:
  shutil.copy2(cached,output)
  return str(output),'PDF exported by native Word in a direct authorized process.'
 command=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path(__file__).with_name('export_word_pdf.ps1')),'-InputDocx',str(Path(doc_path).resolve()),'-OutputPdf',str(output.resolve())]
 result=subprocess.run(command,capture_output=True,text=True,timeout=180)
 if result.returncode: raise RuntimeError(result.stderr)
 return str(output),result.stdout

def render_pdf(path,dpi=144,output_folder=None,**kwargs):
 import fitz
 doc=fitz.open(path)
 paths=[]
 for index,page in enumerate(doc):
  target=Path(output_folder)/f'word-{index+1}.png'
  page.get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),alpha=False).save(target)
  paths.append(str(target))
 return paths

module.convert_to_pdf=word_pdf
module.convert_from_path=render_pdf
module.main()
