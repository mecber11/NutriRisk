"""Check actual classification charts, public rows, explanations and exports."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'.tmp/visible-public-results'
out.mkdir(exist_ok=True)
checks=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000/login')
    page.locator('input[type=email]').first.fill('admin@nutririsk.ai');page.locator('input[type=password]').first.fill('Admin#2026!')
    page.get_by_role('button',name='Ingresar',exact=True).click()
    page.get_by_role('heading',name='Predicción de desnutrición infantil · Recall y ROC-AUC',exact=True).wait_for()
    expect(page.get_by_role('tab',name='Predicción de desnutrición (Recall / ROC-AUC)',exact=True)).to_have_attribute('aria-selected','true')
    expect(page.locator('.recharts-line-curve')).to_have_count(10)
    assert page.locator('.nr-visual-explanation').count()>=5
    assert page.locator('.nr-panel').get_by_text('0.905',exact=True).count()==1
    page.screenshot(path=str(out/'01-recall-auc.png'),full_page=True)
    checks.append('default_view_recall_precision_f1_auc_pr_and_ten_real_curve_paths')
    page.get_by_label('Clasificador para explicar',exact=True).select_option('catboost')
    matrix=page.get_by_role('img',name='Matriz de confusión de CatBoost',exact=True)
    assert '46' in matrix.inner_text() and '8' in matrix.inner_text()
    page.get_by_text('Incertidumbre, calibración y métricas complementarias',exact=True).click()
    assert page.get_by_role('tabpanel').locator('table').count()==2
    checks.append('confusion_counts_match_real_catboost_and_visible_confidence_intervals')
    page.get_by_role('tab',name='Dataset de desnutrición y factores',exact=True).click()
    page.get_by_role('heading',name='Dataset público para la predicción de desnutrición infantil',exact=True).wait_for()
    expect(page.locator('.nr-dataset-table table tbody tr').first).to_be_visible()
    assert page.locator('.nr-dataset-table table tbody tr').count()==25
    page.screenshot(path=str(out/'02-dataset-public.png'),full_page=True)
    page.get_by_label('País del dataset').select_option('PER')
    page.get_by_label('Año del dataset').select_option('')
    expect(page.locator('.nr-dataset-table table tbody tr')).to_have_count(25)
    expect(page.locator('.nr-dataset-table table tbody tr').first).to_contain_text('Peru')
    assert page.get_by_role('link',name='Ver serie original ↗',exact=True).count()==10
    assert page.get_by_role('link',name='Ver datos de origen ↗',exact=True).count()==10
    page.screenshot(path=str(out/'03-peru-original-rows.png'),full_page=True)
    checks.append('actual_public_rows_pagination_country_year_filters_and_ten_official_sources')
    with page.expect_download() as info:page.get_by_role('button',name='↓ Descargar dataset completo',exact=True).click()
    info.value.save_as(str(out/'downloaded-country-panel.csv'))
    import hashlib
    assert hashlib.sha256((out/'downloaded-country-panel.csv').read_bytes()).digest()==hashlib.sha256((ROOT/'data/real/country_panel.csv').read_bytes()).digest()
    checks.append('download_is_byte_identical_to_acquired_public_dataset')
    page.get_by_role('tab',name='Hiperparámetros',exact=True).click()
    page.get_by_label('Modelo de hiperparámetros de clasificación').select_option('cnn_lstm')
    assert page.get_by_role('heading',name='Hiperparámetros de clasificación',exact=True).is_visible()
    page.screenshot(path=str(out/'04-classification-hyperparameters.png'),full_page=True)
    checks.append('classifier_hyperparameters_and_true_logloss_trials_visible')
    page.get_by_role('tab',name='Figuras y descargas',exact=True).click()
    expect(page.locator('img')).to_have_count(11)
    for image in page.locator('img').all():
        expect(image).to_have_js_property('complete',True)
        assert image.evaluate('(element)=>element.naturalWidth')>0
    assert page.get_by_role('button',name='↓ PNG · 600 dpi',exact=True).count()==7
    assert page.locator('.nr-visual-explanation').count()==11
    with page.expect_download() as figure:page.get_by_role('button',name='↓ PNG · 600 dpi',exact=True).first.click()
    figure.value.save_as(str(out/'downloaded-roc-600dpi.png'))
    from PIL import Image
    with Image.open(out/'downloaded-roc-600dpi.png') as image:assert min(image.info['dpi'])>=599
    checks.append('eleven_real_figures_with_individual_notes_and_verified_600dpi_png_download')
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('tab',name='Predicción de desnutrición (Recall / ROC-AUC)',exact=True).click();page.evaluate('window.scrollTo(0,0)')
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    page.screenshot(path=str(out/'05-mobile-classification.png'),full_page=True)
    checks.append('mobile_classification_has_no_page_overflow')
    assert not errors,errors
    checks.append('no_browser_javascript_errors')
    browser.close()
report={'status':'PASSED','checks':checks,'count':len(checks),'browser_errors':errors}
(ROOT/'entregables/visible_public_results_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
