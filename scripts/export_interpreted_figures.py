"""Publication figure exports with visible reading notes below each plot.

Original scientific plots remain unchanged. PDF/SVG vectors are preserved;
PNG is rendered at 600 dpi from the captioned vector page.
"""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET
import fitz

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'backend'/'storage'/'research'/'20261104T170319-269cbcbc'
OUT=ROOT/'entregables'/'figuras_interpretadas'
NOTES=json.loads((ROOT/'.tmp/article/interpretations.json').read_text(encoding='utf-8'))
SVG='http://www.w3.org/2000/svg'
ET.register_namespace('',SVG)
ET.register_namespace('xlink','http://www.w3.org/1999/xlink')

def lines(text,width,size=10):
 result=[];line=''
 for word in text.split():
  candidate=(line+' '+word).strip()
  if line and fitz.get_text_length(candidate,fontname='helv',fontsize=size)>width:
   result.append(line);line=word
  else:line=candidate
 if line:result.append(line)
 return result

def main():
 OUT.mkdir(exist_ok=True)
 manifest=json.loads((RUN/'figures.json').read_text(encoding='utf-8'))
 for figure in manifest['figures']:
  name=figure['name'];note=NOTES[name]
  original=fitz.open(RUN/(name+'.pdf'))
  width,height=original[0].rect.width,original[0].rect.height
  paragraphs=[lines(label+note[field],width-44) for label,field in [('Cómo leer: ','reading'),('Interpretación: ','meaning'),('Alcance: ','limit')]]
  extra=26+sum(len(p)*13+6 for p in paragraphs)
  document=fitz.open();page=document.new_page(width=width,height=height+extra)
  page.show_pdf_page(fitz.Rect(0,0,width,height),original,0)
  page.draw_line(fitz.Point(20,height+9),fitz.Point(width-20,height+9),color=(.1,.45,.55),width=.7)
  y=height+25
  for paragraph in paragraphs:
   for line in paragraph:
    page.insert_text((22,y),line,fontname='helv',fontsize=10,color=(.12,.20,.25));y+=13
   y+=6
  document.save(OUT/(name+'.pdf'))
  page.get_pixmap(dpi=600,alpha=False).save(OUT/(name+'.png'))
  document.close();original.close()
  tree=ET.parse(RUN/(name+'.svg'));root=tree.getroot()
  view=[float(value) for value in root.attrib['viewBox'].split()]
  original_height=view[3]
  root.set('viewBox',f'{view[0]} {view[1]} {view[2]} {original_height+extra}')
  root.set('height',f'{original_height+extra}pt')
  ET.SubElement(root,f'{{{SVG}}}rect',{'x':'0','y':str(original_height),'width':str(view[2]),'height':str(extra),'fill':'white'})
  group=ET.SubElement(root,f'{{{SVG}}}g',{'font-family':'DejaVu Sans, Arial, sans-serif','font-size':'10','fill':'#213744'})
  y=original_height+25
  for paragraph in paragraphs:
   for line in paragraph:
    ET.SubElement(group,f'{{{SVG}}}text',{'x':'22','y':str(y)}).text=line;y+=13
   y+=6
  tree.write(OUT/(name+'.svg'),encoding='utf-8',xml_declaration=True)
  print(name,flush=True)
 with zipfile.ZipFile(ROOT/'entregables'/'Figuras_NutriRisk_con_interpretacion.zip','w',zipfile.ZIP_DEFLATED) as archive:
  for path in OUT.iterdir():archive.write(path,path.name)

if __name__=='__main__':main()
