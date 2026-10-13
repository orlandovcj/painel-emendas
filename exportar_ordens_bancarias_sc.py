#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Independente de Extração de Ordens Bancárias Creditadas em Contas de Emendas (SC)
=======================================================================================
Para cada conta-corrente de emenda parlamentar vinculada a municípios de Santa Catarina,
extrai as ordens bancárias creditadas (data, número da OB e valor) consumindo diretamente
as APIs públicas oficiais do Transferegov.

O resultado é salvo em arquivo CSV com os campos:
    nome_municipio, numero_emenda, codigo_plano_acao, autor_emenda, banco,
    agencia, conta_corrente, data_pagamento, orden_bancaria, valor

Uso:
    python exportar_ordens_bancarias_sc.py
    python exportar_ordens_bancarias_sc.py --output ordens_bancarias_sc.csv
    python exportar_ordens_bancarias_sc.py --delimitador ";"
"""

import os
import sys
import csv
import time
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuração de Logging no terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("OrdensBancariasSC")

# Endpoints da API oficial do Transferegov (Transferências Especiais)
BASE_API_URL = "https://api.transferegov.gestao.gov.br/transferenciasespeciais"
API_PLANOS_URL = f"{BASE_API_URL}/plano_acao_especial"
API_EMPENHOS_URL = f"{BASE_API_URL}/empenho_especial"
API_DHS_URL = f"{BASE_API_URL}/documento_habil_especial"
API_OBS_URL = f"{BASE_API_URL}/ordem_pagamento_ordem_bancaria_especial"

# CNPJ do Governo do Estado de Santa Catarina (usado para garantir filtro estrito aos municípios)
CNPJ_GOVERNO_ESTADO_SC = "82951229000176"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PainelEmendasSC-Exportador/1.0"


def create_session(retries=3, backoff_factor=0.8):
    """Cria uma sessão HTTP com pooling de conexões e política de retentativas automáticas."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    })
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=25, pool_maxsize=25)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def clean_digits(val):
    """Retorna apenas dígitos numéricos."""
    if val is None:
        return ""
    val_str = str(val).split(".")[0].strip()
    return "".join([c for c in val_str if c.isdigit()])


def fetch_all_pages(session, url, limit=1000, timeout=20):
    """Realiza paginação automática em endpoints PostgREST do Transferegov."""
    offset = 0
    records = []
    separator = "&" if "?" in url else "?"

    while True:
        paged_url = f"{url}{separator}limit={limit}&offset={offset}"
        try:
            resp = session.get(paged_url, timeout=timeout)
            if resp.status_code != 200:
                logger.warning(f"Resposta status {resp.status_code} ao consultar: {paged_url}")
                break
            data = resp.json()
            if not data:
                break
            records.extend(data)
            offset += limit
            if len(data) < limit:
                break
        except Exception as e:
            logger.error(f"Erro de conexão na url {paged_url}: {e}")
            break

    return records


def fetch_in_chunks(session, base_url, field_name, id_list, chunk_size=100, max_workers=6, timeout=20):
    """
    Realiza consultas em lote utilizando a cláusula ?field=in.(id1,id2,...)
    em paralelo para máxima performance.
    """
    chunks = [id_list[i:i + chunk_size] for i in range(0, len(id_list), chunk_size)]
    results = []

    def fetch_chunk(chunk):
        ids_str = ",".join(map(str, chunk))
        url = f"{base_url}?{field_name}=in.({ids_str})&limit=1000"
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(f"Status {resp.status_code} no lote com {len(chunk)} IDs.")
                return []
        except Exception as e:
            logger.error(f"Erro ao buscar lote em {base_url}: {e}")
            return []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_chunk, ch) for ch in chunks]
        for f in as_completed(futures):
            res = f.result()
            if res:
                results.extend(res)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Extrai dados das ordens bancárias creditadas por conta-corrente de emendas para municípios de SC."
    )
    parser.add_argument(
        "--output", "-o", type=str, default=os.path.join("dados", "ordens_bancarias_sc.csv"),
        help="Caminho do arquivo CSV de saída (padrão: dados/ordens_bancarias_sc.csv)"
    )
    parser.add_argument(
        "--delimitador", "-d", type=str, default=";",
        help="Delimitador do arquivo CSV (padrão: ';')"
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=6,
        help="Número de requisições simultâneas em lote (padrão: 6)"
    )
    parser.add_argument(
        "--timeout", "-t", type=int, default=20,
        help="Tempo limite para cada requisição HTTP em segundos (padrão: 20)"
    )

    args = parser.parse_args()
    session = create_session()
    start_total = time.time()

    logger.info("==================================================================")
    logger.info(" Iniciando extração de Ordens Bancárias - Municípios de SC")
    logger.info(" Fonte: API Oficial Transferegov (Transferências Especiais / PIX)")
    logger.info("==================================================================")

    # 1. Obter Planos de Ação de Santa Catarina
    logger.info("Passo 1/4: Consultando Planos de Ação vinculados a Santa Catarina...")
    url_planos = f"{API_PLANOS_URL}?uf_beneficiario_plano_acao=eq.SC"
    all_planos = fetch_all_pages(session, url_planos, limit=1000, timeout=args.timeout)
    logger.info(f"Total de planos consultados na API: {len(all_planos)}")

    # Filtrar estritamente municípios de SC (remover Governo do Estado de SC)
    planos_map = {}
    for p in all_planos:
        cnpj = clean_digits(p.get("cnpj_beneficiario_plano_acao", "")).zfill(14)
        if cnpj == CNPJ_GOVERNO_ESTADO_SC:
            continue
        id_p = p.get("id_plano_acao")
        if id_p:
            planos_map[id_p] = p

    logger.info(f"Planos de Ação de municípios catarinenses selecionados: {len(planos_map)}")

    # 2. Obter Empenhos de Santa Catarina
    logger.info("Passo 2/4: Consultando Empenhos Especiais de municípios de SC...")
    url_empenhos = f"{API_EMPENHOS_URL}?uf_beneficiario_empenho=eq.SC"
    all_empenhos = fetch_all_pages(session, url_empenhos, limit=1000, timeout=args.timeout)

    # Filtrar apenas empenhos de municípios vinculados aos nossos planos
    muni_empenhos = [
        e for e in all_empenhos
        if clean_digits(e.get("cnpj_beneficiario_empenho", "")).zfill(14) != CNPJ_GOVERNO_ESTADO_SC
        and e.get("id_plano_acao") in planos_map
    ]
    logger.info(f"Empenhos municipais identificados: {len(muni_empenhos)}")

    emp_to_plano = {e["id_empenho"]: e["id_plano_acao"] for e in muni_empenhos if e.get("id_empenho")}
    emp_ids = list(emp_to_plano.keys())

    if not emp_ids:
        logger.warning("Nenhum empenho encontrado. Encerrando execução.")
        return

    # 3. Obter Documentos Hábeis (DHs) em Lote
    logger.info(f"Passo 3/4: Consultando Documentos Hábeis (DHs) para {len(emp_ids)} empenhos...")
    all_dhs = fetch_in_chunks(
        session=session,
        base_url=API_DHS_URL,
        field_name="id_empenho",
        id_list=emp_ids,
        chunk_size=100,
        max_workers=args.workers,
        timeout=args.timeout
    )
    logger.info(f"Documentos Hábeis obtidos: {len(all_dhs)}")

    dh_map = {d["id_dh"]: d for d in all_dhs if d.get("id_dh")}
    dh_ids = list(dh_map.keys())

    if not dh_ids:
        logger.warning("Nenhum documento hábil encontrado. Encerrando execução.")
        return

    # 4. Obter Ordens Bancárias / Ordens de Pagamento em Lote
    logger.info(f"Passo 4/4: Consultando Ordens Bancárias para {len(dh_ids)} documentos hábeis...")
    all_obs = fetch_in_chunks(
        session=session,
        base_url=API_OBS_URL,
        field_name="id_dh",
        id_list=dh_ids,
        chunk_size=100,
        max_workers=args.workers,
        timeout=args.timeout
    )
    logger.info(f"Ordens de Pagamento/Bancárias obtidas: {len(all_obs)}")

    # 5. Consolidação dos Registros para Saída CSV
    logger.info("Consolidando dados finais para o arquivo CSV...")
    records = []

    for ob in all_obs:
        num_ob = ob.get("numero_ordem_bancaria")
        # Filtrar apenas registros que possuem efetivamente Ordem Bancária gerada
        if not num_ob or str(num_ob).strip() == "" or str(num_ob).strip().lower() in ("nan", "none"):
            continue

        id_dh = ob.get("id_dh")
        dh = dh_map.get(id_dh)
        if not dh:
            continue

        id_emp = dh.get("id_empenho")
        id_p = emp_to_plano.get(id_emp)
        if not id_p:
            continue

        plano = planos_map.get(id_p)
        if not plano:
            continue

        muni = str(plano.get("nome_beneficiario_plano_acao") or "").strip()
        
        raw_emenda = str(
            plano.get("numero_emenda_parlamentar_plano_acao") or
            plano.get("codigo_emenda_parlamentar_formatado_plano_acao") or
            ""
        ).strip()
        numero_emenda = raw_emenda[:12] if len(raw_emenda) >= 12 else raw_emenda

        cod_plano = str(plano.get("codigo_plano_acao") or "").strip()
        autor = str(plano.get("nome_parlamentar_emenda_plano_acao") or "").strip()
        banco = str(plano.get("nome_banco_plano_acao") or "").strip()

        ag_num = clean_digits(plano.get("numero_agencia_plano_acao"))
        ag_dv = str(plano.get("dv_agencia_plano_acao") or "").strip()
        agencia = f"{ag_num}-{ag_dv}" if (ag_num and ag_dv) else ag_num

        cta_num = clean_digits(plano.get("numero_conta_plano_acao"))
        cta_dv = str(plano.get("dv_conta_plano_acao") or "").strip()
        conta_corrente = f"{cta_num}-{cta_dv}" if (cta_num and cta_dv) else cta_num

        data_pag = str(ob.get("data_emissao_ob") or ob.get("data_situacao_op") or "").strip()
        
        raw_val = dh.get("valor_dh")
        try:
            valor = float(raw_val) if raw_val is not None else 0.0
        except (ValueError, TypeError):
            valor = 0.0

        records.append({
            "nome_municipio": muni,
            "numero_emenda": numero_emenda,
            "codigo_plano_acao": cod_plano,
            "autor_emenda": autor,
            "banco": banco,
            "agencia": agencia,
            "conta_corrente": conta_corrente,
            "data_pagamento": data_pag,
            "orden_bancaria": str(num_ob).strip(),
            "valor": f"{valor:.2f}"
        })

    # Ordenar registros por município, conta e data de pagamento para melhor leitura
    records.sort(key=lambda r: (r["nome_municipio"], r["conta_corrente"], r["data_pagamento"]))

    # Garantir criação do diretório de saída caso especificado subpasta
    output_path = os.path.abspath(args.output)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    fieldnames = [
        "nome_municipio",
        "numero_emenda",
        "codigo_plano_acao",
        "autor_emenda",
        "banco",
        "agencia",
        "conta_corrente",
        "data_pagamento",
        "orden_bancaria",
        "valor"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=args.delimitador)
        writer.writeheader()
        writer.writerows(records)

    elapsed = time.time() - start_total
    contas_unicas = len(set(r["conta_corrente"] for r in records if r["conta_corrente"]))
    munis_unicos = len(set(r["nome_municipio"] for r in records if r["nome_municipio"]))

    logger.info("==================================================================")
    logger.info(" Extração Concluída com Sucesso!")
    logger.info(f" Arquivo gerado: {output_path}")
    logger.info(f" Total de Ordens Bancárias registradas: {len(records)}")
    logger.info(f" Total de Contas Correntes únicas contempladas: {contas_unicas}")
    logger.info(f" Total de Municípios de SC contemplados: {munis_unicos}")
    logger.info(f" Tempo total de execução: {elapsed:.2f} segundos")
    logger.info("==================================================================")


if __name__ == "__main__":
    main()
