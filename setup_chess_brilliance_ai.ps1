# setup_chess_brilliance_ai.ps1
# Creates the folder and file structure for the chess_brilliance_ai project

# Base project folder
$base = "."

# Define folders
$folders = @(
    "$base/data/raw_pgns",
    "$base/data/labeled_features",
    "$base/data/samples",
    "$base/engine",
    "$base/teacher",
    "$base/student",
    "$base/utils"
)

# Create folders
foreach ($folder in $folders) {
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
}

# Create empty files
$files = @(
    "$base/teacher/analyze_positions.py",
    "$base/teacher/detect_motifs.py",
    "$base/teacher/label_rules.py",
    "$base/student/train_xgboost.py",
    "$base/student/evaluate_model.py",
    "$base/student/predict_move_type.py",
    "$base/utils/parse_pgns.py",
    "$base/utils/extract_fens.py",
    "$base/utils/material_eval.py",
    "$base/utils/chess_helpers.py",
    "$base/requirements.txt"
)

foreach ($file in $files) {
    New-Item -ItemType File -Force -Path $file | Out-Null
}

# Optional placeholder for Stockfish binary info
"Place your Stockfish binary here (stockfish.exe or stockfish for Linux)" | Out-File "$base/engine/README.txt"

Write-Host "✅ Project structure created successfully at: $base"
