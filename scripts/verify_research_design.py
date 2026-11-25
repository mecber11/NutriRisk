"""Visual acceptance checks for the organized real-data research dashboard."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'.tmp/research-design-qa'
out.mkdir(exist_ok=True)
checks=[]
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1100},accept_downloads=True)
    page=context.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000/login')
    page.locator('input[type=email]').first.fill('admin@nutririsk.ai')
    page.locator('input[type=password]').first.fill('Admin#2026!')
    page.get_by_role('button',name='Ingresar',exact=True).click()
    page.get_by_role('heading',name='Resultados con datos reales',exact=True).wait_for()
    assert page.get_by_role('tab').count()==6
    assert page.locator('.nr-kpi').count()==4
    page.wait_for_selector('.nr-panel .recharts-wrapper svg'); assert page.locator('.nr-panel .recharts-wrapper').count()==2
    assert page.locator('pre,code').count()==0
    page.screenshot(path=str(out/'01-summary.png'),full_page=True)
    checks.append('organized_summary_four_indicators_two_real_charts_six_tabs')
    page.get_by_role('tab',name='Modelos',exact=True).click()
    page.get_by_label('Etapa de evaluación',exact=True).select_option('validation')
    assert page.get_by_role('tabpanel').locator('table').first.locator('tbody tr').count()==5
    page.get_by_label('Etapa de evaluación',exact=True).select_option('test')
    assert page.get_by_role('tabpanel').locator('table').first.locator('tbody tr').count()==7
    page.get_by_label('Modelo del gráfico de dispersión').select_option('catboost')
    page.screenshot(path=str(out/'02-models.png'),full_page=True)
    checks.append('model_stage_filter_baselines_and_country_scatter')
    page.get_by_role('tab',name='Hiperparámetros',exact=True).click()
    page.get_by_label('Modelo para explorar',exact=True).select_option('random_forest')
    page.get_by_label('Región excluida',exact=True).select_option(index=1)
    page.screenshot(path=str(out/'03-hyperparameters.png'),full_page=True)
    page.get_by_text('Explorar el registro completo de 350 ensayos',exact=True).click()
    page.get_by_label('Buscar modelo, región o parámetro').fill('cnn_lstm')
    assert '70 registros' in page.get_by_role('tabpanel').inner_text()
    page.get_by_role('button',name='Siguiente',exact=True).click()
    assert 'página 2 de 4' in page.get_by_role('tabpanel').inner_text()
    checks.append('hyperparameter_model_region_filters_curve_and_complete_trials')
    page.get_by_role('tab',name='Pruebas estadísticas',exact=True).click()
    assert page.get_by_role('img',name='Diferencias de MAE e intervalos de confianza por pares').count()==1
    page.get_by_text('Ver los diez contrastes y sus tamaños de efecto',exact=True).click()
    assert page.get_by_role('tabpanel').locator('table tbody tr').count()==10
    page.screenshot(path=str(out/'04-statistics.png'),full_page=True)
    page.get_by_role('button',name='Diagnósticos de residuos',exact=True).click()
    assert page.get_by_role('tabpanel').locator('table').count()==2
    assert page.get_by_role('tabpanel').locator('table').first.locator('tbody tr').count()==7
    page.screenshot(path=str(out/'05-diagnostics.png'),full_page=True)
    checks.append('all_ten_pairwise_tests_and_separate_residual_diagnostics')
    page.get_by_role('tab',name='Datos y metodología',exact=True).click()
    assert page.get_by_text('Procedencia, licencia, cobertura y faltantes',exact=True).is_visible()
    assert page.get_by_role('tabpanel').locator('table').first.locator('tbody tr').count()==9
    checks.append('source_missingness_and_protocol_retained')
    page.get_by_role('tab',name='Descargas',exact=True).click()
    expect(page.locator('img')).to_have_count(4)
    for image in page.locator('img').all():
        expect(image).to_have_js_property('complete',True)
        assert image.evaluate('(element)=>element.naturalWidth')>0
    with page.expect_download() as info:
        page.get_by_role('button',name='Resultados completos',exact=False).click()
    info.value.save_as(str(out/'results.json'))
    r=json.loads((out/'results.json').read_text(encoding='utf-8'))
    assert r['synthetic'] is False and r['status']=='COMPLETED'
    page.screenshot(path=str(out/'06-downloads.png'),full_page=True)
    checks.append('grouped_downloads_four_figures_and_authenticated_real_results')
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('tab',name='Resumen',exact=True).click()
    page.evaluate('window.scrollTo(0,0)')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
    page.screenshot(path=str(out/'07-mobile.png'),full_page=True)
    page.get_by_role('tab',name='Hiperparámetros',exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
    checks.append('mobile_summary_and_hyperparameters_without_page_overflow')
    assert not errors,errors
    checks.append('no_browser_javascript_errors')
    browser.close()
result={'status':'PASSED','count':len(checks),'checks':checks,'browser_errors':errors}
(ROOT/'entregables/research_design_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))

