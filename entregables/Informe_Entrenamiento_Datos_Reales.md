# NutriRisk AI: Predicción del riesgo de desnutrición infantil con datos públicos reales

Ejecución: `20261106T194207-e0ed9fcf`. Estado: COMPLETED. Semilla: 42.

Modelos de inteligencia artificial para la predicción del riesgo de desnutrición infantil (retraso del crecimiento / stunting) a partir de determinantes socioeconómicos, sanitarios y ambientales del Banco Mundial y JME (UNICEF/OMS/Banco Mundial): 161 países; 7 regiones; ventanas temporales de 3 años; 9 determinantes.

## Protocolo ejecutado

```json
{
  "outer": "leave-one-World-Bank-region-out, all years of test region excluded from fitting/tuning",
  "inner": "20% of remaining countries sampled once per outer fold; their 2022 labels validate candidates; their complete histories excluded from inner train",
  "train_years": [
    2002,
    2021
  ],
  "validation_year": 2022,
  "test_year": 2023,
  "window_years": 3,
  "target": "stunting_prevalence_pct / 100",
  "selection_metric": "inner validation MAE",
  "trials_per_model_per_outer_fold": 10,
  "sampler": "Optuna TPE, seed + outer fold",
  "preprocessing": "training-only median imputation and StandardScaler on flattened 3-year windows, no country/region IDs or outcome features",
  "final_fit": "all non-held-out-region countries, years <=2021; 2022 outer validation is monitoring only, never early stopping",
  "prediction_clipping": [
    0,
    1
  ],
  "cnn_training": "full-batch Adam/MSE, no early stopping, convolution kernel 2 padding1 + LSTM + sigmoid linear head",
  "metrics_scale": "fraction; multiply MAE/RMSE by 100 for percentage points",
  "completed_trial_fits": 350,
  "completed_outer_fits": 35,
  "monitoring_note": "Outer validation 2022 shares training-country identities; selection uses the separate inner-country validation. CatBoost use_best_model=False; all algorithms use fixed trial-selected iteration counts.",
  "random_forest_history": "No iterative epochs; trials and final train/validation metrics are recorded. Boosting/CNN histories are in epochs.csv."
}
```

## Métricas

MAE y RMSE se expresan en puntos porcentuales. R² no tiene unidades.

| Modelo | Etapa | MAE (pp) | RMSE (pp) | R² |
|---|---|---:|---:|---:|
| baseline_mean | test | 13.289756 | 15.166164 | -0.428919 |
| baseline_persistence | test | 0.188820 | 0.272782 | 0.999538 |
| CatBoost | test | 6.762282 | 9.217775 | 0.472153 |
| CatBoost | train | 3.390269 | 4.496829 | 0.895647 |
| CatBoost | validation | 4.148898 | 5.613859 | 0.793658 |
| CNN-LSTM | test | 6.704069 | 8.946950 | 0.502714 |
| CNN-LSTM | train | 5.994618 | 7.854213 | 0.700323 |
| CNN-LSTM | validation | 5.899546 | 7.687219 | 0.616681 |
| Random Forest | test | 6.800900 | 9.550554 | 0.433352 |
| Random Forest | train | 2.913271 | 3.982257 | 0.910751 |
| Random Forest | validation | 3.990577 | 5.485904 | 0.800363 |
| XGBoost + GP espacial | test | 6.798270 | 9.388004 | 0.452477 |
| XGBoost + GP espacial | train | 2.507870 | 3.356421 | 0.941459 |
| XGBoost + GP espacial | validation | 3.536066 | 4.767796 | 0.851121 |
| XGBoost | test | 7.023726 | 9.355246 | 0.456291 |
| XGBoost | train | 2.948339 | 3.956057 | 0.917486 |
| XGBoost | validation | 3.972475 | 5.358400 | 0.810863 |

Las métricas train/validation son promedios de pliegues solapados; test reúne predicciones exteriores disjuntas.

La persistencia usa la etiqueta de 2022 del mismo país excluido. Tiene información adicional y supera ampliamente a los cinco modelos; no se incluye en el contraste de sus cinco rangos.

## Intervalos de confianza

### baseline_mean

```json
{
  "method": "percentile cluster bootstrap by region",
  "replicates": 1000,
  "n_clusters": 7,
  "mae": {
    "lower": 0.11235881116039624,
    "upper": 0.15875460145877554
  },
  "rmse": {
    "lower": 0.12835569970652083,
    "upper": 0.1702024923368834
  },
  "r2": {
    "lower": -2.862792810965977,
    "upper": -0.1630402580201773
  }
}
```

### baseline_persistence

```json
{
  "method": "percentile cluster bootstrap by region",
  "replicates": 1000,
  "n_clusters": 7,
  "mae": {
    "lower": 0.0013551346437700262,
    "upper": 0.0023480013106159884
  },
  "rmse": {
    "lower": 0.002001513387887871,
    "upper": 0.0032542067775653202
  },
  "r2": {
    "lower": 0.9992648987996052,
    "upper": 0.9995971136259362
  }
}
```

### CatBoost

```json
{
  "method": "percentile cluster bootstrap by region",
  "replicates": 1000,
  "n_clusters": 7,
  "mae": {
    "lower": 0.04057619915857405,
    "upper": 0.09437325372230757
  },
  "rmse": {
    "lower": 0.05372576144737957,
    "upper": 0.11848850884466872
  },
  "r2": {
    "lower": 0.05913635335986515,
    "upper": 0.6904706469888362
  }
}
```

### CNN-LSTM

```json
{
  "method": "percentile cluster bootstrap by region",
  "replicates": 1000,
  "n_clusters": 7,
  "mae": {
    "lower": 0.03813584482507233,
    "upper": 0.09405150072605271
  },
  "rmse": {
    "lower": 0.04860630034601332,
    "upper": 0.11631783493817074
  },
  "r2": {
    "lower": 0.11823395152994948,
    "upper": 0.7157561749168408
  }
}
```

### Random Forest

```json
{
  "method": "percentile cluster bootstrap by region",
  "replicates": 1000,
  "n_clusters": 7,
  "mae": {
    "lower": 0.039573665690627764,
    "upper": 0.09344312732680807
  },
  "rmse": {
    "lower": 0.05536654447570488,
    "upper": 0.12206665903638417
  },
  "r2": {
    "lower": -0.010866294278978178,
    "upper": 0.7095702616581827
  }
}
```

### XGBoost + GP espacial

```json
{
  "method": "percentile cluster bootstrap by region",
  "replicates": 1000,
  "n_clusters": 7,
  "mae": {
    "lower": 0.04015868611600905,
    "upper": 0.09476840741117128
  },
  "rmse": {
    "lower": 0.053780012531411965,
    "upper": 0.12163182119794604
  },
  "r2": {
    "lower": -0.000561758611398544,
    "upper": 0.7168608899125393
  }
}
```

### XGBoost

```json
{
  "method": "percentile cluster bootstrap by region",
  "replicates": 1000,
  "n_clusters": 7,
  "mae": {
    "lower": 0.04596613360319996,
    "upper": 0.09179535591453904
  },
  "rmse": {
    "lower": 0.06120718019341395,
    "upper": 0.11749138556499006
  },
  "r2": {
    "lower": 0.060988878054035515,
    "upper": 0.6749806832069501
  }
}
```

## Todas las pruebas estadísticas

Friedman: H0 = igualdad de rangos de error entre los cinco modelos por región. Wilcoxon: diferencias regionales simétricas centradas en cero. Holm controla la familia de diez comparaciones.
Shapiro-Wilk: diagnóstico de normalidad residual. Moran: asociación espacial residual respecto de vecindad de capitales; p por 999 permutaciones. Estos dos diagnósticos presentan p crudas exploratorias.
Los IC, efectos y contrastes no incorporan toda la incertidumbre JME ni la variación por semillas. Siete bloques, dependencia y ajustes solapados limitan la inferencia.

```json
{
  "friedman": {
    "statistic": 1.028571428571425,
    "pvalue": 0.9054331217288571,
    "n_blocks": 7,
    "n_models": 5,
    "blocks": [
      "East Asia & Pacific",
      "Europe & Central Asia",
      "Latin America & Caribbean ",
      "Middle East, North Africa, Afghanistan & Pakistan",
      "North America",
      "South Asia",
      "Sub-Saharan Africa "
    ]
  },
  "kendall_w": 0.03673469387755089,
  "wilcoxon_holm": [
    {
      "a": "random_forest",
      "b": "xgboost",
      "statistic": 10.0,
      "pvalue": 0.578125,
      "mean_mae_difference": 0.0015979850664521293,
      "median_mae_difference": 0.001364621483039008,
      "rank_biserial": 0.2857142857142857,
      "bootstrap_mean_difference_ci": {
        "lower": -0.0065139741579131995,
        "upper": 0.009434140655735324,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    },
    {
      "a": "random_forest",
      "b": "catboost",
      "statistic": 9.0,
      "pvalue": 0.46875,
      "mean_mae_difference": 0.0025875142784629783,
      "median_mae_difference": 0.00262584569541522,
      "rank_biserial": 0.35714285714285715,
      "bootstrap_mean_difference_ci": {
        "lower": -0.0028863513108271692,
        "upper": 0.007796048669708894,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    },
    {
      "a": "random_forest",
      "b": "spatial_xgboost",
      "statistic": 14.0,
      "pvalue": 1.0,
      "mean_mae_difference": -0.0015111285067159331,
      "median_mae_difference": 0.0008187211977431219,
      "rank_biserial": 0.0,
      "bootstrap_mean_difference_ci": {
        "lower": -0.011065725487463051,
        "upper": 0.00727920439347322,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    },
    {
      "a": "random_forest",
      "b": "cnn_lstm",
      "statistic": 13.0,
      "pvalue": 0.9375,
      "mean_mae_difference": -0.0006484280602392219,
      "median_mae_difference": 0.0005685212167612086,
      "rank_biserial": 0.07142857142857142,
      "bootstrap_mean_difference_ci": {
        "lower": -0.011746876514429844,
        "upper": 0.008564001085823253,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    },
    {
      "a": "xgboost",
      "b": "catboost",
      "statistic": 14.0,
      "pvalue": 1.0,
      "mean_mae_difference": 0.0009895292120108493,
      "median_mae_difference": -0.003175219145384961,
      "rank_biserial": 0.0,
      "bootstrap_mean_difference_ci": {
        "lower": -0.004203666434960349,
        "upper": 0.007368832418592875,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    },
    {
      "a": "xgboost",
      "b": "spatial_xgboost",
      "statistic": 14.0,
      "pvalue": 1.0,
      "mean_mae_difference": -0.003109113573168062,
      "median_mae_difference": 5.134719511870611e-06,
      "rank_biserial": 0.0,
      "bootstrap_mean_difference_ci": {
        "lower": -0.016568051847502072,
        "upper": 0.007195803219203309,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    },
    {
      "a": "xgboost",
      "b": "cnn_lstm",
      "statistic": 11.0,
      "pvalue": 0.6875,
      "mean_mae_difference": -0.002246413126691351,
      "median_mae_difference": -0.008407775024573017,
      "rank_biserial": -0.21428571428571427,
      "bootstrap_mean_difference_ci": {
        "lower": -0.013201458637043837,
        "upper": 0.010220135052998852,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    },
    {
      "a": "catboost",
      "b": "spatial_xgboost",
      "statistic": 13.0,
      "pvalue": 0.9375,
      "mean_mae_difference": -0.004098642785178912,
      "median_mae_difference": -0.000587847732308841,
      "rank_biserial": -0.07142857142857142,
      "bootstrap_mean_difference_ci": {
        "lower": -0.015831901502022523,
        "upper": 0.0039042445319376904,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    },
    {
      "a": "catboost",
      "b": "cnn_lstm",
      "statistic": 10.0,
      "pvalue": 0.578125,
      "mean_mae_difference": -0.0032359423387022003,
      "median_mae_difference": -0.0008595257035124704,
      "rank_biserial": -0.2857142857142857,
      "bootstrap_mean_difference_ci": {
        "lower": -0.010596039382136518,
        "upper": 0.0042149289681872,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    },
    {
      "a": "spatial_xgboost",
      "b": "cnn_lstm",
      "statistic": 13.0,
      "pvalue": 0.9375,
      "mean_mae_difference": 0.0008627004464767113,
      "median_mae_difference": 0.004759523383283726,
      "rank_biserial": 0.07142857142857142,
      "bootstrap_mean_difference_ci": {
        "lower": -0.008675894330484631,
        "upper": 0.009900644393756554,
        "replicates": 2000,
        "unit": "region"
      },
      "pvalue_holm": 1
    }
  ],
  "normality": [
    {
      "algorithm": "baseline_mean",
      "test": "Shapiro-Wilk residuals",
      "statistic": 0.920531060679986,
      "pvalue": 9.994858096307429e-08,
      "skewness": 0.7229878421783072,
      "excess_kurtosis": -0.43374065941199325,
      "warning": "Descriptive; spatial dependence violates independent-sample interpretation."
    },
    {
      "algorithm": "baseline_persistence",
      "test": "Shapiro-Wilk residuals",
      "statistic": 0.9242352986729777,
      "pvalue": 1.7826061223755225e-07,
      "skewness": 1.0129037748333596,
      "excess_kurtosis": 3.868162495395233,
      "warning": "Descriptive; spatial dependence violates independent-sample interpretation."
    },
    {
      "algorithm": "catboost",
      "test": "Shapiro-Wilk residuals",
      "statistic": 0.9585036468958029,
      "pvalue": 9.92376947326076e-05,
      "skewness": 0.3787323845685667,
      "excess_kurtosis": 1.6155219181717175,
      "warning": "Descriptive; spatial dependence violates independent-sample interpretation."
    },
    {
      "algorithm": "cnn_lstm",
      "test": "Shapiro-Wilk residuals",
      "statistic": 0.9684082763525471,
      "pvalue": 0.0009662443851297986,
      "skewness": 0.08030559232325815,
      "excess_kurtosis": 1.429662347804661,
      "warning": "Descriptive; spatial dependence violates independent-sample interpretation."
    },
    {
      "algorithm": "random_forest",
      "test": "Shapiro-Wilk residuals",
      "statistic": 0.9535057260896825,
      "pvalue": 3.449836844230279e-05,
      "skewness": 0.28438496666765517,
      "excess_kurtosis": 2.078094119379542,
      "warning": "Descriptive; spatial dependence violates independent-sample interpretation."
    },
    {
      "algorithm": "spatial_xgboost",
      "test": "Shapiro-Wilk residuals",
      "statistic": 0.9671677344811459,
      "pvalue": 0.0007161592726611972,
      "skewness": 0.034106664165714305,
      "excess_kurtosis": 1.3823111677462716,
      "warning": "Descriptive; spatial dependence violates independent-sample interpretation."
    },
    {
      "algorithm": "xgboost",
      "test": "Shapiro-Wilk residuals",
      "statistic": 0.9714103448829541,
      "pvalue": 0.0020315929553796274,
      "skewness": 0.2704936871070367,
      "excess_kurtosis": 1.2730096019122694,
      "warning": "Descriptive; spatial dependence violates independent-sample interpretation."
    }
  ],
  "moran": [
    {
      "algorithm": "catboost",
      "statistic": 0.3850642813114455,
      "pvalue": 0.001,
      "permutations": 999,
      "expected": -0.00625,
      "weights": "symmetric binary 5 nearest capitals; great-circle distances",
      "coordinate_proxy": true
    },
    {
      "algorithm": "cnn_lstm",
      "statistic": 0.41139549419340427,
      "pvalue": 0.001,
      "permutations": 999,
      "expected": -0.00625,
      "weights": "symmetric binary 5 nearest capitals; great-circle distances",
      "coordinate_proxy": true
    },
    {
      "algorithm": "random_forest",
      "statistic": 0.21804985096962104,
      "pvalue": 0.001,
      "permutations": 999,
      "expected": -0.00625,
      "weights": "symmetric binary 5 nearest capitals; great-circle distances",
      "coordinate_proxy": true
    },
    {
      "algorithm": "spatial_xgboost",
      "statistic": 0.2826000414436825,
      "pvalue": 0.001,
      "permutations": 999,
      "expected": -0.00625,
      "weights": "symmetric binary 5 nearest capitals; great-circle distances",
      "coordinate_proxy": true
    },
    {
      "algorithm": "xgboost",
      "statistic": 0.2610896471077243,
      "pvalue": 0.001,
      "permutations": 999,
      "expected": -0.00625,
      "weights": "symmetric binary 5 nearest capitals; great-circle distances",
      "coordinate_proxy": true
    }
  ],
  "inference_warning": "Exploratory inference: seven regions, unequal sample size, overlapping training folds and spatially dependent smoothed JME estimates. Exact Wilcoxon p-values have coarse resolution; no clinical or causal conclusion."
}
```

## Espacio de hiperparámetros

```json
{
  "random_forest": {
    "n_estimators": [
      60,
      100
    ],
    "max_depth": [
      3,
      10
    ],
    "min_samples_leaf": [
      2,
      12
    ],
    "max_features": [
      0.5,
      1
    ]
  },
  "xgboost": {
    "n_estimators": [
      60,
      120
    ],
    "max_depth": [
      2,
      5
    ],
    "learning_rate": {
      "range": [
        0.02,
        0.2
      ],
      "log": true
    },
    "reg_lambda": {
      "range": [
        0.5,
        10
      ],
      "log": true
    },
    "subsample": [
      0.7,
      1
    ]
  },
  "catboost": {
    "iterations": [
      60,
      120
    ],
    "depth": [
      3,
      6
    ],
    "learning_rate": {
      "range": [
        0.02,
        0.2
      ],
      "log": true
    },
    "l2_leaf_reg": [
      1,
      10
    ]
  },
  "cnn_lstm": {
    "hidden": [
      8,
      16,
      32
    ],
    "channels": [
      4,
      8
    ],
    "learning_rate": {
      "range": [
        0.001,
        0.02
      ],
      "log": true
    },
    "weight_decay": {
      "range": [
        1e-05,
        0.01
      ],
      "log": true
    },
    "epochs": [
      30,
      50
    ]
  },
  "spatial_xgboost": {
    "xgboost": {
      "n_estimators": [
        60,
        120
      ],
      "max_depth": [
        2,
        5
      ],
      "learning_rate": {
        "range": [
          0.02,
          0.2
        ],
        "log": true
      },
      "reg_lambda": {
        "range": [
          0.5,
          10
        ],
        "log": true
      },
      "subsample": [
        0.7,
        1
      ]
    },
    "gp_fixed": {
      "length_scale_degrees": [
        30,
        30
      ],
      "signal_variance": 0.01,
      "white_noise": 0.001,
      "alpha": 1e-05,
      "optimizer": null,
      "training_unit": "country-mean training residual"
    }
  }
}
```

## Hiperparámetros finales y métricas de cada ajuste

```json
[
  {
    "fold": 0,
    "region": "East Asia & Pacific",
    "algorithm": "random_forest",
    "hyperparameters": {
      "n_estimators": 100,
      "max_depth": 9,
      "min_samples_leaf": 4,
      "max_features": 0.5909124836035503
    },
    "metrics": {
      "train": {
        "mae": 0.012088827893644995,
        "rmse": 0.017421067714871064,
        "r2": 0.9857615598673448,
        "n": 2680
      },
      "validation": {
        "mae": 0.028450743807582772,
        "rmse": 0.04042059817349219,
        "r2": 0.8973493952050127,
        "n": 134
      },
      "test": {
        "mae": 0.07008117736109559,
        "rmse": 0.09137513368801177,
        "r2": 0.4778283074185914,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BGR",
      "BOL",
      "CIV",
      "GMB",
      "GNB",
      "IRL",
      "KAZ",
      "KGZ",
      "LTU",
      "MLI",
      "MUS",
      "MWI",
      "NER",
      "NGA",
      "OMN",
      "PRT",
      "SDN",
      "SLV",
      "SYR",
      "TGO",
      "TUR",
      "TZA",
      "UZB",
      "VEN",
      "YEM"
    ]
  },
  {
    "fold": 0,
    "region": "East Asia & Pacific",
    "algorithm": "xgboost",
    "hyperparameters": {
      "n_estimators": 120,
      "max_depth": 3,
      "learning_rate": 0.09195011569464331,
      "reg_lambda": 1.272083045469184,
      "subsample": 0.8560204063533432
    },
    "metrics": {
      "train": {
        "mae": 0.02299181594237574,
        "rmse": 0.03097792107576141,
        "r2": 0.9549787640055721,
        "n": 2680
      },
      "validation": {
        "mae": 0.036108226571287684,
        "rmse": 0.048740286280274873,
        "r2": 0.8507438649580233,
        "n": 134
      },
      "test": {
        "mae": 0.06487467339966033,
        "rmse": 0.08858441327046103,
        "r2": 0.5092369013549143,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BGR",
      "BOL",
      "CIV",
      "GMB",
      "GNB",
      "IRL",
      "KAZ",
      "KGZ",
      "LTU",
      "MLI",
      "MUS",
      "MWI",
      "NER",
      "NGA",
      "OMN",
      "PRT",
      "SDN",
      "SLV",
      "SYR",
      "TGO",
      "TUR",
      "TZA",
      "UZB",
      "VEN",
      "YEM"
    ]
  },
  {
    "fold": 0,
    "region": "East Asia & Pacific",
    "algorithm": "catboost",
    "hyperparameters": {
      "iterations": 60,
      "depth": 6,
      "learning_rate": 0.0798261175712336,
      "l2_leaf_reg": 7.372653200164409
    },
    "metrics": {
      "train": {
        "mae": 0.030528843938014787,
        "rmse": 0.040591776101067144,
        "r2": 0.9226983107359263,
        "n": 2680
      },
      "validation": {
        "mae": 0.03825551940218811,
        "rmse": 0.051398020753969,
        "r2": 0.8340226482826271,
        "n": 134
      },
      "test": {
        "mae": 0.06804989254504529,
        "rmse": 0.0931481799451894,
        "r2": 0.4573672259321784,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BGR",
      "BOL",
      "CIV",
      "GMB",
      "GNB",
      "IRL",
      "KAZ",
      "KGZ",
      "LTU",
      "MLI",
      "MUS",
      "MWI",
      "NER",
      "NGA",
      "OMN",
      "PRT",
      "SDN",
      "SLV",
      "SYR",
      "TGO",
      "TUR",
      "TZA",
      "UZB",
      "VEN",
      "YEM"
    ]
  },
  {
    "fold": 0,
    "region": "East Asia & Pacific",
    "algorithm": "spatial_xgboost",
    "hyperparameters": {
      "n_estimators": 120,
      "max_depth": 3,
      "learning_rate": 0.09195011569464331,
      "reg_lambda": 1.272083045469184,
      "subsample": 0.8560204063533432
    },
    "metrics": {
      "train": {
        "mae": 0.021007619635936736,
        "rmse": 0.027934916972663062,
        "r2": 0.9633893326280902,
        "n": 2680
      },
      "validation": {
        "mae": 0.033665651263273165,
        "rmse": 0.04522230109275796,
        "r2": 0.8715123593526037,
        "n": 134
      },
      "test": {
        "mae": 0.06486953868014846,
        "rmse": 0.0890725244392707,
        "r2": 0.5038136692622861,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BGR",
      "BOL",
      "CIV",
      "GMB",
      "GNB",
      "IRL",
      "KAZ",
      "KGZ",
      "LTU",
      "MLI",
      "MUS",
      "MWI",
      "NER",
      "NGA",
      "OMN",
      "PRT",
      "SDN",
      "SLV",
      "SYR",
      "TGO",
      "TUR",
      "TZA",
      "UZB",
      "VEN",
      "YEM"
    ]
  },
  {
    "fold": 0,
    "region": "East Asia & Pacific",
    "algorithm": "cnn_lstm",
    "hyperparameters": {
      "hidden": 32,
      "channels": 4,
      "learning_rate": 0.004407984038169242,
      "weight_decay": 1.2681352169084594e-05,
      "epochs": 30
    },
    "metrics": {
      "train": {
        "mae": 0.07290213971025686,
        "rmse": 0.09599117232556248,
        "r2": 0.5677097233455477,
        "n": 2680
      },
      "validation": {
        "mae": 0.06298979671699786,
        "rmse": 0.08021810921384137,
        "r2": 0.5957026614583976,
        "n": 134
      },
      "test": {
        "mae": 0.07640262378586664,
        "rmse": 0.09617097109042998,
        "r2": 0.42157736890148034,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BGR",
      "BOL",
      "CIV",
      "GMB",
      "GNB",
      "IRL",
      "KAZ",
      "KGZ",
      "LTU",
      "MLI",
      "MUS",
      "MWI",
      "NER",
      "NGA",
      "OMN",
      "PRT",
      "SDN",
      "SLV",
      "SYR",
      "TGO",
      "TUR",
      "TZA",
      "UZB",
      "VEN",
      "YEM"
    ]
  },
  {
    "fold": 1,
    "region": "Europe & Central Asia",
    "algorithm": "random_forest",
    "hyperparameters": {
      "n_estimators": 100,
      "max_depth": 6,
      "min_samples_leaf": 12,
      "max_features": 0.7228791804198594
    },
    "metrics": {
      "train": {
        "mae": 0.03413510430557588,
        "rmse": 0.04653997850068178,
        "r2": 0.8949163947838135,
        "n": 2580
      },
      "validation": {
        "mae": 0.0455131469869249,
        "rmse": 0.06121546694855485,
        "r2": 0.7609700311867685,
        "n": 129
      },
      "test": {
        "mae": 0.04279243242099374,
        "rmse": 0.050376304973208524,
        "r2": -1.4425232375939472,
        "n": 32
      }
    },
    "inner_validation_countries": [
      "ARG",
      "BDI",
      "CHN",
      "COM",
      "CRI",
      "DZA",
      "ECU",
      "ERI",
      "GTM",
      "HTI",
      "IRQ",
      "JOR",
      "JPN",
      "KEN",
      "KIR",
      "LCA",
      "MDG",
      "MHL",
      "MYS",
      "PHL",
      "RWA",
      "SLE",
      "TGO",
      "TTO",
      "USA"
    ]
  },
  {
    "fold": 1,
    "region": "Europe & Central Asia",
    "algorithm": "xgboost",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 4,
      "learning_rate": 0.03772148420348191,
      "reg_lambda": 7.339476779392925,
      "subsample": 0.7620674114030095
    },
    "metrics": {
      "train": {
        "mae": 0.04207768032398335,
        "rmse": 0.05460581695395463,
        "r2": 0.8553360146189188,
        "n": 2580
      },
      "validation": {
        "mae": 0.04884422669068788,
        "rmse": 0.06265582989613151,
        "r2": 0.7495892349736587,
        "n": 129
      },
      "test": {
        "mae": 0.056357787596061824,
        "rmse": 0.061452597220334894,
        "r2": -2.634683256117595,
        "n": 32
      }
    },
    "inner_validation_countries": [
      "ARG",
      "BDI",
      "CHN",
      "COM",
      "CRI",
      "DZA",
      "ECU",
      "ERI",
      "GTM",
      "HTI",
      "IRQ",
      "JOR",
      "JPN",
      "KEN",
      "KIR",
      "LCA",
      "MDG",
      "MHL",
      "MYS",
      "PHL",
      "RWA",
      "SLE",
      "TGO",
      "TTO",
      "USA"
    ]
  },
  {
    "fold": 1,
    "region": "Europe & Central Asia",
    "algorithm": "catboost",
    "hyperparameters": {
      "iterations": 120,
      "depth": 3,
      "learning_rate": 0.05074990559829549,
      "l2_leaf_reg": 9.942152431546932
    },
    "metrics": {
      "train": {
        "mae": 0.044667368640935505,
        "rmse": 0.058407876437927005,
        "r2": 0.8344895418358957,
        "n": 2580
      },
      "validation": {
        "mae": 0.05030257403657982,
        "rmse": 0.06695540235054083,
        "r2": 0.7140426459528151,
        "n": 129
      },
      "test": {
        "mae": 0.04016658672557852,
        "rmse": 0.04513252779203746,
        "r2": -0.9604934774559006,
        "n": 32
      }
    },
    "inner_validation_countries": [
      "ARG",
      "BDI",
      "CHN",
      "COM",
      "CRI",
      "DZA",
      "ECU",
      "ERI",
      "GTM",
      "HTI",
      "IRQ",
      "JOR",
      "JPN",
      "KEN",
      "KIR",
      "LCA",
      "MDG",
      "MHL",
      "MYS",
      "PHL",
      "RWA",
      "SLE",
      "TGO",
      "TTO",
      "USA"
    ]
  },
  {
    "fold": 1,
    "region": "Europe & Central Asia",
    "algorithm": "spatial_xgboost",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 4,
      "learning_rate": 0.03772148420348191,
      "reg_lambda": 7.339476779392925,
      "subsample": 0.7620674114030095
    },
    "metrics": {
      "train": {
        "mae": 0.03355669024765411,
        "rmse": 0.04440114086509329,
        "r2": 0.9043531072077806,
        "n": 2580
      },
      "validation": {
        "mae": 0.041676455297895765,
        "rmse": 0.05518731719210846,
        "r2": 0.8057287268909769,
        "n": 129
      },
      "test": {
        "mae": 0.036520732786251245,
        "rmse": 0.04724967858009868,
        "r2": -1.1487396722203855,
        "n": 32
      }
    },
    "inner_validation_countries": [
      "ARG",
      "BDI",
      "CHN",
      "COM",
      "CRI",
      "DZA",
      "ECU",
      "ERI",
      "GTM",
      "HTI",
      "IRQ",
      "JOR",
      "JPN",
      "KEN",
      "KIR",
      "LCA",
      "MDG",
      "MHL",
      "MYS",
      "PHL",
      "RWA",
      "SLE",
      "TGO",
      "TTO",
      "USA"
    ]
  },
  {
    "fold": 1,
    "region": "Europe & Central Asia",
    "algorithm": "cnn_lstm",
    "hyperparameters": {
      "hidden": 32,
      "channels": 4,
      "learning_rate": 0.013413307395325933,
      "weight_decay": 4.603487705829326e-05,
      "epochs": 30
    },
    "metrics": {
      "train": {
        "mae": 0.06493839797676765,
        "rmse": 0.0869669496406462,
        "r2": 0.6330633577535134,
        "n": 2580
      },
      "validation": {
        "mae": 0.06329493469923966,
        "rmse": 0.08581965515152655,
        "r2": 0.5302102340508987,
        "n": 129
      },
      "test": {
        "mae": 0.030170281165279447,
        "rmse": 0.033847461583511505,
        "r2": -0.10265155233870438,
        "n": 32
      }
    },
    "inner_validation_countries": [
      "ARG",
      "BDI",
      "CHN",
      "COM",
      "CRI",
      "DZA",
      "ECU",
      "ERI",
      "GTM",
      "HTI",
      "IRQ",
      "JOR",
      "JPN",
      "KEN",
      "KIR",
      "LCA",
      "MDG",
      "MHL",
      "MYS",
      "PHL",
      "RWA",
      "SLE",
      "TGO",
      "TTO",
      "USA"
    ]
  },
  {
    "fold": 2,
    "region": "Latin America & Caribbean ",
    "algorithm": "random_forest",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 4,
      "min_samples_leaf": 7,
      "max_features": 0.8972874581141085
    },
    "metrics": {
      "train": {
        "mae": 0.042906961710571984,
        "rmse": 0.05780271554673255,
        "r2": 0.851731225653035,
        "n": 2680
      },
      "validation": {
        "mae": 0.04912820986620214,
        "rmse": 0.0657622698942305,
        "r2": 0.7475901623072138,
        "n": 134
      },
      "test": {
        "mae": 0.05633035840327475,
        "rmse": 0.08289291750381166,
        "r2": -0.07182583467184145,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "ALB",
      "BGD",
      "BHR",
      "BIH",
      "CHN",
      "DJI",
      "GMB",
      "IND",
      "IRQ",
      "JOR",
      "KEN",
      "KGZ",
      "KOR",
      "LBY",
      "MKD",
      "MMR",
      "MOZ",
      "NGA",
      "PAK",
      "POL",
      "SGP",
      "TCD",
      "TON",
      "TUV",
      "UKR",
      "USA"
    ]
  },
  {
    "fold": 2,
    "region": "Latin America & Caribbean ",
    "algorithm": "xgboost",
    "hyperparameters": {
      "n_estimators": 120,
      "max_depth": 4,
      "learning_rate": 0.10260723602492851,
      "reg_lambda": 8.884713643526181,
      "subsample": 0.8369863326816811
    },
    "metrics": {
      "train": {
        "mae": 0.016945514370042332,
        "rmse": 0.024133186654312955,
        "r2": 0.9741546416830845,
        "n": 2680
      },
      "validation": {
        "mae": 0.03325488569003655,
        "rmse": 0.046550987791101804,
        "r2": 0.8735233106231172,
        "n": 134
      },
      "test": {
        "mae": 0.05647880722968667,
        "rmse": 0.07596039630857339,
        "r2": 0.09995584904144128,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "ALB",
      "BGD",
      "BHR",
      "BIH",
      "CHN",
      "DJI",
      "GMB",
      "IND",
      "IRQ",
      "JOR",
      "KEN",
      "KGZ",
      "KOR",
      "LBY",
      "MKD",
      "MMR",
      "MOZ",
      "NGA",
      "PAK",
      "POL",
      "SGP",
      "TCD",
      "TON",
      "TUV",
      "UKR",
      "USA"
    ]
  },
  {
    "fold": 2,
    "region": "Latin America & Caribbean ",
    "algorithm": "catboost",
    "hyperparameters": {
      "iterations": 60,
      "depth": 4,
      "learning_rate": 0.14958676868519274,
      "l2_leaf_reg": 3.3260527528036627
    },
    "metrics": {
      "train": {
        "mae": 0.03257752328139523,
        "rmse": 0.04395809262610601,
        "r2": 0.9142506388031685,
        "n": 2680
      },
      "validation": {
        "mae": 0.041014098740354075,
        "rmse": 0.05640217791044854,
        "r2": 0.8143288465306737,
        "n": 134
      },
      "test": {
        "mae": 0.047041171885754,
        "rmse": 0.0661875433306411,
        "r2": 0.3166520535607772,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "ALB",
      "BGD",
      "BHR",
      "BIH",
      "CHN",
      "DJI",
      "GMB",
      "IND",
      "IRQ",
      "JOR",
      "KEN",
      "KGZ",
      "KOR",
      "LBY",
      "MKD",
      "MMR",
      "MOZ",
      "NGA",
      "PAK",
      "POL",
      "SGP",
      "TCD",
      "TON",
      "TUV",
      "UKR",
      "USA"
    ]
  },
  {
    "fold": 2,
    "region": "Latin America & Caribbean ",
    "algorithm": "spatial_xgboost",
    "hyperparameters": {
      "n_estimators": 120,
      "max_depth": 4,
      "learning_rate": 0.10260723602492851,
      "reg_lambda": 8.884713643526181,
      "subsample": 0.8369863326816811
    },
    "metrics": {
      "train": {
        "mae": 0.01569454494260329,
        "rmse": 0.021227547523242116,
        "r2": 0.9800035520310786,
        "n": 2680
      },
      "validation": {
        "mae": 0.03100322502255602,
        "rmse": 0.0424613633269902,
        "r2": 0.8947697613110811,
        "n": 134
      },
      "test": {
        "mae": 0.05551163720553163,
        "rmse": 0.07416350333400823,
        "r2": 0.14203446222285077,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "ALB",
      "BGD",
      "BHR",
      "BIH",
      "CHN",
      "DJI",
      "GMB",
      "IND",
      "IRQ",
      "JOR",
      "KEN",
      "KGZ",
      "KOR",
      "LBY",
      "MKD",
      "MMR",
      "MOZ",
      "NGA",
      "PAK",
      "POL",
      "SGP",
      "TCD",
      "TON",
      "TUV",
      "UKR",
      "USA"
    ]
  },
  {
    "fold": 2,
    "region": "Latin America & Caribbean ",
    "algorithm": "cnn_lstm",
    "hyperparameters": {
      "hidden": 8,
      "channels": 8,
      "learning_rate": 0.01370636257344906,
      "weight_decay": 5.9614364355099526e-05,
      "epochs": 50
    },
    "metrics": {
      "train": {
        "mae": 0.05762192582250086,
        "rmse": 0.07311051151994115,
        "r2": 0.762800997298196,
        "n": 2680
      },
      "validation": {
        "mae": 0.05956902627335555,
        "rmse": 0.0744897040090056,
        "r2": 0.676149043318394,
        "n": 134
      },
      "test": {
        "mae": 0.040341638759330466,
        "rmse": 0.058665095765017425,
        "r2": 0.4631549685809586,
        "n": 27
      }
    },
    "inner_validation_countries": [
      "ALB",
      "BGD",
      "BHR",
      "BIH",
      "CHN",
      "DJI",
      "GMB",
      "IND",
      "IRQ",
      "JOR",
      "KEN",
      "KGZ",
      "KOR",
      "LBY",
      "MKD",
      "MMR",
      "MOZ",
      "NGA",
      "PAK",
      "POL",
      "SGP",
      "TCD",
      "TON",
      "TUV",
      "UKR",
      "USA"
    ]
  },
  {
    "fold": 3,
    "region": "Middle East, North Africa, Afghanistan & Pakistan",
    "algorithm": "random_forest",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 3,
      "min_samples_leaf": 11,
      "max_features": 0.5334691355941747
    },
    "metrics": {
      "train": {
        "mae": 0.049207992151631304,
        "rmse": 0.06536222397950905,
        "r2": 0.8029034240459977,
        "n": 2820
      },
      "validation": {
        "mae": 0.05436433274856357,
        "rmse": 0.07084783305575158,
        "r2": 0.6885007141077979,
        "n": 141
      },
      "test": {
        "mae": 0.02399513200264276,
        "rmse": 0.03699741059750588,
        "r2": 0.9072466567245802,
        "n": 20
      }
    },
    "inner_validation_countries": [
      "BRA",
      "ECU",
      "GUY",
      "HND",
      "KEN",
      "KGZ",
      "KOR",
      "LCA",
      "LSO",
      "LTU",
      "MDG",
      "MEX",
      "MRT",
      "NER",
      "NGA",
      "PNG",
      "POL",
      "PRK",
      "PRT",
      "PRY",
      "SEN",
      "SRB",
      "SWZ",
      "TGO",
      "TKM",
      "URY",
      "UZB",
      "VEN"
    ]
  },
  {
    "fold": 3,
    "region": "Middle East, North Africa, Afghanistan & Pakistan",
    "algorithm": "xgboost",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 2,
      "learning_rate": 0.1542528629289368,
      "reg_lambda": 4.613328434400988,
      "subsample": 0.7365796826304397
    },
    "metrics": {
      "train": {
        "mae": 0.03873270456500034,
        "rmse": 0.05210354681883496,
        "r2": 0.8747551106091347,
        "n": 2820
      },
      "validation": {
        "mae": 0.04672396844107631,
        "rmse": 0.06289240377948477,
        "r2": 0.7545289386517714,
        "n": 141
      },
      "test": {
        "mae": 0.03547471196651458,
        "rmse": 0.052796838215361526,
        "r2": 0.8111127063075642,
        "n": 20
      }
    },
    "inner_validation_countries": [
      "BRA",
      "ECU",
      "GUY",
      "HND",
      "KEN",
      "KGZ",
      "KOR",
      "LCA",
      "LSO",
      "LTU",
      "MDG",
      "MEX",
      "MRT",
      "NER",
      "NGA",
      "PNG",
      "POL",
      "PRK",
      "PRT",
      "PRY",
      "SEN",
      "SRB",
      "SWZ",
      "TGO",
      "TKM",
      "URY",
      "UZB",
      "VEN"
    ]
  },
  {
    "fold": 3,
    "region": "Middle East, North Africa, Afghanistan & Pakistan",
    "algorithm": "catboost",
    "hyperparameters": {
      "iterations": 60,
      "depth": 3,
      "learning_rate": 0.14351558557307909,
      "l2_leaf_reg": 1.6024444406951446
    },
    "metrics": {
      "train": {
        "mae": 0.03936511718989688,
        "rmse": 0.05184975574721556,
        "r2": 0.8759722493016029,
        "n": 2820
      },
      "validation": {
        "mae": 0.046382205392452934,
        "rmse": 0.06164328275931028,
        "r2": 0.7641828264814832,
        "n": 141
      },
      "test": {
        "mae": 0.035036256031685406,
        "rmse": 0.05631642421098659,
        "r2": 0.7850897857489647,
        "n": 20
      }
    },
    "inner_validation_countries": [
      "BRA",
      "ECU",
      "GUY",
      "HND",
      "KEN",
      "KGZ",
      "KOR",
      "LCA",
      "LSO",
      "LTU",
      "MDG",
      "MEX",
      "MRT",
      "NER",
      "NGA",
      "PNG",
      "POL",
      "PRK",
      "PRT",
      "PRY",
      "SEN",
      "SRB",
      "SWZ",
      "TGO",
      "TKM",
      "URY",
      "UZB",
      "VEN"
    ]
  },
  {
    "fold": 3,
    "region": "Middle East, North Africa, Afghanistan & Pakistan",
    "algorithm": "spatial_xgboost",
    "hyperparameters": {
      "n_estimators": 120,
      "max_depth": 3,
      "learning_rate": 0.02577931171732031,
      "reg_lambda": 4.4090679573621525,
      "subsample": 0.7930221812548667
    },
    "metrics": {
      "train": {
        "mae": 0.03238976989098715,
        "rmse": 0.043891354222679445,
        "r2": 0.9111242252835987,
        "n": 2820
      },
      "validation": {
        "mae": 0.04049854662689905,
        "rmse": 0.05469259953401216,
        "r2": 0.8143644948964422,
        "n": 141
      },
      "test": {
        "mae": 0.03562410376399425,
        "rmse": 0.04790166885165453,
        "r2": 0.8445151059512364,
        "n": 20
      }
    },
    "inner_validation_countries": [
      "BRA",
      "ECU",
      "GUY",
      "HND",
      "KEN",
      "KGZ",
      "KOR",
      "LCA",
      "LSO",
      "LTU",
      "MDG",
      "MEX",
      "MRT",
      "NER",
      "NGA",
      "PNG",
      "POL",
      "PRK",
      "PRT",
      "PRY",
      "SEN",
      "SRB",
      "SWZ",
      "TGO",
      "TKM",
      "URY",
      "UZB",
      "VEN"
    ]
  },
  {
    "fold": 3,
    "region": "Middle East, North Africa, Afghanistan & Pakistan",
    "algorithm": "cnn_lstm",
    "hyperparameters": {
      "hidden": 32,
      "channels": 8,
      "learning_rate": 0.004193830780458456,
      "weight_decay": 5.3490230620743196e-05,
      "epochs": 50
    },
    "metrics": {
      "train": {
        "mae": 0.061684466686337557,
        "rmse": 0.0800982689555244,
        "r2": 0.7040136393713878,
        "n": 2820
      },
      "validation": {
        "mae": 0.06379562496378066,
        "rmse": 0.08312953506185088,
        "r2": 0.571140914231618,
        "n": 141
      },
      "test": {
        "mae": 0.052412768211960795,
        "rmse": 0.06209496836936245,
        "r2": 0.7387238703011467,
        "n": 20
      }
    },
    "inner_validation_countries": [
      "BRA",
      "ECU",
      "GUY",
      "HND",
      "KEN",
      "KGZ",
      "KOR",
      "LCA",
      "LSO",
      "LTU",
      "MDG",
      "MEX",
      "MRT",
      "NER",
      "NGA",
      "PNG",
      "POL",
      "PRK",
      "PRT",
      "PRY",
      "SEN",
      "SRB",
      "SWZ",
      "TGO",
      "TKM",
      "URY",
      "UZB",
      "VEN"
    ]
  },
  {
    "fold": 4,
    "region": "North America",
    "algorithm": "random_forest",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 9,
      "min_samples_leaf": 6,
      "max_features": 0.8138840441170949
    },
    "metrics": {
      "train": {
        "mae": 0.017275317120796503,
        "rmse": 0.025008937185069167,
        "r2": 0.9706492872239562,
        "n": 3200
      },
      "validation": {
        "mae": 0.03352190055583437,
        "rmse": 0.04871907314605912,
        "r2": 0.851235448541823,
        "n": 160
      },
      "test": {
        "mae": 0.016634549874744095,
        "rmse": 0.016634549874744095,
        "r2": null,
        "n": 1
      }
    },
    "inner_validation_countries": [
      "BEL",
      "BFA",
      "BGD",
      "BRA",
      "CHN",
      "COD",
      "CRI",
      "CUB",
      "DEU",
      "IRQ",
      "JPN",
      "KOR",
      "KWT",
      "LAO",
      "LBY",
      "MAR",
      "MDG",
      "MHL",
      "MRT",
      "PAK",
      "PER",
      "PHL",
      "PRT",
      "QAT",
      "SAU",
      "SEN",
      "SGP",
      "SRB",
      "SWZ",
      "TTO",
      "UGA",
      "ZAF"
    ]
  },
  {
    "fold": 4,
    "region": "North America",
    "algorithm": "xgboost",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 2,
      "learning_rate": 0.11457921969851177,
      "reg_lambda": 1.2772987540591778,
      "subsample": 0.9811712072465193
    },
    "metrics": {
      "train": {
        "mae": 0.04119555194512475,
        "rmse": 0.055075223902930334,
        "r2": 0.8576554893283315,
        "n": 3200
      },
      "validation": {
        "mae": 0.04751127394540235,
        "rmse": 0.06439159234969004,
        "r2": 0.740127842454502,
        "n": 160
      },
      "test": {
        "mae": 0.0014373837411403648,
        "rmse": 0.0014373837411403648,
        "r2": null,
        "n": 1
      }
    },
    "inner_validation_countries": [
      "BEL",
      "BFA",
      "BGD",
      "BRA",
      "CHN",
      "COD",
      "CRI",
      "CUB",
      "DEU",
      "IRQ",
      "JPN",
      "KOR",
      "KWT",
      "LAO",
      "LBY",
      "MAR",
      "MDG",
      "MHL",
      "MRT",
      "PAK",
      "PER",
      "PHL",
      "PRT",
      "QAT",
      "SAU",
      "SEN",
      "SGP",
      "SRB",
      "SWZ",
      "TTO",
      "UGA",
      "ZAF"
    ]
  },
  {
    "fold": 4,
    "region": "North America",
    "algorithm": "catboost",
    "hyperparameters": {
      "iterations": 120,
      "depth": 3,
      "learning_rate": 0.0471238834801046,
      "l2_leaf_reg": 3.361736767853774
    },
    "metrics": {
      "train": {
        "mae": 0.04221788201053833,
        "rmse": 0.05587735649186969,
        "r2": 0.8534789964123104,
        "n": 3200
      },
      "validation": {
        "mae": 0.04688446423616995,
        "rmse": 0.06319216562523558,
        "r2": 0.7497189891481354,
        "n": 160
      },
      "test": {
        "mae": 0.005145134654149501,
        "rmse": 0.005145134654149501,
        "r2": null,
        "n": 1
      }
    },
    "inner_validation_countries": [
      "BEL",
      "BFA",
      "BGD",
      "BRA",
      "CHN",
      "COD",
      "CRI",
      "CUB",
      "DEU",
      "IRQ",
      "JPN",
      "KOR",
      "KWT",
      "LAO",
      "LBY",
      "MAR",
      "MDG",
      "MHL",
      "MRT",
      "PAK",
      "PER",
      "PHL",
      "PRT",
      "QAT",
      "SAU",
      "SEN",
      "SGP",
      "SRB",
      "SWZ",
      "TTO",
      "UGA",
      "ZAF"
    ]
  },
  {
    "fold": 4,
    "region": "North America",
    "algorithm": "spatial_xgboost",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 2,
      "learning_rate": 0.11457921969851177,
      "reg_lambda": 1.2772987540591778,
      "subsample": 0.9811712072465193
    },
    "metrics": {
      "train": {
        "mae": 0.03464183881491216,
        "rmse": 0.046033854385496155,
        "r2": 0.9005550210348718,
        "n": 3200
      },
      "validation": {
        "mae": 0.04094026814255489,
        "rmse": 0.05524585625352125,
        "r2": 0.8087062238113895,
        "n": 160
      },
      "test": {
        "mae": 0.04,
        "rmse": 0.04,
        "r2": null,
        "n": 1
      }
    },
    "inner_validation_countries": [
      "BEL",
      "BFA",
      "BGD",
      "BRA",
      "CHN",
      "COD",
      "CRI",
      "CUB",
      "DEU",
      "IRQ",
      "JPN",
      "KOR",
      "KWT",
      "LAO",
      "LBY",
      "MAR",
      "MDG",
      "MHL",
      "MRT",
      "PAK",
      "PER",
      "PHL",
      "PRT",
      "QAT",
      "SAU",
      "SEN",
      "SGP",
      "SRB",
      "SWZ",
      "TTO",
      "UGA",
      "ZAF"
    ]
  },
  {
    "fold": 4,
    "region": "North America",
    "algorithm": "cnn_lstm",
    "hyperparameters": {
      "hidden": 16,
      "channels": 8,
      "learning_rate": 0.013430707915223876,
      "weight_decay": 9.354002479703925e-05,
      "epochs": 50
    },
    "metrics": {
      "train": {
        "mae": 0.058119547118209304,
        "rmse": 0.07251757836697027,
        "r2": 0.7532172684929441,
        "n": 3200
      },
      "validation": {
        "mae": 0.062075874840654424,
        "rmse": 0.07593197695470613,
        "r2": 0.6386310476171659,
        "n": 160
      },
      "test": {
        "mae": 0.021817068606615066,
        "rmse": 0.021817068606615066,
        "r2": null,
        "n": 1
      }
    },
    "inner_validation_countries": [
      "BEL",
      "BFA",
      "BGD",
      "BRA",
      "CHN",
      "COD",
      "CRI",
      "CUB",
      "DEU",
      "IRQ",
      "JPN",
      "KOR",
      "KWT",
      "LAO",
      "LBY",
      "MAR",
      "MDG",
      "MHL",
      "MRT",
      "PAK",
      "PER",
      "PHL",
      "PRT",
      "QAT",
      "SAU",
      "SEN",
      "SGP",
      "SRB",
      "SWZ",
      "TTO",
      "UGA",
      "ZAF"
    ]
  },
  {
    "fold": 5,
    "region": "South Asia",
    "algorithm": "random_forest",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 5,
      "min_samples_leaf": 5,
      "max_features": 0.7632019427864085
    },
    "metrics": {
      "train": {
        "mae": 0.03616848195284793,
        "rmse": 0.048682920173510266,
        "r2": 0.8879496389559307,
        "n": 3100
      },
      "validation": {
        "mae": 0.04371972286359723,
        "rmse": 0.06083650822811072,
        "r2": 0.7718725120418852,
        "n": 155
      },
      "test": {
        "mae": 0.0657538912995899,
        "rmse": 0.07561484744154714,
        "r2": 0.0526272367311148,
        "n": 6
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BHR",
      "BIH",
      "BLR",
      "BRN",
      "CAF",
      "CMR",
      "COG",
      "ETH",
      "FIN",
      "GHA",
      "GUY",
      "IRL",
      "IRN",
      "JPN",
      "KIR",
      "LAO",
      "MEX",
      "MUS",
      "MWI",
      "NAM",
      "PRT",
      "SDN",
      "SGP",
      "SLV",
      "SSD",
      "STP",
      "TCA",
      "TUV",
      "YEM",
      "ZWE"
    ]
  },
  {
    "fold": 5,
    "region": "South Asia",
    "algorithm": "xgboost",
    "hyperparameters": {
      "n_estimators": 120,
      "max_depth": 5,
      "learning_rate": 0.026800603072716287,
      "reg_lambda": 4.690120368790519,
      "subsample": 0.7015713867096708
    },
    "metrics": {
      "train": {
        "mae": 0.026549055774788704,
        "rmse": 0.03555279126202536,
        "r2": 0.9402404354071113,
        "n": 3100
      },
      "validation": {
        "mae": 0.03736749459668514,
        "rmse": 0.05152316251906451,
        "r2": 0.8363733328983437,
        "n": 155
      },
      "test": {
        "mae": 0.051142903447151174,
        "rmse": 0.058672757313343364,
        "r2": 0.42959971911640216,
        "n": 6
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BHR",
      "BIH",
      "BLR",
      "BRN",
      "CAF",
      "CMR",
      "COG",
      "ETH",
      "FIN",
      "GHA",
      "GUY",
      "IRL",
      "IRN",
      "JPN",
      "KIR",
      "LAO",
      "MEX",
      "MUS",
      "MWI",
      "NAM",
      "PRT",
      "SDN",
      "SGP",
      "SLV",
      "SSD",
      "STP",
      "TCA",
      "TUV",
      "YEM",
      "ZWE"
    ]
  },
  {
    "fold": 5,
    "region": "South Asia",
    "algorithm": "catboost",
    "hyperparameters": {
      "iterations": 60,
      "depth": 4,
      "learning_rate": 0.1016391459075008,
      "l2_leaf_reg": 3.219844435971777
    },
    "metrics": {
      "train": {
        "mae": 0.03793000291684494,
        "rmse": 0.05052496374667978,
        "r2": 0.8793097909171609,
        "n": 3100
      },
      "validation": {
        "mae": 0.043901520905503866,
        "rmse": 0.06067110510416445,
        "r2": 0.7731112979541196,
        "n": 155
      },
      "test": {
        "mae": 0.05869115276821172,
        "rmse": 0.06350707423738935,
        "r2": 0.33173157015778576,
        "n": 6
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BHR",
      "BIH",
      "BLR",
      "BRN",
      "CAF",
      "CMR",
      "COG",
      "ETH",
      "FIN",
      "GHA",
      "GUY",
      "IRL",
      "IRN",
      "JPN",
      "KIR",
      "LAO",
      "MEX",
      "MUS",
      "MWI",
      "NAM",
      "PRT",
      "SDN",
      "SGP",
      "SLV",
      "SSD",
      "STP",
      "TCA",
      "TUV",
      "YEM",
      "ZWE"
    ]
  },
  {
    "fold": 5,
    "region": "South Asia",
    "algorithm": "spatial_xgboost",
    "hyperparameters": {
      "n_estimators": 120,
      "max_depth": 5,
      "learning_rate": 0.026800603072716287,
      "reg_lambda": 4.690120368790519,
      "subsample": 0.7015713867096708
    },
    "metrics": {
      "train": {
        "mae": 0.02238744760736358,
        "rmse": 0.029914826076825756,
        "r2": 0.9576909783395638,
        "n": 3100
      },
      "validation": {
        "mae": 0.033649655252930157,
        "rmse": 0.04655694253179698,
        "r2": 0.8663964607295689,
        "n": 155
      },
      "test": {
        "mae": 0.049448426306904276,
        "rmse": 0.055806435745846296,
        "r2": 0.48396957792408557,
        "n": 6
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BHR",
      "BIH",
      "BLR",
      "BRN",
      "CAF",
      "CMR",
      "COG",
      "ETH",
      "FIN",
      "GHA",
      "GUY",
      "IRL",
      "IRN",
      "JPN",
      "KIR",
      "LAO",
      "MEX",
      "MUS",
      "MWI",
      "NAM",
      "PRT",
      "SDN",
      "SGP",
      "SLV",
      "SSD",
      "STP",
      "TCA",
      "TUV",
      "YEM",
      "ZWE"
    ]
  },
  {
    "fold": 5,
    "region": "South Asia",
    "algorithm": "cnn_lstm",
    "hyperparameters": {
      "hidden": 32,
      "channels": 8,
      "learning_rate": 0.00485837303934764,
      "weight_decay": 8.236212595698651e-05,
      "epochs": 50
    },
    "metrics": {
      "train": {
        "mae": 0.05867951791347996,
        "rmse": 0.07868176126507075,
        "r2": 0.7073098115230116,
        "n": 3100
      },
      "validation": {
        "mae": 0.05865335440443408,
        "rmse": 0.07930441422224303,
        "r2": 0.6123464345662706,
        "n": 155
      },
      "test": {
        "mae": 0.05955067847172419,
        "rmse": 0.06636918281742907,
        "r2": 0.2701398116486571,
        "n": 6
      }
    },
    "inner_validation_countries": [
      "BFA",
      "BHR",
      "BIH",
      "BLR",
      "BRN",
      "CAF",
      "CMR",
      "COG",
      "ETH",
      "FIN",
      "GHA",
      "GUY",
      "IRL",
      "IRN",
      "JPN",
      "KIR",
      "LAO",
      "MEX",
      "MUS",
      "MWI",
      "NAM",
      "PRT",
      "SDN",
      "SGP",
      "SLV",
      "SSD",
      "STP",
      "TCA",
      "TUV",
      "YEM",
      "ZWE"
    ]
  },
  {
    "fold": 6,
    "region": "Sub-Saharan Africa ",
    "algorithm": "random_forest",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 9,
      "min_samples_leaf": 4,
      "max_features": 0.8859846148990744
    },
    "metrics": {
      "train": {
        "mae": 0.012146317306790168,
        "rmse": 0.017940127417789893,
        "r2": 0.9813487185586148,
        "n": 2260
      },
      "validation": {
        "mae": 0.02464233570649379,
        "rmse": 0.03621154502873026,
        "r2": 0.8850261026770327,
        "n": 113
      },
      "test": {
        "mae": 0.10991498013114048,
        "rmse": 0.13802218263813507,
        "r2": -0.546585033017668,
        "n": 48
      }
    },
    "inner_validation_countries": [
      "AUS",
      "BLR",
      "BRA",
      "CZE",
      "GTM",
      "JOR",
      "KGZ",
      "LBY",
      "MAR",
      "MDA",
      "MEX",
      "MHL",
      "MMR",
      "PRY",
      "SAU",
      "SGP",
      "SLV",
      "SYR",
      "USA",
      "VEN",
      "VNM",
      "YEM"
    ]
  },
  {
    "fold": 6,
    "region": "Sub-Saharan Africa ",
    "algorithm": "xgboost",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 5,
      "learning_rate": 0.06587639485672231,
      "reg_lambda": 4.428443854913076,
      "subsample": 0.8148366581251354
    },
    "metrics": {
      "train": {
        "mae": 0.01789140869721243,
        "rmse": 0.02447552099186748,
        "r2": 0.965284652320731,
        "n": 2260
      },
      "validation": {
        "mae": 0.02826314739408219,
        "rmse": 0.0383337462839144,
        "r2": 0.8711549699889863,
        "n": 113
      },
      "test": {
        "mae": 0.10855035864810147,
        "rmse": 0.13261516459796494,
        "r2": -0.4277836305379945,
        "n": 48
      }
    },
    "inner_validation_countries": [
      "AUS",
      "BLR",
      "BRA",
      "CZE",
      "GTM",
      "JOR",
      "KGZ",
      "LBY",
      "MAR",
      "MDA",
      "MEX",
      "MHL",
      "MMR",
      "PRY",
      "SAU",
      "SGP",
      "SLV",
      "SYR",
      "USA",
      "VEN",
      "VNM",
      "YEM"
    ]
  },
  {
    "fold": 6,
    "region": "Sub-Saharan Africa ",
    "algorithm": "catboost",
    "hyperparameters": {
      "iterations": 120,
      "depth": 6,
      "learning_rate": 0.16576938953281314,
      "l2_leaf_reg": 2.4830504220639993
    },
    "metrics": {
      "train": {
        "mae": 0.010032109618618898,
        "rmse": 0.01356824137926664,
        "r2": 0.9893314658637264,
        "n": 2260
      },
      "validation": {
        "mae": 0.023682508298698852,
        "rmse": 0.03270800186753092,
        "r2": 0.906197768404248,
        "n": 113
      },
      "test": {
        "mae": 0.11325972693381604,
        "rmse": 0.13405434193654456,
        "r2": -0.45894120850067255,
        "n": 48
      }
    },
    "inner_validation_countries": [
      "AUS",
      "BLR",
      "BRA",
      "CZE",
      "GTM",
      "JOR",
      "KGZ",
      "LBY",
      "MAR",
      "MDA",
      "MEX",
      "MHL",
      "MMR",
      "PRY",
      "SAU",
      "SGP",
      "SLV",
      "SYR",
      "USA",
      "VEN",
      "VNM",
      "YEM"
    ]
  },
  {
    "fold": 6,
    "region": "Sub-Saharan Africa ",
    "algorithm": "spatial_xgboost",
    "hyperparameters": {
      "n_estimators": 60,
      "max_depth": 5,
      "learning_rate": 0.06587639485672231,
      "reg_lambda": 4.428443854913076,
      "subsample": 0.8148366581251354
    },
    "metrics": {
      "train": {
        "mae": 0.015872959802910633,
        "rmse": 0.021545864567095858,
        "r2": 0.9730979435128382,
        "n": 2260
      },
      "validation": {
        "mae": 0.026090836536366485,
        "rmse": 0.0343793646577652,
        "r2": 0.8963663401055001,
        "n": 113
      },
      "test": {
        "mae": 0.114105982297663,
        "rmse": 0.13834038433861245,
        "r2": -0.553724367597145,
        "n": 48
      }
    },
    "inner_validation_countries": [
      "AUS",
      "BLR",
      "BRA",
      "CZE",
      "GTM",
      "JOR",
      "KGZ",
      "LBY",
      "MAR",
      "MDA",
      "MEX",
      "MHL",
      "MMR",
      "PRY",
      "SAU",
      "SGP",
      "SLV",
      "SYR",
      "USA",
      "VEN",
      "VNM",
      "YEM"
    ]
  },
  {
    "fold": 6,
    "region": "Sub-Saharan Africa ",
    "algorithm": "cnn_lstm",
    "hyperparameters": {
      "hidden": 32,
      "channels": 8,
      "learning_rate": 0.019073244188246942,
      "weight_decay": 0.00021879397934373507,
      "epochs": 50
    },
    "metrics": {
      "train": {
        "mae": 0.045677294091062734,
        "rmse": 0.06242866175166916,
        "r2": 0.7741470957186822,
        "n": 2260
      },
      "validation": {
        "mae": 0.042589604007195574,
        "rmse": 0.05921193466990312,
        "r2": 0.69258599752463,
        "n": 113
      },
      "test": {
        "mae": 0.10934645891437927,
        "rmse": 0.12953824773921127,
        "r2": -0.3622978063760529,
        "n": 48
      }
    },
    "inner_validation_countries": [
      "AUS",
      "BLR",
      "BRA",
      "CZE",
      "GTM",
      "JOR",
      "KGZ",
      "LBY",
      "MAR",
      "MDA",
      "MEX",
      "MHL",
      "MMR",
      "PRY",
      "SAU",
      "SGP",
      "SLV",
      "SYR",
      "USA",
      "VEN",
      "VNM",
      "YEM"
    ]
  }
]
```

## Dependencias

```json
{
  "numpy": "1.26.4",
  "pandas": "2.3.3",
  "scipy": "1.17.1",
  "scikit-learn": "1.5.2",
  "xgboost": "2.1.4",
  "catboost": "1.2.10",
  "torch": "2.15.0+cpu",
  "optuna": "4.9.0",
  "joblib": "1.6.0"
}
```

## Limitaciones registradas

- Ecological country-year regression, not individual child risk classification.
- Outcome is modelled UNICEF/WHO/World Bank JME prevalence; possible shared covariates and retrospective revisions limit independence.
- Contemporaneous covariates are used through 2023: retrospective nowcasting, not prospective forecasting.
- No individual clinical, sex, wealth or rural fairness metrics are identifiable.
- PM2.5 is absent in 2024; final test year is 2023.
- Female secondary enrolment missingness is handled by fold-trained medians, not observed replacement measurements; sensitivity analysis has not been run.
- Country capitals are geographic proxies. North America contains one country; regional inference is weak.
- One fixed seed per study; hyperparameter and training stochasticity are not covered by bootstrap intervals.
- Baseline persistence uses held-out country 2022 outcome labels and therefore has a stronger information set than transferable models.
- All intervals are exploratory region-cluster bootstrap; no intervals for true epidemiological prevalence or JME estimation uncertainty.
- Train and validation summary metrics average overlapping outer-fold fits; only test metrics are disjoint out-of-fold predictions.

## Reproducir

Desde la raíz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/acquire_real_data.ps1
cd backend
../.venv/Scripts/python.exe -m scripts.train_real --trials 10 --seed 42
../.venv/Scripts/python.exe -m scripts.verify_real 20261106T194207-e0ed9fcf
```

El snapshot no se actualiza salvo que se solicite `-Refresh`. La nueva ejecución tendrá otro identificador. Las versiones y el hardware pueden modificar resultados numéricos.

## Artefactos de esta ejecución

Carpeta: `backend/storage/research/20261106T194207-e0ed9fcf/`.

- `results.json`: evidencia completa y predicciones.
- `trials.csv`: los 350 ensayos completos.
- `epochs.csv`: pérdidas train/validation por iteración o época. Random Forest no tiene épocas.
- `models/`: 35 predictores exteriores y transformadores; CNN conserva pesos.
- `predictions.csv`, `regional_metrics.csv`, `pairwise_statistics.csv`, `metrics.csv`.
- `figures/`: cuatro gráficos en PNG, SVG y PDF.
- `verification.json`: verificaciones de integridad y recarga de los 35 modelos, incluidas iteraciones fijas de CatBoost.
- `artifact_hashes.json`: huellas de artefactos inmutables.
- `evidence.zip`: paquete de evidencia, snapshot, código y modelos.

## Aplicación y artículo

Iniciar la web sin sembrar datos sintéticos:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_real_web.ps1
```

Abrir http://127.0.0.1:8000/investigacion. La investigación nacional real no valida los módulos clínicos históricos de demostración.
Artículo revisado: `entregables/Articulo_NutriRisk_Datos_Reales.docx` y PDF. La copia anterior se conserva.

Fuentes: https://data.unicef.org/resources/jme/ y https://api.worldbank.org/v2/. Procedencia y condiciones por indicador en `data/real/manifest.json`.