export function VisualExplanation({interpretation,explanation,limitations}:{interpretation:string;explanation:string;limitations:string}) {
  return <div className="nr-visual-explanation"><div><strong>Interpretación</strong><p>{interpretation}</p></div><div><strong>Explicabilidad</strong><p>{explanation}</p></div><div><strong>Alcance</strong><p>{limitations}</p></div></div>;
}
