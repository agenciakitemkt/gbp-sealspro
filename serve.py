#!/usr/bin/env python3
"""Abre a tela de resultado em http://127.0.0.1:8000 (só nesta máquina).

  ./.venv/bin/python serve.py [--port 8000]
"""

import argparse

import uvicorn

HOST = "127.0.0.1"  # fixo de propósito: a tela guarda acesso às contas dos clientes

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    print(f"Abra http://{HOST}:{args.port}")
    uvicorn.run("web.app:app", host=HOST, port=args.port)
