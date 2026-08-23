"""Phase6: Supabase永続化層。scrapers/processors/harness/publishersはService層としてこの
パッケージ経由でのみDBに触れる（依存方向は scrapers/processors/harness/publishers -> store の
一方向。CLAUDE.md第3章の層構造を壊さないよう、storeはドメイン層に依存されるだけの末端に置く）。
"""

from __future__ import annotations
