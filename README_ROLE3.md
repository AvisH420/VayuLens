Role 3 upload package — VayuLens (RAG & Decision Intelligence)

Contents:
- rag/       : RAG pipeline, chunking, embeddings, retriever, prompts, evaluation
- decision/  : Advisory & recommendation engines, API wiring, schemas, utils

What this archive contains:
- Cleaned Python source files for Role 3 only (no __pycache__ or .pyc files)
- README_ROLE3.md (this file)
- requirements.txt (suggested deps; optional heavy ML packages are commented)

How to upload:
1. Option A (recommended if you have push rights):
   - Clone https://github.com/AvisH420/VayuLens.git
   - Create a feature branch: git checkout -b feature/rag/upload-project
   - Copy the rag/ and decision/ folders from this VayuLens_upload into the repo
   - git add rag decision
   - git commit -m "Role 3: add initial rag/ and decision/ modules (RAG + decision intelligence)"
   - git push -u origin feature/rag/upload-project
   - Open a Pull Request against main

2. Option B (if you don't have push rights):
   - Fork the repo on GitHub, clone your fork, then push to your fork and open a PR against AvisH420/VayuLens:main

Notes & recommended PR description:
- Title: Role 3 — Add RAG and Decision Intelligence modules
- Body: Short summary of included modules, any new dependencies, how to run a quick health check (see requirements), and request review from the repo owner.

