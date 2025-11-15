
```
chess_brilliance_ai
├─ .claude
│  └─ settings.local.json
├─ data
│  ├─ labeled_features
│  │  └─ teacher_labels.parquet
│  └─ raw_pgns
│     ├─ Adams.pgn
│     ├─ Akopian.pgn
│     ├─ Alekhine.pgn
│     ├─ Almasi.pgn
│     ├─ Anand.pgn
│     ├─ Aronian.pgn
│     ├─ Ashley.pgn
│     ├─ Bacrot.pgn
│     ├─ Bareev.pgn
│     ├─ BecerraRivero.pgn
│     ├─ Beliavsky.pgn
│     ├─ Benjamin.pgn
│     └─ Benko.pgn
├─ README.md
├─ requirements.txt
├─ setup_chess_brilliance_ai.ps1
├─ student
│  ├─ brilliance_model.json
│  ├─ evaluate_model.py
│  ├─ label_encoder.pkl
│  ├─ predict_move_type.py
│  └─ train_xgboost.py
├─ teacher
│  ├─ analyze_positions.py
│  ├─ detect_motifs.py
│  ├─ label_rules.py
│  └─ __init__.py
├─ test
│  ├─ app.py
│  ├─ AUTO_ANALYSIS_GUIDE.md
│  ├─ basic_move_labels.py
│  ├─ brilliant.html
│  ├─ CALIBRATION_README.md
│  ├─ callibrator samples
│  │  ├─ calibration_samples_1.json
│  │  └─ calibration_samples_2.json
│  ├─ callibrator.html
│  ├─ collect_test_data.py
│  ├─ DIAMOND_MEMBER_GUIDE.md
│  ├─ FEATURE_SUMMARY.md
│  ├─ FEN_AUTOANALYSIS_GUIDE.md
│  ├─ fetch_master_brilliancies.py
│  ├─ MANUAL_COLLECTION_GUIDE.md
│  ├─ opening_book.py
│  ├─ requirements.txt
│  ├─ requirements_test.txt
│  ├─ scrape_chesscom_games.py
│  ├─ self_test_eval.py
│  ├─ TESTING_GUIDE.md
│  ├─ test_data.json
│  ├─ test_label_move.py
│  ├─ TROUBLESHOOTING_AUTO_ANALYSIS.md
│  ├─ validate_brilliance.py
│  ├─ WORKFLOW_COMPARISON.md
│  └─ __init__.py
└─ utils
   ├─ chess_helpers.py
   ├─ extract_fens.py
   ├─ material_eval.py
   ├─ parse_pgns.py
   └─ __init__.py

```