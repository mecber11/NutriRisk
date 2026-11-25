"""Scientific safeguards: correct blocks, Holm adjustment and isolation."""
import numpy as np
import pandas as pd
import pytest
from app.services.research import holm, paired_statistics, bootstrap_regions, predict_fold
from app.services.evidence import retrieve


def test_holm_monotonic_adjustment():
    assert np.allclose(holm([.04, .001, .02]), [.04, .003, .04])


def test_rejects_aggregate_scores_as_blocks():
    with pytest.raises(ValueError):
        paired_statistics(pd.DataFrame({'a': [.1], 'b': [.2], 'c': [.3]}))


def test_identical_models_no_false_significance():
    result = paired_statistics(pd.DataFrame({'a': [.1,.2,.3], 'b': [.1,.2,.3], 'c': [.1,.2,.3]}))
    assert result['friedman']['pvalue'] == 1
    assert all(row['pvalue_holm'] == 1 for row in result['wilcoxon_holm'])


def test_bootstrap_reproducible_and_clustered():
    y = np.array([.1,.2,.3,.4])
    p = np.array([.15,.15,.35,.35])
    groups = np.array(['a','a','b','b'])
    assert bootstrap_regions(y,p,groups,repeats=20) == bootstrap_regions(y,p,groups,repeats=20)


def test_test_covariates_do_not_change_fitted_training_predictions():
    # Batched versus singleton prediction must not refit transforms on test data.
    x = np.arange(48, dtype=float).reshape(8,2,3)
    y = np.linspace(.1,.4,8)
    coords = np.column_stack([np.arange(8), np.arange(8)])
    params = {'n_estimators': 10, 'max_depth': 2, 'min_samples_leaf': 1}
    one, _ = predict_fold('random_forest', x,y,x[:1],coords,coords[:1],params)
    batch, _ = predict_fold('random_forest', x,y,np.concatenate([x[:1], np.full((1,2,3), 1e8)]),coords,coords[:2],params)
    assert one[0] == batch[0]


def test_evidence_abstains_and_includes_sources():
    assert retrieve('zxqvkk000')['data']['sources'] == []
    result = retrieve('OMS desnutrición emaciación')
    assert result['data']['sources']
    assert 'who.int' in result['summary']
    assert 'profesional' in result['summary']


def test_research_requires_authentication(client):
    assert client.get('/api/v1/research/audit').status_code == 401
    assert client.post('/api/v1/automation/monitor').status_code == 401


def test_research_inventory_and_path_validation(client, admin_headers):
    response = client.get('/api/v1/research/audit', headers=admin_headers)
    assert response.status_code == 200
    assert any(row['state'] == 'pendiente de investigación' for row in response.json()['items'])
    assert client.get('/api/v1/research/runs/invalid', headers=admin_headers).status_code == 404
    assert client.post('/api/v1/research/runs', headers=admin_headers, json={'trials': 151}).status_code == 422


def test_six_workflows_reference_existing_operations(client, admin_headers):
    import json
    response = client.get('/api/v1/research/workflows', headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()['items']) == 6
    for item in response.json()['items']:
        exported = client.get('/api/v1/research/workflows/' + item['name'], headers=admin_headers)
        assert exported.status_code == 200
        workflow = json.loads(exported.content)
        assert workflow['active'] is False
        names = {node['name'] for node in workflow['nodes']}
        for source, links in workflow['connections'].items():
            assert source in names
            assert all(connection['node'] in names for branch in links['main'] for connection in branch)
